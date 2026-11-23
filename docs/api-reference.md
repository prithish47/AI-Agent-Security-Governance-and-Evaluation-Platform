# AgentGuard — API Reference

## Base URL

```
http://localhost:8000/api/v1
```

All endpoints are prefixed with `/api/v1`. The OpenAPI/Swagger documentation is available at `http://localhost:8000/docs`.

---

## Authentication

All endpoints except `/auth/register`, `/auth/login`, `/auth/refresh`, and `/health` require a valid JWT access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

---

## Error Response Format

All errors follow a consistent format:

```json
{
  "detail": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Agent with ID abc-123 not found",
    "field": null
  }
}
```

For validation errors (422):
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Endpoints

### Health Check

#### `GET /health`
No authentication required.

**Response 200:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected"
}
```

---

### Authentication

#### `POST /api/v1/auth/register`
Create a new user account.

**Request Body:**
```json
{
  "email": "developer@example.com",
  "username": "developer",
  "password": "SecureP@ssw0rd!"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "email": "developer@example.com",
  "username": "developer",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Errors:** 409 (email/username already exists), 422 (validation error)

---

#### `POST /api/v1/auth/login`
Authenticate and receive tokens.

**Request Body:**
```json
{
  "email": "developer@example.com",
  "password": "SecureP@ssw0rd!"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:** 401 (invalid credentials)

---

#### `POST /api/v1/auth/refresh`
Get a new access token using a refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:** 401 (invalid/expired/revoked refresh token)

---

#### `POST /api/v1/auth/logout`
🔒 Authenticated. Revoke the refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response 200:**
```json
{
  "message": "Successfully logged out"
}
```

---

#### `GET /api/v1/auth/me`
🔒 Authenticated. Get current user information.

**Response 200:**
```json
{
  "id": "uuid",
  "email": "developer@example.com",
  "username": "developer",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### Projects

#### `GET /api/v1/projects`
🔒 Authenticated. List projects the user belongs to.

**Response 200:**
```json
[
  {
    "id": "uuid",
    "name": "Customer Support Bot",
    "description": "AI agent for handling customer support tickets",
    "role": "OWNER",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

#### `POST /api/v1/projects`
🔒 Authenticated. Create a new project. The creating user becomes OWNER.

**Request Body:**
```json
{
  "name": "Customer Support Bot",
  "description": "AI agent for handling customer support tickets"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "name": "Customer Support Bot",
  "description": "...",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

#### `GET /api/v1/projects/{project_id}`
🔒 Authenticated. Must be a member.

**Response 200:** Project details with member count and stats.

---

#### `PATCH /api/v1/projects/{project_id}`
🔒 Requires OWNER or ADMIN role.

**Request Body:**
```json
{
  "name": "Updated Name",
  "description": "Updated description"
}
```

---

#### `DELETE /api/v1/projects/{project_id}`
🔒 Requires OWNER role.

**Response 204:** No content.

---

#### `GET /api/v1/projects/{project_id}/members`
🔒 Requires project membership.

**Response 200:**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "username": "developer",
    "email": "developer@example.com",
    "role": "OWNER",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

#### `POST /api/v1/projects/{project_id}/members`
🔒 Requires OWNER or ADMIN role.

**Request Body:**
```json
{
  "email": "newmember@example.com",
  "role": "DEVELOPER"
}
```

---

### Agents

#### `GET /api/v1/projects/{project_id}/agents`
🔒 Requires project membership.

**Response 200:** List of agents in the project.

---

#### `POST /api/v1/projects/{project_id}/agents`
🔒 Requires DEVELOPER+ role.

**Request Body:**
```json
{
  "name": "Support Agent",
  "description": "Handles customer support queries",
  "system_prompt": "You are a helpful customer support agent...",
  "model_provider": "openai",
  "model_name": "gpt-4",
  "max_iterations": 10,
  "max_risk_level": "MEDIUM",
  "policy_id": "uuid or null"
}
```

---

#### `GET /api/v1/agents/{agent_id}`
🔒 Requires membership in the agent's project.

---

#### `PATCH /api/v1/agents/{agent_id}`
🔒 Requires DEVELOPER+ role.

---

#### `DELETE /api/v1/agents/{agent_id}`
🔒 Requires DEVELOPER+ role.

---

### Tools

#### `GET /api/v1/projects/{project_id}/tools`
🔒 Requires project membership.

**Response 200:**
```json
[
  {
    "id": "uuid",
    "name": "search_customer",
    "description": "Search for customers by name or email",
    "input_schema": {
      "type": "object",
      "properties": {
        "query": {"type": "string", "minLength": 1, "maxLength": 200}
      },
      "required": ["query"]
    },
    "risk_level": "LOW",
    "is_enabled": true,
    "is_executable": true,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

The `is_executable` field indicates whether a matching executor exists in the backend whitelist.

---

#### `POST /api/v1/projects/{project_id}/tools`
🔒 Requires DEVELOPER+ role. Registers tool metadata (not executable code).

**Request Body:**
```json
{
  "name": "search_customer",
  "description": "Search for customers by name or email",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"}
    },
    "required": ["query"]
  },
  "risk_level": "LOW"
}
```

---

#### `PATCH /api/v1/tools/{tool_id}`
🔒 Requires DEVELOPER+ role.

---

#### `DELETE /api/v1/tools/{tool_id}`
🔒 Requires DEVELOPER+ role.

---

### Agent-Tool Assignments

#### `POST /api/v1/agents/{agent_id}/tools`
🔒 Requires DEVELOPER+ role. Assign a tool to an agent.

**Request Body:**
```json
{
  "tool_id": "uuid"
}
```

---

#### `DELETE /api/v1/agents/{agent_id}/tools/{tool_id}`
🔒 Requires DEVELOPER+ role. Remove a tool assignment.

---

### Security Policies

#### `GET /api/v1/projects/{project_id}/policies`
🔒 Requires project membership.

---

#### `POST /api/v1/projects/{project_id}/policies`
🔒 Requires ADMIN+ role.

**Request Body:**
```json
{
  "name": "Production Security Policy",
  "description": "Enforced for all production agents",
  "rules": {
    "denied_tools": ["deleteDatabase", "exportAllCustomers"],
    "approval_required_tools": ["issue_refund"],
    "argument_patterns": [
      {
        "pattern": "(?i)(drop|delete|truncate)\\s+table",
        "description": "SQL injection attempt"
      }
    ],
    "max_argument_size_bytes": 10000,
    "max_array_size": 50
  }
}
```

This creates the policy AND its first version.

---

#### `GET /api/v1/policies/{policy_id}`
🔒 Requires project membership.

---

#### `POST /api/v1/policies/{policy_id}/versions`
🔒 Requires ADMIN+ role. Create a new policy version (does NOT modify existing versions).

**Request Body:**
```json
{
  "rules": {
    "denied_tools": ["deleteDatabase"],
    "approval_required_tools": ["issue_refund", "delete_customer"],
    "argument_patterns": [...]
  }
}
```

---

#### `GET /api/v1/policies/{policy_id}/versions`
🔒 Requires project membership. List all versions of a policy.

---

#### `POST /api/v1/policies/{policy_id}/activate`
🔒 Requires ADMIN+ role. Activate a specific version.

**Request Body:**
```json
{
  "version_id": "uuid"
}
```

---

### Execution

#### `POST /api/v1/agents/{agent_id}/execute`
🔒 Requires DEVELOPER+ role. Run an agent with a task prompt.

**Request Body:**
```json
{
  "task": "Find the support ticket for customer John Doe and check its status"
}
```

**Response 200:**
```json
{
  "execution_id": "uuid",
  "status": "COMPLETED",
  "final_response": "I found the support ticket...",
  "iteration_count": 3,
  "termination_reason": "COMPLETED",
  "started_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:00:05Z"
}
```

---

#### `GET /api/v1/executions/{execution_id}`
🔒 Requires membership in the execution's project.

---

#### `GET /api/v1/executions/{execution_id}/trace`
🔒 Requires membership in the execution's project.

**Response 200:**
```json
{
  "execution_id": "uuid",
  "steps": [
    {
      "step_number": 1,
      "step_type": "TOOL_CALL",
      "tool_name": "search_customer",
      "tool_arguments": {"query": "John Doe"},
      "policy_decision": "ALLOW",
      "policy_rule": null,
      "policy_reason": "All policy rules passed",
      "tool_result": {"customers": [...]},
      "policy_eval_ms": 0.5
    },
    {
      "step_number": 2,
      "step_type": "TOOL_CALL",
      "tool_name": "get_support_ticket",
      "tool_arguments": {"ticket_id": "TKT-001"},
      "policy_decision": "ALLOW",
      "policy_rule": null,
      "policy_reason": "All policy rules passed",
      "tool_result": {"status": "open", ...},
      "policy_eval_ms": 0.3
    },
    {
      "step_number": 3,
      "step_type": "FINAL_ANSWER",
      "model_response": "I found the support ticket..."
    }
  ]
}
```

---

### Approvals

#### `GET /api/v1/projects/{project_id}/approvals`
🔒 Requires APPROVER+ role.

**Query Parameters:** `status` (filter by PENDING/APPROVED/REJECTED/etc.)

---

#### `GET /api/v1/approvals/{approval_id}`
🔒 Requires membership in the approval's project.

---

#### `POST /api/v1/approvals/{approval_id}/approve`
🔒 Requires APPROVER+ role. Cannot approve own agent's actions if user is DEVELOPER.

**Request Body:**
```json
{
  "note": "Verified the refund amount is correct"
}
```

**Response 200:**
```json
{
  "id": "uuid",
  "status": "APPROVED",
  "reviewed_by": "uuid",
  "reviewed_at": "2024-01-01T00:01:00Z",
  "integrity_verified": true
}
```

---

#### `POST /api/v1/approvals/{approval_id}/reject`
🔒 Requires APPROVER+ role.

**Request Body:**
```json
{
  "note": "Refund amount exceeds policy limits"
}
```

---

### Evaluations

#### `GET /api/v1/projects/{project_id}/evaluations`
🔒 Requires project membership.

---

#### `POST /api/v1/projects/{project_id}/evaluations/run`
🔒 Requires DEVELOPER+ role.

**Request Body:**
```json
{
  "agent_id": "uuid",
  "suite_id": "uuid",
  "mode": "both"
}
```

`mode` can be `"baseline"`, `"protected"`, or `"both"`.

**Response 200:**
```json
{
  "run_id": "uuid",
  "status": "COMPLETED",
  "metrics": {
    "baseline": {
      "asr": 0.78,
      "uter": 0.61,
      "ltsr": 1.0,
      "fbr": 0.0,
      "policy_latency_p50_ms": null,
      "policy_latency_p95_ms": null,
      "policy_latency_max_ms": null
    },
    "protected": {
      "asr": 0.0,
      "uter": 0.0,
      "ltsr": 1.0,
      "fbr": 0.0,
      "policy_latency_p50_ms": 0.5,
      "policy_latency_p95_ms": 1.2,
      "policy_latency_max_ms": 2.1
    }
  }
}
```

---

#### `GET /api/v1/evaluations/{evaluation_id}`
🔒 Requires membership in the evaluation's project.

---

#### `GET /api/v1/evaluations/{evaluation_id}/results`
🔒 Requires membership in the evaluation's project.

Returns individual case results.

---

### Audit Logs

#### `GET /api/v1/projects/{project_id}/audit-logs`
🔒 Requires project membership.

**Query Parameters:**
- `event_type` — filter by event type
- `severity` — filter by severity (INFO, WARNING, ERROR, CRITICAL)
- `start_date` — filter events after this date
- `end_date` — filter events before this date
- `actor_id` — filter by actor
- `execution_id` — filter by execution
- `page` — pagination page number
- `page_size` — items per page (default: 50, max: 100)

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "event_type": "TOOL_DENIED",
      "severity": "WARNING",
      "actor_id": "uuid",
      "execution_id": "uuid",
      "metadata": {
        "tool_name": "deleteDatabase",
        "reason": "Tool is explicitly denied by policy",
        "rule": "tool_deny_rule"
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50
}
```

---

## HTTP Status Codes

| Code | Usage |
|---|---|
| 200 | Successful operation |
| 201 | Resource created |
| 204 | Successful deletion |
| 400 | Bad request / business logic error |
| 401 | Not authenticated |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (duplicate resource) |
| 422 | Validation error |
| 500 | Internal server error (no details exposed) |
