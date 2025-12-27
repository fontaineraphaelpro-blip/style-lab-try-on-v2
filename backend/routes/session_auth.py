"""
Session Token Authentication
============================
Vérifie les Session Tokens Shopify pour les apps embarquées.
"""

import os
import jwt
import hmac
import hashlib
from fastapi import HTTPException, Header
from typing import Optional
from datetime import datetime, timedelta

SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")


def verify_session_token(token: str) -> dict:
    """
    Vérifie et décode un Session Token Shopify.
    
    Returns:
        dict: Payload du token (shop, exp, iss, etc.)
    
    Raises:
        HTTPException: Si le token est invalide
    """
    if not token:
        raise HTTPException(status_code=401, detail="No session token provided")
    
    try:
        # Décoder sans vérification d'abord pour obtenir l'issuer
        unverified = jwt.decode(token, options={"verify_signature": False})
        shop = unverified.get("iss", "").replace("https://", "").replace("/", "")
        
        if not shop:
            raise HTTPException(status_code=401, detail="Invalid token: no shop in issuer")
        
        # Vérifier le secret (utiliser le secret de l'app)
        # Note: En production, Shopify utilise un secret spécifique par app
        # Pour l'instant, on utilise SHOPIFY_API_SECRET
        secret = SHOPIFY_API_SECRET
        
        # Décoder avec vérification
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True}
        )
        
        # Vérifier que le token n'est pas expiré
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Token expired")
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


def get_shop_from_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Extrait et vérifie le shop depuis le Session Token.
    
    Usage:
        @router.get("/endpoint")
        async def my_endpoint(shop: str = Depends(get_shop_from_token)):
            ...
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    # Extraire le token (format: "Bearer <token>")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    
    # Vérifier le token
    payload = verify_session_token(token)
    
    # Extraire le shop depuis l'issuer
    iss = payload.get("iss", "")
    shop = iss.replace("https://", "").replace("/", "")
    
    if not shop or ".myshopify.com" not in shop:
        raise HTTPException(status_code=401, detail="Invalid shop in token")
    
    return shop

