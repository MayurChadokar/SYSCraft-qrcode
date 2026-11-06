from __future__ import annotations
import io
from pathlib import Path
import cv2
import numpy as np
import qrcode
from PIL import Image, ImageColor, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_M, ERROR_CORRECT_Q
from ..schemas.qr import Customization

ERROR_LEVELS = {"M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}

class QRValidationError(ValueError):
    pass

def _contrast_ratio(a: str, b: str) -> float:
    def lum(value: str):
        rgb = [x / 255 for x in ImageColor.getrgb(value)]
        rgb = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
        return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + .05) / (y + .05)

def validate_colors(foreground: str, background: str):
    if _contrast_ratio(foreground, background) < 4.5:
        raise QRValidationError("Foreground and background need a contrast ratio of at least 4.5:1")

def make_qr(content: str, options: Customization, logo_path: Path | None = None) -> Image.Image:
    validate_colors(options.foreground, options.background)
    error = "H" if logo_path else options.error_correction
    qr = qrcode.QRCode(version=None, error_correction=ERROR_LEVELS[error], box_size=10, border=options.margin)
    qr.add_data(content, optimize=0)
    qr.make(fit=True)
    image = qr.make_image(fill_color=options.foreground, back_color=options.background).convert("RGB")
    image = image.resize((options.size, options.size), Image.Resampling.NEAREST)
    if logo_path:
        with Image.open(logo_path) as raw:
            logo = raw.convert("RGBA")
            max_side = int(options.size * options.logo_scale)
            logo.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            padding = max(6, options.size // 80)
            plate = Image.new("RGBA", (logo.width + padding * 2, logo.height + padding * 2), options.background)
            plate.alpha_composite(logo, (padding, padding))
            image.paste(plate, ((options.size - plate.width) // 2, (options.size - plate.height) // 2), plate)
    if options.frame_text:
        framed = Image.new("RGB", (options.size, options.size + max(56, options.size // 8)), options.background)
        framed.paste(image, (0, 0))
        draw = ImageDraw.Draw(framed)
        font = ImageFont.load_default(size=max(16, options.size // 28))
        draw.text((options.size // 2, options.size + (framed.height-options.size)//2), options.frame_text,
                  fill=options.foreground, font=font, anchor="mm")
        image = framed
    validate_decodes(image, content)
    return image

def decode_qr(image: Image.Image) -> str:
    array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    value, _, _ = cv2.QRCodeDetector().detectAndDecode(array)
    return value

def validate_decodes(image: Image.Image, expected: str):
    for target in (256, 512, 1024):
        ratio = image.height / image.width
        sample = image.resize((target, round(target * ratio)), Image.Resampling.NEAREST)
        if decode_qr(sample) != expected:
            raise QRValidationError(f"Independent validation failed at {target}px; choose simpler content or remove the logo")

def png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()

