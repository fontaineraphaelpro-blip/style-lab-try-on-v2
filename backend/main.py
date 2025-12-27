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
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

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
    if DATABASE_URL:
        print(f"   Database: {DATABASE_URL[:30]}...")
    else:
        print("   Database: Not configured")
    
    # Initialiser la DB (avec gestion d'erreur)
    # init_db() gère ses propres erreurs et ne fait pas crash
    try:
        init_db()
    except Exception as e:
        # Double sécurité - si init_db() propage quand même une erreur
        print(f"⚠️  Database initialization error caught in lifespan: {e}")
        print("⚠️  App will continue without database")
    
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
    
    # Log toutes les requêtes importantes
    path = request.url.path
    if path.startswith("/app") or path.startswith("/auth") or path.startswith("/api/admin"):
        print(f"📥 {request.method} {path} - Query: {dict(request.query_params)}")
    
    response = await call_next(request)
    
    duration = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    if path.startswith("/app") or path.startswith("/auth") or path.startswith("/api/admin"):
        print(f"📤 {request.method} {path} - {response.status_code} - {duration:.0f}ms")
    
    return response


# ==========================================
# ROUTES
# ==========================================

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

# OAuth Authentication
app.include_router(
    auth_router,
    tags=["Auth"]
)

# Servir le frontend statique
frontend_path = Path(__file__).parent.parent / "frontend"


# ==========================================
# FRONTEND ROUTES (Admin Dashboard)
# ==========================================

@app.get("/app")
async def serve_admin_app(request: Request):
    """
    Sert la page admin principale.
    """
    index_path = frontend_path / "index.html"
    
    print(f"📄 Serving admin app from: {index_path}")
    print(f"   SHOPIFY_API_KEY: {'present' if SHOPIFY_API_KEY else 'missing'}")
    print(f"   Query params: {dict(request.query_params)}")
    
    if not index_path.exists():
        print(f"❌ Frontend not found at: {index_path}")
        return JSONResponse({"error": "Frontend not found"}, status_code=404)
    
    try:
        content = index_path.read_text(encoding="utf-8")
        # Remplacer les placeholders si nécessaire
        content = content.replace("{{ api_key }}", SHOPIFY_API_KEY or "")
        print(f"✅ Serving index.html ({len(content)} bytes)")
        return HTMLResponse(content=content)
    except Exception as e:
        print(f"❌ Error serving index.html: {e}")
        return JSONResponse({"error": f"Error serving frontend: {str(e)}"}, status_code=500)


@app.get("/app/{path:path}")
async def serve_admin_static(path: str, request: Request):
    """
    Sert les fichiers statiques du frontend (CSS, JS, etc.).
    """
    file_path = frontend_path / path
    
    print(f"📁 Static file request: /app/{path} -> {file_path}")
    
    if not file_path.exists() or not file_path.is_file():
        print(f"❌ File not found: {file_path}")
        return JSONResponse({"error": "File not found", "path": path}, status_code=404)
    
    # Déterminer le content-type
    content_type = None
    if path.endswith('.css'):
        content_type = 'text/css'
    elif path.endswith('.js'):
        content_type = 'application/javascript'
    elif path.endswith('.html'):
        content_type = 'text/html'
    
    print(f"✅ Serving static file: {path} ({content_type})")
    return FileResponse(
        str(file_path),
        media_type=content_type
    )


# ==========================================
# ROOT & HEALTH
# ==========================================

@app.get("/")
async def root(request: Request):
    """
    Page d'accueil API.
    Pour les apps embarquées Shopify, cette route peut être appelée avec shop/host.
    """
    query_params = dict(request.query_params)
    shop = query_params.get("shop")
    host = query_params.get("host")
    
    print(f"📥 Root route called - shop: {shop}, host: {host}, all params: {query_params}")
    
    # Si shop est présent mais pas host, c'est peut-être une installation
    # Rediriger vers /auth pour démarrer OAuth
    if shop and not host:
        print(f"🔄 Redirecting to /auth for OAuth installation")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/auth?shop={shop}")
    
    # Si shop ET host sont présents, rediriger vers /app (app déjà installée)
    if shop and host:
        print(f"🔄 Redirecting to /app (app already installed)")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/app?shop={shop}&host={host}")
    
    # Sinon, retourner l'API info
    return {
        "app": "VTON AI Backend",
        "version": "2.0.0",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "proxy": "/apps/tryon/*",
            "admin": "/api/admin/*",
            "webhooks": "/webhooks/*",
            "health": "/health",
            "docs": "/docs" if ENVIRONMENT == "development" else None
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check pour monitoring (Render, uptime robots, etc.).
    """
    checks = {
        "database": "unknown",
        "replicate": "unknown",
        "shopify": "unknown"
    }
    
    # Vérifier DB connection
    try:
        from database import engine
        from sqlalchemy import text
        # Test simple de connexion
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
    
    # Vérifier Replicate API (vérification basique)
    if REPLICATE_TOKEN:
        checks["replicate"] = "configured"
    else:
        checks["replicate"] = "missing"
    
    # Vérifier Shopify credentials
    if SHOPIFY_API_KEY and SHOPIFY_API_SECRET:
        checks["shopify"] = "configured"
    else:
        checks["shopify"] = "missing"
    
    # Déterminer le statut global
    status = "healthy" if all(v in ["ok", "configured"] for v in checks.values()) else "degraded"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": ENVIRONMENT,
        "checks": checks
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