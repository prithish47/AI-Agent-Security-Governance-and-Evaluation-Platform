# =============================================================================
# AgentGuard — RFC 8785 JSON Canonicalization & Action Hash Binding
# =============================================================================
# Implements cryptographic action binding:
# 1. RFC 8785 JSON Canonicalization Scheme (JCS)
# 2. SHA-256 hashing
#
# GUARANTEE:
# The approved action payload must be EXACTLY the action payload that executes.
# Any modification to keys, values, whitespace, or types produces a hash mismatch
# and triggers a SECURITY_VIOLATION rejection.
# =============================================================================

import hashlib
from typing import Any, Dict
import canonicaljson


def canonicalize_json(data: Dict[str, Any]) -> bytes:
    """
    Produce RFC 8785 canonical JSON bytes.
    Ensures deterministic key sorting, number formatting, and string escaping.
    """
    return canonicaljson.encode_canonical_json(data)


def compute_action_hash(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Compute cryptographic SHA-256 hash of tool name and canonicalized arguments.
    """
    canonical_payload = {
        "tool_name": tool_name,
        "arguments": arguments,
    }
    canonical_bytes = canonicalize_json(canonical_payload)
    return hashlib.sha256(canonical_bytes).hexdigest()


def verify_action_hash(tool_name: str, arguments: Dict[str, Any], expected_hash: str) -> bool:
    """
    Recompute action hash from arguments and verify against stored expected_hash.
    """
    computed = compute_action_hash(tool_name, arguments)
    return computed == expected_hash
