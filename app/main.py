from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .config import settings
from .database import Base, engine
from .routes import qr, uploads, dashboard, template_catalog, bulk

Base.metadata.create_all(engine)
app = FastAPI(title=settings.app_name, version="1.0.0")
app.state.limiter = qr.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(qr.router); app.include_router(uploads.router); app.include_router(dashboard.router); app.include_router(template_catalog.router); app.include_router(bulk.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/{page:path}", response_class=HTMLResponse)
def pages(request: Request, page: str = ""):
    allowed = {"": "dashboard", "create": "generator", "bulk": "bulk", "codes": "my_qr", "templates": "templates", "settings": "settings"}
    template = allowed.get(page)
    if template is None: return templates.TemplateResponse(request, "404.html", status_code=404)
    return templates.TemplateResponse(request, f"{template}.html", {"active": page or "overview"})

