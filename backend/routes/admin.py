"""
Admin Dashboard API
===================
Routes pour le dashboard admin avec analytics avancées.
"""

import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

from database import get_db, Shop, TryOnLog, RateLimit, CreditPurchase

router = APIRouter()


# ==========================================
# MODELS
# ==========================================

class SettingsRequest(BaseModel):
    text: str
    bg: str
    color: str
    max_tries: int


class BillingRequest(BaseModel):
    pack_id: str
    custom_amount: Optional[int] = None


# ==========================================
# AUTHENTICATION
# ==========================================

def get_authenticated_shop(
    request: Request,
    db: Session = Depends(get_db)
) -> Shop:
    """
    Authentifie les requêtes admin via Session Token.
    """
    # Extraire le shop depuis les query params (temporaire)
    shop_domain = request.query_params.get("shop")
    
    if not shop_domain:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: No shop parameter"
        )
    
    shop = db.query(Shop).filter(Shop.domain == shop_domain).first()
    
    if not shop or not shop.is_active:
        raise HTTPException(
            status_code=404,
            detail="Shop not found or inactive"
        )
    
    # Mettre à jour last_active_at
    shop.last_active_at = datetime.utcnow()
    db.commit()
    
    return shop


# ==========================================
# DASHBOARD PRINCIPAL
# ==========================================

@router.get("/dashboard")
async def get_dashboard(
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Retourne toutes les données du dashboard.
    Inclut : crédits, stats, analytics, widget config.
    """
    now = datetime.utcnow()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # === STATS GLOBALES ===
    total_tryons = shop.total_tryons
    total_atc = shop.total_atc
    conversion_rate = (
        (total_atc / total_tryons * 100)
        if total_tryons > 0 else 0
    )
    
    # === LOGS RÉCENTS ===
    logs_today = db.query(TryOnLog).filter(
        TryOnLog.shop == shop.domain,
        func.date(TryOnLog.created_at) == today
    ).all()
    
    logs_yesterday = db.query(TryOnLog).filter(
        TryOnLog.shop == shop.domain,
        func.date(TryOnLog.created_at) == yesterday
    ).all()
    
    logs_week = db.query(TryOnLog).filter(
        TryOnLog.shop == shop.domain,
        TryOnLog.created_at >= week_ago
    ).all()
    
    logs_month = db.query(TryOnLog).filter(
        TryOnLog.shop == shop.domain,
        TryOnLog.created_at >= month_ago
    ).all()
    
    # === ANALYTICS ===
    tryons_today = len(logs_today)
    tryons_yesterday = len(logs_yesterday)
    tryons_week = len(logs_week)
    tryons_month = len(logs_month)
    
    # Variation jour/jour
    change_vs_yesterday = (
        ((tryons_today - tryons_yesterday) / tryons_yesterday * 100)
        if tryons_yesterday > 0 else 0
    )
    
    # Latence moyenne
    latencies = [log.latency_ms for log in logs_month if log.latency_ms]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    # Taux d'erreur
    failed_month = len([log for log in logs_month if not log.success])
    error_rate = (
        (failed_month / len(logs_month) * 100)
        if logs_month else 0
    )
    
    # === TOP PRODUITS ===
    top_products = (
        db.query(
            TryOnLog.product_id,
            func.count(TryOnLog.id).label('count')
        )
        .filter(
            TryOnLog.shop == shop.domain,
            TryOnLog.success == True,
            TryOnLog.product_id.isnot(None)
        )
        .group_by(TryOnLog.product_id)
        .order_by(desc('count'))
        .limit(10)
        .all()
    )
    
    # === PRÉVISIONS CRÉDITS ===
    daily_burn_rate = tryons_month / 30 if tryons_month > 0 else 0
    days_remaining = shop.credits / daily_burn_rate if daily_burn_rate > 0 else 999
    
    # === VIP STATUS ===
    vip_threshold = 500
    vip_progress = min(shop.lifetime_credits / vip_threshold * 100, 100)
    is_vip = shop.lifetime_credits >= vip_threshold
    
    return {
        "shop": {
            "domain": shop.domain,
            "installed_at": shop.installed_at.isoformat(),
            "is_vip": is_vip
        },
        "billing": {
            "credits": shop.credits,
            "lifetime_credits": shop.lifetime_credits,
            "daily_burn_rate": round(daily_burn_rate, 2),
            "days_remaining": int(days_remaining),
            "vip_progress": round(vip_progress, 1)
        },
        "usage": {
            "total_tryons": total_tryons,
            "total_atc": total_atc,
            "conversion_rate": round(conversion_rate, 2),
            "tryons_today": tryons_today,
            "tryons_yesterday": tryons_yesterday,
            "tryons_week": tryons_week,
            "tryons_month": tryons_month,
            "change_vs_yesterday": round(change_vs_yesterday, 1)
        },
        "performance": {
            "avg_latency_ms": int(avg_latency),
            "error_rate": round(error_rate, 2),
            "success_rate": round(100 - error_rate, 2)
        },
        "top_products": [
            {
                "product_id": p.product_id,
                "tryons": p.count
            }
            for p in top_products
        ],
        "widget": {
            "text": shop.widget_text,
            "bg": shop.widget_bg,
            "color": shop.widget_color
        },
        "settings": {
            "max_tries_per_user": shop.max_tries_per_user
        }
    }


# ==========================================
# ANALYTICS DÉTAILLÉES
# ==========================================

@router.get("/analytics/daily")
async def get_daily_analytics(
    days: int = 30,
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Retourne les analytics jour par jour.
    """
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    
    daily_data = (
        db.query(
            func.date(TryOnLog.created_at).label('date'),
            func.count(TryOnLog.id).label('total'),
            func.count(TryOnLog.id).filter(TryOnLog.success == True).label('successful'),
            func.avg(TryOnLog.latency_ms).label('avg_latency')
        )
        .filter(
            TryOnLog.shop == shop.domain,
            func.date(TryOnLog.created_at) >= start_date
        )
        .group_by(func.date(TryOnLog.created_at))
        .order_by(func.date(TryOnLog.created_at))
        .all()
    )
    
    return {
        "period": {
            "start": str(start_date),
            "end": str(end_date),
            "days": days
        },
        "data": [
            {
                "date": str(row.date),
                "tryons": row.total,
                "successful": row.successful,
                "failed": row.total - row.successful,
                "avg_latency_ms": int(row.avg_latency) if row.avg_latency else 0
            }
            for row in daily_data
        ]
    }


@router.get("/analytics/products")
async def get_product_analytics(
    limit: int = 20,
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Retourne les produits les plus essayés avec stats.
    """
    products = (
        db.query(
            TryOnLog.product_id,
            func.count(TryOnLog.id).label('total_tryons'),
            func.count(TryOnLog.id).filter(TryOnLog.success == True).label('successful'),
            func.avg(TryOnLog.latency_ms).label('avg_latency')
        )
        .filter(
            TryOnLog.shop == shop.domain,
            TryOnLog.product_id.isnot(None)
        )
        .group_by(TryOnLog.product_id)
        .order_by(desc('total_tryons'))
        .limit(limit)
        .all()
    )
    
    return {
        "products": [
            {
                "product_id": p.product_id,
                "total_tryons": p.total_tryons,
                "successful": p.successful,
                "failed": p.total_tryons - p.successful,
                "success_rate": round(p.successful / p.total_tryons * 100, 1),
                "avg_latency_ms": int(p.avg_latency) if p.avg_latency else 0
            }
            for p in products
        ]
    }


@router.get("/analytics/customers")
async def get_customer_analytics(
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Retourne les stats par client (anonymisées).
    """
    customer_data = (
        db.query(
            TryOnLog.customer_ip,
            func.count(TryOnLog.id).label('tryons'),
            func.max(TryOnLog.created_at).label('last_tryon')
        )
        .filter(
            TryOnLog.shop == shop.domain,
            TryOnLog.customer_ip.isnot(None)
        )
        .group_by(TryOnLog.customer_ip)
        .order_by(desc('tryons'))
        .limit(50)
        .all()
    )
    
    # Statistiques globales
    total_customers = len(customer_data)
    avg_tryons_per_customer = (
        shop.total_tryons / total_customers
        if total_customers > 0 else 0
    )
    
    return {
        "summary": {
            "total_customers": total_customers,
            "avg_tryons_per_customer": round(avg_tryons_per_customer, 1)
        },
        "top_customers": [
            {
                "customer_hash": hashlib.sha256(c.customer_ip.encode()).hexdigest()[:12],
                "tryons": c.tryons,
                "last_tryon": c.last_tryon.isoformat()
            }
            for c in customer_data[:20]
        ]
    }


# ==========================================
# SETTINGS
# ==========================================

@router.post("/settings")
async def save_settings(
    request: SettingsRequest,
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Sauvegarde les paramètres du widget et de sécurité.
    """
    shop.widget_text = request.text
    shop.widget_bg = request.bg
    shop.widget_color = request.color
    shop.max_tries_per_user = request.max_tries
    
    db.commit()
    
    return {
        "success": True,
        "message": "Settings saved successfully"
    }


# ==========================================
# BILLING
# ==========================================

@router.post("/buy-credits")
async def initiate_credit_purchase(
    request: BillingRequest,
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Initie un achat de crédits via Shopify Billing API.
    
    Packs disponibles:
    - pack_10: 10 crédits = 4.99€
    - pack_30: 30 crédits = 12.99€ (BEST VALUE)
    - pack_100: 100 crédits = 29.99€
    - pack_custom: X crédits = prix dynamique
    """
    
    PACKS = {
        "pack_10": {"credits": 10, "price": 4.99},
        "pack_30": {"credits": 30, "price": 12.99},
        "pack_100": {"credits": 100, "price": 29.99},
    }
    
    if request.pack_id == "pack_custom":
        if not request.custom_amount or request.custom_amount < 10:
            raise HTTPException(
                status_code=400,
                detail="Custom amount must be at least 10 credits"
            )
        credits = request.custom_amount
        price = credits * 0.35  # 0.35€ par crédit en bulk
    else:
        pack = PACKS.get(request.pack_id)
        if not pack:
            raise HTTPException(status_code=400, detail="Invalid pack_id")
        credits = pack["credits"]
        price = pack["price"]
    
    # TODO: Implémenter Shopify Billing API
    # Pour l'instant, retourner une URL de test
    
    purchase = CreditPurchase(
        shop=shop.domain,
        credits_purchased=credits,
        amount_usd=price,
        status='pending'
    )
    db.add(purchase)
    db.commit()
    
    # Utiliser l'URL de l'app depuis les variables d'environnement ou construire dynamiquement
    import os
    app_url = os.getenv("APP_URL", "https://style-lab-try-on-v2-production.up.railway.app")
    
    return {
        "success": True,
        "purchase_id": purchase.id,
        "credits": credits,
        "price_usd": price,
        "confirmation_url": f"{app_url}/billing/confirm?id={purchase.id}"
    }


@router.post("/track-atc")
async def track_add_to_cart(
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Track un événement Add to Cart après un try-on.
    """
    shop.total_atc += 1
    db.commit()
    
    return {"success": True, "total_atc": shop.total_atc}


# ==========================================
# LOGS & DEBUG
# ==========================================

@router.get("/logs/recent")
async def get_recent_logs(
    limit: int = 50,
    shop: Shop = Depends(get_authenticated_shop),
    db: Session = Depends(get_db)
):
    """
    Retourne les logs récents pour debug.
    """
    logs = (
        db.query(TryOnLog)
        .filter(TryOnLog.shop == shop.domain)
        .order_by(TryOnLog.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return {
        "logs": [
            {
                "id": log.id,
                "product_id": log.product_id,
                "success": log.success,
                "error_message": log.error_message,
                "latency_ms": log.latency_ms,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
    }