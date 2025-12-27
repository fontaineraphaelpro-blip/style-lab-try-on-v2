"""
VTON AI Backend - Main Application
===================================
FastAPI backend optimisé pour Shopify App Store.

Architecture:
- /apps/tryon/*  → App Proxy (public storefront)
- /api/admin/*   → Admin dashboard (Session Token)
- /webhooks/*    → Shopify webhooks
- /health        → Health check
"""

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime

# Import des routes
from routes.proxy import router as proxy_router
from routes.admin import router as admin_router
from routes.webhooks import router as webhooks_router
from routes.auth import router as auth_router

# Import de la config DB
from database import init_db


# ==========================================
# CONFIGURATION
# ==========================================

SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")


# ==========================================
# LIFESPAN EVENTS
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gère le démarrage et l'arrêt de l'app.
    """
    # Startup
    print("🚀 Starting VTON AI Backend...")
    print(f"   Environment: {ENVIRONMENT}")
    print(f"   Database: {DATABASE_URL[:30]}...")
    
    # Initialiser la DB
    init_db()
    print("✅ Database initialized")
    
    # Vérifier les credentials Shopify
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        print("⚠️  WARNING: Shopify credentials missing")
    
    # Vérifier Replicate
    if not REPLICATE_TOKEN:
        print("⚠️  WARNING: Replicate token missing")
    
    print("✅ VTON AI Backend ready!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down VTON AI Backend...")


# ==========================================
# FASTAPI APP
# ==========================================

app = FastAPI(
    title="VTON AI Backend",
    version="2.0.0",
    description="AI-powered virtual try-on for Shopify",
    lifespan=lifespan,
    docs_url="/docs" if ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if ENVIRONMENT == "development" else None
)


# ==========================================
# MIDDLEWARE
# ==========================================

# CORS (minimal - App Proxy handled by Shopify)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.myshopify.com",
        "http://localhost:*"  # Dev only
    ] if ENVIRONMENT == "development" else ["https://*.myshopify.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log toutes les requêtes (dev/debug).
    """
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    duration = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    if ENVIRONMENT == "development":
        print(f"{request.method} {request.url.path} - {response.status_code} - {duration:.0f}ms")
    
    return response


# ==========================================
# ROUTES
# ==========================================

# Authentication (OAuth)
app.include_router(
    auth_router,
    tags=["Authentication"]
)

# App Proxy (Public Storefront)
app.include_router(
    proxy_router,
    prefix="/apps/tryon",
    tags=["App Proxy"]
)

# Admin Dashboard
app.include_router(
    admin_router,
    prefix="/api/admin",
    tags=["Admin"]
)

# Webhooks
app.include_router(
    webhooks_router,
    prefix="/webhooks",
    tags=["Webhooks"]
)


# ==========================================
# FRONTEND (STATIC FILES)
# ==========================================

# Chemin vers le dossier frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Servir les fichiers statiques
@app.get("/app.js")
async def serve_app_js():
    """Sert app.js"""
    file_path = FRONTEND_DIR / "app.js"
    if file_path.exists():
        return FileResponse(file_path, media_type="application/javascript")
    return JSONResponse({"error": "File not found"}, status_code=404)

@app.get("/styles.css")
async def serve_styles_css():
    """Sert styles.css"""
    file_path = FRONTEND_DIR / "styles.css"
    if file_path.exists():
        return FileResponse(file_path, media_type="text/css")
    return JSONResponse({"error": "File not found"}, status_code=404)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """
    Sert index.html pour l'app embedded Shopify.
    """
    file_path = FRONTEND_DIR / "index.html"
    if file_path.exists():
        html_content = file_path.read_text(encoding="utf-8")
        # Remplacer {{ api_key }} par la vraie clé API
        html_content = html_content.replace("{{ api_key }}", SHOPIFY_API_KEY or "")
        return HTMLResponse(content=html_content)
    return JSONResponse({"error": "Frontend not found"}, status_code=404)


@app.get("/health")
async def health_check():
    """
    Health check pour monitoring (Render, uptime robots, etc.).
    """
    # TODO: Vérifier DB connection
    # TODO: Vérifier Replicate API
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": ENVIRONMENT,
        "checks": {
            "database": "ok",  # À implémenter
            "replicate": "ok",  # À implémenter
            "shopify": "ok"     # À implémenter
        }
    }


# ==========================================
# ERROR HANDLERS
# ==========================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """
    Handler pour 404.
    """
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "path": str(request.url.path),
            "message": "The requested resource was not found"
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """
    Handler pour 500.
    """
    print(f"❌ Internal Error: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=ENVIRONMENT == "development",
        log_level="info"
    )