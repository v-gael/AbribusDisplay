"""Chargement de la configuration depuis .env (versionné, valeurs par défaut)
puis .env.local (non versionné, surcharge — TOKEN, API_URL, etc.)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv

RootColor = Tuple[int, int, int]


def _hex_to_rgb(value: str) -> RootColor:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Couleur hexadécimale invalide: {value!r}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _load_env_files() -> None:
    root = Path(__file__).resolve().parent.parent
    # .env : versionné, valeurs par défaut — ne pas y mettre de secret
    load_dotenv(root / ".env", override=False)
    # .env.local : non versionné, surcharge (TOKEN, API_URL, etc.)
    load_dotenv(root / ".env.local", override=True)


@dataclass(frozen=True)
class Settings:
    # Couleurs
    text_stop_color: RootColor
    text_hour_color: RootColor
    text_header_color: RootColor
    text_minutes_color: RootColor
    text_direction_color: RootColor
    background_color: RootColor
    header_background_color: RootColor

    # API
    token: str
    api_url: str
    api_verify_ssl: bool

    # Timings
    call_rate: int
    refresh_rate: int

    # Rendu
    image_width: int
    image_height: int
    font_path: str
    rows_per_screen: int

    # Affichage
    display_mode: str  # "fbi" | "file"
    output_path: str
    framebuffer_device: str

    @staticmethod
    def load() -> "Settings":
        _load_env_files()

        def env(name: str, default: str | None = None) -> str:
            value = os.getenv(name, default)
            if value is None:
                raise RuntimeError(f"Variable d'environnement manquante: {name}")
            return value

        return Settings(
            text_stop_color=_hex_to_rgb(env("TEXT_STOP_COLOR", "#FFFFFF")),
            text_hour_color=_hex_to_rgb(env("TEXT_HOUR_COLOR", "#FFFFFF")),
            text_header_color=_hex_to_rgb(env("TEXT_HEADER_COLOR", "#7baee2")),
            text_minutes_color=_hex_to_rgb(env("TEXT_MINUTES_COLOR", "#FFFFFF")),
            text_direction_color=_hex_to_rgb(env("TEXT_DIRECTION_COLOR", "#FFFFFF")),
            background_color=_hex_to_rgb(env("BACKGROUND_COLOR", "#05203c")),
            header_background_color=_hex_to_rgb(env("HEADER_BACKGROUND_COLOR", "#1b4872")),
            token=env("TOKEN", ""),
            api_url=env("API_URL"),
            api_verify_ssl=env("API_VERIFY_SSL", "true").strip().lower() not in ("false", "0", "no"),
            call_rate=int(env("CALL_RATE", "60")),
            refresh_rate=int(env("REFRESH_RATE", "5")),
            image_width=int(env("IMAGE_WIDTH", "480")),
            image_height=int(env("IMAGE_HEIGHT", "320")),
            font_path=env("FONT_PATH", "assets/fonts/RobotoCondensed-Bold.ttf"),
            rows_per_screen=int(env("ROWS_PER_SCREEN", "5")),
            display_mode=env("DISPLAY_MODE", "file").lower(),
            output_path=env("OUTPUT_PATH", "output/display.png"),
            framebuffer_device=env("FRAMEBUFFER_DEVICE", "/dev/fb1"),
        )
