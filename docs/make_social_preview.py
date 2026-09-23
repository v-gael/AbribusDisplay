"""Génère docs/social-preview.png (1280×640), l'image d'aperçu affichée
quand le lien du dépôt est partagé (LinkedIn, mail, messagerie...).

À envoyer à la main dans GitHub (Settings → General → Social preview) : il
n'y a pas d'API pour ça. Utilise le rendu réel (première frame de
docs/demo.json) et les couleurs du panneau (Settings), pour rester fidèle
au projet si l'un ou l'autre change.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from src.config import Settings
from src.models import NextPassagesResponse
from src.renderer import render
from src.state import AppState

DOCS_DIR = ROOT / "docs"
FONT_PATH = ROOT / "assets" / "fonts" / "RobotoCondensed-Bold.ttf"
WIDTH, HEIGHT = 1280, 640
# Marge de sécurité recommandée par GitHub (bords parfois rognés à l'affichage)
MARGIN = 72


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size)


def main() -> None:
    settings = Settings.load()
    response = NextPassagesResponse.from_dict(json.loads((DOCS_DIR / "demo.json").read_text()))
    state = AppState()
    state.set_ok(response.displays, datetime.now(UTC))
    now = response.generated_at.astimezone(ZoneInfo(settings.display_timezone))
    panel = render(state, settings, now=now)

    image = Image.new("RGB", (WIDTH, HEIGHT), settings.background_color)
    draw = ImageDraw.Draw(image)

    # Panneau à droite, agrandi, avec un liseré couleur d'en-tête façon écran
    scale = 1.25
    panel = panel.resize((int(panel.width * scale), int(panel.height * scale)), Image.Resampling.LANCZOS)
    border = 10
    panel_x = WIDTH - MARGIN - panel.width
    panel_y = (HEIGHT - panel.height) // 2
    draw.rounded_rectangle(
        (panel_x - border, panel_y - border, panel_x + panel.width + border, panel_y + panel.height + border),
        radius=18,
        fill=settings.header_background_color,
    )
    image.paste(panel, (panel_x, panel_y))

    # Texte à gauche
    text_x = MARGIN
    draw.text((text_x, 190), "AbribusDisplay", font=_font(64), fill=settings.text_stop_color)
    subtitle = ["Panneau « prochains passages »", "de bus sur Raspberry Pi"]
    for i, line in enumerate(subtitle):
        draw.text((text_x, 290 + i * 46), line, font=_font(36), fill=settings.text_header_color)
    draw.text(
        (text_x, 420),
        "Python · Pillow · Docker · Raspberry Pi",
        font=_font(26),
        fill=settings.text_direction_color,
    )

    output_path = DOCS_DIR / "social-preview.png"
    image.save(output_path)
    print(f"{WIDTH}x{HEIGHT} -> {output_path}")


if __name__ == "__main__":
    main()
