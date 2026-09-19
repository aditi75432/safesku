// SafeSKU Build It authorization model.
// The agent is intentionally read-only. Human identity decisions stay human-owned.

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
