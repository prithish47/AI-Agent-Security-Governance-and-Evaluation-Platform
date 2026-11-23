# AgentGuard — System Architecture

## 1. Overview

AgentGuard is an **AI Agent Security and Reliability Platform** that sits between AI agents (LLMs) and the tools they want to execute. Its foundational principle:

> **LLMs propose actions. AgentGuard authorizes, controls, executes, and audits them.**

The LLM is treated as an **untrusted decision-making component**. It can suggest tool calls, but it can never directly execute them. Every proposed action must pass through a deterministic security boundary before anything happens.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                       │
│  Dashboard │ Playground │ Approvals │ Evaluations │ Audit Logs  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST API (HTTP/JSON)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                           │
│                                                                 │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │ Auth &   │  │  API Layer    │  │  Application Services    │  │
│  │ RBAC     │  │  (Endpoints)  │  │  (Business Logic)        │  │
│  └────┬─────┘  └───────┬───────┘  └────────────┬─────────────┘  │
│       │                │                       │                │
│  ┌────▼────────────────▼───────────────────────▼─────────────┐  │
│  │              AGENT RUNTIME ORCHESTRATOR                    │  │
│  │  ┌─────────────────┐    ┌────────────────────────────┐    │  │
│  │  │  AI Model       │    │  Pinned Execution Context   │    │  │
│  │  │  Adapter         │    │  (Immutable Snapshot)       │    │  │
│  │  └────────┬────────┘    └──────────────┬─────────────┘    │  │
│  │           │                            │                  │  │
│  │           ▼                            │                  │  │
│  │  ┌─────────────────┐                  │                  │  │
│  │  │ Tool Call        │                  │                  │  │
│  │  │ Proposal         │                  │                  │  │
│  │  └────────┬────────┘                  │                  │  │
│  │           │                            │                  │  │
│  │  ═════════▼════════════════════════════▼══════════════    │  │
│  │  ║     GUARDED TOOL EXECUTOR — SECURITY BOUNDARY    ║    │  │
│  │  ║                                                   ║    │  │
│  │  ║  ┌──────────────────────────────────────────────┐ ║    │  │
│  │  ║  │          POLICY EVALUATOR (Pure Python)      │ ║    │  │
│  │  ║  │                                              │ ║    │  │
│  │  ║  │  1. Tool Permission Rule                     │ ║    │  │
│  │  ║  │  2. Tool Deny Rule                           │ ║    │  │
│  │  ║  │  3. Risk Level Ceiling Rule                  │ ║    │  │
│  │  ║  │  4. Resource Ownership Rule                  │ ║    │  │
│  │  ║  │  5. Argument Constraint Rule                 │ ║    │  │
│  │  ║  │  6. Argument Pattern Rule                    │ ║    │  │
│  │  ║  │  7. Approval Required Rule                   │ ║    │  │
│  │  ║  └──────────┬────────────┬────────────┬────────┘ ║    │  │
│  │  ║             │            │            │          ║    │  │
│  │  ║         ┌───▼──┐   ┌────▼───┐  ┌─────▼──────┐   ║    │  │
│  │  ║         │ALLOW │   │ DENY   │  │ REQUIRES   │   ║    │  │
│  │  ║         │      │   │        │  │ APPROVAL   │   ║    │  │
│  │  ║         └───┬──┘   └────┬───┘  └─────┬──────┘   ║    │  │
│  │  ═════════════╪════════════╪════════════╪════════════    │  │
│  │               │            │            │                │  │
│  │               ▼            ▼            ▼                │  │
│  │        Execute Tool   Block &     Create Pending         │  │
│  │        via Whitelist  Audit       Approval & Suspend     │  │
│  │               │            │            │                │  │
│  │               ▼            ▼            ▼                │  │
│  │           AUDIT EVENT RECORDING (Append-Only)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   PERSISTENCE LAYER                       │  │
│  │              SQLAlchemy 2.0 + Alembic                     │  │
│  └──────────────────────────┬───────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │   PostgreSQL 17     │
                   │   (Docker)          │
                   └─────────────────────┘
```

---

## 3. Layered Architecture

The application follows a **modular layered architecture** with clear separation of concerns:

### Layer 1: API Layer (`app/api/`)
- FastAPI route definitions
- Request parsing and response serialization
- HTTP status codes and error formatting
- No business logic lives here

### Layer 2: Authentication & Authorization (`app/auth/`, `app/core/security.py`)
- JWT token creation and validation
- Password hashing with Argon2id
- RBAC permission checking
- Project membership verification
- Every request is authenticated before reaching business logic

### Layer 3: Application Services (`app/*/service.py`)
- Business logic orchestration
- Coordinates between domain logic and persistence
- Transaction management
- Input validation beyond schema level

### Layer 4: Domain Logic (`app/policies/engine.py`, `app/runtime/`)
- **Pure Python** — no dependencies on FastAPI, SQLAlchemy, or external services
- Policy evaluation engine
- Risk assessment
- Execution context management
- This is the heart of AgentGuard's security

### Layer 5: Policy Evaluation Engine (`app/policies/engine.py`)
- 7 deterministic policy rules
- Short-circuit evaluation
- Fail-closed by default
- Independently testable without any infrastructure

### Layer 6: Agent Runtime (`app/runtime/`)
- Controlled execution loop
- Bounded iterations
- Pinned context snapshots
- Tool proposal routing

### Layer 7: Tool Execution (`app/tools/executor.py`)
- Guarded Tool Executor — the security boundary
- Whitelist-based executor catalog (no dynamic code loading)
- Pre/post execution auditing

### Layer 8: AI Provider Adapters (`app/ai/`)
- OpenAI, Gemini, Ollama, Mock providers
- Common interface returning typed responses
- Model responses treated as untrusted input

### Layer 9: Persistence (`app/persistence/`)
- SQLAlchemy 2.0 models
- Async database sessions
- Repository pattern for data access
- Alembic migrations

### Layer 10: Audit & Evaluation (`app/audit/`, `app/evaluation/`)
- Append-only audit event recording
- Adversarial benchmark engine
- Metric calculations from real execution data

---

## 4. Request Flow — Tool Execution

Here's what happens when a user sends a prompt through the Playground:

```
1. User sends prompt via POST /api/v1/agents/{agent_id}/execute
       │
2. JWT middleware authenticates the request
       │
3. RBAC checks: user has DEVELOPER+ role in the agent's project
       │
4. Agent Runtime Orchestrator initializes:
   - Loads agent config
   - Loads active policy version
   - Loads assigned tools & permissions
   - Creates IMMUTABLE execution context snapshot
   - Creates execution record in DB
       │
5. Runtime calls AI Model Adapter with:
   - System prompt (including available tools)
   - User message
   - Conversation history
       │
6. AI Model responds with either:
   ├── Final Answer → Return to user, record trace, DONE
   └── Tool Call Proposal → Continue to step 7
       │
7. Tool proposal enters GUARDED TOOL EXECUTOR:
   │
   ├─ 7a. Verify tool exists in executable whitelist
   ├─ 7b. Verify tool is enabled
   ├─ 7c. Validate arguments against schema
   ├─ 7d. POLICY EVALUATOR runs all 7 rules in order:
   │       │
   │       ├── Rule 1: Tool Permission → DENY if not assigned
   │       ├── Rule 2: Tool Deny List → DENY if explicitly blocked
   │       ├── Rule 3: Risk Ceiling → DENY if exceeds agent's max
   │       ├── Rule 4: Resource Ownership → DENY if wrong tenant
   │       ├── Rule 5: Argument Constraints → DENY if invalid
   │       ├── Rule 6: Argument Patterns → DENY if suspicious
   │       ├── Rule 7: Approval Required → REQUIRES_APPROVAL
   │       └── All passed → ALLOW
   │
   ├─ ALLOW → Execute tool, capture result, record audit event
   ├─ DENY → Block execution, record audit event, return denial to model
   └─ REQUIRES_APPROVAL → Suspend execution, create pending approval
       │
8. If tool executed, return result to AI Model (go to step 5)
       │
9. Check iteration count against min(agent.max_iterations, global_ceiling=20)
   └── If exceeded → STOP, record MAX_ITERATIONS_REACHED
       │
10. Record complete execution trace
```

---

## 5. The Security Boundary — Why It Matters

The **Guarded Tool Executor** is the single chokepoint through which ALL tool calls must pass. This design ensures:

1. **No bypass possible**: The AI model adapter returns structured proposals, never executable code. There is no path from "model says do X" to "X actually happens" that doesn't go through the executor.

2. **Fail-closed**: If any policy data is missing, malformed, or ambiguous, the action is DENIED. We never default to allowing.

3. **Deterministic**: The same inputs always produce the same policy decision. No randomness, no AI-based security decisions.

4. **Auditable**: Every decision is recorded with the rule that made it, the reason, and the full context.

---

## 6. Multi-Tenancy Model

```
User ──┐
       ├── Project A (via Membership, Role: OWNER)
       │       ├── Agent 1
       │       │     ├── Tool Assignment: search_customer
       │       │     └── Tool Assignment: get_order_status
       │       ├── Agent 2
       │       ├── Tool: search_customer (registered in Project A)
       │       ├── Policy: "Production Security Policy" (versions 1,2,3)
       │       ├── Executions (scoped to Project A)
       │       └── Audit Events (scoped to Project A)
       │
       └── Project B (via Membership, Role: DEVELOPER)
               ├── Agent 3
               └── ...
```

Every resource is scoped to a project. Backend queries ALWAYS filter by project_id. The frontend cannot trick the backend into returning cross-project data because:
- The user's project membership is verified from the JWT + database
- Queries join through project_members to verify access
- Composite foreign keys ensure child resources belong to the right project

---

## 7. Technology Decisions

| Decision | Choice | Why |
|---|---|---|
| Web Framework | FastAPI | Async support, automatic OpenAPI docs, Pydantic integration, modern Python |
| ORM | SQLAlchemy 2.0 | Mature, async support, powerful query builder, Alembic integration |
| Database | PostgreSQL 17 | JSONB for flexible schemas, strong constraints, mature ecosystem |
| Auth | JWT (PyJWT) + Argon2id | Stateless auth tokens + strongest password hashing algorithm |
| Frontend | Next.js + shadcn/ui | App Router for modern React, shadcn for professional components |
| AI Abstraction | Custom adapter pattern | Keeps vendor lock-in out of core logic, enables mock testing |
| Policy Engine | Pure Python | No framework dependencies = independently testable, portable |
| Canonicalization | RFC 8785 (JCS) | Standard for deterministic JSON serialization, needed for approval integrity |

---

## 8. Deployment Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
│                                              │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Frontend     │  │  Backend             │  │
│  │  Next.js      │  │  FastAPI + Uvicorn   │  │
│  │  Port 3000    │  │  Port 8000           │  │
│  └──────┬───────┘  └──────────┬───────────┘  │
│         │                     │               │
│         │    REST API         │               │
│         └────────────────────►│               │
│                               │               │
│                     ┌─────────▼──────────┐   │
│                     │  PostgreSQL 17     │   │
│                     │  Port 5432         │   │
│                     └────────────────────┘   │
└──────────────────────────────────────────────┘
```

Each service runs in its own container. The frontend communicates with the backend exclusively through the REST API. No shared state, no direct database access from the frontend.
