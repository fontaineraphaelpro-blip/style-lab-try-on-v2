"""
Shopify OAuth Authentication Routes
====================================
Gère l'installation et l'authentification OAuth de l'app Shopify.

Flux:
1. /login?shop=SHOP.myshopify.com → Redirige vers /auth/shopify
2. /auth/shopify → Initie l'OAuth avec Shopify
3. /auth/callback → Reçoit le code OAuth et échange contre access_token
"""

import os
import hmac
import hashlib
import secrets
import requests
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from urllib.parse import urlencode

from database import get_db, Shop

router = APIRouter()

# Configuration
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
APP_URL = os.getenv("APP_URL", "https://style-lab-try-on-v2-production.up.railway.app")
SCOPES = "write_products,read_products"


def verify_hmac(query_params: dict) -> bool:
    """
    Vérifie la signature HMAC de Shopify.
    """
    hmac_param = query_params.get('hmac')
    if not hmac_param:
        return False
    
    # Retirer hmac et signature de la vérification
    params = {k: v for k, v in query_params.items() if k not in ['hmac', 'signature']}
    
    # Trier et créer la query string
    sorted_params = sorted(params.items())
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
    
    # Calculer le HMAC
    computed_hmac = hmac.new(
        SHOPIFY_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_hmac, hmac_param)


@router.get("/login")
async def login_page(shop: str = Query(None)):
    """
    Page de login - redirige vers l'OAuth Shopify.
    """
    if not shop:
        return JSONResponse(
            status_code=400,
            content={"error": "Shop parameter is required"}
        )
    
    # Normaliser le shop domain
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    # Rediriger vers l'OAuth
    return RedirectResponse(url=f"/auth/shopify?shop={shop}")


@router.get("/auth/shopify")
async def initiate_oauth(
    shop: str = Query(..., description="Shop domain (e.g., mystore.myshopify.com)"),
    request: Request = None
):
    """
    Initie le flux OAuth avec Shopify.
    Redirige vers la page d'autorisation Shopify.
    """
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Shopify credentials not configured"
        )
    
    # Normaliser le shop domain
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    # Générer un state nonce pour la sécurité
    state = secrets.token_urlsafe(32)
    
    # Stocker le state (dans une vraie app, utiliser Redis ou session)
    # Pour l'instant, on le passe dans l'URL de callback
    
    # Construire l'URL d'autorisation Shopify
    redirect_uri = f"{APP_URL}/auth/callback"
    
    auth_params = {
        'client_id': SHOPIFY_API_KEY,
        'scope': SCOPES,
        'redirect_uri': redirect_uri,
        'state': state,
        'grant_options[]': 'per-user'
    }
    
    auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(auth_params)}"
    
    # Rediriger vers Shopify
    return RedirectResponse(url=auth_url)


@router.get("/auth/callback")
async def oauth_callback(
    code: str = Query(None),
    shop: str = Query(None),
    state: str = Query(None),
    hmac: str = Query(None),
    request: Request = None
):
    """
    Callback OAuth - reçoit le code et échange contre access_token.
    """
    if not code or not shop:
        raise HTTPException(
            status_code=400,
            detail="Missing code or shop parameter"
        )
    
    # Normaliser le shop domain
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    # Vérifier la signature HMAC
    query_params = dict(request.query_params)
    if not verify_hmac(query_params):
        raise HTTPException(
            status_code=403,
            detail="Invalid HMAC signature"
        )
    
    # Échanger le code contre un access_token
    token_url = f"https://{shop}/admin/oauth/access_token"
    
    token_data = {
        'client_id': SHOPIFY_API_KEY,
        'client_secret': SHOPIFY_API_SECRET,
        'code': code
    }
    
    try:
        response = requests.post(token_url, json=token_data, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            print(f"❌ OAuth token exchange failed: {response.status_code} - {error_text}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to exchange OAuth code: {error_text}"
            )
        
        response.raise_for_status()
        token_response = response.json()
        
        access_token = token_response.get('access_token')
        if not access_token:
            print(f"❌ No access_token in response: {token_response}")
            raise HTTPException(
                status_code=500,
                detail="Failed to get access token from Shopify"
            )
        
        print(f"✅ Access token obtenu pour {shop}")
        
        # Sauvegarder ou mettre à jour le shop dans la DB
        db = next(get_db())
        shop_record = db.query(Shop).filter(Shop.domain == shop).first()
        
        is_new_shop = False
        if shop_record:
            # Mise à jour
            shop_record.access_token = access_token
            shop_record.is_active = True
            shop_record.last_active_at = datetime.utcnow()
            if not shop_record.installed_at:
                shop_record.installed_at = datetime.utcnow()
                is_new_shop = True
        else:
            # Nouveau shop - donner des crédits gratuits
            is_new_shop = True
            FREE_CREDITS_ON_INSTALL = 10  # Crédits gratuits à l'installation
            
            shop_record = Shop(
                domain=shop,
                access_token=access_token,
                installed_at=datetime.utcnow(),
                last_active_at=datetime.utcnow(),
                is_active=True,
                credits=FREE_CREDITS_ON_INSTALL,  # Crédits gratuits
                lifetime_credits=FREE_CREDITS_ON_INSTALL
            )
            db.add(shop_record)
            print(f"✅ Nouveau shop installé: {shop} - {FREE_CREDITS_ON_INSTALL} crédits gratuits ajoutés")
        
        db.commit()
        db.close()
        
        print(f"✅ Shop sauvegardé: {shop} - Crédits: {shop_record.credits}")
        
        # Rediriger vers l'app embedded
        # Pour une app embedded, Shopify redirige automatiquement vers application_url
        # On peut aussi rediriger directement vers l'application_url avec le shop en paramètre
        redirect_url = f"{APP_URL}?shop={shop}"
        
        return RedirectResponse(url=redirect_url)
        
    except requests.RequestException as e:
        print(f"❌ OAuth token exchange failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to exchange OAuth code: {str(e)}"
        )
    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OAuth callback error: {str(e)}"
        )


@router.get("/api/auth/callback")
async def api_oauth_callback(
    code: str = Query(None),
    shop: str = Query(None),
    state: str = Query(None),
    hmac: str = Query(None),
    request: Request = None
):
    """
    Callback OAuth alternatif (pour compatibilité).
    Même logique que /auth/callback.
    """
    return await oauth_callback(code, shop, state, hmac, request)


@router.get("/auth/shopify/callback")
async def shopify_oauth_callback(
    code: str = Query(None),
    shop: str = Query(None),
    state: str = Query(None),
    hmac: str = Query(None),
    request: Request = None
):
    """
    Callback OAuth alternatif (pour compatibilité).
    Même logique que /auth/callback.
    """
    return await oauth_callback(code, shop, state, hmac, request)
