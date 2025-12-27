"""
OAuth Authentication Routes
===========================
Gère l'installation et l'authentification OAuth de l'app Shopify.
"""

import os
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
import requests

from database import get_db, Shop

router = APIRouter()

# Configuration
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
APPLICATION_URL = os.getenv("APPLICATION_URL", "https://style-lab-try-on-v2-1.onrender.com")
SCOPES = "write_products,read_products"


def verify_hmac(query_params: dict) -> bool:
    """
    Vérifie la signature HMAC de Shopify pour l'OAuth.
    """
    hmac_param = query_params.get("hmac")
    if not hmac_param:
        return False
    
    # Créer une copie sans hmac et signature
    params = {k: v for k, v in query_params.items() if k not in ["hmac", "signature"]}
    
    # Trier et créer la query string
    sorted_params = sorted(params.items())
    query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
    
    # Calculer le HMAC
    computed_hmac = hmac.new(
        SHOPIFY_API_SECRET.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_hmac, hmac_param)


@router.get("/auth")
async def auth_start(shop: str = Query(...)):
    """
    Point d'entrée pour l'installation de l'app.
    Redirige vers Shopify OAuth.
    """
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    
    # URL de redirection après autorisation
    redirect_uri = f"{APPLICATION_URL}/auth/callback"
    
    # Construire l'URL OAuth Shopify
    auth_url = (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={SHOPIFY_API_KEY}"
        f"&scope={SCOPES}"
        f"&redirect_uri={redirect_uri}"
    )
    
    return RedirectResponse(url=auth_url)


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    hmac: str = Query(None),
    state: str = Query(None)
):
    """
    Callback OAuth après autorisation par le merchant.
    Échange le code contre un access token.
    """
    # Vérifier HMAC
    query_params = dict(request.query_params)
    if not verify_hmac(query_params):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    
    # Échanger le code contre un access token
    token_url = f"https://{shop}/admin/oauth/access_token"
    
    payload = {
        "client_id": SHOPIFY_API_KEY,
        "client_secret": SHOPIFY_API_SECRET,
        "code": code
    }
    
    try:
        response = requests.post(token_url, json=payload)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received")
        
        # Sauvegarder ou mettre à jour le shop en DB
        db = next(get_db())
        shop_record = db.query(Shop).filter(Shop.domain == shop).first()
        
        if shop_record:
            # Mise à jour
            shop_record.access_token = access_token
            shop_record.is_active = True
            shop_record.last_active_at = datetime.utcnow()
            if not shop_record.installed_at:
                shop_record.installed_at = datetime.utcnow()
        else:
            # Création
            shop_record = Shop(
                domain=shop,
                access_token=access_token,
                is_active=True,
                installed_at=datetime.utcnow(),
                last_active_at=datetime.utcnow()
            )
            db.add(shop_record)
        
        db.commit()
        
        # Rediriger vers l'app embarquée
        # Format correct pour les apps embarquées Shopify
        shop_name = shop.replace('.myshopify.com', '')
        app_url = f"{APPLICATION_URL}/app?shop={shop}&host={shop_name}"
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Installation réussie</title>
            <meta charset="UTF-8">
            <script>
                // Rediriger vers l'app embarquée
                if (window.top !== window.self) {{
                    window.top.location.href = "{app_url}";
                }} else {{
                    window.location.href = "{app_url}";
                }}
            </script>
        </head>
        <body style="font-family: system-ui; text-align: center; padding: 50px;">
            <h1>✅ Installation réussie!</h1>
            <p>Redirection en cours...</p>
            <p><a href="{app_url}" style="color: #6366f1;">Cliquez ici si la redirection ne fonctionne pas</a></p>
        </body>
        </html>
        """)
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange token: {str(e)}")


@router.get("/auth/shopify/callback")
async def auth_shopify_callback(request: Request):
    """
    Alias pour /auth/callback (compatibilité).
    """
    return await auth_callback(request)


@router.get("/api/auth/callback")
async def auth_api_callback(request: Request):
    """
    Alias pour /auth/callback (compatibilité API).
    """
    return await auth_callback(request)

