from __future__ import annotations

import os
from typing import Any


POLICY_TEXT = r'''
permit (
    principal == User::"investigator",
    action in [Action::"read", Action::"investigate", Action::"export"],
    resource
);

permit (
    principal == User::"reviewer",
    action in [Action::"read", Action::"investigate", Action::"export", Action::"review_identity"],
    resource
);

forbid (
    principal == Agent::"safesku",
    action == Action::"review_identity",
    resource
);
'''.strip()


def build_it_enabled() -> bool:
    return os.getenv("SAFE_SKU_BUILD_IT", "false").lower() == "true"


def stack_status() -> dict[str, Any]:
    return {
        "track": "build_it",
        "agent": os.getenv("SAFE_SKU_AGENT_MODE", "local"),
        "search": os.getenv("SAFE_SKU_SEARCH_MODE", "sqlite"),
        "policy": "cedar",
        "sam_local": True,
    }


def authorize(action: str, *, role: str | None = None, resource_id: str = "workspace") -> dict[str, Any]:
    """Authorize one SafeSKU application action with the local Cedar engine.

    The application keeps policy decisions separate from business logic. In the
    Build It track, this is a local policy decision with no AWS account required.
    """
    try:
        from cedarpy import Decision, is_authorized
    except Exception as exc:  # pragma: no cover - installation failure path
        raise RuntimeError("Cedar runtime is not installed. Run: pip install cedarpy") from exc

    principal_role = (role or os.getenv("SAFE_SKU_ROLE", "reviewer")).strip().lower()
    principal_type = "Agent" if principal_role == "agent" else "User"
    request = {
        "principal": f'{principal_type}::"{principal_role}"',
        "action": f'Action::"{action}"',
        "resource": f'Investigation::"{resource_id}"',
        "context": {},
    }
    result = is_authorized(request, POLICY_TEXT, [])
    allowed = result.decision == Decision.Allow
    return {
        "allowed": allowed,
        "decision": str(result.decision),
        "principal": request["principal"],
        "action": request["action"],
        "resource": request["resource"],
        "policy_engine": "cedar",
    }
