# =============================================================================
# AgentGuard — Precompiled Tool Catalog & Whitelist
# =============================================================================
# CRITICAL RESTRICTION:
# Database tool definitions NEVER contain executable Python code or arbitrary scripts.
# All actual executable tool implementations exist exclusively in this precompiled catalog.
# No eval, no exec, no dynamic imports, no unrestricted shell commands.
# =============================================================================

from typing import Any, Callable, Dict, List, Optional
from app.tools.synthetic_data import (
    SYNTHETIC_CUSTOMERS,
    SYNTHETIC_TICKETS,
    SYNTHETIC_ORDERS,
    SYNTHETIC_KNOWLEDGE_BASE,
)


def search_customer_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search synthetic customers by name or email query."""
    query = str(args.get("query", "")).lower().strip()
    if not query:
        return {"customers": [], "count": 0, "message": "Empty query provided"}

    matches = [
        c for c in SYNTHETIC_CUSTOMERS
        if query in c["name"].lower() or query in c["email"].lower()
    ]
    return {"customers": matches, "count": len(matches)}


def get_customer_details_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve full details for a customer ID."""
    cust_id = str(args.get("customer_id", "")).strip()
    for c in SYNTHETIC_CUSTOMERS:
        if c["id"] == cust_id:
            return {"customer": c, "found": True}
    return {"customer": None, "found": False, "message": f"Customer '{cust_id}' not found"}


def get_support_ticket_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """Lookup a support ticket by ticket ID."""
    ticket_id = str(args.get("ticket_id", "")).strip()
    for t in SYNTHETIC_TICKETS:
        if t["id"] == ticket_id:
            return {"ticket": t, "found": True}
    return {"ticket": None, "found": False, "message": f"Ticket '{ticket_id}' not found"}


def update_ticket_status_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update support ticket status."""
    ticket_id = str(args.get("ticket_id", "")).strip()
    new_status = str(args.get("status", "")).upper().strip()

    valid_statuses = {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}
    if new_status not in valid_statuses:
        return {"success": False, "message": f"Invalid ticket status: '{new_status}'"}

    for t in SYNTHETIC_TICKETS:
        if t["id"] == ticket_id:
            t["status"] = new_status
            return {"success": True, "ticket_id": ticket_id, "updated_status": new_status}
    return {"success": False, "message": f"Ticket '{ticket_id}' not found"}


def get_order_status_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """Lookup order status by order ID."""
    order_id = str(args.get("order_id", "")).strip()
    for o in SYNTHETIC_ORDERS:
        if o["id"] == order_id:
            return {"order": o, "found": True}
    return {"order": None, "found": False, "message": f"Order '{order_id}' not found"}


def calculate_refund_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate eligible refund for an order without issuing funds."""
    order_id = str(args.get("order_id", "")).strip()
    for o in SYNTHETIC_ORDERS:
        if o["id"] == order_id:
            if not o.get("eligible_for_refund", False):
                return {"order_id": order_id, "eligible": False, "calculated_refund": 0.0, "reason": "Order past return window"}
            return {"order_id": order_id, "eligible": True, "calculated_refund": o["amount"], "tax_refund": 0.0}
    return {"order_id": order_id, "eligible": False, "message": f"Order '{order_id}' not found"}


def issue_refund_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Issue financial refund (HIGH RISK - Requires Human Approval).
    Operates strictly on synthetic accounts.
    """
    order_id = str(args.get("order_id", "")).strip()
    amount = float(args.get("amount", 0.0))

    if amount <= 0:
        return {"success": False, "message": "Refund amount must be greater than zero"}

    for o in SYNTHETIC_ORDERS:
        if o["id"] == order_id:
            return {
                "success": True,
                "order_id": order_id,
                "refunded_amount": amount,
                "transaction_ref": "SYNTH-REFUND-TX-8829",
                "message": f"Successfully issued synthetic refund of ${amount:.2f}",
            }
    return {"success": False, "message": f"Order '{order_id}' not found"}


def search_knowledge_base_executor(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search synthetic internal knowledge base articles."""
    query = str(args.get("query", "")).lower().strip()
    matches = [
        kb for kb in SYNTHETIC_KNOWLEDGE_BASE
        if query in kb["topic"].lower() or query in kb["content"].lower()
    ]
    return {"articles": matches, "count": len(matches)}


# =============================================================================
# REGISTERED EXECUTOR CATALOG WHITELIST
# =============================================================================
TOOL_CATALOG: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "search_customer": search_customer_executor,
    "get_customer_details": get_customer_details_executor,
    "get_support_ticket": get_support_ticket_executor,
    "update_ticket_status": update_ticket_status_executor,
    "get_order_status": get_order_status_executor,
    "calculate_refund": calculate_refund_executor,
    "issue_refund": issue_refund_executor,
    "search_knowledge_base": search_knowledge_base_executor,
}


def get_executor(tool_name: str) -> Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]:
    """Lookup safe executor in precompiled whitelist. Returns None if unwhitelisted."""
    return TOOL_CATALOG.get(tool_name)
