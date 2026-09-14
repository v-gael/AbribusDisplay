"""Modèles de données correspondant au JSON renvoyé par l'API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


def _parse_datetime(value: str) -> datetime:
    # Le format ISO 8601 renvoyé contient un offset, ex: 2026-09-14T12:05:15+00:00
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class NextPassage:
    route_short_name: str
    route_color: Optional[str]  # hex sans '#', ex "F29400"
    route_text_color: Optional[str]
    headsign: str
    expected_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> "NextPassage":
        return cls(
            route_short_name=data["routeShortName"],
            route_color=data.get("routeColor") or None,
            route_text_color=data.get("routeTextColor") or None,
            headsign=data["headsign"],
            expected_at=_parse_datetime(data["expectedAt"]),
        )

    def minutes_until(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        delta = self.expected_at - now
        minutes = int(delta.total_seconds() // 60)
        return max(minutes, 0)


@dataclass(frozen=True)
class DisplayItem:
    label: str
    quay_name: str
    next_passages: List[NextPassage]

    @classmethod
    def from_dict(cls, data: dict) -> "DisplayItem":
        return cls(
            label=data.get("label", ""),
            quay_name=data.get("quayName", ""),
            next_passages=[NextPassage.from_dict(p) for p in data.get("nextPassages", [])],
        )

    @property
    def is_empty(self) -> bool:
        return len(self.next_passages) == 0


@dataclass(frozen=True)
class NextPassagesResponse:
    generated_at: datetime
    displays: List[DisplayItem]

    @classmethod
    def from_dict(cls, data: dict) -> "NextPassagesResponse":
        return cls(
            generated_at=_parse_datetime(data["generatedAt"]),
            displays=[DisplayItem.from_dict(d) for d in data.get("displays", [])],
        )
