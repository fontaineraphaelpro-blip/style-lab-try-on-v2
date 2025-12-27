"""
App Proxy Routes
================
Routes publiques accessibles via le storefront Shopify.
URL: https://SHOP.myshopify.com/apps/tryon/*

IMPORTANT: Ces routes doivent vérifier la signature HMAC Shopify.
"""

import io
import os
import base64
import time
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database import get_db, Shop, TryOnLog, RateLimit
from services.replicate_service import ReplicateService
from datetime import datetime

router = APIRouter()

# Configuration
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")


def verify_proxy_signature(query_params: dict) -> bool:
    """
    Vérifie que la requête vient bien de Shopify App Proxy.
    Shopify ajoute automatiquement une signature HMAC.
    """
    signature = query_params.pop('signature', None)
    if not signature:
        return False
    
    # Reconstruire la query string triée
    sorted_params = sorted(query_params.items())
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
    
    # Calculer le HMAC
    computed_signature = hmac.new(
        SHOPIFY_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, signature)


def extract_shop_from_proxy(query_params: dict) -> str:
    """
    Extrait le shop domain depuis les paramètres Shopify.
    Shopify injecte automatiquement: shop, path_prefix, timestamp, etc.
    """
    shop = query_params.get('shop', '')
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    return shop


# ==========================================
# WIDGET JAVASCRIPT
# ==========================================

@router.get("/widget.js")
async def serve_widget_js(request: Request):
    """
    Sert le widget JavaScript optimisé.
    Chargé de manière asynchrone sur le storefront.
    """
    
    # Widget JS optimisé (minifié en production)
    widget_code = """
(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        apiBase: window.location.origin + '/apps/tryon',
        selectors: {
            productImage: '.product__media img',
            addToCartButton: 'form[action*="/cart/add"] button[type="submit"]'
        }
    };
    
    class VTONWidget {
        constructor() {
            this.shop = window.Shopify?.shop || '';
            this.productId = this.extractProductId();
            this.productImage = this.getProductImage();
            this.settings = {
                text: 'Try It On',
                bg: '#000000',
                color: '#ffffff'
            };
            this.init();
        }
        
        async loadSettings() {
            try {
                const shopDomain = this.shop || window.location.hostname;
                if (!shopDomain) return;
                
                const settingsUrl = `${CONFIG.apiBase}/widget-settings?shop=${shopDomain}`;
                const response = await fetch(settingsUrl);
                if (response.ok) {
                    this.settings = await response.json();
                }
            } catch (error) {
                console.log('[VTON] Could not load settings, using defaults');
            }
        }
        
        darkenColor(color, percent) {
            // Convertir hex en RGB
            const num = parseInt(color.replace('#', ''), 16);
            const r = Math.max(0, (num >> 16) - percent);
            const g = Math.max(0, ((num >> 8) & 0x00FF) - percent);
            const b = Math.max(0, (num & 0x0000FF) - percent);
            return '#' + ((r << 16) | (g << 8) | b).toString(16).padStart(6, '0');
        }
        
        extractProductId() {
            const meta = document.querySelector('meta[property="og:url"]');
            if (meta) {
                const match = meta.content.match(/products\/([^?]+)/);
                return match ? match[1] : null;
            }
            return null;
        }
        
        getProductImage() {
            const img = document.querySelector(CONFIG.selectors.productImage);
            return img ? img.src : null;
        }
        
        async init() {
            if (!this.productId || !this.productImage) {
                console.log('[VTON] Not a product page, skipping...');
                return;
            }
            
            // Charger les paramètres personnalisés
            await this.loadSettings();
            
            window.addEventListener('DOMContentLoaded', () => {
                this.injectButton();
            });
        }
        
        injectButton() {
            const addToCartBtn = document.querySelector(CONFIG.selectors.addToCartButton);
            if (!addToCartBtn) return;
            
            const vtonBtn = document.createElement('button');
            vtonBtn.type = 'button';
            vtonBtn.className = 'vton-button';
            vtonBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2"/>
                    <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2"/>
                    <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2"/>
                </svg>
                <span>${this.settings.text || 'Try It On'}</span>
            `;
            // Appliquer les couleurs personnalisées
            vtonBtn.style.backgroundColor = this.settings.bg || '#000000';
            vtonBtn.style.color = this.settings.color || '#ffffff';
            vtonBtn.onclick = () => this.openModal();
            
            // Insérer après le bouton Add to Cart
            addToCartBtn.parentElement.insertAdjacentElement('afterend', vtonBtn);
            
            // Injecter les styles
            this.injectStyles();
        }
        
        injectStyles() {
            if (document.getElementById('vton-styles')) return;
            
            const styles = document.createElement('style');
            styles.id = 'vton-styles';
            // Calculer la couleur hover (assombrir de 20%)
            const bgColor = this.settings.bg || '#000000';
            const hoverColor = this.darkenColor(bgColor, 20);
            
            styles.textContent = `
                .vton-button {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    width: 100%;
                    padding: 12px 24px;
                    margin-top: 12px;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                    justify-content: center;
                }
                .vton-button:hover {
                    background: ${hoverColor} !important;
                    transform: translateY(-1px);
                    opacity: 0.9;
                }
                .vton-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.8);
                    display: none;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                }
                .vton-modal.active {
                    display: flex;
                }
                .vton-modal-content {
                    background: white;
                    border-radius: 12px;
                    padding: 32px;
                    max-width: 600px;
                    width: 90%;
                    max-height: 90vh;
                    overflow-y: auto;
                }
            `;
            document.head.appendChild(styles);
        }
        
        openModal() {
            // Créer la modal si elle n'existe pas
            let modal = document.getElementById('vton-modal');
            if (!modal) {
                modal = this.createModal();
                document.body.appendChild(modal);
            }
            modal.classList.add('active');
        }
        
        createModal() {
            const modal = document.createElement('div');
            modal.id = 'vton-modal';
            modal.className = 'vton-modal';
            modal.innerHTML = `
                <div class="vton-modal-content">
                    <h2>Virtual Try-On</h2>
                    <div class="vton-upload-area">
                        <label for="vton-photo-upload">
                            <div class="upload-box">
                                <svg width="48" height="48" viewBox="0 0 24 24">
                                    <path d="M12 4L12 20M4 12L20 12" stroke="#666" stroke-width="2"/>
                                </svg>
                                <p>Upload your photo</p>
                            </div>
                        </label>
                        <input type="file" id="vton-photo-upload" accept="image/*" style="display:none;">
                    </div>
                    <div id="vton-preview" style="display:none;">
                        <img id="vton-preview-img" src="" alt="Preview">
                    </div>
                    <button id="vton-generate-btn" class="vton-button" disabled>
                        Generate Try-On
                    </button>
                    <div id="vton-result" style="display:none;">
                        <img id="vton-result-img" src="" alt="Result">
                    </div>
                    <button class="vton-close" onclick="document.getElementById('vton-modal').classList.remove('active')">
                        Close
                    </button>
                </div>
            `;
            
            // Event listeners
            const uploadInput = modal.querySelector('#vton-photo-upload');
            const generateBtn = modal.querySelector('#vton-generate-btn');
            
            uploadInput.addEventListener('change', (e) => this.handlePhotoUpload(e));
            generateBtn.addEventListener('click', () => this.generateTryOn());
            
            return modal;
        }
        
        handlePhotoUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                this.userPhoto = e.target.result;
                
                const preview = document.getElementById('vton-preview');
                const previewImg = document.getElementById('vton-preview-img');
                previewImg.src = e.target.result;
                preview.style.display = 'block';
                
                document.getElementById('vton-generate-btn').disabled = false;
            };
            reader.readAsDataURL(file);
        }
        
        async generateTryOn() {
            const btn = document.getElementById('vton-generate-btn');
            btn.disabled = true;
            btn.textContent = 'Generating...';
            
            try {
                // Convertir en base64 sans préfixe
                const personBase64 = this.userPhoto.split(',')[1];
                
                const response = await fetch(`${CONFIG.apiBase}/generate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        person_image_base64: personBase64,
                        clothing_url: this.productImage,
                        product_id: this.productId
                    })
                });
                
                if (response.status === 402) {
                    alert('This shop has run out of credits. Please contact the store owner.');
                    btn.textContent = 'Generate Try-On';
                    btn.disabled = false;
                    return;
                }
                
                if (response.status === 429) {
                    alert('Daily limit reached. Please try again tomorrow.');
                    btn.textContent = 'Generate Try-On';
                    btn.disabled = false;
                    return;
                }
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Generation failed');
                }
                
                const data = await response.json();
                
                // Afficher le résultat
                const resultDiv = document.getElementById('vton-result');
                const resultImg = document.getElementById('vton-result-img');
                const shopBtn = document.getElementById('vton-shop-btn');
                
                resultImg.src = data.result_image_url;
                resultDiv.style.display = 'block';
                
                // Afficher le bouton "Shop This Look"
                if (shopBtn) {
                    shopBtn.style.display = 'block';
                    shopBtn.onclick = () => {
                        // Trouver le bouton Add to Cart et cliquer dessus
                        const addToCartBtn = document.querySelector(CONFIG.selectors.addToCartButton);
                        if (addToCartBtn) {
                            addToCartBtn.click();
                        }
                        // Fermer la modal
                        document.getElementById('vton-modal').classList.remove('active');
                    };
                }
                
                btn.textContent = 'Generate Another';
                btn.disabled = false;
                
            } catch (error) {
                console.error('[VTON] Error:', error);
                alert('An error occurred. Please try again.');
                btn.textContent = 'Generate Try-On';
                btn.disabled = false;
            }
        }
    }
    
    // Initialiser le widget
    new VTONWidget();
})();
"""
    
    return Response(
        content=widget_code,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )


# ==========================================
# GENERATION ENDPOINT (PUBLIC)
# ==========================================

class GenerateRequest(BaseModel):
    person_image_base64: str
    clothing_url: Optional[str] = None
    clothing_file_base64: Optional[str] = None
    product_id: Optional[str] = None


@router.post("/generate")
async def generate_tryon(
    request: Request,
    body: GenerateRequest
):
    """
    Génère un virtual try-on depuis le storefront.
    Cette route est appelée via l'App Proxy Shopify.
    """
    start_time = time.time()
    
    # 1. Extraire le shop depuis les query params
    query_params = dict(request.query_params)
    
    # 2. Vérifier la signature Shopify (CRITICAL)
    if not verify_proxy_signature(query_params.copy()):
        raise HTTPException(
            status_code=403,
            detail="Invalid signature - request not from Shopify"
        )
    
    shop = extract_shop_from_proxy(query_params)
    if not shop:
        raise HTTPException(status_code=400, detail="Shop parameter missing")
    
    # 3. Récupérer la config du shop
    db = next(get_db())
    shop_record = db.query(Shop).filter(Shop.domain == shop).first()
    
    if not shop_record:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # 4. Vérifier les crédits
    if shop_record.credits < 1:
        return JSONResponse(
            {"error": "Insufficient credits", "credits": 0},
            status_code=402
        )
    
    # 5. Rate limiting par IP
    client_ip = request.client.host
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    rate_limit = db.query(RateLimit).filter(
        RateLimit.shop == shop,
        RateLimit.customer_ip == client_ip,
        RateLimit.date == today
    ).first()
    
    if not rate_limit:
        rate_limit = RateLimit(shop=shop, customer_ip=client_ip, date=today, count=0)
        db.add(rate_limit)
    
    if rate_limit.count >= shop_record.max_tries_per_user:
        return JSONResponse(
            {"error": "Daily limit reached", "limit": shop_record.max_tries_per_user},
            status_code=429
        )
    
    try:
        # 6. Préparer les images
        person_bytes = base64.b64decode(body.person_image_base64)
        person_file = io.BytesIO(person_bytes)
        
        garment_input = None
        if body.clothing_file_base64:
            garment_bytes = base64.b64decode(body.clothing_file_base64)
            garment_input = io.BytesIO(garment_bytes)
        elif body.clothing_url:
            garment_input = body.clothing_url
            if garment_input.startswith("//"):
                garment_input = "https:" + garment_input
        else:
            raise HTTPException(status_code=400, detail="No garment provided")
        
        # 7. Générer le try-on via Replicate
        result_url = ReplicateService.generate_tryon(
            person_image=person_file,
            garment_image=garment_input,
            category="upper_body"
        )
        
        # 8. Mettre à jour les stats
        shop_record.credits -= 1
        shop_record.total_tryons += 1
        rate_limit.count += 1
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        log = TryOnLog(
            shop=shop,
            customer_ip=client_ip,
            product_id=body.product_id,
            success=True,
            latency_ms=latency_ms,
            result_image_url=result_url
        )
        db.add(log)
        db.commit()
        
        return JSONResponse({
            "result_image_url": result_url,
            "credits_remaining": shop_record.credits,
            "generation_time_ms": latency_ms
        })
        
    except Exception as e:
        # Log l'erreur
        latency_ms = int((time.time() - start_time) * 1000)
        log = TryOnLog(
            shop=shop,
            customer_ip=client_ip,
            product_id=body.product_id,
            success=False,
            error_message=str(e),
            latency_ms=latency_ms
        )
        db.add(log)
        db.commit()
        
        return JSONResponse(
            {"error": "Generation failed", "message": str(e)},
            status_code=500
        )