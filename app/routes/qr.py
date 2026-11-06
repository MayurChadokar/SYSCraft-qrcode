import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from ..config import GENERATED_DIR, UPLOAD_DIR, settings
from ..database import get_db
from ..models import QRCode
from ..schemas import QRCreate, QRUpdate, Customization
from ..services.qr_generator import QRValidationError, make_qr, png_bytes
from ..services.export_service import pdf_bytes, svg_bytes

router = APIRouter(prefix="/api/qr", tags=["QR Codes"])
limiter = Limiter(key_func=get_remote_address)

def serialize(item: QRCode):
    return {"id": item.id, "name": item.name, "qr_type": item.qr_type, "content": item.content,
            "customization": json.loads(item.customization_json), "image_url": f"/api/qr/{item.id}/image",
            "created_at": item.created_at.isoformat()}

def render(payload: QRCreate):
    logo = UPLOAD_DIR / payload.customization.logo_id if payload.customization.logo_id else None
    if logo and (not logo.is_file() or logo.parent.resolve() != UPLOAD_DIR.resolve()):
        raise HTTPException(400, "Invalid logo")
    try:
        return make_qr(payload.content, payload.customization, logo)
    except QRValidationError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.post("/preview")
@limiter.limit(settings.rate_limit)
def preview(request: Request, payload: QRCreate):
    return Response(png_bytes(render(payload)), media_type="image/png", headers={"Cache-Control": "no-store"})

@router.post("/generate", status_code=201)
@limiter.limit(settings.rate_limit)
def generate(request: Request, payload: QRCreate, db: Session = Depends(get_db)):
    image = render(payload)
    item = QRCode(name=payload.name.strip(), qr_type=payload.qr_type, content=payload.content,
                  customization_json=payload.customization.model_dump_json(), image_path="pending")
    db.add(item); db.flush()
    filename = f"qr_{item.id}.png"
    (GENERATED_DIR / filename).write_bytes(png_bytes(image))
    item.image_path = str(GENERATED_DIR / filename)
    db.commit(); db.refresh(item)
    return serialize(item)

@router.get("/")
def list_qr(db: Session = Depends(get_db), q: str = "", qr_type: str | None = None,
            page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=50)):
    stmt = select(QRCode)
    if q: stmt = stmt.where(QRCode.name.ilike(f"%{q}%"))
    if qr_type: stmt = stmt.where(QRCode.qr_type == qr_type)
    items = db.scalars(stmt.order_by(QRCode.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {"items": [serialize(x) for x in items], "page": page, "page_size": page_size}

@router.get("/{qr_id}")
def get_qr(qr_id: int, db: Session = Depends(get_db)):
    item = db.get(QRCode, qr_id)
    if not item: raise HTTPException(404, "QR code not found")
    return serialize(item)

@router.get("/{qr_id}/image")
def qr_image(qr_id: int, db: Session = Depends(get_db)):
    item = db.get(QRCode, qr_id)
    if not item: raise HTTPException(404, "QR code not found")
    options = Customization.model_validate_json(item.customization_json)
    logo = UPLOAD_DIR / options.logo_id if options.logo_id else None
    if logo and not logo.is_file():
        logo = None
        options.logo_id = None
    image = make_qr(item.content, options, logo)
    return Response(png_bytes(image), media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

@router.put("/{qr_id}")
def update_qr(qr_id: int, payload: QRUpdate, db: Session = Depends(get_db)):
    item = db.get(QRCode, qr_id)
    if not item: raise HTTPException(404, "QR code not found")
    item.name = payload.name.strip(); db.commit(); db.refresh(item)
    return serialize(item)

@router.put("/{qr_id}/customization")
def update_customization(qr_id: int, options: Customization, db: Session = Depends(get_db)):
    item = db.get(QRCode, qr_id)
    if not item: raise HTTPException(404, "QR code not found")
    logo = UPLOAD_DIR / options.logo_id if options.logo_id else None
    if logo and (not logo.is_file() or logo.parent.resolve() != UPLOAD_DIR.resolve()):
        raise HTTPException(400, "Invalid logo")
    try:
        image = make_qr(item.content, options, logo)
    except QRValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    Path(item.image_path).write_bytes(png_bytes(image))
    item.customization_json = options.model_dump_json()
    db.commit(); db.refresh(item)
    return serialize(item)

@router.delete("/{qr_id}", status_code=204)
def delete_qr(qr_id: int, db: Session = Depends(get_db)):
    item = db.get(QRCode, qr_id)
    if not item: raise HTTPException(404, "QR code not found")
    path = Path(item.image_path)
    if path.is_file() and path.parent.resolve() == GENERATED_DIR.resolve(): path.unlink()
    db.delete(item); db.commit()

@router.get("/{qr_id}/download")
def download(qr_id: int, format: str = Query("png", pattern="^(png|svg|pdf)$"), db: Session = Depends(get_db)):
    item = db.get(QRCode, qr_id)
    if not item: raise HTTPException(404, "QR code not found")
    options = Customization.model_validate_json(item.customization_json)
    image = make_qr(item.content, options, UPLOAD_DIR/options.logo_id if options.logo_id else None)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in item.name)[:80]
    if format == "png": data, media = png_bytes(image), "image/png"
    elif format == "pdf": data, media = pdf_bytes(image), "application/pdf"
    else:
        if options.logo_id or options.frame_text: raise HTTPException(422, "SVG export does not support logos or frames; use PNG or PDF")
        data, media = svg_bytes(item.content, options), "image/svg+xml"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{safe_name}.{format}"'})

