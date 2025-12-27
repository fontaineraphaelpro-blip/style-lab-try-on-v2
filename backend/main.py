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
from typing import Optional
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
APP_URL = os.getenv("APP_URL", "https://style-lab-try-on-v2-production.up.railway.app")


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
# Autoriser aussi les requêtes depuis Railway et localhost
allowed_origins = [
    "https://*.myshopify.com",
    "http://localhost:*",
    "https://*.up.railway.app",
    "https://*.railway.app"
] if ENVIRONMENT == "development" else [
    "https://*.myshopify.com",
    "https://*.up.railway.app",
    "https://*.railway.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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

# Routes compatibles frontend (legacy)
from fastapi import Depends
from routes.admin import get_authenticated_shop, get_dashboard, save_settings, initiate_credit_purchase, track_add_to_cart
from database import get_db, Shop
from sqlalchemy.orm import Session

@app.get("/api/get-data")
async def api_get_data(
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """Route compatible frontend - retourne les données du dashboard dans le format attendu"""
    dashboard_data = await get_dashboard(shop=shop, db=db)
    
    return {
        "credits": dashboard_data["billing"]["credits"],
        "lifetime": dashboard_data["billing"]["lifetime_credits"],
        "usage": dashboard_data["usage"]["total_tryons"],
        "atc": dashboard_data["usage"]["total_atc"],
        "widget": dashboard_data["widget"],
        "security": {
            "max_tries": dashboard_data["settings"]["max_tries_per_user"]
        }
    }

@app.post("/api/save-settings")
async def api_save_settings(
    request: Request,
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """Route compatible frontend - sauvegarde les paramètres"""
    from pydantic import BaseModel
    from typing import Optional
    
    class SettingsRequest(BaseModel):
        shop: str
        text: str
        bg: str
        color: str
        max_tries: int
    
    body = await request.json()
    settings_req = SettingsRequest(**body)
    
    from routes.admin import SettingsRequest as AdminSettingsRequest
    admin_settings = AdminSettingsRequest(
        text=settings_req.text,
        bg=settings_req.bg,
        color=settings_req.color,
        max_tries=settings_req.max_tries
    )
    
    return await save_settings(request=admin_settings, shop=shop, db=db)

@app.post("/api/buy-credits")
async def api_buy_credits(
    request: Request,
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """Route compatible frontend - initie l'achat de crédits"""
    from routes.admin import BillingRequest
    
    body = await request.json()
    billing_req = BillingRequest(
        pack_id=body.get("pack_id"),
        custom_amount=body.get("custom_amount")
    )
    
    return await initiate_credit_purchase(request=billing_req, shop=shop, db=db)

@app.post("/api/track-atc")
async def api_track_atc(
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """Route compatible frontend - track add to cart"""
    return await track_add_to_cart(shop=shop, db=db)

@app.get("/api/billing/confirm")
async def api_billing_confirm(
    request: Request,
    purchase_id: Optional[int] = None,
    charge_id: Optional[str] = None
):
    """Route compatible frontend - confirmation d'achat"""
    from routes.admin import billing_confirm
    from fastapi import Query
    
    # Récupérer les paramètres depuis la query string si non fournis
    if not purchase_id:
        purchase_id_param = request.query_params.get("purchase_id")
        purchase_id = int(purchase_id_param) if purchase_id_param and purchase_id_param.isdigit() else None
    
    if not charge_id:
        charge_id = request.query_params.get("charge_id")
    
    return await billing_confirm(purchase_id=purchase_id, charge_id=charge_id, request=request)

@app.post("/api/generate")
async def api_generate(request: Request):
    """Route compatible frontend - génère un try-on (admin mode)"""
    import io
    import base64
    import time
    from routes.proxy import GenerateRequest
    from services.replicate_service import ReplicateService
    from database import get_db, Shop, TryOnLog, RateLimit
    from datetime import datetime
    from fastapi import HTTPException
    
    try:
        body = await request.json()
        shop_domain = body.get("shop")
        
        if not shop_domain:
            raise HTTPException(status_code=400, detail="Shop parameter missing")
        
        # Normaliser le shop
        if not shop_domain.endswith('.myshopify.com'):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        # Récupérer le shop
        db = next(get_db())
        shop_record = db.query(Shop).filter(Shop.domain == shop_domain).first()
        
        if not shop_record:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Vérifier les crédits
        if shop_record.credits < 1:
            return JSONResponse(
                {"error": "Insufficient credits", "credits": 0},
                status_code=402
            )
        
        # Préparer les images
        if not body.get("person_image_base64"):
            raise HTTPException(status_code=400, detail="Person image required")
        
        person_bytes = base64.b64decode(body.get("person_image_base64"))
        person_file = io.BytesIO(person_bytes)
        
        garment_input = None
        if body.get("clothing_file_base64"):
            garment_bytes = base64.b64decode(body.get("clothing_file_base64"))
            garment_input = io.BytesIO(garment_bytes)
        elif body.get("clothing_url"):
            garment_input = body.get("clothing_url")
            if garment_input.startswith("//"):
                garment_input = "https:" + garment_input
        else:
            raise HTTPException(status_code=400, detail="No garment provided")
        
        start_time = time.time()
        
        # Générer le try-on
        result_url = ReplicateService.generate_tryon(
            person_image=person_file,
            garment_image=garment_input,
            category=body.get("category", "upper_body")
        )
        
        # Mettre à jour les stats
        shop_record.credits -= 1
        shop_record.total_tryons += 1
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        client_ip = request.client.host
        log = TryOnLog(
            shop=shop_domain,
            customer_ip=client_ip,
            product_id=body.get("product_id"),
            success=True,
            latency_ms=latency_ms,
            result_image_url=result_url
        )
        db.add(log)
        db.commit()
        db.close()
        
        return {
            "success": True,
            "result_image_url": result_url,
            "credits_remaining": shop_record.credits
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Generate error: {e}")
        print(f"❌ Traceback: {error_trace}")
        env = os.getenv("ENVIRONMENT", "production")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Generation failed",
                "message": str(e),
                "details": error_trace if env == "development" else None
            }
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