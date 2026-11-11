"""Password check for the LAN-facing dashboard (pure; the Streamlit gate lives in the app)."""

from __future__ import annotations

import hmac


def verify_password(provided: str, expected: str) -> bool:
    """Constant-time comparison. An empty expected password never matches anything."""
    if not expected:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
