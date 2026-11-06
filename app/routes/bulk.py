from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from openpyxl import load_workbook
import xlrd
from sqlalchemy.orm import Session

from ..config import GENERATED_DIR
from ..database import get_db
from ..models import QRCode
from ..schemas.qr import Customization, QRCreate
from ..services.qr_generator import QRValidationError, make_qr, png_bytes
from .qr import limiter

router = APIRouter(prefix="/api/bulk", tags=["Bulk QR Codes"])
ALLOWED_TYPES = {"url", "text", "email", "phone", "whatsapp", "wifi", "vcard", "sms", "location", "event", "product", "company", "custom"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 500


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _rows_from_csv(data: bytes):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "CSV must use UTF-8 encoding") from exc
    return list(csv.DictReader(io.StringIO(text)))


def _rows_from_xlsx(data: bytes):
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheet = workbook.active
        values = sheet.iter_rows(values_only=True)
        headers = [_clean(x).lower() for x in next(values)]
        return [dict(zip(headers, row)) for row in values]
    except (StopIteration, KeyError, ValueError, OSError) as exc:
        raise HTTPException(422, "Could not read the Excel workbook") from exc


def _rows_from_xls(data: bytes):
    try:
        book = xlrd.open_workbook(file_contents=data)
        sheet = book.sheet_by_index(0)
        if sheet.nrows == 0:
            return []
        headers = [_clean(sheet.cell_value(0, col)).lower() for col in range(sheet.ncols)]
        return [dict(zip(headers, sheet.row_values(row))) for row in range(1, sheet.nrows)]
    except (xlrd.XLRDError, IndexError) as exc:
        raise HTTPException(422, "Could not read the legacy Excel workbook") from exc


def _safe_name(value: str, row_number: int) -> str:
    result = "".join(char if char.isalnum() or char in "-_" else "_" for char in value).strip("_")[:80]
    return result or f"qr_{row_number}"


@router.get("/template")
def download_template():
    content = (
        "name,qr_type,content,foreground,background,size,margin,frame_text\r\n"
        "SYSCRAFT Website,url,https://example.com,#111827,#ffffff,512,4,Scan me\r\n"
        "Office Message,text,Welcome to SYSCRAFT,#111827,#ffffff,512,4,\r\n"
    )
    return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="syscraft_bulk_qr_template.csv"'})


@router.post("/generate")
@limiter.limit("5/minute")
async def generate_bulk(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = (file.filename or "").lower()
    extension = Path(filename).suffix
    if extension not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(415, "Upload a CSV, XLSX, or XLS file")
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "Spreadsheet exceeds the 10 MB limit")
    rows = _rows_from_csv(data) if extension == ".csv" else _rows_from_xlsx(data) if extension == ".xlsx" else _rows_from_xls(data)
    if not rows:
        raise HTTPException(422, "The spreadsheet has no data rows")
    if len(rows) > MAX_ROWS:
        raise HTTPException(422, f"A maximum of {MAX_ROWS} rows is allowed per upload")
    normalized_headers = {str(key).strip().lower() for key in rows[0].keys() if key is not None}
    missing = {"name", "qr_type", "content"} - normalized_headers
    if missing:
        raise HTTPException(422, "Missing required columns: " + ", ".join(sorted(missing)))

    archive_buffer = io.BytesIO()
    manifest = io.StringIO(newline="")
    errors = io.StringIO(newline="")
    manifest_writer = csv.writer(manifest)
    error_writer = csv.writer(errors)
    manifest_writer.writerow(["row", "name", "qr_type", "content", "file", "validation"])
    error_writer.writerow(["row", "name", "error"])
    written_paths: list[Path] = []
    success_count = 0

    try:
        with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for index, raw in enumerate(rows, start=2):
                row = {str(key).strip().lower(): _clean(value) for key, value in raw.items() if key is not None}
                name, qr_type, content = row.get("name", ""), row.get("qr_type", "").lower(), row.get("content", "")
                try:
                    if not name or not content:
                        raise ValueError("name and content are required")
                    if qr_type not in ALLOWED_TYPES:
                        raise ValueError(f"unsupported qr_type '{qr_type}'")
                    options = Customization(
                        foreground=row.get("foreground") or "#111827",
                        background=row.get("background") or "#ffffff",
                        size=int(row.get("size") or 512),
                        margin=int(row.get("margin") or 4),
                        error_correction="H",
                        frame_text=row.get("frame_text") or None,
                    )
                    payload = QRCreate(name=name, qr_type=qr_type, content=content, customization=options)
                    image = make_qr(payload.content, payload.customization)
                    item = QRCode(name=payload.name, qr_type=payload.qr_type, content=payload.content,
                                  customization_json=payload.customization.model_dump_json(), image_path="pending")
                    db.add(item)
                    db.flush()
                    stored_path = GENERATED_DIR / f"qr_{item.id}.png"
                    image_data = png_bytes(image)
                    stored_path.write_bytes(image_data)
                    written_paths.append(stored_path)
                    item.image_path = str(stored_path)
                    zip_name = f"qr_codes/{index - 1:04d}_{_safe_name(name, index)}.png"
                    archive.writestr(zip_name, image_data)
                    manifest_writer.writerow([index, name, qr_type, content, zip_name, "decoded_content_matches"])
                    success_count += 1
                except (ValueError, QRValidationError, TypeError) as exc:
                    error_writer.writerow([index, name, str(exc)])
            if success_count == 0:
                db.rollback()
                for path in written_paths:
                    path.unlink(missing_ok=True)
                raise HTTPException(422, "No valid QR codes could be generated. Check the spreadsheet rows.")
            archive.writestr("manifest.csv", manifest.getvalue().encode("utf-8-sig"))
            if errors.getvalue().count("\n") > 1:
                archive.writestr("errors.csv", errors.getvalue().encode("utf-8-sig"))
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        for path in written_paths:
            path.unlink(missing_ok=True)
        raise

    archive_buffer.seek(0)
    return Response(
        archive_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="syscraft_qr_codes.zip"',
            "X-Generated-Count": str(success_count),
            "X-Total-Rows": str(len(rows)),
        },
    )
