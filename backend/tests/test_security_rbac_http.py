# =============================================================================
# AgentGuard — HTTP Authentication, Project RBAC & Tenant Isolation Tests
# =============================================================================

import uuid
from datetime import timedelta

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.persistence.models import ApprovalStatus, User


@pytest_asyncio.fixture
async def sec_env():
    """Isolated async SQLite DB + AsyncClient for HTTP security regression tests."""
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


async def _create_user(client: AsyncClient, email: str, username: str) -> tuple[str, str]:
    """Register and authenticate a user; return (user_id, access_token)."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "StrongPassword!123"},
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword!123"},
    )
    assert login.status_code == 200
    return user_id, login.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_missing_invalid_expired_and_inactive_jwt_return_401(sec_env):
    """Verify 401 responses for missing, malformed, tampered, expired, and inactive-user JWTs."""
    client, session_factory = sec_env
    user_id, valid_token = await _create_user(client, "jwt@example.com", "jwt_user")

    fake_uuid = str(uuid.uuid4())
    protected_gets = [
        "/api/v1/auth/me",
        "/api/v1/projects",
        f"/api/v1/projects/{fake_uuid}",
        f"/api/v1/projects/{fake_uuid}/members",
        f"/api/v1/projects/{fake_uuid}/agents",
        f"/api/v1/agents/{fake_uuid}",
        f"/api/v1/projects/{fake_uuid}/tools",
        f"/api/v1/tools/{fake_uuid}",
        f"/api/v1/projects/{fake_uuid}/policies",
        f"/api/v1/policies/{fake_uuid}",
        f"/api/v1/policies/{fake_uuid}/versions",
        f"/api/v1/executions/{fake_uuid}",
        f"/api/v1/executions/{fake_uuid}/trace",
        f"/api/v1/projects/{fake_uuid}/approvals",
        f"/api/v1/approvals/{fake_uuid}",
        f"/api/v1/projects/{fake_uuid}/evaluations",
        f"/api/v1/evaluations/{fake_uuid}",
        f"/api/v1/evaluations/{fake_uuid}/results",
        f"/api/v1/projects/{fake_uuid}/audit-logs",
    ]

    # 1. Missing Authorization header -> 401 on every protected route
    for path in protected_gets:
        res = await client.get(path)
        assert res.status_code == 401, f"Expected 401 without token on {path}, got {res.status_code}"

    protected_posts = [
        ("/api/v1/projects", {"name": "Unauth Project"}),
        (f"/api/v1/projects/{fake_uuid}/members", {"user_id": fake_uuid, "role": "VIEWER"}),
        (f"/api/v1/projects/{fake_uuid}/agents", {"name": "Bot"}),
        (f"/api/v1/agents/{fake_uuid}/tools", {"tool_id": fake_uuid}),
        (f"/api/v1/projects/{fake_uuid}/tools", {"name": "search_customer", "description": "Lookup"}),
        (f"/api/v1/projects/{fake_uuid}/policies", {"name": "Pol", "rules": {}}),
        (f"/api/v1/policies/{fake_uuid}/versions", {"rules": {}}),
        (f"/api/v1/policies/{fake_uuid}/activate", {"version_id": fake_uuid}),
        (f"/api/v1/agents/{fake_uuid}/execute", {"task": "hello world"}),
        (f"/api/v1/approvals/{fake_uuid}/approve", {"note": "ok"}),
        (f"/api/v1/approvals/{fake_uuid}/reject", {"note": "no"}),
        (f"/api/v1/approvals/{fake_uuid}/resume", None),
        (f"/api/v1/projects/{fake_uuid}/evaluations/run", {"agent_id": fake_uuid}),
    ]
    for path, body in protected_posts:
        res = await client.post(path, json=body)
        assert res.status_code == 401, f"Expected 401 without token on POST {path}, got {res.status_code}"

    # 2. Invalid / tampered / non-Bearer tokens -> 401
    for bad_header in [
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer not.a.valid.jwt"},
        {"Authorization": f"Bearer {valid_token}tampered"},
    ]:
        res = await client.get("/api/v1/projects", headers=bad_header)
        assert res.status_code == 401

    # 3. Wrong token type or malformed `sub` -> 401
    wrong_type_jwt = jwt.encode(
        {"sub": user_id, "type": "refresh", "iss": "agentguard"},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert (await client.get("/api/v1/auth/me", headers=_auth(wrong_type_jwt))).status_code == 401

    bad_sub_jwt = jwt.encode(
        {"sub": "not-a-uuid", "type": "access", "iss": "agentguard"},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert (await client.get("/api/v1/auth/me", headers=_auth(bad_sub_jwt))).status_code == 401

    # 4. Expired JWT -> 401
    expired_jwt = create_access_token(
        uuid.UUID(user_id),
        "jwt@example.com",
        "jwt_user",
        expires_delta=timedelta(seconds=-10),
    )
    res_exp = await client.get("/api/v1/projects", headers=_auth(expired_jwt))
    assert res_exp.status_code == 401

    # 5. Deactivated user -> 401 even with previously valid token
    async with session_factory() as db:
        await db.execute(update(User).where(User.id == uuid.UUID(user_id)).values(is_active=False))
        await db.commit()
    assert (await client.get("/api/v1/auth/me", headers=_auth(valid_token))).status_code == 401


@pytest.mark.asyncio
async def test_cross_project_tenant_isolation_over_http(sec_env):
    """Verify User A cannot access or associate any Project B resource by UUID."""
    client, _ = sec_env
    _, token_a = await _create_user(client, "alice@example.com", "alice_a")
    _, token_b = await _create_user(client, "bob@example.com", "bob_b")

    # Alice creates Project A; Bob creates Project B
    proj_a = (await client.post("/api/v1/projects", json={"name": "Alpha"}, headers=_auth(token_a))).json()
    proj_b = (await client.post("/api/v1/projects", json={"name": "Beta"}, headers=_auth(token_b))).json()
    pid_a, pid_b = proj_a["id"], proj_b["id"]

    # Scoped GET /projects only shows caller's projects
    list_a = (await client.get("/api/v1/projects", headers=_auth(token_a))).json()
    assert [p["id"] for p in list_a] == [pid_a]

    # Bob populates Project B with tool, policy, agent, execution, approval, evaluation
    tool_b = (
        await client.post(
            f"/api/v1/projects/{pid_b}/tools",
            json={"name": "issue_refund", "description": "Refund order", "risk_level": "HIGH"},
            headers=_auth(token_b),
        )
    ).json()
    pol_b = (
        await client.post(
            f"/api/v1/projects/{pid_b}/policies",
            json={"name": "Beta Policy", "rules": {"approval_required_tools": ["issue_refund"]}},
            headers=_auth(token_b),
        )
    ).json()
    agent_b = (
        await client.post(
            f"/api/v1/projects/{pid_b}/agents",
            json={
                "name": "Beta Bot",
                "max_risk_level": "HIGH",
                "policy_id": pol_b["id"],
            },
            headers=_auth(token_b),
        )
    ).json()
    await client.post(
        f"/api/v1/agents/{agent_b['id']}/tools",
        json={"tool_id": tool_b["id"]},
        headers=_auth(token_b),
    )
    exec_b = (
        await client.post(
            f"/api/v1/agents/{agent_b['id']}/execute",
            json={"task": "Issue refund for ORD-9001 $250"},
            headers=_auth(token_b),
        )
    ).json()
    approvals_b = (await client.get(f"/api/v1/projects/{pid_b}/approvals", headers=_auth(token_b))).json()
    appr_b_id = approvals_b[0]["id"]
    eval_b = (
        await client.post(
            f"/api/v1/projects/{pid_b}/evaluations/run",
            json={"agent_id": agent_b["id"], "mode": "protected"},
            headers=_auth(token_b),
        )
    ).json()

    # Alice attempts to access Project B across all project-path and by-ID routes -> 403
    forbidden_gets = [
        f"/api/v1/projects/{pid_b}",
        f"/api/v1/projects/{pid_b}/members",
        f"/api/v1/projects/{pid_b}/agents",
        f"/api/v1/agents/{agent_b['id']}",
        f"/api/v1/projects/{pid_b}/tools",
        f"/api/v1/tools/{tool_b['id']}",
        f"/api/v1/projects/{pid_b}/policies",
        f"/api/v1/policies/{pol_b['id']}",
        f"/api/v1/policies/{pol_b['id']}/versions",
        f"/api/v1/executions/{exec_b['id']}",
        f"/api/v1/executions/{exec_b['id']}/trace",
        f"/api/v1/projects/{pid_b}/approvals",
        f"/api/v1/approvals/{appr_b_id}",
        f"/api/v1/projects/{pid_b}/evaluations",
        f"/api/v1/evaluations/{eval_b['id']}",
        f"/api/v1/evaluations/{eval_b['id']}/results",
        f"/api/v1/projects/{pid_b}/audit-logs",
    ]
    for path in forbidden_gets:
        res = await client.get(path, headers=_auth(token_a))
        assert res.status_code == 403, f"Cross-project GET {path} returned {res.status_code}"

    # Alice attempts mutations / executions / approvals on Project B -> 403
    assert (await client.patch(f"/api/v1/projects/{pid_b}", json={"name": "Hacked"}, headers=_auth(token_a))).status_code == 403
    assert (await client.delete(f"/api/v1/projects/{pid_b}", headers=_auth(token_a))).status_code == 403
    assert (await client.post(f"/api/v1/agents/{agent_b['id']}/execute", json={"task": "hi"}, headers=_auth(token_a))).status_code == 403
    assert (await client.post(f"/api/v1/approvals/{appr_b_id}/approve", json={"note": "pwn"}, headers=_auth(token_a))).status_code == 403
    assert (await client.post(f"/api/v1/approvals/{appr_b_id}/reject", json={"note": "pwn"}, headers=_auth(token_a))).status_code == 403
    assert (await client.post(f"/api/v1/approvals/{appr_b_id}/resume", headers=_auth(token_a))).status_code == 403
    assert (await client.delete(f"/api/v1/tools/{tool_b['id']}", headers=_auth(token_a))).status_code == 403
    assert (await client.post(f"/api/v1/policies/{pol_b['id']}/versions", json={"rules": {}}, headers=_auth(token_a))).status_code == 403

    # Cross-project resource association attempts by Alice in Project A referencing Project B UUIDs -> rejected
    cross_agent = await client.post(
        f"/api/v1/projects/{pid_a}/agents",
        json={"name": "Cross Policy Bot", "policy_id": pol_b["id"]},
        headers=_auth(token_a),
    )
    assert cross_agent.status_code == 404

    cross_eval = await client.post(
        f"/api/v1/projects/{pid_a}/evaluations/run",
        json={"agent_id": agent_b["id"], "mode": "protected"},
        headers=_auth(token_a),
    )
    assert cross_eval.status_code == 404


@pytest.mark.asyncio
async def test_role_permissions_and_approval_separation_of_duties(sec_env):
    """Verify 5-role RBAC enforcement and same-user approval separation of duties over HTTP."""
    client, _ = sec_env

    owner_id, owner_tok = await _create_user(client, "owner@example.com", "proj_owner")
    admin_id, admin_tok = await _create_user(client, "admin@example.com", "proj_admin")
    dev_id, dev_tok = await _create_user(client, "dev@example.com", "proj_dev")
    appr_id, appr_tok = await _create_user(client, "approver@example.com", "proj_approver")
    viewer_id, viewer_tok = await _create_user(client, "viewer@example.com", "proj_viewer")
    outsider_id, _ = await _create_user(client, "outsider@example.com", "outsider")

    # Owner creates project
    proj = (await client.post("/api/v1/projects", json={"name": "RBAC Project"}, headers=_auth(owner_tok))).json()
    pid = proj["id"]

    # Owner assigns ADMIN, DEVELOPER, APPROVER, VIEWER
    for uid, role in [
        (admin_id, "ADMIN"),
        (dev_id, "DEVELOPER"),
        (appr_id, "APPROVER"),
        (viewer_id, "VIEWER"),
    ]:
        res = await client.post(
            f"/api/v1/projects/{pid}/members",
            json={"user_id": uid, "role": role},
            headers=_auth(owner_tok),
        )
        assert res.status_code == 201

    # ADMIN cannot escalate outsider to OWNER (403), but can add non-owner roles; DEV cannot add members (403)
    assert (
        await client.post(
            f"/api/v1/projects/{pid}/members",
            json={"user_id": outsider_id, "role": "OWNER"},
            headers=_auth(admin_tok),
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/projects/{pid}/members",
            json={"user_id": outsider_id, "role": "VIEWER"},
            headers=_auth(dev_tok),
        )
    ).status_code == 403

    # ADMIN creates security policy; DEVELOPER cannot create policy (403)
    assert (
        await client.post(
            f"/api/v1/projects/{pid}/policies",
            json={"name": "Dev Attempt", "rules": {}},
            headers=_auth(dev_tok),
        )
    ).status_code == 403

    pol_res = await client.post(
        f"/api/v1/projects/{pid}/policies",
        json={"name": "Billing Guard", "rules": {"approval_required_tools": ["issue_refund"]}},
        headers=_auth(admin_tok),
    )
    assert pol_res.status_code == 201
    pol_id = pol_res.json()["id"]

    # DEVELOPER creates tool, agent, assigns tool, and runs execution
    tool_res = await client.post(
        f"/api/v1/projects/{pid}/tools",
        json={"name": "issue_refund", "description": "Issue refund", "risk_level": "HIGH"},
        headers=_auth(dev_tok),
    )
    assert tool_res.status_code == 201
    tool_id = tool_res.json()["id"]

    agent_res = await client.post(
        f"/api/v1/projects/{pid}/agents",
        json={"name": "Billing Bot", "max_risk_level": "HIGH", "policy_id": pol_id},
        headers=_auth(dev_tok),
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    assert (
        await client.post(
            f"/api/v1/agents/{agent_id}/tools",
            json={"tool_id": tool_id},
            headers=_auth(dev_tok),
        )
    ).status_code == 201

    # VIEWER can read dashboard & audit logs (200) but cannot mutate or execute (403)
    assert (await client.get(f"/api/v1/projects/{pid}", headers=_auth(viewer_tok))).status_code == 200
    assert (await client.get(f"/api/v1/projects/{pid}/audit-logs", headers=_auth(viewer_tok))).status_code == 200
    assert (await client.post(f"/api/v1/agents/{agent_id}/execute", json={"task": "hi"}, headers=_auth(viewer_tok))).status_code == 403
    assert (await client.post(f"/api/v1/projects/{pid}/tools", json={"name": "x", "description": "12345"}, headers=_auth(viewer_tok))).status_code == 403

    # APPROVER cannot mutate policies, tools, agents or execute (403)
    assert (await client.post(f"/api/v1/agents/{agent_id}/execute", json={"task": "hi"}, headers=_auth(appr_tok))).status_code == 403
    assert (await client.post(f"/api/v1/projects/{pid}/policies", json={"name": "x", "rules": {}}, headers=_auth(appr_tok))).status_code == 403

    # DEVELOPER executes refund task -> REQUIRES_APPROVAL
    exec_res = await client.post(
        f"/api/v1/agents/{agent_id}/execute",
        json={"task": "Refund order ORD-9001 for $250"},
        headers=_auth(dev_tok),
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "REQUIRES_APPROVAL"

    approvals = (await client.get(f"/api/v1/projects/{pid}/approvals", headers=_auth(appr_tok))).json()
    assert len(approvals) == 1
    appr_id_1 = approvals[0]["id"]

    # DEVELOPER & VIEWER cannot approve, reject, or resume (403)
    assert (await client.post(f"/api/v1/approvals/{appr_id_1}/approve", json={"note": "self"}, headers=_auth(dev_tok))).status_code == 403
    assert (await client.post(f"/api/v1/approvals/{appr_id_1}/reject", json={"note": "self"}, headers=_auth(dev_tok))).status_code == 403
    assert (await client.post(f"/api/v1/approvals/{appr_id_1}/approve", json={"note": "view"}, headers=_auth(viewer_tok))).status_code == 403

    # APPROVER approves and resumes (200) -> reviewer_id recorded from JWT, single-use enforced
    approved = await client.post(
        f"/api/v1/approvals/{appr_id_1}/approve",
        json={"note": "Verified by approver"},
        headers=_auth(appr_tok),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["reviewed_by"] == appr_id

    resumed = await client.post(f"/api/v1/approvals/{appr_id_1}/resume", headers=_auth(appr_tok))
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "COMPLETED"

    # Replay resume -> 409 Conflict
    assert (await client.post(f"/api/v1/approvals/{appr_id_1}/resume", headers=_auth(appr_tok))).status_code == 409

    # SEPARATION OF DUTIES (instance-level): ADMIN initiates execution -> ADMIN cannot approve or reject own action (403)
    admin_exec = await client.post(
        f"/api/v1/agents/{agent_id}/execute",
        json={"task": "Refund order ORD-9001 for $250"},
        headers=_auth(admin_tok),
    )
    assert admin_exec.status_code == 200
    assert admin_exec.json()["status"] == "REQUIRES_APPROVAL"

    pending = (await client.get(f"/api/v1/projects/{pid}/approvals?status=PENDING", headers=_auth(admin_tok))).json()
    assert len(pending) == 1
    appr_id_2 = pending[0]["id"]

    # ADMIN self-approve & self-reject blocked (403)
    assert (await client.post(f"/api/v1/approvals/{appr_id_2}/approve", json={"note": "self"}, headers=_auth(admin_tok))).status_code == 403
    assert (await client.post(f"/api/v1/approvals/{appr_id_2}/reject", json={"note": "self"}, headers=_auth(admin_tok))).status_code == 403

    # Separate APPROVER rejects -> 200
    rejected = await client.post(
        f"/api/v1/approvals/{appr_id_2}/reject",
        json={"note": "Declined by independent approver"},
        headers=_auth(appr_tok),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["reviewed_by"] == appr_id

    # ADMIN cannot DELETE project (403), OWNER can DELETE project (204)
    assert (await client.delete(f"/api/v1/projects/{pid}", headers=_auth(admin_tok))).status_code == 403
    assert (await client.delete(f"/api/v1/projects/{pid}", headers=_auth(owner_tok))).status_code == 204
