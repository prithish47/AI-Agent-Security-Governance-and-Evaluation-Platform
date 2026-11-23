# AgentGuard — Phase Details & Rationale

This document provides deeper context on each implementation phase: what we're building, why it matters, and what to watch out for.

---

## Phase 1: Foundation

### What We Build
- Project skeleton with backend (FastAPI), frontend (Next.js), and database (PostgreSQL)
- Docker Compose to orchestrate all three services
- Health endpoints to verify connectivity
- Configuration management via environment variables

### Why This Matters
Before writing any business logic, we need infrastructure that works. A broken dev environment wastes hours. We validate that:
- Backend can serve HTTP requests
- Frontend can render pages
- Database accepts connections
- Docker Compose wires everything together
- Frontend can reach the backend API (CORS configured)

### Key Decisions
- **Async FastAPI**: We use async endpoints and SQLAlchemy async sessions because database I/O is the main bottleneck. While a single request doesn't benefit much from async, it allows the server to handle many concurrent requests efficiently without threading overhead.
- **Environment-based config**: All configuration comes from environment variables, loaded via Pydantic Settings. This is a 12-factor app best practice—the same code runs in dev, staging, and production with different configs.

### Pitfalls to Avoid
- Don't skip Docker setup—it's needed for consistent environments
- Don't hardcode database URLs or secrets
- Test CORS early—cross-origin issues are frustrating to debug later

---

## Phase 2: Core Domain & Database

### What We Build
- 17 SQLAlchemy models representing all domain entities
- Alembic migration infrastructure
- CRUD services and API endpoints for core entities
- Database constraints (FK, unique, not-null, check)

### Why This Matters
The database schema is the foundation of data integrity. Getting it wrong early means painful migrations later. We use the database as a **safety net**:
- Foreign keys prevent orphaned records
- Unique constraints prevent duplicates
- Not-null constraints prevent incomplete data
- JSONB columns store flexible data without over-normalizing

### Key Relationships
```
User → ProjectMember → Project
                         ├→ Agent → AgentToolAssignment → ToolDefinition
                         ├→ SecurityPolicy → PolicyVersion
                         ├→ Execution → ExecutionStep
                         ├→ ApprovalRequest
                         └→ AuditEvent
```

Every resource chains back to a Project. This makes tenant isolation enforceable at the query level.

### Why Alembic (Not `create_all`)
SQLAlchemy's `create_all()` creates tables from models, but it:
- Can't modify existing tables
- Can't track what changed
- Has no rollback capability
- Isn't suitable for production

Alembic generates versioned migration scripts that:
- Document every schema change
- Can upgrade and downgrade
- Are version-controlled
- Run the same way in every environment

---

## Phase 3: Security Engine

### What We Build
- Pure Python policy evaluator with 7 rules
- Domain models for tool proposals and decisions
- Fail-closed evaluation behavior
- Guarded Tool Executor
- Synthetic tool implementations with mock data

### Why This Matters
This is the **core value proposition** of AgentGuard. Everything else is infrastructure supporting this engine. The policy evaluator is intentionally designed as pure Python because:

1. **Independently testable**: You can test security rules without starting a server, connecting a database, or calling an AI API
2. **Fast**: No I/O means evaluations complete in microseconds
3. **Deterministic**: Same inputs always produce same outputs
4. **Portable**: Could be extracted into a library or used in other contexts

### The 7 Rules and Why Each Exists

| # | Rule | Threat It Addresses |
|---|---|---|
| 1 | Tool Permission | Prevents using tools not assigned to the agent |
| 2 | Tool Deny List | Blocks inherently dangerous tools regardless of assignment |
| 3 | Risk Ceiling | Prevents agents from executing above their authorization level |
| 4 | Resource Ownership | Prevents cross-tenant data access |
| 5 | Argument Constraints | Prevents malformed or oversized inputs |
| 6 | Argument Patterns | Detects suspicious content (SQL injection, path traversal) |
| 7 | Approval Required | Gates high-impact actions behind human review |

### Why This Order?
The cheapest and most decisive checks come first:
- Checking tool permission is O(1) lookup
- Deny list is another O(1) lookup
- Risk ceiling is a simple comparison
- These quickly filter out most unauthorized calls

Expensive checks (argument validation, regex matching) come later—no point validating arguments for a tool that's not even permitted.

Approval check is LAST because a deny must never be overridden by an approval request. If a tool is on the deny list, it doesn't matter if someone could approve it.

---

## Phase 4: Authentication & RBAC

### What We Build
- User registration with Argon2id password hashing
- JWT-based authentication (access + refresh tokens)
- Project membership system
- Role-based permission checking
- Tenant-scoped endpoint protection

### Why Argon2id (Not bcrypt or PBKDF2)
Argon2id is the OWASP-recommended password hashing algorithm because:
- It's **memory-hard**: attackers can't parallelize GPU attacks efficiently
- It's resistant to **side-channel attacks** (unlike pure Argon2i)
- It's the winner of the Password Hashing Competition
- bcrypt works but has a 72-byte password limit and is GPU-acceleratable
- PBKDF2 is FIPS-approved but not memory-hard

### Why Two Token Types
- **Access token** (short-lived, 15-30 min): Used for every API request. If stolen, the window of exploitation is small.
- **Refresh token** (longer-lived, 7 days): Used only to get new access tokens. Stored hashed in the database so it can be **revoked** (logout). If you only had access tokens, you couldn't implement logout.

### RBAC Design
Permissions are defined in a **centralized matrix**, not scattered throughout the code:

```python
# BAD: role checks scattered everywhere
if current_user.role == "ADMIN" or current_user.role == "OWNER":
    # do thing

# GOOD: centralized permission system
require_permission(user_id, project_id, Permission.MANAGE_POLICIES)
```

The centralized approach means:
- Adding a new role = update one place
- Auditing permissions = read one file
- Testing = mock one function

---

## Phase 5: Agent Runtime

### What We Build
- Controlled execution loop for AI agents
- AI model adapter interface + mock provider
- Context pinning (immutable snapshot at execution start)
- Bounded iterations
- Execution trace recording

### Why Context Pinning
Imagine an agent execution is running with a policy that allows `issue_refund`. Mid-execution, an admin changes the policy to deny `issue_refund`. Without context pinning:
- The agent might have been told it CAN issue refunds (tool list sent to AI)
- But now the policy denies it
- This creates confusing behavior and inconsistent audit trails

With context pinning:
- At execution start, we snapshot the agent config, policy version, and tool permissions
- This snapshot is IMMUTABLE for the duration of the execution
- Policy changes take effect on the NEXT execution, not the current one

### Why Bounded Iterations
LLMs can enter infinite loops—calling the same tool repeatedly, or alternating between two tools without converging. Without a ceiling:
- API costs spiral
- Server resources are consumed
- The user waits forever

We use `min(agent.max_iterations, global_ceiling=20)`:
- Each agent can set its own limit (e.g., 5 for simple tasks)
- A global ceiling prevents any agent from exceeding 20
- When hit, we stop gracefully and record `MAX_ITERATIONS_REACHED`

### Execution Flow
```
START
  │
  ▼
Create immutable context snapshot
  │
  ▼
Iteration 1: Call AI model → Get response
  │
  ├── Final answer? → Record trace, DONE
  │
  ├── Tool proposal? → Send to Guarded Executor
  │                      │
  │                      ├── ALLOW → Execute, record step
  │                      ├── DENY → Record step, return denial to model
  │                      └── APPROVAL → Suspend execution
  │
  └── Error? → Record error, DONE
  │
  ▼
Iteration 2: Call AI model with tool result → ...
  │
  ▼
... until DONE or MAX_ITERATIONS
```

---

## Phase 6: Human Approvals

### What We Build
- Pending approval creation when policy says REQUIRES_APPROVAL
- RFC 8785 JSON Canonicalization
- SHA-256 hash of canonicalized arguments
- Approve/reject workflow
- Atomic single-use consumption
- Execution resumption after approval

### Why Cryptographic Action Binding
The gap between "propose action" and "approve action" is a window for tampering. Consider:

1. Agent proposes: `issue_refund(amount=50)`
2. This gets stored as a pending approval
3. An attacker modifies the stored arguments to `issue_refund(amount=5000)`
4. Approver sees `amount=5000` and approves it
5. The wrong amount is refunded

Cryptographic binding prevents this:
1. Agent proposes: `issue_refund(amount=50)`
2. We canonicalize: `{"amount":50}` (RFC 8785 ordering)
3. We hash: `SHA-256("{"amount":50}")` = `abc123...`
4. We store both the arguments AND the hash
5. Before execution, we re-canonicalize and re-hash the stored arguments
6. If the hash doesn't match → SECURITY VIOLATION

### Why RFC 8785 (Not Just `json.dumps(sort_keys=True)`)
Python's `json.dumps(sort_keys=True)` has issues:
- Number formatting varies (`1.0` vs `1` vs `1.00`)
- Unicode escaping varies
- Whitespace handling varies between implementations

RFC 8785 (JSON Canonicalization Scheme) specifies exact rules for every detail. It guarantees that any two implementations produce the same bytes for the same logical JSON value.

---

## Phase 7: AI Integration

### What We Build
- OpenAI-compatible API adapter
- Google Gemini adapter
- Ollama adapter (local models)
- Tool schema conversion per provider

### Why a Provider Abstraction
Each AI provider has different:
- API endpoints and authentication
- Request/response formats
- Tool/function calling syntax
- Error codes and retry behavior

The adapter pattern means the runtime doesn't care which provider it's talking to:

```python
# The runtime only sees this interface:
class AIProvider:
    async def generate(self, messages, tools) -> AIResponse:
        ...

# AIResponse is always:
# - FinalAnswer(text)
# - ToolCallProposal(tool_name, arguments)
# - ModelError(error_message)
```

This also enables the Mock provider, which is essential for testing without API keys.

---

## Phase 8: Evaluation Engine

### What We Build
- 21 benchmark cases (18 adversarial + 3 legitimate)
- Baseline execution (no security) vs. protected execution (with AgentGuard)
- Metric calculations from real data
- Comparison reports

### Why Both Baseline and Protected
Showing that AgentGuard blocks attacks is only half the story. We also need to show:
- **Without AgentGuard**: How many attacks succeed? (baseline)
- **With AgentGuard**: How many attacks are blocked? (protected)
- **False positives**: Does AgentGuard block legitimate actions? (critical!)

A security system that blocks everything is 100% secure but 0% useful. The evaluation engine measures this tradeoff.

### Metric Definitions

| Metric | Formula | What It Tells You |
|---|---|---|
| ASR | attacks_succeeded / total_attacks | How often attackers get through |
| UTER | unauthorized_tools_executed / unauthorized_attempts | How often forbidden tools actually run |
| LTSR | legit_succeeded / total_legit | How often normal work completes |
| FBR | legit_blocked / total_legit | How often security wrongly blocks normal work |

**Zero denominators return null**, not zero. If you haven't run any adversarial tests, ASR is undefined—not "perfect."

---

## Phase 9: Frontend

### What We Build
- Complete developer dashboard with 10+ pages
- Authentication flow
- Interactive execution playground
- Approval management
- Evaluation visualizations
- Audit log browser

### Design Philosophy
This is a **developer tool**, not a consumer app. That means:
- Dense information display (devs want data, not whitespace)
- Dark theme (comfortable for long sessions)
- Clear status indicators (green/red/yellow, not ambiguous icons)
- Fast navigation (sidebar, not nested menus)
- Real data only (no placeholder cards, no fake metrics)

### The Playground Is Key
The Execution Playground is where developers actually experience AgentGuard:
1. Pick an agent
2. Type a prompt (or use a preset)
3. Watch the execution unfold
4. See each step: model thought → tool proposal → policy decision → result
5. Understand exactly why something was allowed or blocked

This is the demo moment. If this page doesn't work well, nothing else matters.

---

## Phase 10: Production Readiness

### What We Build
- Production Docker configuration
- GitHub Actions CI pipeline
- Complete test suite execution
- Security audit checklist
- Final documentation

### The Checklist
Before declaring done, every item on the Definition of Done (spec section 22) must be verified with evidence. Not "I think it works"—actual test output, screenshots, or verification commands.
