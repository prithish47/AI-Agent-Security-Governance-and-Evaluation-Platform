# AgentGuard — Implementation Plan

## Overview

This document defines the 10-phase implementation plan for AgentGuard. Each phase builds on the previous one, creating a solid foundation before adding complexity.

---

## Phase 1: Foundation (Current)

**Goal**: Get the skeleton running — backend, frontend, database, Docker, all wired together.

### Tasks
- [ ] Initialize Git repository
- [ ] Create project directory structure
- [ ] Set up FastAPI backend with health endpoint
- [ ] Set up Next.js frontend with TypeScript + Tailwind + shadcn/ui
- [ ] Configure PostgreSQL with Docker
- [ ] Set up SQLAlchemy 2.0 async engine
- [ ] Configure Alembic for migrations
- [ ] Create Docker Compose with all 3 services
- [ ] Create `.env.example` with all configuration variables
- [ ] Verify backend starts at http://localhost:8000
- [ ] Verify frontend starts at http://localhost:3000
- [ ] Verify frontend can call backend health endpoint
- [ ] Create `.gitignore`
- [ ] Create initial `README.md`

### Deliverables
- Running FastAPI server with `/health` and `/docs`
- Running Next.js app with a basic page
- PostgreSQL accessible
- Docker Compose launches everything
- Basic frontend → backend connectivity proven

### Verification
```bash
# Backend health
curl http://localhost:8000/health

# Swagger docs accessible
# Open http://localhost:8000/docs

# Frontend loads
# Open http://localhost:3000

# Docker Compose
docker compose up --build
```

---

## Phase 2: Core Domain & Database

**Goal**: Create the data layer — all SQLAlchemy models, database constraints, and Alembic migrations.

### Tasks
- [ ] Create SQLAlchemy models for all 17 entities
- [ ] Define UUID primary keys, JSONB columns, foreign keys
- [ ] Create composite foreign keys for tenant isolation
- [ ] Generate initial Alembic migration
- [ ] Implement CRUD services for:
  - Projects
  - Agents
  - Tools
  - Agent-Tool Assignments
  - Security Policies
  - Policy Versions
- [ ] Create API endpoints for all CRUD operations
- [ ] Add Pydantic request/response schemas
- [ ] Test database constraints (unique, FK, not-null)
- [ ] Test that migrations apply cleanly to a fresh database

### Key Models
1. `User` — authentication identity
2. `Project` — tenant/workspace
3. `ProjectMember` — user-project-role association
4. `Agent` — AI agent configuration
5. `ToolDefinition` — tool metadata (no executable code)
6. `AgentToolAssignment` — which tools an agent can use
7. `SecurityPolicy` — policy container
8. `PolicyVersion` — immutable versioned snapshot of rules
9. `Execution` — agent execution record
10. `ExecutionStep` — individual step within an execution
11. `ApprovalRequest` — pending human approval
12. `AuditEvent` — security event log
13. `EvaluationSuite` — benchmark suite definition
14. `EvaluationCase` — individual benchmark case
15. `EvaluationRun` — benchmark execution run
16. `EvaluationResult` — individual case result
17. `RefreshToken` — JWT refresh token storage

### Verification
- Alembic migration applies successfully
- CRUD endpoints return correct data
- Foreign key violations raise proper errors
- JSONB columns store and retrieve correctly

---

## Phase 3: Security Engine

**Goal**: Build the pure-Python policy evaluator — the heart of AgentGuard.

### Tasks
- [ ] Define domain models (ToolProposal, PolicyDecision, etc.) as plain dataclasses/Pydantic models
- [ ] Implement 7 policy rules as independent, testable functions
- [ ] Implement deterministic short-circuit evaluator
- [ ] Implement fail-closed behavior
- [ ] Build Guarded Tool Executor
- [ ] Create synthetic tool implementations (mock customer DB, tickets, etc.)
- [ ] Write extensive unit tests (target: 50+ test cases)

### Policy Rules (Evaluation Order)
1. **Tool Permission Rule** — Is this tool assigned to this agent?
2. **Tool Deny Rule** — Is this tool on the explicit deny list?
3. **Risk Ceiling Rule** — Does the tool's risk level exceed the agent's max?
4. **Resource Ownership Rule** — Is the resource in the agent's authorized scope?
5. **Argument Constraint Rule** — Are arguments valid per schema?
6. **Argument Pattern Rule** — Do arguments contain suspicious patterns?
7. **Approval Required Rule** — Does this operation need human approval?

### Verification
- Unit tests pass without any database or network
- Fail-closed: missing policy → DENY
- Deny overrides everything
- Risk ceiling enforced
- All 7 rules tested independently and together

---

## Phase 4: Authentication & RBAC

**Goal**: Secure the application — users, passwords, tokens, roles, project isolation.

### Tasks
- [ ] Implement user registration with Argon2id password hashing
- [ ] Implement login returning JWT access + refresh tokens
- [ ] Implement token refresh endpoint
- [ ] Implement logout with refresh token revocation
- [ ] Implement `/auth/me` current user endpoint
- [ ] Create JWT middleware for FastAPI
- [ ] Implement project membership system
- [ ] Implement 5-role RBAC (OWNER, ADMIN, DEVELOPER, APPROVER, VIEWER)
- [ ] Create centralized permission checking
- [ ] Enforce project scoping on all existing endpoints
- [ ] Write security integration tests

### RBAC Matrix
| Capability | OWNER | ADMIN | DEVELOPER | APPROVER | VIEWER |
|---|---|---|---|---|---|
| Delete project | ✓ | | | | |
| Manage members | ✓ | ✓ | | | |
| Manage policies | ✓ | ✓ | | | |
| Configure agents/tools | ✓ | ✓ | ✓ | | |
| Run executions | ✓ | ✓ | ✓ | | |
| Approve actions | ✓ | ✓ | | ✓ | |
| View dashboard/logs | ✓ | ✓ | ✓ | ✓ | ✓ |

### Verification
- Registration creates user with hashed password
- Login returns valid JWT
- Expired tokens are rejected
- Cross-project access is denied
- Role permissions enforced
- Developers cannot approve actions

---

## Phase 5: Agent Runtime

**Goal**: Build the controlled execution loop that orchestrates AI calls, tool proposals, and policy enforcement.

### Tasks
- [ ] Define AI provider interface (abstract base)
- [ ] Implement Mock AI provider with deterministic scenarios
- [ ] Build agent runtime orchestrator
- [ ] Implement bounded execution loop with iteration limits
- [ ] Implement context pinning (immutable snapshot at start)
- [ ] Wire tool proposals through Guarded Tool Executor
- [ ] Implement execution trace recording
- [ ] Handle all termination conditions
- [ ] Create execution and trace API endpoints
- [ ] Write runtime integration tests

### Termination Conditions
- `COMPLETED` — model returned final answer
- `DENIED` — tool call was blocked by policy
- `REQUIRES_APPROVAL` — execution suspended pending approval
- `MAX_ITERATIONS_REACHED` — hit the iteration ceiling
- `MODEL_ERROR` — AI provider returned an error
- `TOOL_ERROR` — tool execution failed
- `SECURITY_ERROR` — security violation detected

### Verification
- Mock provider drives complete execution cycles
- Iteration limit enforced (never exceeds ceiling)
- Context pinning prevents mid-execution config changes
- All tool calls go through Guarded Tool Executor
- Execution traces recorded accurately

---

## Phase 6: Human Approvals

**Goal**: Build the complete approval workflow with cryptographic integrity.

### Tasks
- [ ] Create pending approval persistence
- [ ] Implement RFC 8785 JSON Canonicalization
- [ ] Implement SHA-256 action binding (hash on create, verify on consume)
- [ ] Build approve/reject endpoints
- [ ] Implement atomic single-use consumption (DB transaction)
- [ ] Implement execution resumption after approval
- [ ] Add approval status lifecycle (PENDING → APPROVED/REJECTED → CONSUMED/EXPIRED)
- [ ] Verify approver has correct project role
- [ ] Write integrity tests (tamper detection, replay prevention)

### Verification
- Approvals created with correct SHA-256 hash
- Modified payloads detected and rejected
- Each approval consumed exactly once
- Approvers must have APPROVER/ADMIN/OWNER role
- Developers cannot approve their own agent's actions
- Resumed execution continues correctly

---

## Phase 7: AI Integration

**Goal**: Implement real AI provider adapters so the system works with actual models.

### Tasks
- [ ] Implement OpenAI-compatible adapter
- [ ] Implement Google Gemini adapter
- [ ] Implement Ollama adapter
- [ ] Implement tool schema conversion for each provider
- [ ] Support provider configuration via environment variables
- [ ] Add provider selection in agent configuration
- [ ] Write integration tests (with mock HTTP responses)

### Verification
- Each provider correctly formats tool schemas
- Each provider correctly parses tool call responses
- Provider errors handled gracefully
- No API keys needed for tests (mock HTTP)

---

## Phase 8: Evaluation Engine

**Goal**: Build the adversarial benchmark system with 21 test cases.

### Tasks
- [ ] Define 21 benchmark cases (18 adversarial + 3 legitimate)
- [ ] Implement benchmark runner (baseline + protected modes)
- [ ] Implement metric calculations (ASR, UTER, LTSR, FBR, latency)
- [ ] Create evaluation persistence (suites, runs, results)
- [ ] Create evaluation API endpoints
- [ ] Handle zero-denominator cases (return null, not zero)
- [ ] Write metric calculation tests

### Benchmark Cases
**Adversarial** (expected: blocked by AgentGuard):
1-18: See specification section 11

**Legitimate** (expected: succeed under AgentGuard):
19-21: Normal read/search/multi-step operations

### Verification
- All 21 cases execute with mock provider
- Metrics calculated from real results
- Baseline shows vulnerabilities
- Protected mode shows interceptions
- Zero denominators return null

---

## Phase 9: Frontend

**Goal**: Build the complete developer dashboard.

### Tasks
- [ ] Set up authentication flow (login, register, token storage)
- [ ] Create typed API client
- [ ] Build application shell (sidebar, top nav, project selector)
- [ ] Implement all 10 pages:
  1. Dashboard Overview
  2. Projects
  3. Agents
  4. Tool Catalog
  5. Security Policies
  6. Execution Playground
  7. Human Approvals
  8. Evaluations
  9. Audit Logs
  10. Settings
- [ ] Add loading states, empty states, error handling
- [ ] Add toast notifications and confirmation dialogs
- [ ] Dark theme developer-tool aesthetic
- [ ] Responsive layout

### Verification
- All pages load with real backend data
- CRUD operations work end-to-end
- Playground executes agents and shows traces
- Approvals can be reviewed and actioned
- Charts display real evaluation metrics

---

## Phase 10: Production Readiness

**Goal**: Polish, test, document, and prepare for deployment.

### Tasks
- [ ] Create production Dockerfiles
- [ ] Finalize Docker Compose configuration
- [ ] Create GitHub Actions CI pipeline
- [ ] Run full test suite and fix failures
- [ ] Security review (check all 20 engineering rules)
- [ ] Performance measurements
- [ ] Complete all documentation
- [ ] Clean installation verification (fresh clone → running app)
- [ ] Create final verification report

### Verification
- `docker compose up` launches complete application
- All automated tests pass
- Fresh clone + setup commands → working app
- Documentation accurate and complete
- BUILD-STATUS.md reflects actual state

---

## Dependency Graph

```
Phase 1 (Foundation)
    │
    ▼
Phase 2 (Database & Models)
    │
    ├──────────────────┐
    ▼                  ▼
Phase 3 (Security)  Phase 4 (Auth/RBAC)
    │                  │
    └────────┬─────────┘
             ▼
       Phase 5 (Runtime)
             │
             ▼
       Phase 6 (Approvals)
             │
     ┌───────┼────────┐
     ▼       ▼        ▼
Phase 7   Phase 8   Phase 9
(AI)     (Eval)   (Frontend)
     │       │        │
     └───────┼────────┘
             ▼
      Phase 10 (Production)
```

Phases 3 and 4 can be developed in parallel. Phases 7, 8, and 9 can be developed in parallel after Phase 6.

---

## Estimated Complexity

| Phase | Complexity | Key Risk |
|---|---|---|
| 1 | Low | Docker networking, dependency versions |
| 2 | Medium | Getting all 17 models + constraints right |
| 3 | Medium | Policy evaluation correctness, fail-closed |
| 4 | Medium | JWT lifecycle, RBAC enforcement completeness |
| 5 | High | Runtime loop correctness, context pinning |
| 6 | High | RFC 8785, atomic consumption, integrity |
| 7 | Medium | Provider API differences, error handling |
| 8 | Medium | Deterministic fixtures, metric accuracy |
| 9 | High | Many pages, real data integration |
| 10 | Medium | CI/CD, clean install verification |
