# AgentGuard — Security Model

## 1. Threat Model

AgentGuard's security model addresses threats that arise when AI agents (LLMs) interact with external tools. The LLM is treated as an **untrusted component** because:

- LLMs can be manipulated through **prompt injection** (direct or indirect)
- LLMs may **hallucinate** tool calls, arguments, or resource identifiers
- LLMs have no inherent concept of **authorization** or **data ownership**
- LLM outputs are **non-deterministic** and can vary between identical inputs

### Threat Categories

| Threat | Description | Mitigation |
|---|---|---|
| Direct Prompt Injection | Attacker crafts input to override system instructions | Policy engine blocks unauthorized tool calls regardless of prompt |
| Indirect Prompt Injection | Malicious content in retrieved data (tickets, docs) triggers actions | Tool execution requires passing all policy rules; model output is untrusted |
| Unauthorized Tool Execution | Model calls a tool it shouldn't have access to | Tool Permission Rule + explicit whitelist |
| Privilege Escalation | Model attempts actions beyond its assigned risk level | Risk Ceiling Rule + RBAC |
| Cross-Tenant Data Access | Model tries to access another project's resources | Resource Ownership Rule + project-scoped queries |
| Destructive Operations | Model attempts to delete critical data | Tool Deny Rule + Approval Required Rule |
| Data Exfiltration | Model tries to export sensitive data | Tool Deny Rule + Argument Pattern Rule |
| Infinite Loops | Model keeps calling tools without converging | Bounded iteration limit |
| Argument Manipulation | Model crafts malicious arguments (SQL injection, path traversal) | Argument Constraint Rule + Argument Pattern Rule |
| Approval Tampering | Modifying approved action before execution | RFC 8785 canonicalization + SHA-256 hash verification |

---

## 2. Zero-Trust Architecture

### Principle: Trust Nothing From the LLM

```
LLM says: "Call search_customer with tenant_id=tenant-999"
                                              ▲
                                              │
                              THIS IS UNTRUSTED.
                              We resolve tenant from the
                              authenticated execution context,
                              NOT from the model's output.
```

The LLM can suggest what to do, but the backend independently verifies:
1. **Is this tool allowed?** (Tool Permission Rule)
2. **Is this tool blocked?** (Tool Deny Rule)  
3. **Is the risk level acceptable?** (Risk Ceiling Rule)
4. **Is the resource in scope?** (Resource Ownership Rule)
5. **Are the arguments valid?** (Argument Constraint Rule)
6. **Are the arguments suspicious?** (Argument Pattern Rule)
7. **Does this need human approval?** (Approval Required Rule)

### Fail-Closed Default

If ANY of the following conditions exist, the action is **DENIED**:

- Policy data is missing
- Policy data is malformed
- Policy version is not active
- Tool is not in the executable whitelist
- Tool is disabled
- Arguments cannot be validated
- Any rule evaluation throws an exception

We never default to "allow" when in doubt.

---

## 3. Authentication Security

### Password Storage
- **Algorithm**: Argon2id (the recommended password hashing algorithm as of 2024+)
- **Why Argon2id**: It's resistant to both GPU attacks (like bcrypt) AND side-channel attacks (unlike Argon2i). It's the OWASP-recommended algorithm.
- **Configuration**: Memory cost, time cost, and parallelism are configured via environment variables with secure defaults.

### JWT Tokens
- **Access Token**: Short-lived (15-30 minutes), used for API authentication
- **Refresh Token**: Longer-lived (7 days), stored hashed in database, used to get new access tokens
- **Signing**: HMAC-SHA256 with a strong secret key
- **Validation**: Signature verification + expiration check + issuer/audience validation

### Token Lifecycle
```
Login → Access Token (15min) + Refresh Token (7 days)
                                     │
           Access Token expires      │
                │                    │
                ▼                    │
         POST /auth/refresh ◄───────┘
                │
                ▼
         New Access Token (15min)

Logout → Refresh Token revoked in DB
```

### What We DON'T Trust
- Client-supplied user IDs → Always extract from JWT
- Client-supplied project IDs for authorization → Always verify membership in DB
- Client-supplied roles → Always look up from project_members table

---

## 4. RBAC (Role-Based Access Control)

### Roles and Permissions

```python
class Permission(Enum):
    # Project management
    DELETE_PROJECT = "delete_project"
    MANAGE_MEMBERS = "manage_members"
    
    # Configuration
    MANAGE_POLICIES = "manage_policies"
    MANAGE_AGENTS = "manage_agents"
    MANAGE_TOOLS = "manage_tools"
    
    # Execution
    RUN_EXECUTIONS = "run_executions"
    RUN_EVALUATIONS = "run_evaluations"
    
    # Approval
    APPROVE_ACTIONS = "approve_actions"
    
    # Read
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_AUDIT_LOGS = "view_audit_logs"

ROLE_PERMISSIONS = {
    "OWNER": {all permissions},
    "ADMIN": {all except DELETE_PROJECT},
    "DEVELOPER": {MANAGE_AGENTS, MANAGE_TOOLS, RUN_EXECUTIONS, RUN_EVALUATIONS, VIEW_*},
    "APPROVER": {APPROVE_ACTIONS, VIEW_*},
    "VIEWER": {VIEW_*},
}
```

### Separation of Duties

A critical security principle: the person who creates an action should not be the person who approves it.

- **Developers** can configure agents and run executions, but CANNOT approve high-risk actions
- **Approvers** can review and approve/reject actions, but CANNOT modify policies or run executions
- **Viewers** can observe everything but CANNOT modify or execute anything

### Enforcement

Permissions are checked via a **centralized permission system**, not scattered `if role == "ADMIN"` checks:

```python
# Centralized check - used everywhere
async def require_permission(user_id, project_id, permission, db):
    member = await get_project_member(user_id, project_id, db)
    if permission not in ROLE_PERMISSIONS[member.role]:
        raise ForbiddenError(f"Role {member.role} lacks {permission}")
```

---

## 5. Multi-Tenant Isolation

### How It Works

Every project-scoped query includes the project_id:

```python
# CORRECT - always filter by project_id
agents = await db.execute(
    select(Agent).where(
        Agent.project_id == verified_project_id
    )
)

# WRONG - trusting user input for project scope
agents = await db.execute(
    select(Agent).where(
        Agent.project_id == request.body.project_id  # NEVER DO THIS
    )
)
```

The `verified_project_id` comes from:
1. The URL path parameter (e.g., `/projects/{project_id}/agents`)
2. Cross-referenced with the authenticated user's project membership
3. The user's membership and role are verified in the database

### Database Enforcement

Foreign keys ensure referential integrity:
```sql
-- An agent must belong to a valid project
FOREIGN KEY (project_id) REFERENCES projects(id)

-- A tool assignment's agent and tool must exist
FOREIGN KEY (agent_id) REFERENCES agents(id)
FOREIGN KEY (tool_id) REFERENCES tool_definitions(id)
```

Composite uniqueness prevents duplicates within a project:
```sql
UNIQUE(project_id, name) ON agents
UNIQUE(project_id, name) ON tool_definitions
```

---

## 6. Policy Engine Security

### Deterministic Evaluation

The policy engine is **pure Python** — no database calls, no network calls, no randomness. Given the same inputs, it always produces the same output.

This matters because:
- It can be exhaustively unit tested
- Security decisions are predictable and explainable
- It doesn't depend on external services being available
- It can be audited without running the full application

### Short-Circuit Evaluation

Rules are evaluated in a strict order. The first rule that returns DENY stops evaluation immediately:

```
Input: Tool proposal

Step 1: Tool Permission → DENY? Stop. ALLOW? Continue.
Step 2: Tool Deny List  → DENY? Stop. ALLOW? Continue.
Step 3: Risk Ceiling    → DENY? Stop. ALLOW? Continue.
Step 4: Resource Owner  → DENY? Stop. ALLOW? Continue.
Step 5: Arg Constraints → DENY? Stop. ALLOW? Continue.
Step 6: Arg Patterns    → DENY? Stop. ALLOW? Continue.
Step 7: Approval Req.   → REQUIRES_APPROVAL? Stop.
Step 8: All passed      → ALLOW
```

A DENY from any rule is **final**. An approval requirement cannot override a denial.

### Why This Order?

1. **Permission first**: No point checking arguments if the tool isn't even assigned
2. **Deny list second**: Explicit denials are non-negotiable
3. **Risk ceiling third**: Quick check before expensive validation
4. **Ownership fourth**: Tenant isolation before argument parsing
5. **Constraints fifth**: Structural validation of arguments
6. **Patterns sixth**: Content-level checks for suspicious values
7. **Approval last**: Only reached if everything else passed

---

## 7. Approval Integrity

### The Problem

When a tool call requires approval, there's a time gap between when the action is proposed and when it's approved. During this gap, an attacker could potentially modify the action.

### The Solution: Cryptographic Action Binding

```
On Proposal:
  1. Take the tool arguments (JSON object)
  2. Canonicalize using RFC 8785 (JCS)
     - Deterministic key ordering
     - Deterministic number formatting
     - Deterministic string escaping
  3. SHA-256 hash the canonical form
  4. Store both the arguments AND the hash

On Approval + Execution:
  1. Retrieve the stored arguments
  2. Re-canonicalize them
  3. Re-hash
  4. Compare with stored hash
  5. If different → SECURITY VIOLATION, do not execute
```

### Why RFC 8785?

JSON doesn't guarantee key ordering. `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` are semantically identical but produce different hashes. RFC 8785 (JSON Canonicalization Scheme) defines a deterministic serialization that always produces the same bytes for semantically identical JSON.

### Single-Use Consumption

Approvals are consumed atomically using database transactions:

```python
# Atomic consumption - prevents double-use
result = await db.execute(
    update(ApprovalRequest)
    .where(
        ApprovalRequest.id == approval_id,
        ApprovalRequest.status == "APPROVED"  # Only if still APPROVED
    )
    .values(status="CONSUMED")
    .returning(ApprovalRequest.id)
)
if not result.scalar():
    raise SecurityError("Approval already consumed or not in APPROVED state")
```

The `WHERE status = 'APPROVED'` clause ensures that if two threads try to consume the same approval simultaneously, only one succeeds.

---

## 8. Tool Execution Security

### No Executable Code in Database

The database stores tool **metadata** only:
- Name, description, input schema, risk level

The database does NOT store:
- Python code
- Import paths
- Class names
- Shell commands
- Dynamic function references

### Whitelist Executor Catalog

Actual tool implementations are registered in a Python dictionary at application startup:

```python
TOOL_EXECUTORS = {
    "search_customer": search_customer_executor,
    "get_order_status": get_order_status_executor,
    "get_support_ticket": get_support_ticket_executor,
    # ... etc
}
```

If a tool name isn't in this dictionary, it cannot execute. Period.

### Synthetic Data Only

All tools operate on synthetic/mock data:
- Fake customers
- Fake orders
- Fake support tickets
- Fake refund calculations

No real external systems, databases, or APIs are connected.

---

## 9. What AgentGuard Does NOT Claim

Transparency about limitations:

1. **Regex patterns cannot reliably detect prompt injection.** AgentGuard's argument pattern rules are an additional defense layer, not a complete solution.

2. **The audit log is append-only in the application layer**, but we don't implement cryptographic tamper-evidence (like hash chains). A database admin with direct access could modify records.

3. **JWT tokens can be stolen** if the client-side storage is compromised. We mitigate with short expiration times and refresh token revocation.

4. **The mock AI provider is deterministic**, but real AI providers are not. Security guarantees hold because they're enforced deterministically, independent of AI behavior.

5. **Rate limiting and DDoS protection** are not implemented. These would be handled by a reverse proxy (nginx, Cloudflare) in production.
