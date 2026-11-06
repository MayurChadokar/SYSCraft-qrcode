import io
import csv
import zipfile
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.qr import Customization
from app.services.qr_generator import QRValidationError, decode_qr, make_qr, png_bytes

client = TestClient(app)

@pytest.mark.parametrize("size", [256, 512, 1024])
def test_qr_round_trip_at_multiple_sizes(size):
    content = "https://example.com/verified?source=qr-studio"
    image = make_qr(content, Customization(size=size, margin=4))
    assert decode_qr(image) == content

def test_png_is_real_and_decodable():
    content = "Exact user-provided content: 123"
    data = png_bytes(make_qr(content, Customization()))
    image = Image.open(io.BytesIO(data))
    assert image.format == "PNG"
    assert decode_qr(image) == content

def test_low_contrast_is_rejected():
    with pytest.raises(QRValidationError):
        make_qr("test", Customization(foreground="#777777", background="#888888"))

def test_preview_api():
    response = client.post("/api/qr/preview", json={"name":"Test", "qr_type":"text", "content":"API integrity test", "customization":{}})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert decode_qr(Image.open(io.BytesIO(response.content))) == "API integrity test"

def test_invalid_empty_content():
    response = client.post("/api/qr/preview", json={"name":"Test", "qr_type":"text", "content":"", "customization":{}})
    assert response.status_code == 422

def test_generate_and_exports():
    response = client.post("/api/qr/generate", json={"name":"Export test", "qr_type":"url", "content":"https://example.org", "customization":{}})
    assert response.status_code == 201
    qr_id = response.json()["id"]
    for fmt, media in (("png","image/png"),("svg","image/svg+xml"),("pdf","application/pdf")):
        exported = client.get(f"/api/qr/{qr_id}/download?format={fmt}")
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith(media)

def test_bulk_csv_generates_validated_zip():
    csv_data = "name,qr_type,content\nFirst,text,Exact bulk value\nWebsite,url,https://example.com/bulk\n"
    response = client.post("/api/bulk/generate", files={"file": ("codes.csv", csv_data, "text/csv")})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["x-generated-count"] == "2"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert "manifest.csv" in names
        png_names = [name for name in names if name.endswith(".png")]
        assert len(png_names) == 2
        decoded = [decode_qr(Image.open(io.BytesIO(archive.read(name)))) for name in png_names]
        assert decoded == ["Exact bulk value", "https://example.com/bulk"]

