# =============================================================================
# AgentGuard — RFC 8785 JSON Canonicalization & Action Hash Binding
# =============================================================================
# Implements cryptographic action binding:
# 1. RFC 8785 JSON Canonicalization Scheme (JCS)
#    - UTF-16 code-unit object key ordering (Section 3.2.3)
#    - ECMA-262 Number serialization (Section 3.2.2.3)
#    - Strict control-character escaping & UTF-8 validation (Section 3.2.2.2)
#    - Rejection of NaN, Infinity, lone surrogates, and non-JSON types
# 2. SHA-256 hashing over full immutable execution binding
# =============================================================================

import hashlib
import hmac
import math
import uuid
from typing import Any, Dict


def _format_ecma_number(value: float) -> str:
    """
    Format an IEEE 754 float according to ECMA-262 Section 7.1.12.1 (RFC 8785 §3.2.2.3).
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError("RFC 8785 does not allow NaN or Infinity values")
    if value == 0.0:
        return "0"

    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    raw = repr(abs_val)

    # Parse shortest round-trip decimal representation into (digits, exponent)
    if "e" in raw or "E" in raw:
        mantissa_str, exp_str = raw.lower().split("e")
        exp_offset = int(exp_str)
    else:
        mantissa_str = raw
        exp_offset = 0

    if "." in mantissa_str:
        int_part, frac_part = mantissa_str.split(".")
        digits = int_part + frac_part
        n = len(int_part) + exp_offset
    else:
        digits = mantissa_str
        n = len(digits) + exp_offset

    # Strip leading zeros (e.g. 0.00123 -> digits="123", adjust n)
    stripped_leading = digits.lstrip("0")
    n -= len(digits) - len(stripped_leading)
    # Strip trailing zeros
    s = stripped_leading.rstrip("0")
    k = len(s)

    if k <= n <= 21:
        return sign + s + ("0" * (n - k))
    if 0 < n <= 21:
        return sign + s[:n] + "." + s[n:]
    if -6 < n <= 0:
        return sign + "0." + ("0" * (-n)) + s

    exp = n - 1
    exp_sign = "+" if exp > 0 else "-"
    if k == 1:
        return f"{sign}{s}e{exp_sign}{abs(exp)}"
    return f"{sign}{s[0]}.{s[1:]}e{exp_sign}{abs(exp)}"


def _escape_rfc8785_string(value: str) -> str:
    """Serialize a JSON string per RFC 8785 §3.2.2.2 and validate UTF-8."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("String contains invalid Unicode lone surrogates") from exc

    out = ['"']
    for ch in value:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif code == 0x08:
            out.append("\\b")
        elif code == 0x09:
            out.append("\\t")
        elif code == 0x0A:
            out.append("\\n")
        elif code == 0x0C:
            out.append("\\f")
        elif code == 0x0D:
            out.append("\\r")
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _serialize_jcs(value: Any) -> str:
    """Recursively serialize any valid JSON value to an RFC 8785 JCS string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _format_ecma_number(value)
    if isinstance(value, str):
        return _escape_rfc8785_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize_jcs(item) for item in value) + "]"
    if isinstance(value, dict):
        items = []
        for k in value.keys():
            if not isinstance(k, str):
                raise ValueError(f"RFC 8785 object keys must be strings, got {type(k).__name__}")
            try:
                utf16_key = k.encode("utf-16-be")
            except UnicodeEncodeError as exc:
                raise ValueError("Object key contains invalid Unicode lone surrogates") from exc
            items.append((utf16_key, k, value[k]))
        items.sort(key=lambda entry: entry[0])
        serialized_pairs = [
            f"{_escape_rfc8785_string(k)}:{_serialize_jcs(v)}"
            for _, k, v in items
        ]
        return "{" + ",".join(serialized_pairs) + "}"

    raise ValueError(f"Unsupported type for RFC 8785 canonicalization: {type(value).__name__}")


def canonicalize_json(data: Any) -> bytes:
    """
    Produce RFC 8785 canonical JSON UTF-8 bytes.
    Ensures UTF-16 code-unit key sorting, ECMA-262 number formatting,
    and strict escaping/validation.
    """
    return _serialize_jcs(data).encode("utf-8")


def build_action_binding_payload(
    *,
    project_id: uuid.UUID | str,
    agent_id: uuid.UUID | str,
    execution_id: uuid.UUID | str,
    tool_name: str,
    arguments: Dict[str, Any],
    policy_version: int,
    agent_risk_ceiling: str,
) -> Dict[str, Any]:
    """
    Construct the canonical immutable action binding payload.
    All fields are persisted on ApprovalRequest/Execution so verification is
    fully reproducible at review and consumption time.
    """
    return {
        "binding_version": 1,
        "project_id": str(project_id),
        "agent_id": str(agent_id),
        "execution_id": str(execution_id),
        "tool_name": tool_name,
        "tool_arguments": arguments,
        "policy_version": int(policy_version),
        "agent_risk_ceiling": str(agent_risk_ceiling),
    }


def compute_action_hash(
    *,
    project_id: uuid.UUID | str,
    agent_id: uuid.UUID | str,
    execution_id: uuid.UUID | str,
    tool_name: str,
    arguments: Dict[str, Any],
    policy_version: int,
    agent_risk_ceiling: str,
) -> str:
    """Compute SHA-256 hex digest of the RFC 8785 canonical action binding."""
    payload = build_action_binding_payload(
        project_id=project_id,
        agent_id=agent_id,
        execution_id=execution_id,
        tool_name=tool_name,
        arguments=arguments,
        policy_version=policy_version,
        agent_risk_ceiling=agent_risk_ceiling,
    )
    canonical_bytes = canonicalize_json(payload)
    return hashlib.sha256(canonical_bytes).hexdigest()


def verify_action_hash(
    *,
    project_id: uuid.UUID | str,
    agent_id: uuid.UUID | str,
    execution_id: uuid.UUID | str,
    tool_name: str,
    arguments: Dict[str, Any],
    policy_version: int,
    agent_risk_ceiling: str,
    expected_hash: str,
) -> bool:
    """
    Recompute action hash from full bound context and verify in constant time.
    """
    if not expected_hash:
        return False
    try:
        computed = compute_action_hash(
            project_id=project_id,
            agent_id=agent_id,
            execution_id=execution_id,
            tool_name=tool_name,
            arguments=arguments,
            policy_version=policy_version,
            agent_risk_ceiling=agent_risk_ceiling,
        )
    except ValueError:
        return False
    return hmac.compare_digest(computed, expected_hash)
