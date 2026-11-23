# =============================================================================
# AgentGuard — Phase 2 Domain & CRUD Tests
# =============================================================================

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.persistence.models import Base, ProjectRole, RiskLevel, AuditSeverity
from app.projects import service as project_service
from app.projects.schemas import ProjectCreate, ProjectUpdate, ProjectMemberCreate
from app.agents import service as agent_service
from app.agents.schemas import AgentCreate, AgentUpdate
from app.tools import service as tool_service
from app.tools.schemas import ToolCreate, ToolUpdate
from app.policies import service as policy_service
from app.policies.schemas import PolicyCreate, PolicyVersionCreate
from app.audit import service as audit_service
from app.audit.schemas import AuditEventCreate
from app.core.exceptions import NotFoundError, ConflictError


@pytest_asyncio.fixture
async def test_db():
    """Create an isolated in-memory SQLite async database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_lifecycle(test_db: AsyncSession):
    """Test project creation, listing, updating, and deletion."""
    # 1. Create project
    p = await project_service.create_project(
        test_db, ProjectCreate(name="Security Bot", description="Customer support bot")
    )
    assert p.id is not None
    assert p.name == "Security Bot"

    # 2. Get project
    fetched = await project_service.get_project(test_db, p.id)
    assert fetched.name == "Security Bot"

    # 3. Update project
    updated = await project_service.update_project(
        test_db, p.id, ProjectUpdate(description="Updated description")
    )
    assert updated.description == "Updated description"

    # 4. List projects
    all_projects = await project_service.list_projects(test_db)
    assert len(all_projects) == 1

    # 5. Delete project
    await project_service.delete_project(test_db, p.id)
    with pytest.raises(NotFoundError):
        await project_service.get_project(test_db, p.id)


@pytest.mark.asyncio
async def test_agent_and_tool_assignment(test_db: AsyncSession):
    """Test agent creation, tool registration, and assignment with constraints."""
    # Create project
    proj = await project_service.create_project(test_db, ProjectCreate(name="Support System"))

    # Register tool
    tool = await tool_service.create_tool(
        test_db,
        proj.id,
        ToolCreate(
            name="search_customer",
            description="Search customers by query",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            risk_level=RiskLevel.LOW,
        ),
    )
    assert tool.id is not None
    assert tool_service.check_is_executable(tool.name) is True

    # Register duplicate tool name in same project should fail
    with pytest.raises(ConflictError):
        await tool_service.create_tool(
            test_db,
            proj.id,
            ToolCreate(name="search_customer", description="duplicate"),
        )

    # Create agent
    agent = await agent_service.create_agent(
        test_db,
        proj.id,
        AgentCreate(
            name="Tier 1 Support",
            system_prompt="Helpful agent",
            model_provider="mock",
            model_name="mock-model",
            max_iterations=10,
            max_risk_level=RiskLevel.LOW,
        ),
    )
    assert agent.id is not None

    # Assign tool to agent
    assignment = await agent_service.assign_tool_to_agent(test_db, agent.id, tool.id)
    assert assignment.agent_id == agent.id
    assert assignment.tool_id == tool.id

    # Duplicate assignment should fail
    with pytest.raises(ConflictError):
        await agent_service.assign_tool_to_agent(test_db, agent.id, tool.id)

    # Unassign tool
    await agent_service.unassign_tool_from_agent(test_db, agent.id, tool.id)


@pytest.mark.asyncio
async def test_policy_immutability_and_versioning(test_db: AsyncSession):
    """Test policy version immutability and activation."""
    proj = await project_service.create_project(test_db, ProjectCreate(name="Policy Project"))

    # 1. Create policy with initial rules (Version 1)
    rules_v1 = {"denied_tools": ["deleteDatabase"], "max_argument_size_bytes": 5000}
    policy = await policy_service.create_policy(
        test_db,
        proj.id,
        PolicyCreate(name="Strict Policy", description="Production policy", rules=rules_v1),
        creator="admin",
    )
    assert policy.active_version_id is not None

    versions = await policy_service.list_policy_versions(test_db, policy.id)
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].is_active is True
    assert versions[0].rules["denied_tools"] == ["deleteDatabase"]

    # 2. Add Version 2 (immutable snapshot)
    rules_v2 = {"denied_tools": ["deleteDatabase", "exportAllCustomers"], "max_argument_size_bytes": 2000}
    v2 = await policy_service.create_policy_version(
        test_db,
        policy.id,
        PolicyVersionCreate(rules=rules_v2),
        creator="lead_dev",
    )
    assert v2.version_number == 2
    assert v2.is_active is False

    # Verify Version 1 is unchanged
    v1_check = [v for v in await policy_service.list_policy_versions(test_db, policy.id) if v.version_number == 1][0]
    assert v1_check.rules == rules_v1

    # 3. Activate Version 2
    activated = await policy_service.activate_policy_version(test_db, policy.id, v2.id)
    assert activated.is_active is True

    # Version 1 should now be deactivated
    v1_updated = [v for v in await policy_service.list_policy_versions(test_db, policy.id) if v.version_number == 1][0]
    assert v1_updated.is_active is False


@pytest.mark.asyncio
async def test_audit_logging_append_only(test_db: AsyncSession):
    """Test appending and querying security audit events."""
    proj = await project_service.create_project(test_db, ProjectCreate(name="Audit Test Project"))

    # Record 3 events
    await audit_service.record_audit_event(
        test_db,
        AuditEventCreate(
            project_id=proj.id,
            event_type="LOGIN_SUCCESS",
            severity=AuditSeverity.INFO,
            event_metadata={"ip": "127.0.0.1"},
        ),
    )
    await audit_service.record_audit_event(
        test_db,
        AuditEventCreate(
            project_id=proj.id,
            event_type="TOOL_DENIED",
            severity=AuditSeverity.WARNING,
            event_metadata={"tool": "deleteDatabase", "reason": "Denied by policy"},
        ),
    )
    await audit_service.record_audit_event(
        test_db,
        AuditEventCreate(
            project_id=proj.id,
            event_type="SECURITY_VIOLATION",
            severity=AuditSeverity.CRITICAL,
            event_metadata={"reason": "Action hash mismatch"},
        ),
    )

    # Query all events
    events, total = await audit_service.list_audit_events(test_db, proj.id)
    assert total == 3
    assert len(events) == 3

    # Query by severity filter
    critical_events, crit_total = await audit_service.list_audit_events(
        test_db, proj.id, severity=AuditSeverity.CRITICAL
    )
    assert crit_total == 1
    assert critical_events[0].event_type == "SECURITY_VIOLATION"
