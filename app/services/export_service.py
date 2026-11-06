import io
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
import segno
from ..schemas.qr import Customization

def pdf_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=A4)
    width, height = A4
    side = min(width, height) * .68
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    canvas.drawImage(ImageReader(buffer), (width-side)/2, (height-side)/2, side, side * image.height/image.width, preserveAspectRatio=True)
    canvas.showPage(); canvas.save()
    return output.getvalue()

def svg_bytes(content: str, options: Customization) -> bytes:
    output = io.BytesIO()
    qr = segno.make(content, error=options.error_correction.lower(), boost_error=False)
    qr.save(output, kind="svg", scale=max(1, options.size // qr.symbol_size(scale=1, border=options.margin)[0]),
            border=options.margin, dark=options.foreground, light=options.background, xmldecl=True)
    return output.getvalue()

