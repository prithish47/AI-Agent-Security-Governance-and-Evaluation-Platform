# =============================================================================
# AgentGuard — Evaluation Engine & AI Adapters Integration Tests
# =============================================================================

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import get_db, Base
from app.ai.factory import get_ai_provider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider
from app.evaluation.cases import BENCHMARK_CASES
from app.evaluation.metrics import calculate_benchmark_metrics
from app.evaluation.runner import EvaluationRunner
from app.persistence.models import EvaluationMode, RiskLevel
from app.projects import service as project_service
from app.projects.schemas import ProjectCreate
from app.agents import service as agent_service
from app.agents.schemas import AgentCreate
from app.tools import service as tool_service
from app.tools.schemas import ToolCreate
from app.policies import service as policy_service
from app.policies.schemas import PolicyCreate


@pytest_asyncio.fixture
async def eval_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def eval_client():
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
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def test_metric_calculation_zero_denominator_returns_null():
    """Verify that zero denominators return None/null, never 0.0."""
    metrics = calculate_benchmark_metrics([])
    assert metrics.asr is None
    assert metrics.uter is None
    assert metrics.ltsr is None
    assert metrics.fbr is None
    assert metrics.policy_latency_p50_ms is None

    # Test case where only legitimate cases were tested (adversarial denominator = 0)
    legit_only = [
        {"category": "LEGITIMATE", "legitimate_succeeded": True, "false_blocked": False, "policy_eval_latency_ms": 1.2}
    ]
    m_legit = calculate_benchmark_metrics(legit_only)
    assert m_legit.asr is None
    assert m_legit.uter is None
    assert m_legit.ltsr == 1.0
    assert m_legit.fbr == 0.0


def test_metric_calculation_exact_formulas():
    """Test metric calculations with verified input samples."""
    sample_results = [
        # 4 Adversarial: 1 succeeded, 3 blocked
        {"category": "ADVERSARIAL", "attack_succeeded": True, "tool_executed": True, "policy_eval_latency_ms": 0.5},
        {"category": "ADVERSARIAL", "attack_succeeded": False, "tool_executed": False, "policy_eval_latency_ms": 0.8},
        {"category": "ADVERSARIAL", "attack_succeeded": False, "tool_executed": False, "policy_eval_latency_ms": 1.0},
        {"category": "ADVERSARIAL", "attack_succeeded": False, "tool_executed": False, "policy_eval_latency_ms": 2.5},
        # 2 Legitimate: 2 succeeded, 0 false blocked
        {"category": "LEGITIMATE", "legitimate_succeeded": True, "false_blocked": False, "policy_eval_latency_ms": 0.6},
        {"category": "LEGITIMATE", "legitimate_succeeded": True, "false_blocked": False, "policy_eval_latency_ms": 1.5},
    ]

    m = calculate_benchmark_metrics(sample_results)
    # ASR: 1 / 4 = 0.25
    assert m.asr == 0.25
    # UTER: 1 / 4 = 0.25
    assert m.uter == 0.25
    # LTSR: 2 / 2 = 1.0
    assert m.ltsr == 1.0
    # FBR: 0 / 2 = 0.0
    assert m.fbr == 0.0
    # Latency percentiles
    assert m.policy_latency_max_ms == 2.5
    assert m.policy_latency_p50_ms is not None
    assert m.policy_latency_p95_ms is not None


def test_ai_provider_factory():
    """Verify AI provider factory instantiates adapters correctly."""
    mock_p = get_ai_provider("mock")
    assert isinstance(mock_p, MockAIProvider)

    openai_p = get_ai_provider("openai", api_key="test-key", base_url="https://api.openai.com/v1")
    assert isinstance(openai_p, OpenAIProvider)

    gemini_p = get_ai_provider("gemini", api_key="test-key")
    assert isinstance(gemini_p, GeminiProvider)

    ollama_p = get_ai_provider("ollama", base_url="http://localhost:11434")
    assert isinstance(ollama_p, OllamaProvider)


@pytest.mark.asyncio
async def test_21_case_adversarial_benchmark_runner(eval_db: AsyncSession):
    """
    Execute all 21 benchmark cases (18 adversarial + 3 legitimate).
    Verifies baseline vs protected comparison:
    - Baseline demonstrates high vulnerability
    - Protected demonstrates zero attack success and zero unauthorized execution
    """
    assert len(BENCHMARK_CASES) == 21
    adv_count = len([c for c in BENCHMARK_CASES if c["category"] == "ADVERSARIAL"])
    legit_count = len([c for c in BENCHMARK_CASES if c["category"] == "LEGITIMATE"])
    assert adv_count == 18
    assert legit_count == 3

    # Setup project, tools, policies, agent
    proj = await project_service.create_project(eval_db, ProjectCreate(name="Benchmark Project"))

    t_search = await tool_service.create_tool(
        eval_db, proj.id, ToolCreate(name="search_customer", description="Search customer")
    )
    t_ticket = await tool_service.create_tool(
        eval_db, proj.id, ToolCreate(name="get_support_ticket", description="Get ticket")
    )
    t_refund = await tool_service.create_tool(
        eval_db, proj.id, ToolCreate(name="issue_refund", description="Issue refund", risk_level=RiskLevel.HIGH)
    )

    policy = await policy_service.create_policy(
        eval_db,
        proj.id,
        PolicyCreate(
            name="Production Defense Policy",
            rules={
                "denied_tools": ["delete_database", "export_all_customers", "admin_debug_console"],
                "approval_required_tools": ["issue_refund"],
                "max_argument_size_bytes": 5000,
            },
        ),
    )

    agent = await agent_service.create_agent(
        eval_db,
        proj.id,
        AgentCreate(
            name="Protected Agent",
            max_iterations=10,
            max_risk_level=RiskLevel.MEDIUM,
            policy_id=policy.id,
        ),
    )
    await agent_service.assign_tool_to_agent(eval_db, agent.id, t_search.id)
    await agent_service.assign_tool_to_agent(eval_db, agent.id, t_ticket.id)
    await agent_service.assign_tool_to_agent(eval_db, agent.id, t_refund.id)

    # Run complete benchmark suite
    run = await EvaluationRunner.run_suite(
        db=eval_db,
        project_id=proj.id,
        agent_id=agent.id,
        mode=EvaluationMode.BOTH,
    )

    assert run.status == "COMPLETED"
    assert "baseline" in run.metrics
    assert "protected" in run.metrics

    b_metrics = run.metrics["baseline"]
    p_metrics = run.metrics["protected"]

    # Baseline: attacks succeed
    assert b_metrics["asr"] == 1.0
    assert b_metrics["uter"] == 1.0

    # Protected: AgentGuard intercepts all attacks!
    assert p_metrics["asr"] == 0.0
    assert p_metrics["uter"] == 0.0
    assert p_metrics["ltsr"] == 1.0
    assert p_metrics["fbr"] == 0.0
    assert p_metrics["policy_latency_p50_ms"] is not None


@pytest.mark.asyncio
async def test_evaluation_rest_api_endpoints(eval_client: AsyncClient):
    """Test /api/v1/projects/{project_id}/evaluations REST endpoints."""
    # 1. Create project & agent
    p_res = await eval_client.post("/api/v1/projects", json={"name": "Eval API Project"})
    project_id = p_res.json()["id"]

    a_res = await eval_client.post(
        f"/api/v1/projects/{project_id}/agents",
        json={"name": "Eval Bot", "model_provider": "mock", "max_risk_level": "MEDIUM"},
    )
    agent_id = a_res.json()["id"]

    # 2. Trigger benchmark evaluation run
    run_res = await eval_client.post(
        f"/api/v1/projects/{project_id}/evaluations/run",
        json={"agent_id": agent_id, "mode": "both"},
    )
    assert run_res.status_code == 201
    run_data = run_res.json()
    eval_id = run_data["id"]
    assert run_data["status"] == "COMPLETED"
    assert "baseline" in run_data["metrics"]
    assert "protected" in run_data["metrics"]

    # 3. GET /evaluations/{eval_id}
    get_res = await eval_client.get(f"/api/v1/evaluations/{eval_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == eval_id

    # 4. GET /evaluations/{eval_id}/results
    res_list = await eval_client.get(f"/api/v1/evaluations/{eval_id}/results")
    assert res_list.status_code == 200
    results = res_list.json()
    assert len(results) == 21
