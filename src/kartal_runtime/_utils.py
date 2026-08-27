from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with an explicit Z suffix."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically for hashing and persistence."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def ensure_jsonable(value: Any, *, label: str = "value") -> None:
    try:
        canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must contain only JSON-serializable values") from exc
