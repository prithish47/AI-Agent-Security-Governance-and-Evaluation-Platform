# =============================================================================
# AgentGuard — Phase 2 REST API Endpoint Tests
# =============================================================================

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import get_db, Base
from app.persistence.models import RiskLevel


@pytest_asyncio.fixture
async def api_client():
    """Create a test client with an in-memory SQLite database overriding get_db."""
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


@pytest.mark.asyncio
async def test_api_projects_endpoints(api_client: AsyncClient):
    """Test /api/v1/projects REST endpoints."""
    # 1. Create project
    res = await api_client.post("/api/v1/projects", json={"name": "Fintech Project", "description": "Banking"})
    assert res.status_code == 201
    data = res.json()
    project_id = data["id"]
    assert data["name"] == "Fintech Project"

    # 2. Get project
    res = await api_client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Fintech Project"

    # 3. List projects
    res = await api_client.get("/api/v1/projects")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 4. Update project
    res = await api_client.patch(f"/api/v1/projects/{project_id}", json={"description": "Updated banking"})
    assert res.status_code == 200
    assert res.json()["description"] == "Updated banking"


@pytest.mark.asyncio
async def test_api_tools_and_agents_endpoints(api_client: AsyncClient):
    """Test tools and agents API endpoints."""
    # Create project
    p_res = await api_client.post("/api/v1/projects", json={"name": "Ops Project"})
    project_id = p_res.json()["id"]

    # Create tool
    t_res = await api_client.post(
        f"/api/v1/projects/{project_id}/tools",
        json={
            "name": "search_customer",
            "description": "Lookup customer account",
            "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}},
            "risk_level": "LOW",
        },
    )
    assert t_res.status_code == 201
    tool_id = t_res.json()["id"]
    assert t_res.json()["is_executable"] is True

    # Create agent
    a_res = await api_client.post(
        f"/api/v1/projects/{project_id}/agents",
        json={
            "name": "Ops Bot",
            "system_prompt": "Ops assistant",
            "model_provider": "mock",
            "model_name": "mock-model",
            "max_iterations": 10,
            "max_risk_level": "LOW",
        },
    )
    assert a_res.status_code == 201
    agent_id = a_res.json()["id"]

    # Assign tool to agent
    assign_res = await api_client.post(
        f"/api/v1/agents/{agent_id}/tools",
        json={"tool_id": tool_id},
    )
    assert assign_res.status_code == 201

    # Unassign tool
    del_res = await api_client.delete(f"/api/v1/agents/{agent_id}/tools/{tool_id}")
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_api_policies_endpoints(api_client: AsyncClient):
    """Test policy creation, versioning, and activation via REST."""
    p_res = await api_client.post("/api/v1/projects", json={"name": "Policy Workspace"})
    project_id = p_res.json()["id"]

    # Create policy
    pol_res = await api_client.post(
        f"/api/v1/projects/{project_id}/policies",
        json={
            "name": "Default Guard",
            "rules": {"denied_tools": ["wipeDisk"]},
        },
    )
    assert pol_res.status_code == 201
    policy_id = pol_res.json()["id"]

    # List versions
    ver_res = await api_client.get(f"/api/v1/policies/{policy_id}/versions")
    assert ver_res.status_code == 200
    versions = ver_res.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["is_active"] is True

    # Create version 2
    v2_res = await api_client.post(
        f"/api/v1/policies/{policy_id}/versions",
        json={"rules": {"denied_tools": ["wipeDisk", "dropTable"]}},
    )
    assert v2_res.status_code == 201
    v2_id = v2_res.json()["id"]
    assert v2_res.json()["version_number"] == 2
    assert v2_res.json()["is_active"] is False

    # Activate version 2
    act_res = await api_client.post(
        f"/api/v1/policies/{policy_id}/activate",
        json={"version_id": v2_id},
    )
    assert act_res.status_code == 200
    assert act_res.json()["is_active"] is True
