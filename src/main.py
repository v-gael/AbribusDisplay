"""Point d'entrée: démarre le thread de récupération des données et le thread de rendu."""
from __future__ import annotations

import logging
import signal
import threading
import time
from datetime import datetime, timezone

from .api_client import ApiError, InvalidTokenError, fetch_next_passages
from .config import Settings
from .display import build_display
from .renderer import render, save_image
from .state import AppState, Status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AbribusDisplay")

_stop_event = threading.Event()


def _fetch_loop(settings: Settings, state: AppState) -> None:
    while not _stop_event.is_set():
        try:
            response = fetch_next_passages(
                settings.api_url, settings.token, verify_ssl=settings.api_verify_ssl
            )
            state.set_ok(response.displays, datetime.now(timezone.utc))
            logger.info("Données mises à jour (%d affichage(s))", len(response.displays))
        except InvalidTokenError:
            logger.error("Token invalide (401)")
            state.set_error(Status.INVALID_TOKEN)
        except ApiError as exc:
            logger.error("Erreur API: %s", exc)
            state.set_error(Status.ERROR)
        _stop_event.wait(settings.call_rate)


def _render_loop(settings: Settings, state: AppState) -> None:
    display = build_display(settings.display_mode, settings.output_path, settings.framebuffer_device)
    display.start()
    try:
        while not _stop_event.is_set():
            image = render(state, settings)
            save_image(image, settings.output_path)
            display.refresh()
            _stop_event.wait(settings.refresh_rate)
    finally:
        display.stop()


def _handle_signal(signum, frame) -> None:  # noqa: ANN001
    logger.info("Signal %s reçu, arrêt en cours...", signum)
    _stop_event.set()


def main() -> None:
    settings = Settings.load()
    state = AppState()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    fetch_thread = threading.Thread(target=_fetch_loop, args=(settings, state), name="fetcher", daemon=True)
    render_thread = threading.Thread(target=_render_loop, args=(settings, state), name="renderer", daemon=True)

    # Premier fetch synchrone pour ne pas afficher un écran vide au démarrage
    try:
        response = fetch_next_passages(
            settings.api_url, settings.token, verify_ssl=settings.api_verify_ssl
        )
        state.set_ok(response.displays, datetime.now(timezone.utc))
    except InvalidTokenError:
        state.set_error(Status.INVALID_TOKEN)
    except ApiError as exc:
        logger.error("Erreur API au démarrage: %s", exc)
        state.set_error(Status.ERROR)

    fetch_thread.start()
    render_thread.start()

    while not _stop_event.is_set():
        time.sleep(0.5)

    fetch_thread.join(timeout=2)
    render_thread.join(timeout=2)
    logger.info("Arrêt propre terminé")


if __name__ == "__main__":
    main()
