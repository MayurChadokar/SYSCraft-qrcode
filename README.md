# SYSCRAFT QR CODE STUDIO

SYSCRAFT QR CODE STUDIO is a production-oriented FastAPI application for creating genuine, standards-compliant QR codes. Every raster QR is decoded with OpenCV at 256, 512, and 1024 pixels and compared byte-for-byte with the original content before it can be stored or downloaded.

## Highlights

- 13 content types with correct URL, Wi-Fi, vCard, SMS, email, geo, and calendar payload construction
- Safe customization only: colors, output size, quiet zone, centered logo, and an external frame
- High error correction is automatically enforced for logos
- Contrast validation and independent decode validation
- PNG, SVG, and PDF exports generated from the real encoded content
- Responsive light/dark SaaS interface, management library, filters, templates, and dashboard statistics
- SQLAlchemy storage compatible with SQLite and configurable for PostgreSQL
- Upload validation, secure random filenames, path checks, rate limits, and strict request schemas

## Setup

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. API documentation is at `http://localhost:8000/docs`.

Set a long random `SECRET_KEY` in `.env` before deployment. To use PostgreSQL, install an appropriate driver and set `DATABASE_URL`, for example `postgresql+psycopg://user:password@host/database`.

## Testing

```powershell
pytest -q
```

Tests cover exact-content round trips, multiple raster sizes, contrast rejection, API input validation, and PNG/SVG/PDF exports.

## Production

Run behind a TLS-terminating reverse proxy and use multiple Uvicorn workers:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Use PostgreSQL for multi-worker deployments, set a strong secret, restrict proxy body size, and serve `/static` via a CDN or web server. Uploaded logos are treated as untrusted image data and are never executed.

## Deploy free on Render

The included `render.yaml` creates a free Render web service. Because free Render services have an ephemeral filesystem, production records use an external free PostgreSQL database instead of SQLite.

1. Create a free Supabase or Neon project and copy its PostgreSQL connection string.
2. In Render, choose **New → Blueprint** and connect this repository.
3. When Render asks for `DATABASE_URL`, paste the PostgreSQL connection string.
4. Apply the Blueprint, wait for `/health` to pass, and open the generated `onrender.com` URL.

QR previews and downloads are regenerated from database content and do not depend on saved local PNG files. On the free architecture, uploaded center logos are temporary and can disappear when Render sleeps or redeploys. Use QR codes without logos for durable free hosting, or connect external object storage later.

## Integrity policy

QR modules are never replaced with decorative shapes, stretched, rotated, or AI-generated. A standards-compliant quiet zone of at least four modules is mandatory. Frames are outside the QR matrix. SVG is emitted directly from the same content with Segno; logo/frame combinations are intentionally restricted to validated PNG and PDF exports.
