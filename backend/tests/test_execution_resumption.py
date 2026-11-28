# =============================================================================
# AgentGuard — Milestone 2.1: Secure Multi-Turn Execution Resumption Tests
# =============================================================================

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.base import AIProvider, AIResponse, ToolCallProposal
from app.approvals import service as approval_service
from app.approvals.canonical import compute_action_hash, compute_tool_schema_hash
from app.core.database import Base, get_db
from app.core.exceptions import ConflictError, SecurityViolationError
from app.main import app
from app.persistence.models import (
    Agent,
    ApprovalRequest,
    ApprovalStatus,
    AuditSeverity,
    Execution,
    ExecutionStatus,
    ExecutionStep,
    RiskLevel,
)
from app.runtime.orchestrator import AgentRuntimeOrchestrator
from app.agents import service as agent_service
from app.agents.schemas import AgentCreate
from app.policies import service as policy_service
from app.policies.schemas import PolicyCreate
from app.projects import service as project_service
from app.projects.schemas import ProjectCreate
from app.tools import service as tool_service
from app.tools.schemas import ToolCreate


@pytest_asyncio.fixture
async def resume_env():
    """Isolated async SQLite DB + AsyncClient for execution resumption integration tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _register_and_login(client: AsyncClient, email: str, username: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "StrongPassword!123"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword!123"},
    )
    assert login.status_code == 200
    return reg.json()["id"], login.json()["access_token"]


def _auth(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


# =============================================================================
# 1. Multi-turn execution without approval
# =============================================================================


@pytest.mark.asyncio
async def test_multiturn_execution_without_approval(resume_env):
    """
    Legitimate multi-step support inquiry:
    Step 1: search_customer (ALLOWED)
    Step 2: get_support_ticket (ALLOWED)
    Step 3: final answer
    Execution finishes COMPLETED and conversation history is persisted.
    """
    client, session_factory = resume_env
    _, owner_tok = await _register_and_login(client, "owner_mt@example.com", "owner_mt")

    # Setup project, tools, policy, agent
    proj = (await client.post("/api/v1/projects", json={"name": "MT Project"}, headers=_auth(owner_tok))).json()
    pid = proj["id"]

    t1 = (await client.post(
        f"/api/v1/projects/{pid}/tools",
        json={"name": "search_customer", "description": "Search customers", "risk_level": "LOW"},
        headers=_auth(owner_tok),
    )).json()

    t2 = (await client.post(
        f"/api/v1/projects/{pid}/tools",
        json={"name": "get_support_ticket", "description": "Lookup ticket", "risk_level": "LOW"},
        headers=_auth(owner_tok),
    )).json()

    pol = (await client.post(
        f"/api/v1/projects/{pid}/policies",
        json={"name": "Permissive Policy", "rules": {}},
        headers=_auth(owner_tok),
    )).json()

    agent = (await client.post(
        f"/api/v1/projects/{pid}/agents",
        json={"name": "Support Bot", "max_risk_level": "HIGH", "max_iterations": 10, "policy_id": pol["id"]},
        headers=_auth(owner_tok),
    )).json()

    await client.post(f"/api/v1/agents/{agent['id']}/tools", json={"tool_id": t1["id"]}, headers=_auth(owner_tok))
    await client.post(f"/api/v1/agents/{agent['id']}/tools", json={"tool_id": t2["id"]}, headers=_auth(owner_tok))

    # Execute task
    res = await client.post(
        f"/api/v1/agents/{agent['id']}/execute",
        json={"task": "Please check support ticket for Alice Johnson"},
        headers=_auth(owner_tok),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["iteration_count"] >= 2
    assert "Alice Johnson" in data["final_response"]

    # Verify execution trace
    trace = (await client.get(f"/api/v1/executions/{data['id']}/trace", headers=_auth(owner_tok))).json()
    steps = trace["steps"]
    step_types = [s["step_type"] for s in steps]
    assert "TOOL_CALL" in step_types
    assert "FINAL_ANSWER" in step_types
    assert steps[-1]["step_type"] == "FINAL_ANSWER"


# =============================================================================
# 2. Multi-turn execution with approval and full resumption
# =============================================================================


@pytest.mark.asyncio
async def test_multiturn_execution_with_approval_and_resumption(resume_env):
    """
    Execution pauses at REQUIRES_APPROVAL.
    Human approves.
    Resumption executes approved tool, feeds result to model, model reasons and returns final answer.
    Execution transitions RUNNING -> REQUIRES_APPROVAL -> RUNNING -> COMPLETED.
    """
    client, session_factory = resume_env
    _, owner_tok = await _register_and_login(client, "owner_appr@example.com", "owner_appr")
    dev_id, dev_tok = await _register_and_login(client, "dev_appr@example.com", "dev_appr")
    appr_id, appr_tok = await _register_and_login(client, "appr_appr@example.com", "appr_appr")

    proj = (await client.post("/api/v1/projects", json={"name": "Resumption Proj"}, headers=_auth(owner_tok))).json()
    pid = proj["id"]

    await client.post(f"/api/v1/projects/{pid}/members", json={"user_id": dev_id, "role": "DEVELOPER"}, headers=_auth(owner_tok))
    await client.post(f"/api/v1/projects/{pid}/members", json={"user_id": appr_id, "role": "APPROVER"}, headers=_auth(owner_tok))

    tool = (await client.post(
        f"/api/v1/projects/{pid}/tools",
        json={"name": "issue_refund", "description": "Refund", "risk_level": "HIGH"},
        headers=_auth(owner_tok),
    )).json()

    pol = (await client.post(
        f"/api/v1/projects/{pid}/policies",
        json={"name": "Refund Policy", "rules": {"approval_required_tools": ["issue_refund"]}},
        headers=_auth(owner_tok),
    )).json()

    agent = (await client.post(
        f"/api/v1/projects/{pid}/agents",
        json={"name": "Refund Agent", "max_risk_level": "HIGH", "max_iterations": 5, "policy_id": pol["id"]},
        headers=_auth(owner_tok),
    )).json()

    await client.post(f"/api/v1/agents/{agent['id']}/tools", json={"tool_id": tool["id"]}, headers=_auth(owner_tok))

    # Dev triggers task requiring approval
    exec_res = (await client.post(
        f"/api/v1/agents/{agent['id']}/execute",
        json={"task": "Refund order ORD-9001 for $250"},
        headers=_auth(dev_tok),
    )).json()
    assert exec_res["status"] == "REQUIRES_APPROVAL"
    execution_id = exec_res["id"]

    # Approver approves
    approvals = (await client.get(f"/api/v1/projects/{pid}/approvals?status=PENDING", headers=_auth(appr_tok))).json()
    assert len(approvals) == 1
    approval_id = approvals[0]["id"]

    app_res = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"note": "Approved by supervisor"},
        headers=_auth(appr_tok),
    )
    assert app_res.status_code == 200

    # Resume execution
    resume_res = await client.post(
        f"/api/v1/approvals/{approval_id}/resume",
        headers=_auth(appr_tok),
    )
    assert resume_res.status_code == 200
    resumed_data = resume_res.json()
    assert resumed_data["id"] == execution_id
    assert resumed_data["status"] == "COMPLETED"
    assert "250.00" in resumed_data["final_response"]
    assert resumed_data["iteration_count"] >= 2

    # Verify trace steps
    trace = (await client.get(f"/api/v1/executions/{execution_id}/trace", headers=_auth(appr_tok))).json()
    step_types = [s["step_type"] for s in trace["steps"]]
    assert step_types == ["TOOL_CALL", "APPROVED_TOOL_EXECUTION", "FINAL_ANSWER"]


# =============================================================================
# 3. Multiple approval pauses in one execution
# =============================================================================


class TwoApprovalAIProvider(AIProvider):
    """Simulates an AI agent that proposes two distinct high-risk operations in sequence."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> AIResponse:
        tool_results = [m for m in conversation_history if m.get("role") == "tool"]

        if len(tool_results) == 0:
            # First tool proposal: refund 100
            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="issue_refund",
                    arguments={"order_id": "ORD-1001", "amount": 100.0},
                )
            )
        elif len(tool_results) == 1:
            # Second tool proposal: refund 200
            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="issue_refund",
                    arguments={"order_id": "ORD-2002", "amount": 200.0},
                )
            )
        else:
            # Both refunds complete -> produce final answer
            return AIResponse(final_answer="Both refunds of $100 and $200 were processed successfully.")


@pytest.mark.asyncio
async def test_multiple_approval_pauses_in_one_execution(resume_env):
    """
    Test an execution pausing for approval TWICE before finishing:
    Turn 1: tool 1 requires approval -> suspends
    Resume 1: approved & consumed -> loop continues
    Turn 2: tool 2 requires approval -> suspends again!
    Resume 2: approved & consumed -> loop continues
    Turn 3: model returns final answer -> COMPLETED.
    """
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Multi Pause Proj"))
        t_refund = await tool_service.create_tool(
            db,
            proj.id,
            ToolCreate(
                name="issue_refund",
                description="Financial refund",
                input_schema={"type": "object", "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}}},
                risk_level=RiskLevel.HIGH,
            ),
        )
        policy = await policy_service.create_policy(
            db,
            proj.id,
            PolicyCreate(
                name="Strict Policy",
                rules={"approval_required_tools": ["issue_refund"]},
            ),
        )
        agent = await agent_service.create_agent(
            db,
            proj.id,
            AgentCreate(
                name="Multi-Refund Bot",
                max_iterations=10,
                max_risk_level=RiskLevel.HIGH,
                policy_id=policy.id,
            ),
        )
        await agent_service.assign_tool_to_agent(db, agent.id, t_refund.id)

        custom_provider = TwoApprovalAIProvider()

        # 1. Initial execution -> pauses at approval 1
        exec_1 = await AgentRuntimeOrchestrator.execute_task(
            db=db,
            agent_id=agent.id,
            task_prompt="Process multiple refunds",
            provider=custom_provider,
        )
        assert exec_1.status == ExecutionStatus.REQUIRES_APPROVAL
        execution_id = exec_1.id

        # Check approval 1
        apprs_1 = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        assert len(apprs_1) == 1
        appr_1 = apprs_1[0]
        assert appr_1.tool_arguments["amount"] == 100.0

        # Approve 1
        await approval_service.approve_request(db, appr_1.id)

        # Resume 1 -> executes refund 1, model proposes refund 2 -> pauses at approval 2!
        exec_2 = await approval_service.resume_and_consume_approval(
            db, appr_1.id, provider=custom_provider
        )
        assert exec_2.id == execution_id
        assert exec_2.status == ExecutionStatus.REQUIRES_APPROVAL

        # Check approval 2
        apprs_2 = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        assert len(apprs_2) == 1
        appr_2 = apprs_2[0]
        assert appr_2.id != appr_1.id
        assert appr_2.tool_arguments["amount"] == 200.0

        # Approve 2
        await approval_service.approve_request(db, appr_2.id)

        # Resume 2 -> executes refund 2, model produces final answer -> COMPLETED!
        exec_3 = await approval_service.resume_and_consume_approval(
            db, appr_2.id, provider=custom_provider
        )
        assert exec_3.id == execution_id
        assert exec_3.status == ExecutionStatus.COMPLETED
        assert "Both refunds" in (exec_3.final_response or "")

        # Verify steps sequence
        stmt_steps = select(ExecutionStep).where(ExecutionStep.execution_id == execution_id).order_by(ExecutionStep.step_number.asc())
        steps = list((await db.execute(stmt_steps)).scalars().all())
        step_types = [s.step_type for s in steps]
        assert step_types == [
            "TOOL_CALL",                 # Proposed refund 1
            "APPROVED_TOOL_EXECUTION",   # Executed refund 1
            "TOOL_CALL",                 # Proposed refund 2
            "APPROVED_TOOL_EXECUTION",   # Executed refund 2
            "FINAL_ANSWER",              # Completed
        ]


# =============================================================================
# 4. Rejected approval cannot resume
# =============================================================================


@pytest.mark.asyncio
async def test_rejected_approval_cannot_resume(resume_env):
    """A rejected approval marks the execution DENIED and cannot be resumed."""
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Reject Proj"))
        tool = await tool_service.create_tool(
            db, proj.id, ToolCreate(name="issue_refund", description="Refund", risk_level=RiskLevel.HIGH)
        )
        policy = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol", rules={"approval_required_tools": ["issue_refund"]})
        )
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="Bot", max_risk_level=RiskLevel.HIGH, policy_id=policy.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        execution = await AgentRuntimeOrchestrator.execute_task(
            db=db, agent_id=agent.id, task_prompt="Refund ORD-9001 $250"
        )
        assert execution.status == ExecutionStatus.REQUIRES_APPROVAL

        approvals = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        appr = approvals[0]

        # Reviewer rejects
        await approval_service.reject_request(db, appr.id, note="Suspected fraudulent request")
        await db.refresh(appr)
        await db.refresh(execution)

        assert appr.status == ApprovalStatus.REJECTED
        assert execution.status == ExecutionStatus.DENIED
        assert "fraudulent" in (execution.termination_reason or "")

        # Resumption attempt MUST fail with ConflictError
        with pytest.raises(ConflictError):
            await approval_service.resume_and_consume_approval(db, appr.id)


# =============================================================================
# 5. Expired approval cannot resume
# =============================================================================


@pytest.mark.asyncio
async def test_expired_approval_cannot_resume(resume_env):
    """An approval past expires_at transitions to EXPIRED and cannot be resumed."""
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Expire Proj"))
        tool = await tool_service.create_tool(
            db, proj.id, ToolCreate(name="issue_refund", description="Refund", risk_level=RiskLevel.HIGH)
        )
        policy = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol", rules={"approval_required_tools": ["issue_refund"]})
        )
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="Bot", max_risk_level=RiskLevel.HIGH, policy_id=policy.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        execution = await AgentRuntimeOrchestrator.execute_task(
            db=db, agent_id=agent.id, task_prompt="Refund ORD-9001 $250"
        )
        approvals = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        appr = approvals[0]

        # Force expiration timestamp into the past
        appr.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        await db.commit()

        # Approval attempt fails
        with pytest.raises(ConflictError):
            await approval_service.approve_request(db, appr.id)

        await db.refresh(appr)
        assert appr.status == ApprovalStatus.EXPIRED


# =============================================================================
# 6. Duplicate and concurrent resume requests
# =============================================================================


@pytest.mark.asyncio
async def test_duplicate_resume_requests_rejected(resume_env):
    """An approved action consumed once cannot be consumed a second time."""
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Dup Proj"))
        tool = await tool_service.create_tool(
            db, proj.id, ToolCreate(name="issue_refund", description="Refund", risk_level=RiskLevel.HIGH)
        )
        policy = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol", rules={"approval_required_tools": ["issue_refund"]})
        )
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="Bot", max_risk_level=RiskLevel.HIGH, policy_id=policy.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        await AgentRuntimeOrchestrator.execute_task(
            db=db, agent_id=agent.id, task_prompt="Refund ORD-9001 $250"
        )
        apprs = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        appr = apprs[0]

        await approval_service.approve_request(db, appr.id)

        # 1st resume succeeds
        exec_res = await approval_service.resume_and_consume_approval(db, appr.id)
        assert exec_res.status == ExecutionStatus.COMPLETED

        # 2nd resume fails with ConflictError (single-use constraint)
        with pytest.raises(ConflictError) as exc_info:
            await approval_service.resume_and_consume_approval(db, appr.id)
        assert "single-use" in str(exc_info.value)


# =============================================================================
# 7. Iteration limit strictly enforced across suspension and resumption
# =============================================================================


@pytest.mark.asyncio
async def test_iteration_limit_enforced_across_suspension(resume_env):
    """
    If agent has max_iterations=1:
    Turn 1: proposes tool call -> pauses with iteration_count=1.
    Resumption: executes approved action. Loop checks 1 < 1 (False) -> terminates MAX_ITERATIONS_REACHED.
    Approval pauses NEVER reset iteration counter.
    """
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Limit Proj"))
        tool = await tool_service.create_tool(
            db, proj.id, ToolCreate(name="issue_refund", description="Refund", risk_level=RiskLevel.HIGH)
        )
        policy = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol", rules={"approval_required_tools": ["issue_refund"]})
        )
        # Bounded at 1 iteration
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="SingleTurnBot", max_iterations=1, max_risk_level=RiskLevel.HIGH, policy_id=policy.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        exec_res = await AgentRuntimeOrchestrator.execute_task(
            db=db, agent_id=agent.id, task_prompt="Refund ORD-9001 $250"
        )
        assert exec_res.status == ExecutionStatus.REQUIRES_APPROVAL
        assert exec_res.iteration_count == 1

        apprs = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        appr = apprs[0]

        await approval_service.approve_request(db, appr.id)

        # Resumption executes approved tool, then hits iteration limit
        resumed = await approval_service.resume_and_consume_approval(db, appr.id)
        assert resumed.status == ExecutionStatus.MAX_ITERATIONS_REACHED
        assert resumed.iteration_count == 1
        assert "exceeded maximum permitted iteration limit" in (resumed.termination_reason or "")


# =============================================================================
# 8. Tool failure after approval consumption
# =============================================================================


@pytest.mark.asyncio
async def test_tool_failure_after_approval_consumption(resume_env):
    """
    If an approved tool fails during execution:
    - Approval is consumed (at-most-once guaranteed)
    - Execution enters TOOL_ERROR
    - Step trace records failure details
    """
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Tool Fail Proj"))
        tool = await tool_service.create_tool(
            db, proj.id, ToolCreate(name="issue_refund", description="Refund", risk_level=RiskLevel.HIGH)
        )
        policy = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol", rules={"approval_required_tools": ["issue_refund"]})
        )
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="Bot", max_risk_level=RiskLevel.HIGH, policy_id=policy.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        exec_res = await AgentRuntimeOrchestrator.execute_task(
            db=db, agent_id=agent.id, task_prompt="Refund ORD-9001 $250"
        )
        apprs = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        appr = apprs[0]

        # Simulate corrupt unwhitelisted tool in consumed approval record
        appr.tool_name = "non_existent_tool_catalog_entry"
        # Recompute hash for valid approval
        appr.action_hash = compute_action_hash(
            project_id=appr.project_id,
            agent_id=appr.agent_id,
            execution_id=appr.execution_id,
            tool_name=appr.tool_name,
            arguments=appr.tool_arguments,
            policy_version=appr.policy_version,
            agent_risk_ceiling=appr.agent_risk_ceiling,
            binding_version=appr.binding_version,
        )
        await db.commit()

        await approval_service.approve_request(db, appr.id)

        # Resume -> executor fails safe
        resumed = await approval_service.resume_and_consume_approval(db, appr.id)
        assert resumed.status == ExecutionStatus.TOOL_ERROR
        assert "failed" in (resumed.termination_reason or "").lower()

        # Approval remains CONSUMED
        await db.refresh(appr)
        assert appr.status == ApprovalStatus.CONSUMED


# =============================================================================
# 9. Model timeout after tool execution
# =============================================================================


class TimeoutAIProvider(AIProvider):
    """Simulates model provider network timeout after tool execution."""

    def __init__(self):
        self.turns = 0

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> AIResponse:
        self.turns += 1
        if self.turns == 1:
            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="issue_refund",
                    arguments={"order_id": "ORD-9001", "amount": 250.0},
                )
            )
        # Timeout on resumption
        raise TimeoutError("Model provider gateway timeout after 30000ms")


@pytest.mark.asyncio
async def test_model_timeout_after_tool_execution(resume_env):
    """
    If the AI model provider times out after tool execution:
    - Tool execution was recorded
    - Step trace records ERROR
    - Execution enters MODEL_ERROR safely
    """
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Timeout Proj"))
        tool = await tool_service.create_tool(
            db, proj.id, ToolCreate(name="issue_refund", description="Refund", risk_level=RiskLevel.HIGH)
        )
        policy = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol", rules={"approval_required_tools": ["issue_refund"]})
        )
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="Bot", max_risk_level=RiskLevel.HIGH, policy_id=policy.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        provider = TimeoutAIProvider()

        exec_res = await AgentRuntimeOrchestrator.execute_task(
            db=db, agent_id=agent.id, task_prompt="Refund ORD-9001 $250", provider=provider
        )
        assert exec_res.status == ExecutionStatus.REQUIRES_APPROVAL

        apprs = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        appr = apprs[0]

        await approval_service.approve_request(db, appr.id)

        resumed = await approval_service.resume_and_consume_approval(db, appr.id, provider=provider)
        assert resumed.status == ExecutionStatus.MODEL_ERROR
        assert "gateway timeout" in (resumed.termination_reason or "")


# =============================================================================
# 10. Execution context preservation across suspension and resumption
# =============================================================================


@pytest.mark.asyncio
async def test_execution_context_preservation(resume_env):
    """Verify that execution ID, agent config, policy version, and conversation history persist across pauses."""
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Preserve Proj"))
        tool = await tool_service.create_tool(
            db, proj.id, ToolCreate(name="issue_refund", description="Refund", risk_level=RiskLevel.HIGH)
        )
        policy = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol", rules={"approval_required_tools": ["issue_refund"]})
        )
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="Bot", max_risk_level=RiskLevel.HIGH, policy_id=policy.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        initial = await AgentRuntimeOrchestrator.execute_task(
            db=db, agent_id=agent.id, task_prompt="Refund ORD-9001 $250"
        )
        original_id = initial.id
        original_policy_version = initial.context_snapshot["policy_version"]

        apprs = await approval_service.list_project_approvals(db, proj.id, status=ApprovalStatus.PENDING)
        appr = apprs[0]
        await approval_service.approve_request(db, appr.id)

        resumed = await approval_service.resume_and_consume_approval(db, appr.id)

        assert resumed.id == original_id
        assert resumed.project_id == proj.id
        assert resumed.agent_id == agent.id
        assert resumed.context_snapshot["policy_version"] == original_policy_version
        assert len(resumed.conversation_history) >= 2


# =============================================================================
# 11. Policy and tool definition substitution rejection
# =============================================================================


@pytest.mark.asyncio
async def test_policy_and_tool_schema_substitution_rejection(resume_env):
    """
    Cryptographic action binding with version 2:
    Detects if policy_id or tool_schema_hash was substituted between proposal and resumption.
    """
    _, session_factory = resume_env
    async with session_factory() as db:
        proj = await project_service.create_project(db, ProjectCreate(name="Subst Proj"))
        tool = await tool_service.create_tool(
            db,
            proj.id,
            ToolCreate(
                name="issue_refund",
                description="Refund",
                input_schema={"type": "object", "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}}},
                risk_level=RiskLevel.HIGH,
            ),
        )
        policy1 = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol 1", rules={"approval_required_tools": ["issue_refund"]})
        )
        policy2 = await policy_service.create_policy(
            db, proj.id, PolicyCreate(name="Pol 2", rules={"approval_required_tools": ["issue_refund"]})
        )
        agent = await agent_service.create_agent(
            db, proj.id, AgentCreate(name="Bot", max_risk_level=RiskLevel.HIGH, policy_id=policy1.id)
        )
        await agent_service.assign_tool_to_agent(db, agent.id, tool.id)

        # Compute v2 hash with policy1 and tool schema
        tool_schema_hash = compute_tool_schema_hash(tool.input_schema)
        exec_record = Execution(
            project_id=proj.id,
            agent_id=agent.id,
            task_prompt="Refund ORD-9001 $250",
            status=ExecutionStatus.REQUIRES_APPROVAL,
            context_snapshot={
                "agent_name": agent.name,
                "agent_risk_ceiling": "HIGH",
                "assigned_tools": ["issue_refund"],
                "policy_version": 1,
                "policy_id": str(policy1.id),
                "tool_schemas": {"issue_refund": tool.input_schema},
            },
        )
        db.add(exec_record)
        await db.flush()

        action_hash_v2 = compute_action_hash(
            project_id=proj.id,
            agent_id=agent.id,
            execution_id=exec_record.id,
            tool_name="issue_refund",
            arguments={"order_id": "ORD-9001", "amount": 250.0},
            policy_version=1,
            agent_risk_ceiling="HIGH",
            binding_version=2,
            policy_id=policy1.id,
            tool_schema_hash=tool_schema_hash,
        )

        appr = ApprovalRequest(
            project_id=proj.id,
            execution_id=exec_record.id,
            agent_id=agent.id,
            tool_name="issue_refund",
            tool_arguments={"order_id": "ORD-9001", "amount": 250.0},
            policy_version=1,
            agent_risk_ceiling="HIGH",
            binding_version=2,
            policy_id=policy1.id,
            tool_schema_hash=tool_schema_hash,
            action_hash=action_hash_v2,
            status=ApprovalStatus.PENDING,
        )
        db.add(appr)
        await db.commit()
        await db.refresh(appr)

        # Case 1: Attacker substitutes policy_id on execution snapshot
        exec_record.context_snapshot["policy_id"] = str(policy2.id)
        await db.commit()

        with pytest.raises(SecurityViolationError) as exc_pol:
            await approval_service.approve_request(db, appr.id)
        assert "Policy ID mismatch" in str(exc_pol.value)

        # Restore policy_id and reset approval & execution status to PENDING / REQUIRES_APPROVAL
        appr.status = ApprovalStatus.PENDING
        exec_record.status = ExecutionStatus.REQUIRES_APPROVAL
        exec_record.context_snapshot["policy_id"] = str(policy1.id)
        await db.commit()

        # Case 2: Attacker substitutes tool schema
        exec_record.context_snapshot["tool_schemas"]["issue_refund"] = {
            "type": "object",
            "properties": {"tampered_param": {"type": "string"}},
        }
        await db.commit()

        with pytest.raises(SecurityViolationError) as exc_schema:
            await approval_service.approve_request(db, appr.id)
        assert "schema mismatch" in str(exc_schema.value)
