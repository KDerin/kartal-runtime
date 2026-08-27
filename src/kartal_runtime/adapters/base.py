from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class AdapterEvent:
    """Normalized event emitted by an external orchestration framework."""

    event_type: str
    run_id: str
    agent_id: str | None
    payload: Mapping[str, Any] = field(default_factory=dict)


class RuntimeAdapter(Protocol):
    """Contract for converting framework events into KARTAL artifacts."""

    name: str

    def ingest(self, event: AdapterEvent) -> None: ...
