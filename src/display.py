"""Abstraction de l'affichage final : fbi sur le framebuffer du Pi, ou simple fichier en dev."""

from __future__ import annotations

import abc
import contextlib
import logging
import os
import signal
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class Display(abc.ABC):
    def start(self) -> None:
        """Appelé une fois au démarrage, avant la première image générée."""

    def refresh(self) -> None:
        """Appelé après chaque nouvelle image écrite sur disque."""

    def stop(self) -> None:
        """Appelé à l'arrêt de l'application."""


class FileDisplay(Display):
    """Mode développement (Mac/Linux) : l'image est simplement écrite sur disque.

    Utile pendant le dev : ouvrez le fichier avec la visionneuse de votre choix,
    ou un watcher qui recharge automatiquement l'image à chaque modification.
    """

    def __init__(self, output_path: str) -> None:
        self._output_path = output_path

    def refresh(self) -> None:
        logger.debug("Image régénérée: %s", self._output_path)


def _kill_running_fbi() -> None:
    """Tue toute instance fbi déjà présente.

    `fbi -T` se fork-daemonise (fork + setsid) pour prendre le contrôle de la
    console : le process qu'on lance avec Popen sort immédiatement (code 0),
    et c'est un petit-fils détaché - non rattaché à ce process Python - qui
    fait le travail réel. On ne peut donc pas le suivre via le PID de Popen ;
    sans ce nettoyage, chaque redémarrage laisserait l'ancienne instance
    tourner indéfiniment en arrière-plan (fuite de process).
    """
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            with open(f"/proc/{entry.name}/comm") as f:
                if f.read().strip() != "fbi":
                    continue
        except OSError:
            continue
        with contextlib.suppress(ProcessLookupError):
            os.kill(int(entry.name), signal.SIGKILL)

    # Ce process est le PID 1 du conteneur : les orphelins tués ci-dessus lui
    # sont réattachés et resteraient zombies (jamais réclamés) sans ce reap
    # explicite, faute d'init pour s'en charger à sa place.
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid == 0:
            break


class FbiDisplay(Display):
    """Mode production (Raspberry Pi) : pilote `fbi` sur le framebuffer.

    `fbi` est lancé une seule fois en tâche de fond ; à chaque nouvelle image,
    on lui envoie SIGUSR1 pour qu'il recharge le fichier sans clignoter/relancer.
    """

    def __init__(self, output_path: str, framebuffer_device: str) -> None:
        self._output_path = Path(output_path)
        self._device = framebuffer_device
        self._process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        # fbi a besoin d'un fichier existant pour démarrer
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._output_path.exists():
            self._output_path.touch()

        _kill_running_fbi()
        self._process = subprocess.Popen(
            [
                "fbi",
                "-d",
                self._device,
                "-T",
                "1",
                "-noverbose",
                "-a",
                str(self._output_path),
            ],
        )
        logger.info("fbi démarré (pid=%s) sur %s", self._process.pid, self._device)

    def refresh(self) -> None:
        if self._process is None or self._process.poll() is not None:
            logger.warning("fbi n'est pas actif, tentative de redémarrage")
            self.start()
            return
        try:
            os.kill(self._process.pid, signal.SIGUSR1)
        except ProcessLookupError:
            logger.warning("Process fbi introuvable, redémarrage")
            self.start()

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
        _kill_running_fbi()


def build_display(mode: str, output_path: str, framebuffer_device: str) -> Display:
    if mode == "fbi":
        return FbiDisplay(output_path, framebuffer_device)
    if mode == "file":
        return FileDisplay(output_path)
    raise ValueError(f"DISPLAY_MODE inconnu: {mode!r} (attendu: 'fbi' ou 'file')")
