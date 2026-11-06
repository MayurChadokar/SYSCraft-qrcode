from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import QRCode

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])
@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(QRCode)) or 0
    today = datetime.now(timezone.utc).date()
    records = db.scalars(select(QRCode).order_by(QRCode.created_at.desc()).limit(5)).all()
    created_today = db.scalar(select(func.count()).select_from(QRCode).where(func.date(QRCode.created_at) == str(today))) or 0
    return {"total": total, "today": created_today, "static": total,
            "recent": [{"id": x.id, "name": x.name, "type": x.qr_type, "created_at": x.created_at.isoformat()} for x in records]}

