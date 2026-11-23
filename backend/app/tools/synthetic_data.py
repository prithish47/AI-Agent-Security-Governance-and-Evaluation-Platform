# =============================================================================
# AgentGuard — Synthetic Environment Data
# =============================================================================
# Mock database for safe, controlled tool execution.
# Protects production systems: no real external systems or databases are connected.
# =============================================================================

from typing import Any, Dict, List, Optional

SYNTHETIC_CUSTOMERS: List[Dict[str, Any]] = [
    {
        "id": "CUST-1001",
        "name": "Alice Johnson",
        "email": "alice.johnson@example.com",
        "tier": "enterprise",
        "account_balance": 1540.50,
        "created_at": "2024-01-15T08:30:00Z",
    },
    {
        "id": "CUST-1002",
        "name": "Bob Smith",
        "email": "bob.smith@example.com",
        "tier": "standard",
        "account_balance": 45.00,
        "created_at": "2024-02-20T11:15:00Z",
    },
    {
        "id": "CUST-1003",
        "name": "Charlie Davis",
        "email": "charlie.davis@example.com",
        "tier": "premium",
        "account_balance": 320.00,
        "created_at": "2024-03-01T14:45:00Z",
    },
]

SYNTHETIC_TICKETS: List[Dict[str, Any]] = [
    {
        "id": "TKT-5001",
        "customer_id": "CUST-1001",
        "title": "Payment gateway timeout",
        "status": "OPEN",
        "priority": "HIGH",
        "description": "Customer reported billing charge did not return success receipt.",
    },
    {
        "id": "TKT-5002",
        "customer_id": "CUST-1002",
        "title": "Password reset inquiry",
        "status": "RESOLVED",
        "priority": "LOW",
        "description": "User requested self-service password reset instructions.",
    },
]

SYNTHETIC_ORDERS: List[Dict[str, Any]] = [
    {
        "id": "ORD-9001",
        "customer_id": "CUST-1001",
        "amount": 250.00,
        "status": "DELIVERED",
        "item": "Enterprise AI Security License",
        "eligible_for_refund": True,
    },
    {
        "id": "ORD-9002",
        "customer_id": "CUST-1002",
        "amount": 45.00,
        "status": "SHIPPED",
        "item": "Hardware Key",
        "eligible_for_refund": False,
    },
]

SYNTHETIC_KNOWLEDGE_BASE: List[Dict[str, str]] = [
    {
        "topic": "refund_policy",
        "content": "Refunds are processed within 5-7 business days for eligible delivered items up to 30 days after purchase.",
    },
    {
        "topic": "api_rate_limits",
        "content": "Standard API tiers permit 100 requests per minute; enterprise tiers permit 5000 requests per minute.",
    },
]
