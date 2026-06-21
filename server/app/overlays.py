from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont


def hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(value, str):
        return fallback

    value = value.strip().lstrip("#")

    if len(value) != 6:
        return fallback

    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return fallback


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size=max(8, int(size)))
        except OSError:
            continue

    return ImageFont.load_default()


def entity_text(entity: dict, context: dict) -> str:
    entity_type = entity.get("type")

    if entity_type == "datetime":
        return context["captured_at"].strftime("%Y-%m-%d %H:%M:%S")

    if entity_type == "date":
        return context["captured_at"].strftime("%Y-%m-%d")

    if entity_type == "time":
        return context["captured_at"].strftime("%H:%M:%S")

    if entity_type == "period":
        return str(context.get("period", "")).upper()

    if entity_type == "node_id":
        return str(context.get("node_id", ""))

    if entity_type == "text":
        return str(entity.get("text") or entity.get("label") or "")

    return ""


def anchored_position(
    anchor: str,
    x: float,
    y: float,
    text_width: int,
    text_height: int,
    image_width: int,
    image_height: int,
) -> tuple[int, int]:
    left = int(x * image_width)
    top = int(y * image_height)

    if "right" in anchor:
        left -= text_width
    elif "center" in anchor:
        left -= text_width // 2

    if "bottom" in anchor:
        top -= text_height
    elif anchor == "center":
        top -= text_height // 2

    return left, top


def apply_overlays_to_image(
    image_path: Path,
    overlay_settings,
    *,
    node_id: str,
    captured_at: datetime,
    period: str,
    timezone_name: str,
) -> None:
    if not overlay_settings or not overlay_settings.enabled:
        return

    entities = overlay_settings.entities or []

    if not entities:
        return

    local_captured_at = captured_at.astimezone(ZoneInfo(timezone_name))

    with Image.open(image_path) as image:
        image = image.convert("RGBA")
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        context = {
            "node_id": node_id,
            "captured_at": local_captured_at,
            "period": period,
        }

        for entity in entities:
            if not entity.get("enabled", True):
                continue

            text = entity_text(entity, context)

            if not text:
                continue

            font = load_font(entity.get("font_size", 28))
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            padding = max(5, int(entity.get("font_size", 28) * 0.22))
            box_width = text_width + padding * 2
            box_height = text_height + padding * 2
            left, top = anchored_position(
                entity.get("anchor", "top-left"),
                min(1, max(0, float(entity.get("x", 0)))),
                min(1, max(0, float(entity.get("y", 0)))),
                box_width,
                box_height,
                image.width,
                image.height,
            )

            left = max(0, min(image.width - box_width, left))
            top = max(0, min(image.height - box_height, top))
            opacity = min(1, max(0, float(entity.get("background_opacity", 0.35))))
            background = (*hex_to_rgb(entity.get("background", "#000000"), (0, 0, 0)), int(255 * opacity))
            color = (*hex_to_rgb(entity.get("color", "#ffffff"), (255, 255, 255)), 255)

            if opacity > 0:
                draw.rounded_rectangle(
                    (left, top, left + box_width, top + box_height),
                    radius=max(4, padding),
                    fill=background,
                )

            draw.text(
                (left + padding, top + padding - text_bbox[1]),
                text,
                font=font,
                fill=color,
            )

        image = Image.alpha_composite(image, overlay).convert("RGB")
        image.save(image_path)
