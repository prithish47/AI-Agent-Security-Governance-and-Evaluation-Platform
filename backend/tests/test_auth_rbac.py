# =============================================================================
# AgentGuard — Authentication, RBAC & Tenant Isolation Tests
# =============================================================================

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import get_db, Base
from app.core.security import verify_password
from app.persistence.models import ProjectRole, User
from app.auth import service as auth_service
from app.auth.schemas import UserRegister, UserLogin
from app.auth.rbac import (
    Permission,
    ROLE_PERMISSIONS,
    has_permission,
    verify_project_permission,
)
from app.projects import service as project_service
from app.projects.schemas import ProjectCreate, ProjectMemberCreate
from app.core.exceptions import ForbiddenError, UnauthorizedError, ConflictError


@pytest_asyncio.fixture
async def auth_db():
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
async def auth_client():
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
async def test_registration_and_argon2id_hashing(auth_db: AsyncSession):
    """Test user registration and verify Argon2id password hashing."""
    user = await auth_service.register_user(
        auth_db,
        UserRegister(
            email="security.analyst@example.com",
            username="sec_analyst",
            password="UltraSecureP@ssw0rd!2026",
        ),
    )
    assert user.id is not None
    assert user.email == "security.analyst@example.com"
    # Never store plaintext password
    assert user.password_hash != "UltraSecureP@ssw0rd!2026"
    assert "$argon2id$" in user.password_hash
    assert verify_password("UltraSecureP@ssw0rd!2026", user.password_hash) is True
    assert verify_password("WrongPassword!", user.password_hash) is False

    # Duplicate email should fail
    with pytest.raises(ConflictError):
        await auth_service.register_user(
            auth_db,
            UserRegister(
                email="security.analyst@example.com",
                username="different_user",
                password="AnotherPassword!1",
            ),
        )


@pytest.mark.asyncio
async def test_login_and_jwt_lifecycle(auth_db: AsyncSession):
    """Test authentication, JWT token issuance, refresh, and logout revocation."""
    user = await auth_service.register_user(
        auth_db,
        UserRegister(
            email="dev.lead@example.com",
            username="dev_lead",
            password="DevLeadSecurePassword123!",
        ),
    )

    # 1. Login
    tokens = await auth_service.authenticate_user(
        auth_db,
        UserLogin(email="dev.lead@example.com", password="DevLeadSecurePassword123!"),
    )
    token_resp = await auth_service.create_tokens_for_user(auth_db, user)
    assert token_resp.access_token is not None
    assert token_resp.refresh_token is not None

    # 2. Refresh token
    new_tokens = await auth_service.refresh_access_token(auth_db, token_resp.refresh_token)
    assert new_tokens.access_token is not None
    assert new_tokens.refresh_token == token_resp.refresh_token

    # 3. Logout (revokes refresh token)
    await auth_service.revoke_refresh_token(auth_db, token_resp.refresh_token)
    with pytest.raises(UnauthorizedError):
        await auth_service.refresh_access_token(auth_db, token_resp.refresh_token)


@pytest.mark.asyncio
async def test_rbac_separation_of_duties_matrix(auth_db: AsyncSession):
    """
    Test separation of duties:
    - Developers cannot approve high-risk operations
    - Approvers cannot modify security policies
    - Viewers cannot execute or modify anything
    """
    # Verify capability matrix
    assert has_permission(ProjectRole.OWNER, Permission.DELETE_PROJECT) is True
    assert has_permission(ProjectRole.ADMIN, Permission.DELETE_PROJECT) is False

    # Developers cannot approve actions
    assert has_permission(ProjectRole.DEVELOPER, Permission.APPROVE_ACTIONS) is False
    assert has_permission(ProjectRole.DEVELOPER, Permission.RUN_EXECUTIONS) is True

    # Approvers cannot manage policies
    assert has_permission(ProjectRole.APPROVER, Permission.MANAGE_POLICIES) is False
    assert has_permission(ProjectRole.APPROVER, Permission.APPROVE_ACTIONS) is True

    # Viewers have read-only
    assert has_permission(ProjectRole.VIEWER, Permission.RUN_EXECUTIONS) is False
    assert has_permission(ProjectRole.VIEWER, Permission.MANAGE_POLICIES) is False
    assert has_permission(ProjectRole.VIEWER, Permission.VIEW_DASHBOARD) is True


@pytest.mark.asyncio
async def test_tenant_isolation_and_cross_project_denial(auth_db: AsyncSession):
    """Verify that a user belonging to Project A is denied access to Project B."""
    # Create two users
    user_a = await auth_service.register_user(
        auth_db,
        UserRegister(email="user.a@example.com", username="user_a", password="Password123!A"),
    )
    user_b = await auth_service.register_user(
        auth_db,
        UserRegister(email="user.b@example.com", username="user_b", password="Password123!B"),
    )

    # User A creates Project A
    proj_a = await project_service.create_project(
        auth_db, ProjectCreate(name="Project Alpha"), creator_id=user_a.id
    )

    # User B creates Project B
    proj_b = await project_service.create_project(
        auth_db, ProjectCreate(name="Project Beta"), creator_id=user_b.id
    )

    # User A has OWNER permission in Project Alpha
    member_a = await verify_project_permission(proj_a.id, user_a, Permission.MANAGE_POLICIES, auth_db)
    assert member_a.role == ProjectRole.OWNER

    # User A attempts to access Project Beta -> MUST FAIL WITH FORBIDDEN
    with pytest.raises(ForbiddenError):
        await verify_project_permission(proj_b.id, user_a, Permission.VIEW_DASHBOARD, auth_db)

    # Developer cannot approve actions check
    dev_user = await auth_service.register_user(
        auth_db,
        UserRegister(email="dev@example.com", username="dev_tester", password="DevPassword123!"),
    )
    await project_service.add_project_member(
        auth_db, proj_a.id, ProjectMemberCreate(user_id=dev_user.id, role=ProjectRole.DEVELOPER)
    )

    with pytest.raises(ForbiddenError):
        await verify_project_permission(proj_a.id, dev_user, Permission.APPROVE_ACTIONS, auth_db)


@pytest.mark.asyncio
async def test_auth_api_routes(auth_client: AsyncClient):
    """Test /api/v1/auth REST routes."""
    # 1. Register
    reg_res = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test.api@example.com",
            "username": "api_user",
            "password": "SecurePassword999!",
        },
    )
    assert reg_res.status_code == 201
    assert reg_res.json()["email"] == "test.api@example.com"

    # 2. Login
    login_res = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "test.api@example.com", "password": "SecurePassword999!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    token = data["access_token"]
    refresh_token = data["refresh_token"]

    # 3. GET /auth/me with Bearer token
    me_res = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "api_user"

    # 4. Refresh token
    ref_res = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_res.status_code == 200
    assert "access_token" in ref_res.json()

    # 5. Logout
    logout_res = await auth_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200
