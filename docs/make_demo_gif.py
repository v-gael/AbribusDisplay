"""Génère docs/demo.gif (aperçu animé affiché en haut du README) à partir de
docs/demo.json, avec le rendu réel (src/renderer.py).

Une frame par élément de `displays`, dans l'ordre du round-robin : à
relancer (`make demo-gif`) après une modification visible du rendu, pour que
le README reste fidèle.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Settings
from src.models import NextPassagesResponse
from src.renderer import render
from src.state import AppState

DOCS_DIR = ROOT / "docs"
FRAME_DURATION_MS = 3000


def main() -> None:
    settings = Settings.load()
    response = NextPassagesResponse.from_dict(json.loads((DOCS_DIR / "demo.json").read_text()))
    state = AppState()
    state.set_ok(response.displays, datetime.now(UTC))

    # Rendu à la date "generatedAt" du JSON (comme tests/render_example.py) :
    # les minutes affichées restent stables quel que soit le jour d'exécution.
    # Convertie dans DISPLAY_TIMEZONE pour que l'heure du bandeau soit celle
    # qu'afficherait réellement le panneau (generatedAt est en UTC).
    now = response.generated_at.astimezone(ZoneInfo(settings.display_timezone))
    frames = [render(state, settings, now=now) for _ in response.displays]

    output_path = DOCS_DIR / "demo.gif"
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
    )
    print(f"{len(frames)} frames -> {output_path}")


if __name__ == "__main__":
    main()
