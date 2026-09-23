"""Régénère des aperçus PNG dans output/ à partir des JSON de tests/, avec le
rendu réel (src/renderer.py).

Sert à vérifier visuellement une modification du rendu : comparer le
résultat obtenu (output/<nom>.png) à l'image de référence du même nom dans
tests/ (voir tests/README.md). N'écrit jamais dans tests/, uniquement dans
output/.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import Settings
from src.models import NextPassagesResponse
from src.renderer import render, save_image
from src.state import AppState

TESTS_DIR = ROOT / "tests"
OUTPUT_DIR = ROOT / "output"


def render_one(json_path: Path, settings: Settings) -> Path:
    data = json.loads(json_path.read_text())
    response = NextPassagesResponse.from_dict(data)
    state = AppState()
    state.set_ok(response.displays, datetime.now(UTC))

    # On rend l'image à la date "generatedAt" du fixture (et non à l'heure
    # réelle) : les "expectedAt" sont écrits en dur en relatif à cette date
    # (ex: +4 min), donc le rendu reste stable indéfiniment sans dépendre de
    # la date à laquelle ce script est exécuté.
    output_path = OUTPUT_DIR / f"{json_path.stem}.png"
    save_image(render(state, settings, now=response.generated_at), str(output_path))
    return output_path


def main() -> None:
    settings = Settings.load()
    json_files = sorted(TESTS_DIR.glob("*.json"))
    for json_path in json_files:
        output_path = render_one(json_path, settings)
        print(f"{json_path.name} -> {output_path} (référence : tests/{json_path.stem}.png)")


if __name__ == "__main__":
    main()
