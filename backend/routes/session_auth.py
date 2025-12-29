"""
Shopify Session Token Authentication
=====================================
Vérifie les Session Tokens JWT pour les requêtes admin.

Les apps Shopify embedded utilisent des Session Tokens JWT signés par Shopify
pour authentifier les requêtes depuis l'iframe.
"""

import os
import jwt
import requests
from fastapi import HTTPException, Request
from typing import Optional

SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")

# Cache pour les clés publiques Shopify (éviter de les récupérer à chaque requête)
_shopify_public_keys_cache = {}


def get_shopify_public_key(shop: str) -> str:
    """
    Récupère la clé publique Shopify pour vérifier les Session Tokens.
    """
    # Utiliser le cache si disponible
    if shop in _shopify_public_keys_cache:
        return _shopify_public_keys_cache[shop]
    
    try:
        # Récupérer la clé publique depuis Shopify
        url = f"https://{shop}/admin/api/unstable/public_keys.json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        # Shopify retourne une liste de clés, prendre la première
        public_key = data.get("public_keys", [{}])[0].get("public_key")
        
        if public_key:
            _shopify_public_keys_cache[shop] = public_key
            return public_key
    except Exception as e:
        print(f"⚠️  Error fetching Shopify public key: {e}")
    
    return None


def verify_session_token(token: str, shop: str) -> dict:
    """
    Vérifie un Session Token JWT Shopify.
    
    Args:
        token: Le Session Token JWT
        shop: Le domaine du shop (ex: mystore.myshopify.com)
        
    Returns:
        dict: Les claims du token (iss, dest, aud, sub, exp, nbf, iat, sid, etc.)
        
    Raises:
        HTTPException: Si le token est invalide
    """
    if not token:
        raise HTTPException(status_code=401, detail="No session token provided")
    
    try:
        # Décoder le token sans vérification d'abord pour obtenir le shop
        unverified = jwt.decode(token, options={"verify_signature": False})
        
        # Le shop est dans 'dest' (destination)
        token_shop = unverified.get("dest", "").replace("https://", "").replace("/", "")
        
        if not token_shop:
            raise HTTPException(status_code=401, detail="Invalid token: no shop in token")
        
        # Normaliser le shop
        if not token_shop.endswith('.myshopify.com'):
            token_shop = f"{token_shop}.myshopify.com"
        
        # Vérifier que le shop correspond
        if shop and shop != token_shop:
            raise HTTPException(status_code=401, detail="Token shop mismatch")
        
        # Récupérer la clé publique Shopify
        public_key = get_shopify_public_key(token_shop)
        
        if not public_key:
            # Fallback: utiliser le secret API (pour les tokens plus anciens)
            # Note: Les Session Tokens modernes nécessitent la clé publique
            print(f"⚠️  Using API secret as fallback for {token_shop}")
            try:
                decoded = jwt.decode(
                    token,
                    SHOPIFY_API_SECRET,
                    algorithms=["HS256"],
                    audience=SHOPIFY_API_KEY
                )
                return decoded
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=401, detail="Invalid session token (fallback failed)")
        
        # Vérifier le token avec la clé publique
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=SHOPIFY_API_KEY,
            issuer=f"https://{token_shop}",
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True
            }
        )
        
        return decoded
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session token: {str(e)}")
    except Exception as e:
        print(f"❌ Session token verification error: {e}")
        raise HTTPException(status_code=401, detail="Session token verification failed")


def get_shop_from_session_token(request: Request) -> Optional[str]:
    """
    Extrait le shop depuis le Session Token ou les query params.
    """
    # Essayer d'abord depuis le token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            shop = unverified.get("dest", "").replace("https://", "").replace("/", "")
            if shop:
                return shop
        except:
            pass
    
    # Fallback: query params
    shop = request.query_params.get("shop")
    if shop:
        if not shop.endswith('.myshopify.com'):
            shop = f"{shop}.myshopify.com"
        return shop
    
    return None
