from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont


VARIABLE_PATTERN = re.compile(r"\$[A-Za-z][A-Za-z0-9_.]*")


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


def format_value(value) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "on" if value else "off"

    if isinstance(value, float):
        return f"{value:.1f}".rstrip("0").rstrip(".")

    return str(value)


def variable_values(context: dict) -> dict[str, object]:
    captured_at = context["captured_at"]
    environment = context.get("environment")
    heater = context.get("heater")
    camera_settings = context.get("camera_settings")

    values = {
        "$capture.datetime": captured_at.strftime("%Y-%m-%d %H:%M:%S"),
        "$capture.date": captured_at.strftime("%Y-%m-%d"),
        "$capture.time": captured_at.strftime("%H:%M:%S"),
        "$capture.period": str(context.get("period", "")).upper(),
        "$node.id": context.get("node_id", ""),
        "$node.node_id": context.get("node_id", ""),
        "$picamera2.state": "capturing" if getattr(camera_settings, "capture_enabled", False) else "idle",
    }

    if environment is not None:
        values.update(
            {
                "$bme280.temperature": environment.temperature_c,
                "$bme280.temperature_c": environment.temperature_c,
                "$bme280.humidity": environment.humidity_percent,
                "$bme280.humidity_percent": environment.humidity_percent,
                "$bme280.pressure": environment.pressure_hpa,
                "$bme280.pressure_hpa": environment.pressure_hpa,
                "$bme280.dew_point": environment.dew_point_c,
                "$bme280.dew_point_c": environment.dew_point_c,
            }
        )

    if heater is not None:
        values.update(
            {
                "$heater.desired": heater.desired_enabled,
                "$heater.actual": heater.actual_enabled,
                "$heater.state": heater.actual_enabled,
                "$heater.gpio": heater.gpio_pin,
                "$heater.driver": heater.driver,
            }
        )

    return values


def render_template(template: str, context: dict) -> str:
    values = variable_values(context)

    def replace(match: re.Match) -> str:
        return format_value(values.get(match.group(0)))

    return VARIABLE_PATTERN.sub(replace, template)


def entity_text(entity: dict, context: dict) -> str:
    if entity.get("text"):
        return render_template(str(entity.get("text") or ""), context)

    entity_type = entity.get("type")

    if entity_type == "datetime":
        return render_template("$capture.datetime", context)

    if entity_type == "date":
        return render_template("$capture.date", context)

    if entity_type == "time":
        return render_template("$capture.time", context)

    if entity_type == "period":
        return render_template("$capture.period", context)

    if entity_type == "node_id":
        return render_template("$node.id", context)

    if entity_type == "text":
        return str(entity.get("label") or "")

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
    environment=None,
    heater=None,
    camera_settings=None,
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
            "environment": environment,
            "heater": heater,
            "camera_settings": camera_settings,
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
