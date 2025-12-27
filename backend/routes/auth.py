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
APPLICATION_URL = os.getenv("APPLICATION_URL", "https://style-lab-try-on-v2.up.railway.app")
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
    state: str = Query(None),
    host: str = Query(None)  # Paramètre host pour apps embarquées
):
    """
    Callback OAuth après autorisation par le merchant.
    Échange le code contre un access token.
    """
    print(f"🔐 OAuth callback received - shop: {shop}, host: {host}")
    
    # Vérifier HMAC
    query_params = dict(request.query_params)
    if not verify_hmac(query_params):
        print(f"❌ HMAC verification failed")
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    
    print(f"✅ HMAC verified successfully")
    
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
        try:
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
        except Exception as db_error:
            # Log l'erreur mais continue quand même (l'app peut fonctionner sans DB)
            print(f"⚠️ Database error during OAuth callback: {db_error}")
            # Ne pas bloquer l'installation si la DB n'est pas disponible
        
        # Rediriger vers l'app embarquée
        # Pour les apps embarquées, utiliser le paramètre host de Shopify
        if host:
            # host est un token base64 fourni par Shopify pour les apps embarquées
            app_url = f"{APPLICATION_URL}/app?shop={shop}&host={host}"
        else:
            # Fallback si host n'est pas fourni
            shop_name = shop.replace('.myshopify.com', '')
            app_url = f"{APPLICATION_URL}/app?shop={shop}"
        
        print(f"✅ OAuth successful, redirecting to: {app_url}")
        
        # Redirection pour apps embarquées Shopify avec App Bridge
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Installation réussie</title>
            <meta charset="UTF-8">
            <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
            <script>
                // Attendre que App Bridge soit chargé
                function redirectToApp() {{
                    const appUrl = "{app_url}";
                    console.log("🔄 Redirecting to:", appUrl);
                    
                    // Pour les apps embarquées, utiliser App Bridge Redirect si disponible
                    if (window.AppBridge && window.AppBridge.default) {{
                        try {{
                            const app = window.AppBridge.default({{
                                apiKey: "{SHOPIFY_API_KEY or ""}",
                                host: "{host or ""}",
                                shop: "{shop}"
                            }});
                            
                            // Utiliser App Bridge Redirect pour une redirection propre
                            if (app && app.getState) {{
                                window.location.href = appUrl;
                            }} else {{
                                // Fallback: redirection standard
                                if (window.top !== window.self) {{
                                    window.top.location.href = appUrl;
                                }} else {{
                                    window.location.href = appUrl;
                                }}
                            }}
                        }} catch (error) {{
                            console.error("App Bridge error:", error);
                            // Fallback: redirection standard
                            window.location.href = appUrl;
                        }}
                    }} else {{
                        // Fallback: redirection standard si App Bridge n'est pas disponible
                        if (window.top !== window.self) {{
                            window.top.location.href = appUrl;
                        }} else {{
                            window.location.href = appUrl;
                        }}
                    }}
                }}
                
                // Essayer immédiatement
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', redirectToApp);
                }} else {{
                    redirectToApp();
                }}
                
                // Timeout de sécurité
                setTimeout(function() {{
                    if (window.location.href.indexOf('/app') === -1) {{
                        console.log("⏰ Timeout, forcing redirect");
                        window.location.href = "{app_url}";
                    }}
                }}, 2000);
            </script>
        </head>
        <body style="font-family: system-ui; text-align: center; padding: 50px; background: #f5f5f5;">
            <div style="background: white; padding: 40px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 500px; margin: 100px auto;">
                <h1 style="color: #10b981; margin-bottom: 20px;">✅ Installation réussie!</h1>
                <p style="color: #64748b; margin-bottom: 30px;">Redirection vers l'application...</p>
                <p><a href="{app_url}" style="color: #6366f1; text-decoration: none; font-weight: 500;">Cliquez ici si la redirection ne fonctionne pas</a></p>
            </div>
        </body>
        </html>
        """)
        
    except requests.RequestException as e:
        error_msg = f"Failed to exchange token: {str(e)}"
        print(f"❌ OAuth callback error: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ OAuth callback unexpected error: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


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

