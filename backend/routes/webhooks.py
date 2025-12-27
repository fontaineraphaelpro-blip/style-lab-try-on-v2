"""
Shopify Webhooks
================
Gère les webhooks GDPR et app lifecycle.
"""

import os
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db, Shop, TryOnLog, RateLimit, CreditPurchase

router = APIRouter()

SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")


def verify_webhook_hmac(body: bytes, hmac_header: str) -> bool:
    """
    Vérifie que le webhook vient bien de Shopify.
    """
    if not hmac_header:
        return False
    
    computed_hmac = hmac.new(
        SHOPIFY_API_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_hmac, hmac_header)


# ==========================================
# GDPR WEBHOOKS (REQUIRED)
# ==========================================

@router.post("/customers/data_request")
async def customer_data_request(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    GDPR: Customer demande ses données.
    Shopify exige une réponse dans les 30 jours.
    """
    body = await request.body()
    
    # Vérifier HMAC
    if not verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    shop_domain = data.get("shop_domain")
    customer = data.get("customer")
    
    print(f"📋 GDPR Data Request: {shop_domain} - Customer: {customer.get('id')}")
    
    # Récupérer les données du customer
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        # TODO: Récupérer les logs liés à ce customer
        # Pour l'instant, on ne stocke que les IPs (anonyme)
        
        # Envoyer les données au customer (email, API, etc.)
        # TODO: Implémenter l'envoi
        
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/customers/redact")
async def customer_redact(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    GDPR: Customer demande la suppression de ses données.
    Shopify exige une action immédiate.
    """
    body = await request.body()
    
    if not verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    shop_domain = data.get("shop_domain")
    customer = data.get("customer")
    
    print(f"🗑️  GDPR Customer Redact: {shop_domain} - Customer: {customer.get('id')}")
    
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        # Supprimer les données liées au customer
        # Note: On ne stocke que des IPs, pas d'ID customer
        # Donc peu de données à supprimer
        
        db.query(TryOnLog).filter(
            TryOnLog.shop == shop_domain,
            TryOnLog.customer_id == str(customer.get('id'))
        ).delete()
        
        db.commit()
        
        return JSONResponse({"success": True})
    except Exception as e:
        db.rollback()
        print(f"❌ Error in customer redact: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/shop/redact")
async def shop_redact(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    GDPR: Shop est supprimé (48h après uninstall).
    Supprimer TOUTES les données du shop.
    """
    body = await request.body()
    
    if not verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    shop_domain = data.get("shop_domain")
    
    print(f"🗑️  GDPR Shop Redact: {shop_domain}")
    
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        # Supprimer TOUTES les données
        db.query(TryOnLog).filter(TryOnLog.shop == shop_domain).delete()
        db.query(RateLimit).filter(RateLimit.shop == shop_domain).delete()
        db.query(CreditPurchase).filter(CreditPurchase.shop == shop_domain).delete()
        db.query(Shop).filter(Shop.domain == shop_domain).delete()
        
        db.commit()
        
        print(f"✅ Shop {shop_domain} data deleted")
        
        return JSONResponse({"success": True})
    except Exception as e:
        db.rollback()
        print(f"❌ Error in shop redact: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ==========================================
# APP LIFECYCLE
# ==========================================

@router.post("/app/uninstalled")
async def app_uninstalled(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    App désinstallée par le merchant.
    Marquer le shop comme inactif (ne pas supprimer tout de suite).
    """
    body = await request.body()
    
    if not verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    shop_domain = data.get("shop_domain")
    
    print(f"👋 App Uninstalled: {shop_domain}")
    
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        shop = db.query(Shop).filter(Shop.domain == shop_domain).first()
        
        if shop:
            shop.is_active = False
            shop.uninstalled_at = datetime.utcnow()
            db.commit()
            print(f"✅ Shop {shop_domain} marked as inactive")
        
        return JSONResponse({"success": True})
    except Exception as e:
        db.rollback()
        print(f"❌ Error in app uninstalled: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ==========================================
# TESTING (DEV ONLY)
# ==========================================

@router.post("/test")
async def test_webhook(request: Request):
    """
    Endpoint de test pour vérifier que les webhooks fonctionnent.
    À SUPPRIMER en production.
    """
    data = await request.json()
    print(f"🧪 Test Webhook received: {data}")
    return JSONResponse({"success": True, "echo": data})


# ==========================================
# BILLING WEBHOOKS
# ==========================================

@router.post("/billing/charges/activate")
async def billing_charge_activate(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    Webhook appelé quand une charge d'application est activée (acceptée).
    Active automatiquement les crédits.
    """
    body = await request.body()
    
    if not verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    charge_id = str(data.get("id"))
    shop_domain = data.get("shop_domain")
    
    print(f"💳 Billing Charge Activated: {shop_domain} - Charge: {charge_id}")
    
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        # Trouver l'achat correspondant
        purchase = db.query(CreditPurchase).filter(
            CreditPurchase.charge_id == charge_id,
            CreditPurchase.shop == shop_domain
        ).first()
        
        if purchase and purchase.status != "completed":
            # Activer les crédits
            shop = db.query(Shop).filter(Shop.domain == shop_domain).first()
            if shop:
                shop.credits += purchase.credits_purchased
                shop.lifetime_credits += purchase.credits_purchased
                purchase.status = "completed"
                purchase.activated_at = datetime.utcnow()
                db.commit()
                print(f"✅ Credits activated: {purchase.credits_purchased} credits for {shop_domain}")
            else:
                print(f"⚠️  Shop not found: {shop_domain}")
        else:
            print(f"⚠️  Purchase not found or already completed: {charge_id}")
        
        return JSONResponse({"success": True})
    except Exception as e:
        db.rollback()
        print(f"❌ Error in billing charge activate: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()