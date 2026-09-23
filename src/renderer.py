"""Génération de l'image d'affichage avec Pillow, à partir de l'état courant."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from .config import Settings
from .state import AppState, Status

logger = logging.getLogger(__name__)

_NO_BUS_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "no_bus.png"
_NO_SIGNAL_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "no_signal.png"
_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "RobotoCondensed-Bold.ttf"

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}
_no_bus_icon_cache: dict[int, Image.Image | None] = {}
_no_signal_icon_cache: dict[int, Image.Image | None] = {}


def _load_icon(path: Path, size: int, cache: dict[int, Image.Image | None]) -> Image.Image | None:
    if size not in cache:
        try:
            icon = Image.open(path).convert("RGBA")
            cache[size] = icon.resize((size, size), Image.Resampling.LANCZOS)
        except OSError:
            logger.warning("Icône introuvable à %s, affichage sans icône.", path)
            cache[size] = None
    return cache[size]


def _get_no_bus_icon(size: int) -> Image.Image | None:
    return _load_icon(_NO_BUS_ICON_PATH, size, _no_bus_icon_cache)


def _get_no_signal_icon(size: int) -> Image.Image | None:
    return _load_icon(_NO_SIGNAL_ICON_PATH, size, _no_signal_icon_cache)


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(str(_FONT_PATH), size)
    return _font_cache[size]


def _hex_to_rgb(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not value:
        return fallback
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[float, float]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _draw_smooth_rounded_rect(
    image: Image.Image,
    box: tuple[float, float, float, float],
    radius: float,
    fill: tuple[int, int, int],
) -> None:
    # ImageDraw.rounded_rectangle n'anti-crénèle pas ses bords (contrairement
    # au texte, rendu via FreeType) : dessiner en sur-échantillonnage puis
    # redimensionner en LANCZOS lisse les contours, comme sur la maquette.
    supersample = 4
    x0, y0, x1, y1 = box
    w = max(round(x1 - x0), 1)
    h = max(round(y1 - y0), 1)
    mask = Image.new("RGBA", (w * supersample, h * supersample), (0, 0, 0, 0))
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, w * supersample - 1, h * supersample - 1),
        radius=radius * supersample,
        fill=(*fill, 255),
    )
    mask = mask.resize((w, h), Image.Resampling.LANCZOS)
    image.paste(mask, (round(x0), round(y0)), mask)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    # anchor="mm" : centre sur le milieu réel des glyphes, contrairement à un
    # centrage manuel via textbbox + ancre par défaut ("la", basée sur
    # l'ascendant de la police) qui ignore l'écart entre l'ascendant et le
    # haut réel de l'encre, et pousse le texte vers le bas.
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    draw.text((cx, cy), text, font=font, fill=color, anchor="mm")


def _display_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        logger.warning("Fuseau horaire DISPLAY_TIMEZONE=%r introuvable, repli sur UTC", name)
        return ZoneInfo("UTC")


def render(state: AppState, settings: Settings, now: datetime | None = None) -> Image.Image:
    # datetime.now().astimezone() dépend du fuseau système : sur le conteneur
    # Docker (souvent en UTC par défaut), l'heure affichée serait fausse.
    # On force donc le fuseau configuré (DISPLAY_TIMEZONE) plutôt que de
    # supposer que l'hôte est correctement configuré.
    now = now or datetime.now(_display_timezone(settings.display_timezone))
    width, height = settings.image_width, settings.image_height

    image = Image.new("RGB", (width, height), settings.background_color)
    draw = ImageDraw.Draw(image)

    # --- Dimensions des zones (proportionnelles à la hauteur) ---
    top_bar_h = int(height * 0.145)
    col_header_h = int(height * 0.105)
    rows_top = top_bar_h + col_header_h

    display_item = state.next_display()
    status = state.snapshot_status()
    has_api_error = state.snapshot_has_api_error()

    quay_name = display_item.quay_name if display_item else ""

    # --- Barre du haut : nom d'arrêt + heure ---
    draw.rectangle((0, 0, width, top_bar_h), fill=settings.background_color)
    title_font = _get_font(int(top_bar_h * 0.55))
    hour_font = _get_font(int(top_bar_h * 0.55))

    padding = int(width * 0.03)
    draw.text(
        (padding, top_bar_h / 2),
        quay_name.upper(),
        font=title_font,
        fill=settings.text_stop_color,
        anchor="lm",
    )
    hour_text = now.strftime("%H:%M")
    hw, _ = _text_size(draw, hour_text, hour_font)
    draw.text(
        (width - padding - hw, top_bar_h / 2),
        hour_text,
        font=hour_font,
        fill=settings.text_hour_color,
        anchor="lm",
    )

    # --- Barre des en-têtes de colonnes ---
    draw.rectangle((0, top_bar_h, width, rows_top), fill=settings.header_background_color)
    header_font = _get_font(int(col_header_h * 0.62))

    col_route_x = padding
    col_minutes_x = int(width * 0.227)
    col_direction_x = int(width * 0.39)

    draw.text(
        (col_route_x, top_bar_h + col_header_h / 2),
        "N° ligne",
        font=header_font,
        fill=settings.text_header_color,
        anchor="lm",
    )
    draw.text(
        (col_minutes_x, top_bar_h + col_header_h / 2),
        "Dans",
        font=header_font,
        fill=settings.text_header_color,
        anchor="lm",
    )
    draw.text(
        (col_direction_x, top_bar_h + col_header_h / 2),
        "Direction",
        font=header_font,
        fill=settings.text_header_color,
        anchor="lm",
    )

    # Pictogramme de souci d'accès à l'API (token invalide ou API injoignable),
    # même écart au bord droit que l'heure, pour signaler le problème sans
    # jamais remplacer les données valides encore affichées (voir AppState).
    if has_api_error:
        icon_size = int(col_header_h * 0.68)
        icon = _get_no_signal_icon(icon_size)
        if icon is not None:
            icon_x = width - padding - icon_size
            icon_y = int(top_bar_h + col_header_h / 2 - icon_size / 2)
            image.paste(icon, (icon_x, icon_y), icon)

    # --- Corps du tableau ---
    if status is not Status.OK or display_item is None:
        # Status.ERROR : API injoignable sans données valides reçues, à ne pas
        # confondre avec une vraie absence de passage (displays vide, OK).
        if status is Status.INVALID_TOKEN:
            message = "Token invalide, vérifier la configuration"
        elif status is Status.ERROR:
            message = "Données indisponibles"
        else:
            message = "Pas de passage prévu actuellement"
        msg_font = _get_font(int(height * 0.055))
        # texte multi-lignes centré si trop large
        max_w = int(width * 0.85)
        words = message.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            w, _ = _text_size(draw, trial, msg_font)
            if w > max_w and current:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)

        line_h = int(height * 0.07)
        total_h = line_h * len(lines)
        start_y = rows_top + ((height - rows_top) - total_h) / 2
        for i, line in enumerate(lines):
            y = start_y + i * line_h
            _draw_centered_text(
                draw,
                (0, int(y), width, int(y + line_h)),
                line,
                msg_font,
                settings.text_direction_color,
            )
        return image

    # On n'affiche pas les passages déjà passés (expected_at < now) : l'API
    # peut renvoyer un passage tout juste dépassé entre deux appels.
    passages = [p for p in display_item.next_passages if p.expected_at >= now]

    if not passages:
        msg_font = _get_font(int(height * 0.055))
        body_h = height - rows_top
        # Proportions mesurées sur la maquette test/no_bus.png : le bloc
        # icône + texte n'est pas centré verticalement dans le corps, il est
        # légèrement plus haut (marge basse plus grande que la marge haute).
        icon_top = rows_top + int(body_h * 0.105)
        icon_size = int(body_h * 0.585)
        icon_text_gap = int(height * 0.006)
        text_box_h = int(height * 0.07)

        icon = _get_no_bus_icon(icon_size)
        if icon is not None:
            image.paste(icon, (int((width - icon_size) / 2), int(icon_top)), icon)

        text_box_top = icon_top + icon_size + icon_text_gap
        _draw_centered_text(
            draw,
            (0, int(text_box_top), width, int(text_box_top + text_box_h)),
            "Pas de passage prévu actuellement",
            msg_font,
            settings.text_direction_color,
        )
        return image

    # La hauteur de ligne (et donc la taille des polices/pastilles) se base sur
    # ROWS_PER_SCREEN plutôt que sur le nombre réel de passages : avec peu de
    # passages, les lignes gardent une taille normale (l'espace restant reste
    # vide) au lieu de s'étirer démesurément sur toute la hauteur.
    effective_rows = max(len(passages), settings.rows_per_screen)
    row_h = (height - rows_top) / effective_rows
    route_font = _get_font(int(row_h * 0.333))
    minutes_font = _get_font(int(row_h * 0.396))
    direction_font = _get_font(int(row_h * 0.333))

    for i, passage in enumerate(passages):
        row_top = rows_top + i * row_h
        row_bottom = row_top + row_h
        row_center = (row_top + row_bottom) / 2

        if i > 0:
            draw.line((0, row_top, width, row_top), fill=settings.header_background_color, width=2)

        # Pastille n° de ligne
        route_bg = _hex_to_rgb(passage.route_color, settings.header_background_color)
        route_fg = _hex_to_rgb(passage.route_text_color, settings.text_direction_color)
        pill_text = passage.route_short_name
        pw, ph = _text_size(draw, pill_text, route_font)
        # Largeur fixe (comme sur la maquette : toutes les pastilles ont la même
        # largeur, quelle que soit la longueur du texte), avec repli si le texte
        # est trop long pour ne jamais le couper.
        pill_w = max(int(row_h * 1.146), pw + int(row_h * 0.3))
        pill_h = int(row_h * 0.71)
        pill_x0 = padding
        pill_y0 = row_center - pill_h / 2
        pill_x1 = pill_x0 + pill_w
        pill_y1 = pill_y0 + pill_h
        # Coins arrondis mais pas en capsule complète : sur la maquette, le
        # rayon vaut environ 0.34x la hauteur de la pastille (mesuré), pas 0.5.
        radius = pill_h * 0.34
        _draw_smooth_rounded_rect(image, (pill_x0, pill_y0, pill_x1, pill_y1), radius, route_bg)
        _draw_centered_text(draw, (pill_x0, pill_y0, pill_x1, pill_y1), pill_text, route_font, route_fg)

        # Minutes restantes : aligné à gauche sous l'en-tête "Dans", comme
        # dans la maquette (même x que le texte du header de colonne).
        minutes = passage.minutes_until(now)
        minutes_text = f"{minutes} min"
        draw.text(
            (col_minutes_x, row_center),
            minutes_text,
            font=minutes_font,
            fill=settings.text_minutes_color,
            anchor="lm",
        )

        # Direction (retour à la ligne si trop long)
        max_w = width - col_direction_x - padding
        words = passage.headsign.split(" ")
        lines = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            w, _ = _text_size(draw, trial, direction_font)
            if w > max_w and current:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        lines = lines[:2]  # on ne garde pas plus de 2 lignes par ligne de tableau

        line_h = int(row_h * 0.4)
        block_h = line_h * len(lines)
        block_top = row_center - block_h / 2
        for j, line in enumerate(lines):
            draw.text(
                (col_direction_x, block_top + j * line_h + line_h / 2),
                line,
                font=direction_font,
                fill=settings.text_direction_color,
                anchor="lm",
            )

    return image


def save_image(image: Image.Image, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    image.save(tmp_path, format=path.suffix.lstrip(".").upper() or "PNG")
    tmp_path.replace(path)  # écriture atomique pour éviter de lire un fichier à moitié écrit
