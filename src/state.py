"""État applicatif partagé entre le thread de fetch et le thread de rendu."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .models import DisplayItem


class Status(Enum):
    OK = "ok"  # dernière réponse valide, avec ou sans displays
    INVALID_TOKEN = "invalid_token"  # 401, et jamais eu de réponse valide avant
    ERROR = "error"  # autre erreur, et jamais eu de réponse valide avant


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
    displays: list[DisplayItem] = field(default_factory=list)
    last_updated: datetime | None = None
    display_index: int = 0
    has_api_error: bool = False
    """Reflète le dernier appel API (échec ou non), même quand on continue
    d'afficher des données valides précédemment reçues (voir `set_error`).
    Sert uniquement à signaler un souci de connectivité (pictogramme), sans
    jamais déclencher l'écran d'erreur plein écran."""

    def set_ok(self, displays: list[DisplayItem], when: datetime) -> None:
        with self._lock:
            self.status = Status.OK
            self.displays = displays
            self.last_updated = when
            self.has_api_error = False
            if self.display_index >= len(displays):
                self.display_index = 0

    def set_error(self, status: Status) -> None:
        """N'écrase les données que si on n'a jamais eu de displays valides."""
        with self._lock:
            self.has_api_error = True
            if not self.displays:
                self.status = status

    def next_display(self) -> DisplayItem | None:
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

    def snapshot_has_api_error(self) -> bool:
        with self._lock:
            return self.has_api_error
