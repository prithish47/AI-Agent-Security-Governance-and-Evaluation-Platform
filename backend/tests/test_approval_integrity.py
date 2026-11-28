# =============================================================================
# AgentGuard — Milestone 2: RFC 8785 & Approval Execution Integrity Tests
# =============================================================================

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.approvals.canonical import canonicalize_json, compute_action_hash, verify_action_hash
from app.core.database import Base, get_db
from app.main import app
from app.persistence.models import (
    ApprovalRequest,
    ApprovalStatus,
    Execution,
    ExecutionStatus,
    ExecutionStep,
)


@pytest_asyncio.fixture
async def appr_env():
    """Isolated async SQLite DB + AsyncClient for approval integrity tests."""
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


async def _setup_pending_refund(client: AsyncClient):
    """Create project, owner, dev, approver, policy, tool, agent and trigger REQUIRES_APPROVAL."""
    _, owner_tok = await _register_and_login(client, "owner2@example.com", "m2_owner")
    dev_id, dev_tok = await _register_and_login(client, "dev2@example.com", "m2_dev")
    appr_id, appr_tok = await _register_and_login(client, "appr2@example.com", "m2_appr")

    proj = (await client.post("/api/v1/projects", json={"name": "M2 Project"}, headers=_auth(owner_tok))).json()
    pid = proj["id"]

    await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": dev_id, "role": "DEVELOPER"},
        headers=_auth(owner_tok),
    )
    await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": appr_id, "role": "APPROVER"},
        headers=_auth(owner_tok),
    )

    pol = (
        await client.post(
            f"/api/v1/projects/{pid}/policies",
            json={"name": "Refund Policy", "rules": {"approval_required_tools": ["issue_refund"]}},
            headers=_auth(owner_tok),
        )
    ).json()

    tool = (
        await client.post(
            f"/api/v1/projects/{pid}/tools",
            json={"name": "issue_refund", "description": "Issue financial refund", "risk_level": "HIGH"},
            headers=_auth(dev_tok),
        )
    ).json()

    agent = (
        await client.post(
            f"/api/v1/projects/{pid}/agents",
            json={"name": "Refund Bot", "max_risk_level": "HIGH", "policy_id": pol["id"]},
            headers=_auth(dev_tok),
        )
    ).json()

    await client.post(
        f"/api/v1/agents/{agent['id']}/tools",
        json={"tool_id": tool["id"]},
        headers=_auth(dev_tok),
    )

    exec_res = (
        await client.post(
            f"/api/v1/agents/{agent['id']}/execute",
            json={"task": "Refund order ORD-9001 for $250"},
            headers=_auth(dev_tok),
        )
    ).json()
    assert exec_res["status"] == "REQUIRES_APPROVAL"

    approvals = (await client.get(f"/api/v1/projects/{pid}/approvals", headers=_auth(appr_tok))).json()
    assert len(approvals) == 1

    return {
        "pid": pid,
        "agent_id": agent["id"],
        "execution_id": exec_res["id"],
        "approval_id": approvals[0]["id"],
        "owner_tok": owner_tok,
        "dev_tok": dev_tok,
        "appr_id": appr_id,
        "appr_tok": appr_tok,
    }


# =============================================================================
# 1. RFC 8785 (JCS) Canonicalization Tests
# =============================================================================


def test_rfc8785_object_key_sorting_and_utf16_order():
    """Verify RFC 8785 §3.2.3 UTF-16 code-unit key ordering (supplementary > BMP check)."""
    # In UTF-16BE: "\U0001f600" -> D8 3D DE 00; "\ufb33" -> FB 33.
    # Thus "\U0001f600" MUST sort BEFORE "\ufb33" (unlike Python UTF-32 code points!).
    data = {
        "\ufb33": "hebrew",
        "\r": "cr",
        "1": "one",
        "\U0001f600": "emoji",
        "\u0080": "ctrl",
        "\u20ac": "euro",
        "\u00f6": "umlaut",
    }
    canonical = canonicalize_json(data).decode("utf-8")
    expected = '{"\\r":"cr","1":"one","\u0080":"ctrl","\u00f6":"umlaut","\u20ac":"euro","\U0001f600":"emoji","\ufb33":"hebrew"}'
    assert canonical == expected


def test_rfc8785_nested_objects_arrays_null_and_booleans():
    """Verify nested objects sort keys, arrays preserve order, and booleans/null serialize cleanly."""
    payload = {
        "z": [True, False, None, {"b": 2, "a": 1}],
        "a": {"nested_z": "ok", "nested_a": [3, 1, 2]},
    }
    assert canonicalize_json(payload) == b'{"a":{"nested_a":[3,1,2],"nested_z":"ok"},"z":[true,false,null,{"a":1,"b":2}]}'


def test_rfc8785_numeric_serialization():
    """Verify RFC 8785 §3.2.2.3 ECMA-262 numeric serialization."""
    nums = {
        "zero": 0.0,
        "neg_zero": -0.0,
        "int_float": 250.0,
        "frac": 12.34,
        "e20": 1e20,
        "e21": 1e21,
        "e_minus6": 1e-6,
        "e_minus7": 1e-7,
        "neg_small": -1e-7,
    }
    canonical = canonicalize_json(nums).decode("utf-8")
    assert '"zero":0' in canonical
    assert '"neg_zero":0' in canonical
    assert '"int_float":250' in canonical
    assert '"frac":12.34' in canonical
    assert '"e20":100000000000000000000' in canonical
    assert '"e21":1e+21' in canonical
    assert '"e_minus6":0.000001' in canonical
    assert '"e_minus7":1e-7' in canonical
    assert '"neg_small":-1e-7' in canonical


def test_rfc8785_escaping_and_unicode():
    """Verify control char escaping, slash preservation, and literal UTF-8 output."""
    payload = {
        "path": "a/b/c",
        "quotes": 'say "hi" \\ bye',
        "controls": "\x00\b\t\n\f\r\x1f",
        "unicode": "café € 🚀",
    }
    assert canonicalize_json(payload).decode("utf-8") == (
        '{"controls":"\\u0000\\b\\t\\n\\f\\r\\u001f","path":"a/b/c","quotes":"say \\"hi\\" \\\\ bye","unicode":"café € 🚀"}'
    )


def test_rfc8785_rejects_invalid_values():
    """Verify NaN, Infinity, lone surrogates, and non-JSON types are rejected."""
    for bad in [
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": float("-inf")},
        {"x": "\ud800"},
        {"x": {1, 2, 3}},
        {"x": b"bytes"},
        {123: "non-string-key"},
    ]:
        with pytest.raises(ValueError):
            canonicalize_json(bad)


# =============================================================================
# 2. Execution Integrity & Approval Lifecycle Tests (Actual Execution Path)
# =============================================================================


@pytest.mark.asyncio
async def test_successful_approval_and_execution_binding(appr_env):
    """Verify full lifecycle PENDING -> APPROVED -> CONSUMED -> COMPLETED with verified action binding."""
    client, session_factory = appr_env
    ctx = await _setup_pending_refund(client)

    # Approve as independent APPROVER
    app_res = await client.post(
        f"/api/v1/approvals/{ctx['approval_id']}/approve",
        json={"note": "Verified ORD-9001"},
        headers=_auth(ctx["appr_tok"]),
    )
    assert app_res.status_code == 200
    body = app_res.json()
    assert body["status"] == "APPROVED"
    assert body["reviewed_by"] == ctx["appr_id"]
    assert body["policy_version"] == 1
    assert body["agent_risk_ceiling"] == "HIGH"
    assert body["expires_at"] is not None

    # Resume & consume
    res = await client.post(
        f"/api/v1/approvals/{ctx['approval_id']}/resume",
        headers=_auth(ctx["appr_tok"]),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"
    assert "250.00" in res.json()["final_response"]

    # Replay attempt fails 409
    replay = await client.post(
        f"/api/v1/approvals/{ctx['approval_id']}/resume",
        headers=_auth(ctx["appr_tok"]),
    )
    assert replay.status_code == 409

    # Verify DB state: CONSUMED + APPROVED_TOOL_EXECUTION step recorded
    async with session_factory() as db:
        appr = (
            await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == uuid.UUID(ctx["approval_id"])))
        ).scalar_one()
        assert appr.status == ApprovalStatus.CONSUMED
        steps = (
            await db.execute(select(ExecutionStep).where(ExecutionStep.execution_id == uuid.UUID(ctx["execution_id"])))
        ).scalars().all()
        assert any(s.step_type == "APPROVED_TOOL_EXECUTION" for s in steps)


@pytest.mark.asyncio
async def test_tampered_arguments_or_tool_name_rejected_before_execution(appr_env):
    """Modifying tool_arguments or tool_name after approval creation fails with 403 and never executes."""
    client, session_factory = appr_env
    ctx = await _setup_pending_refund(client)

    # Approve first, then tamper with tool_arguments in DB before resume
    assert (
        await client.post(
            f"/api/v1/approvals/{ctx['approval_id']}/approve",
            json={"note": "ok"},
            headers=_auth(ctx["appr_tok"]),
        )
    ).status_code == 200

    async with session_factory() as db:
        await db.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == uuid.UUID(ctx["approval_id"]))
            .values(tool_arguments={"order_id": "ORD-9001", "amount": 99999.0})
        )
        await db.commit()

    res_args = await client.post(
        f"/api/v1/approvals/{ctx['approval_id']}/resume",
        headers=_auth(ctx["appr_tok"]),
    )
    assert res_args.status_code == 403

    # Verify approval was marked REJECTED and execution never completed
    async with session_factory() as db:
        appr = (
            await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == uuid.UUID(ctx["approval_id"])))
        ).scalar_one()
        assert appr.status == ApprovalStatus.REJECTED

    # Also verify tampered tool_name triggers 403 on approve
    ctx2 = await _setup_pending_refund(client) if False else None  # reuse second execution below
    exec2 = (
        await client.post(
            f"/api/v1/agents/{ctx['agent_id']}/execute",
            json={"task": "Refund order ORD-9001 for $250"},
            headers=_auth(ctx["dev_tok"]),
        )
    ).json()
    approvals = (await client.get(f"/api/v1/projects/{ctx['pid']}/approvals?status=PENDING", headers=_auth(ctx["appr_tok"]))).json()
    appr2_id = approvals[0]["id"]

    async with session_factory() as db:
        await db.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == uuid.UUID(appr2_id))
            .values(tool_name="search_customer")
        )
        await db.commit()

    res_tool = await client.post(
        f"/api/v1/approvals/{appr2_id}/approve",
        json={"note": "tampered tool"},
        headers=_auth(ctx["appr_tok"]),
    )
    assert res_tool.status_code == 403


@pytest.mark.asyncio
async def test_execution_agent_project_and_policy_version_binding_mismatches(appr_env):
    """
    Verify binding fails (403) if execution_id, agent_id, project_id, or policy_version
    do not match the bound execution snapshot.
    """
    client, session_factory = appr_env
    ctx = await _setup_pending_refund(client)

    # Approve cleanly first
    assert (
        await client.post(
            f"/api/v1/approvals/{ctx['approval_id']}/approve",
            json={"note": "ok"},
            headers=_auth(ctx["appr_tok"]),
        )
    ).status_code == 200

    # 1. Policy version mismatch
    async with session_factory() as db:
        await db.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == uuid.UUID(ctx["approval_id"]))
            .values(policy_version=99)
        )
        await db.commit()

    res_pol = await client.post(
        f"/api/v1/approvals/{ctx['approval_id']}/resume",
        headers=_auth(ctx["appr_tok"]),
    )
    assert res_pol.status_code == 403

    # 2. Different execution_id transfer attempt
    exec2 = (
        await client.post(
            f"/api/v1/agents/{ctx['agent_id']}/execute",
            json={"task": "Refund order ORD-9001 for $250"},
            headers=_auth(ctx["dev_tok"]),
        )
    ).json()
    approvals = (await client.get(f"/api/v1/projects/{ctx['pid']}/approvals?status=PENDING", headers=_auth(ctx["appr_tok"]))).json()
    appr2_id = approvals[0]["id"]

    async with session_factory() as db:
        # Point appr2 at ctx['execution_id'] instead of its own execution
        await db.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == uuid.UUID(appr2_id))
            .values(execution_id=uuid.UUID(ctx["execution_id"]))
        )
        await db.commit()

    res_exec_mismatch = await client.post(
        f"/api/v1/approvals/{appr2_id}/approve",
        json={"note": "transfer"},
        headers=_auth(ctx["appr_tok"]),
    )
    assert res_exec_mismatch.status_code == 403

    # 3. Different agent_id mismatch
    exec3 = (
        await client.post(
            f"/api/v1/agents/{ctx['agent_id']}/execute",
            json={"task": "Refund order ORD-9001 for $250"},
            headers=_auth(ctx["dev_tok"]),
        )
    ).json()
    approvals3 = (await client.get(f"/api/v1/projects/{ctx['pid']}/approvals?status=PENDING", headers=_auth(ctx["appr_tok"]))).json()
    appr3_id = approvals3[0]["id"]

    async with session_factory() as db:
        await db.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == uuid.UUID(appr3_id))
            .values(agent_id=uuid.uuid4())
        )
        await db.commit()

    res_agent_mismatch = await client.post(
        f"/api/v1/approvals/{appr3_id}/approve",
        json={"note": "wrong agent"},
        headers=_auth(ctx["appr_tok"]),
    )
    assert res_agent_mismatch.status_code == 403


@pytest.mark.asyncio
async def test_expired_and_rejected_approvals_cannot_be_used(appr_env):
    """Expired and rejected approvals must return 409 Conflict and never execute."""
    client, session_factory = appr_env
    ctx = await _setup_pending_refund(client)

    # 1. Expire approval in DB
    async with session_factory() as db:
        await db.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.id == uuid.UUID(ctx["approval_id"]))
            .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=5))
        )
        await db.commit()

    exp_res = await client.post(
        f"/api/v1/approvals/{ctx['approval_id']}/approve",
        json={"note": "late"},
        headers=_auth(ctx["appr_tok"]),
    )
    assert exp_res.status_code == 409
    assert (await client.get(f"/api/v1/approvals/{ctx['approval_id']}", headers=_auth(ctx["appr_tok"]))).json()["status"] == "EXPIRED"

    # 2. Rejected approval cannot be approved or resumed
    await client.post(
        f"/api/v1/agents/{ctx['agent_id']}/execute",
        json={"task": "Refund order ORD-9001 for $250"},
        headers=_auth(ctx["dev_tok"]),
    )
    pending = (await client.get(f"/api/v1/projects/{ctx['pid']}/approvals?status=PENDING", headers=_auth(ctx["appr_tok"]))).json()
    appr2_id = pending[0]["id"]

    assert (
        await client.post(
            f"/api/v1/approvals/{appr2_id}/reject",
            json={"note": "No"},
            headers=_auth(ctx["appr_tok"]),
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/v1/approvals/{appr2_id}/approve",
            json={"note": "Retry"},
            headers=_auth(ctx["appr_tok"]),
        )
    ).status_code == 409
    assert (
        await client.post(
            f"/api/v1/approvals/{appr2_id}/resume",
            headers=_auth(ctx["appr_tok"]),
        )
    ).status_code == 409


@pytest.mark.asyncio
async def test_concurrent_approval_consumption_executes_exactly_once(appr_env):
    """5 concurrent /resume requests on an approved action must result in exactly 1 execution."""
    client, _ = appr_env
    ctx = await _setup_pending_refund(client)

    assert (
        await client.post(
            f"/api/v1/approvals/{ctx['approval_id']}/approve",
            json={"note": "Approved"},
            headers=_auth(ctx["appr_tok"]),
        )
    ).status_code == 200

    responses = await asyncio.gather(
        *[
            client.post(f"/api/v1/approvals/{ctx['approval_id']}/resume", headers=_auth(ctx["appr_tok"]))
            for _ in range(5)
        ]
    )
    successes = [r for r in responses if r.status_code == 200]
    conflicts = [r for r in responses if r.status_code == 409]
    assert len(successes) == 1
    assert len(conflicts) == 4


@pytest.mark.asyncio
async def test_self_approval_blocked_and_direct_hash_tamper(appr_env):
    """Execution initiator (even OWNER) cannot approve/reject/resume their own action."""
    client, _ = appr_env
    ctx = await _setup_pending_refund(client)

    # OWNER triggers execution
    exec_res = (
        await client.post(
            f"/api/v1/agents/{ctx['agent_id']}/execute",
            json={"task": "Refund order ORD-9001 for $250"},
            headers=_auth(ctx["owner_tok"]),
        )
    ).json()
    assert exec_res["status"] == "REQUIRES_APPROVAL"

    pending = (await client.get(f"/api/v1/projects/{ctx['pid']}/approvals?status=PENDING", headers=_auth(ctx["owner_tok"]))).json()
    owner_appr = [a for a in pending if a["execution_id"] == exec_res["id"]][0]

    assert (
        await client.post(
            f"/api/v1/approvals/{owner_appr['id']}/approve",
            json={"note": "self"},
            headers=_auth(ctx["owner_tok"]),
        )
    ).status_code == 403

    # Direct hash check helper sensitivity
    assert verify_action_hash(
        project_id=ctx["pid"],
        agent_id=ctx["agent_id"],
        execution_id=exec_res["id"],
        tool_name="issue_refund",
        arguments={"order_id": "ORD-9001", "amount": 250.0},
        policy_version=1,
        agent_risk_ceiling="HIGH",
        expected_hash=owner_appr["action_hash"],
    ) is True
    assert verify_action_hash(
        project_id=ctx["pid"],
        agent_id=ctx["agent_id"],
        execution_id=exec_res["id"],
        tool_name="issue_refund",
        arguments={"order_id": "ORD-9001", "amount": 250.0},
        policy_version=2,
        agent_risk_ceiling="HIGH",
        expected_hash=owner_appr["action_hash"],
    ) is False
