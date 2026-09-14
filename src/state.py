"""État applicatif partagé entre le thread de fetch et le thread de rendu."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from .models import DisplayItem


class Status(Enum):
    OK = "ok"                # dernière réponse valide, avec ou sans displays
    INVALID_TOKEN = "invalid_token"  # 401, et jamais eu de réponse valide avant
    ERROR = "error"          # autre erreur, et jamais eu de réponse valide avant


@dataclass
class AppState:
    """
    Règle appliquée: si un appel échoue mais qu'on a déjà des données valides
    en mémoire, on les garde (on log l'erreur mais on ne casse pas l'affichage).
    Les statuts INVALID_TOKEN / ERROR ne s'affichent que si on n'a JAMAIS eu
    de données valides.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    status: Status = Status.OK
    displays: List[DisplayItem] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    display_index: int = 0

    def set_ok(self, displays: List[DisplayItem], when: datetime) -> None:
        with self._lock:
            self.status = Status.OK
            self.displays = displays
            self.last_updated = when
            if self.display_index >= len(displays):
                self.display_index = 0

    def set_error(self, status: Status) -> None:
        """N'écrase les données que si on n'a jamais eu de displays valides."""
        with self._lock:
            if not self.displays:
                self.status = status

    def next_display(self) -> Optional[DisplayItem]:
        """Round-robin: renvoie le DisplayItem courant puis avance l'index."""
        with self._lock:
            if not self.displays:
                return None
            item = self.displays[self.display_index % len(self.displays)]
            self.display_index = (self.display_index + 1) % len(self.displays)
            return item

    def snapshot_status(self) -> Status:
        with self._lock:
            return self.status
