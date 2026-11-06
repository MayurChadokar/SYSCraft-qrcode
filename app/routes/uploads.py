import io, secrets
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image
from ..config import UPLOAD_DIR, settings

router = APIRouter(prefix="/api/uploads", tags=["Uploads"])

@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes: raise HTTPException(413, "Logo exceeds 2 MB")
    try:
        image = Image.open(io.BytesIO(data)); image.verify()
        if image.format not in {"PNG", "JPEG", "WEBP"}: raise ValueError
    except Exception as exc:
        raise HTTPException(415, "Upload a valid PNG, JPEG, or WebP image") from exc
    extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image.format]
    name = secrets.token_hex(16) + extension
    (UPLOAD_DIR / name).write_bytes(data)
    return {"logo_id": name}

