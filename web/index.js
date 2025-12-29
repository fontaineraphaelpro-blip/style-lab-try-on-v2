// @ts-check
import { join } from "path";
import { readFileSync } from "fs";
import express from "express";
import serveStatic from "serve-static";

import shopify from "./shopify.js";
import productCreator from "./product-creator.js";
import PrivacyWebhookHandlers from "./privacy.js";

// ==========================================
// TRY-ON MODULES (INTÉGRATION)
// ==========================================
// Ces modules ajoutent la logique try-on sans modifier OAuth/tokens/DB du template
import * as tryonService from "./tryon-service.js";
import * as tryonDb from "./tryon-db.js";

const PORT = parseInt(
  process.env.BACKEND_PORT || process.env.PORT || "3000",
  10
);

const STATIC_PATH =
  process.env.NODE_ENV === "production"
    ? `${process.cwd()}/frontend/dist`
    : `${process.cwd()}/frontend/`;

const app = express();

// Set up Shopify authentication and webhook handling
app.get(shopify.config.auth.path, shopify.auth.begin());
app.get(
  shopify.config.auth.callbackPath,
  shopify.auth.callback(),
  shopify.redirectToShopifyOrAppRoot()
);
app.post(
  shopify.config.webhooks.path,
  shopify.processWebhooks({ webhookHandlers: PrivacyWebhookHandlers })
);

// If you are adding routes outside of the /api path, remember to
// also add a proxy rule for them in web/frontend/vite.config.js

app.use("/api/*", shopify.validateAuthenticatedSession());

app.use(express.json());

app.get("/api/products/count", async (_req, res) => {
  const client = new shopify.api.clients.Graphql({
    session: res.locals.shopify.session,
  });

  const countData = await client.request(`
    query shopifyProductCount {
      productsCount {
        count
      }
    }
  `);

  res.status(200).send({ count: countData.data.productsCount.count });
});

app.post("/api/products", async (_req, res) => {
  let status = 200;
  let error = null;

  try {
    await productCreator(res.locals.shopify.session);
  } catch (e) {
    console.log(`Failed to process products/create: ${e.message}`);
    status = 500;
    error = e.message;
  }
  res.status(status).send({ success: status === 200, error });
});

// ==========================================
// TRY-ON ROUTES (INTÉGRATION)
// ==========================================
// Ces routes utilisent res.locals.shopify.session du template
// pour obtenir le shop authentifié. Ne modifie PAS le flow OAuth.

// Note: L'initialisation du shop dans la DB try-on se fait automatiquement
// lors de la première utilisation via getOrCreateShop() dans les routes API.
// Le template gère déjà l'OAuth et les sessions, on n'a pas besoin de l'intercepter.

// Dashboard - Récupère les stats
app.get("/api/get-data", async (req, res) => {
  try {
    const session = res.locals.shopify.session;
    const shopDomain = session.shop;
    const accessToken = session.accessToken;
    
    // Initialiser le shop s'il n'existe pas encore
    tryonDb.getOrCreateShop(shopDomain, accessToken);
    
    const stats = tryonDb.getDashboardStats(shopDomain);
    if (!stats) {
      return res.status(404).json({ error: "Shop not found" });
    }

    res.json({
      credits: stats.billing.credits,
      lifetime: stats.billing.lifetime_credits,
      usage: stats.usage.total_tryons,
      atc: stats.usage.total_atc,
      widget: stats.widget,
      security: stats.settings,
    });
  } catch (error) {
    console.error("Error in /api/get-data:", error);
    res.status(500).json({ error: error.message });
  }
});

// Sauvegarder les paramètres du widget
app.post("/api/save-settings", async (req, res) => {
  try {
    const session = res.locals.shopify.session;
    const shopDomain = session.shop;
    const accessToken = session.accessToken;
    
    // Initialiser le shop s'il n'existe pas encore
    tryonDb.getOrCreateShop(shopDomain, accessToken);
    
    const { text, bg, color, max_tries } = req.body;
    tryonDb.updateWidgetSettings(shopDomain, { text, bg, color, max_tries });
    
    res.json({ success: true, message: "Settings saved successfully" });
  } catch (error) {
    console.error("Error in /api/save-settings:", error);
    res.status(500).json({ error: error.message });
  }
});

// Acheter des crédits
app.post("/api/buy-credits", async (req, res) => {
  try {
    const session = res.locals.shopify.session;
    const shopDomain = session.shop;
    const accessToken = session.accessToken;
    
    // Initialiser le shop s'il n'existe pas encore
    const shop = tryonDb.getOrCreateShop(shopDomain, accessToken);
    
    if (!shop) {
      return res.status(404).json({ error: "Shop not found" });
    }

    const { pack_id, custom_amount } = req.body;
    
    const PACKS = {
      pack_10: { credits: 10, price: 4.99 },
      pack_30: { credits: 30, price: 12.99 },
      pack_100: { credits: 100, price: 29.99 },
    };

    let credits, price;
    if (pack_id === "pack_custom") {
      if (!custom_amount || custom_amount < 10) {
        return res.status(400).json({ error: "Custom amount must be at least 10 credits" });
      }
      credits = custom_amount;
      price = credits * 0.35;
    } else {
      const pack = PACKS[pack_id];
      if (!pack) {
        return res.status(400).json({ error: "Invalid pack_id" });
      }
      credits = pack.credits;
      price = pack.price;
    }

    // Créer l'enregistrement d'achat
    const purchase = tryonDb.createCreditPurchase({
      shop: shopDomain,
      credits_purchased: credits,
      amount_usd: price,
      status: "pending",
    });

    // Créer une charge Shopify (One-time application charge)
    const APP_URL = process.env.APP_URL || process.env.SHOPIFY_APP_URL || "http://localhost:3000";
    const shopifyUrl = `https://${shopDomain}/admin/api/2025-01/application_charges.json`;
    
    const chargeData = {
      application_charge: {
        name: `VTON Credits - ${credits} credits`,
        price: price,
        return_url: `${APP_URL}/api/billing/confirm?purchase_id=${purchase.id}`,
      },
    };

    const response = await fetch(shopifyUrl, {
      method: "POST",
      headers: {
        "X-Shopify-Access-Token": shop.access_token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(chargeData),
    });

    if (!response.ok) {
      throw new Error(`Shopify API error: ${response.statusText}`);
    }

    const chargeResult = await response.json();
    const charge = chargeResult.application_charge;
    
    // Mettre à jour l'achat avec le charge_id
    tryonDb.updatePurchaseStatus(purchase.id, "pending");

    res.json({
      success: true,
      purchase_id: purchase.id,
      credits,
      price_usd: price,
      confirmation_url: charge.confirmation_url,
    });
  } catch (error) {
    console.error("Error in /api/buy-credits:", error);
    res.status(500).json({ error: error.message });
  }
});

// Confirmation de paiement
app.get("/api/billing/confirm", async (req, res) => {
  try {
    const { purchase_id, charge_id } = req.query;
    
    const purchase = tryonDb.getPurchase(purchase_id, charge_id);
    if (!purchase) {
      return res.status(404).send("<h1>Purchase not found</h1>");
    }

    const shop = tryonDb.getShop(purchase.shop);
    if (!shop) {
      return res.status(404).send("<h1>Shop not found</h1>");
    }

    // Vérifier le statut de la charge Shopify
    if (purchase.charge_id) {
      const shopifyUrl = `https://${purchase.shop}/admin/api/2025-01/application_charges/${purchase.charge_id}.json`;
      
      const response = await fetch(shopifyUrl, {
        headers: {
          "X-Shopify-Access-Token": shop.access_token,
        },
      });

      if (response.ok) {
        const chargeData = await response.json();
        const charge = chargeData.application_charge;
        
        if (charge.status === "accepted") {
          // Activer les crédits
          if (purchase.status !== "completed") {
            tryonDb.updateShopCredits(purchase.shop, purchase.credits_purchased);
            tryonDb.updatePurchaseStatus(purchase.id, "completed", new Date().toISOString());
          }
          
          return res.send(`
            <html>
            <head><title>Payment Confirmed</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
              <h1 style="color: green;">✅ Payment Confirmed!</h1>
              <p>You have successfully purchased <strong>${purchase.credits_purchased} credits</strong>.</p>
              <p>Your credits have been added to your account.</p>
              <p><a href="/">Return to Dashboard</a></p>
            </body>
            </html>
          `);
        } else if (charge.status === "declined") {
          tryonDb.updatePurchaseStatus(purchase.id, "failed");
          return res.status(400).send("<h1>Payment Declined</h1>");
        }
      }
    }

    res.send(`
      <html>
      <head><title>Payment Processing</title></head>
      <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>⏳ Payment Processing</h1>
        <p>Your payment is being processed. Credits will be added automatically once confirmed.</p>
        <p><a href="/">Return to Dashboard</a></p>
      </body>
      </html>
    `);
  } catch (error) {
    console.error("Error in /api/billing/confirm:", error);
    res.status(500).send(`<h1>Error</h1><p>${error.message}</p>`);
  }
});

// Track Add to Cart
app.post("/api/track-atc", async (req, res) => {
  try {
    const session = res.locals.shopify.session;
    const shopDomain = session.shop;
    
    tryonDb.incrementATC(shopDomain);
    const shop = tryonDb.getShop(shopDomain);
    
    res.json({ success: true, total_atc: shop.total_atc });
  } catch (error) {
    console.error("Error in /api/track-atc:", error);
    res.status(500).json({ error: error.message });
  }
});

// Générer un try-on (admin mode)
app.post("/api/generate", async (req, res) => {
  const startTime = Date.now();
  
  try {
    const session = res.locals.shopify.session;
    const shopDomain = session.shop;
    const accessToken = session.accessToken;
    
    // Initialiser le shop s'il n'existe pas encore
    const shop = tryonDb.getOrCreateShop(shopDomain, accessToken);
    
    if (!shop) {
      return res.status(404).json({ error: "Shop not found" });
    }

    if (shop.credits < 1) {
      return res.status(402).json({ error: "Insufficient credits", credits: 0 });
    }

    const { person_image_base64, clothing_url, clothing_file_base64, product_id } = req.body;

    if (!person_image_base64) {
      return res.status(400).json({ error: "person_image_base64 is required" });
    }

    // Préparer les images
    const personBuffer = Buffer.from(person_image_base64, "base64");
    const garmentInput = clothing_file_base64 
      ? Buffer.from(clothing_file_base64, "base64")
      : clothing_url;

    if (!garmentInput) {
      return res.status(400).json({ error: "No garment provided" });
    }

    // Générer le try-on
    const resultUrl = await tryonService.generateTryOn(
      personBuffer,
      garmentInput,
      "upper_body"
    );

    // Mettre à jour les stats
    tryonDb.updateShopCredits(shopDomain, -1);
    tryonDb.incrementTryOns(shopDomain);

    const latencyMs = Date.now() - startTime;

    tryonDb.createTryOnLog({
      shop: shopDomain,
      product_id: product_id || null,
      success: true,
      latency_ms: latencyMs,
      result_image_url: resultUrl,
    });

    const updatedShop = tryonDb.getShop(shopDomain);

    res.json({
      result_image_url: resultUrl,
      credits_remaining: updatedShop.credits,
      generation_time_ms: latencyMs,
    });
  } catch (error) {
    console.error("Error in /api/generate:", error);
    
    const latencyMs = Date.now() - startTime;
    const session = res.locals.shopify?.session;
    const shopDomain = session?.shop;

    if (shopDomain) {
      tryonDb.createTryOnLog({
        shop: shopDomain,
        success: false,
        error_message: error.message,
        latency_ms: latencyMs,
      });
    }

    res.status(500).json({ error: "Generation failed", message: error.message });
  }
});

// App Proxy: Widget JavaScript (public)
app.get("/apps/tryon/widget.js", (req, res) => {
  // Widget JS code complet pour le storefront
  const widgetCode = `
(function() {
  'use strict';
  
  const CONFIG = {
    apiBase: window.location.origin + '/apps/tryon',
    selectors: {
      productImage: '.product__media img, .product-single__media img, [data-product-image]',
      addToCartButton: 'form[action*="/cart/add"] button[type="submit"], button[name="add"]'
    }
  };
  
  class VTONWidget {
    constructor() {
      this.shop = window.Shopify?.shop || '';
      this.productId = this.extractProductId();
      this.productImage = this.getProductImage();
      if (this.productId && this.productImage) {
        this.init();
      }
    }
    
    extractProductId() {
      const meta = document.querySelector('meta[property="og:url"]');
      if (meta) {
        const match = meta.content.match(/products\\/([^?]+)/);
        return match ? match[1] : null;
      }
      return null;
    }
    
    getProductImage() {
      const img = document.querySelector(CONFIG.selectors.productImage);
      return img ? img.src : null;
    }
    
    init() {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => this.injectButton());
      } else {
        this.injectButton();
      }
    }
    
    injectButton() {
      const addToCartBtn = document.querySelector(CONFIG.selectors.addToCartButton);
      if (!addToCartBtn) {
        setTimeout(() => this.injectButton(), 500);
        return;
      }
      
      if (document.getElementById('vton-button')) return;
      
      const vtonBtn = document.createElement('button');
      vtonBtn.id = 'vton-button';
      vtonBtn.type = 'button';
      vtonBtn.className = 'vton-button';
      vtonBtn.innerHTML = '<span>Try It On</span>';
      vtonBtn.onclick = () => this.openModal();
      
      addToCartBtn.parentElement.insertAdjacentElement('afterend', vtonBtn);
      this.injectStyles();
    }
    
    injectStyles() {
      if (document.getElementById('vton-styles')) return;
      
      const styles = document.createElement('style');
      styles.id = 'vton-styles';
      styles.textContent = \`
        .vton-button {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          padding: 12px 24px;
          margin-top: 12px;
          background: #000;
          color: #fff;
          border: none;
          border-radius: 4px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          justify-content: center;
        }
        .vton-button:hover {
          background: #333;
          transform: translateY(-1px);
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
      \`;
      document.head.appendChild(styles);
    }
    
    openModal() {
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
      modal.innerHTML = \`
        <div class="vton-modal-content">
          <h2>Virtual Try-On</h2>
          <div class="vton-upload-area">
            <label for="vton-photo-upload">
              <div class="upload-box">
                <p>Upload your photo</p>
              </div>
            </label>
            <input type="file" id="vton-photo-upload" accept="image/*" style="display:none;">
          </div>
          <div id="vton-preview" style="display:none;">
            <img id="vton-preview-img" src="" alt="Preview" style="max-width: 100%;">
          </div>
          <button id="vton-generate-btn" class="vton-button" disabled>Generate Try-On</button>
          <div id="vton-result" style="display:none;">
            <img id="vton-result-img" src="" alt="Result" style="max-width: 100%;">
          </div>
          <button class="vton-close" onclick="document.getElementById('vton-modal').classList.remove('active')">Close</button>
        </div>
      \`;
      
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
        const personBase64 = this.userPhoto.split(',')[1];
        const response = await fetch(\`\${CONFIG.apiBase}/generate?shop=\${this.shop}\`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            person_image_base64: personBase64,
            clothing_url: this.productImage,
            product_id: this.productId
          })
        });
        
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Generation failed');
        }
        
        const data = await response.json();
        const resultDiv = document.getElementById('vton-result');
        const resultImg = document.getElementById('vton-result-img');
        resultImg.src = data.result_image_url;
        resultDiv.style.display = 'block';
        btn.textContent = 'Generate Another';
        btn.disabled = false;
      } catch (error) {
        console.error('[VTON] Error:', error);
        alert('An error occurred: ' + error.message);
        btn.textContent = 'Generate Try-On';
        btn.disabled = false;
      }
    }
  }
  
  new VTONWidget();
})();
  `;
  
  res.setHeader("Content-Type", "application/javascript");
  res.setHeader("Cache-Control", "public, max-age=3600");
  res.send(widgetCode);
});

// App Proxy: Génération try-on (public, avec vérification HMAC)
app.post("/apps/tryon/generate", async (req, res) => {
  const startTime = Date.now();
  
  try {
    // Vérifier la signature HMAC Shopify (à implémenter)
    const shop = req.query.shop;
    if (!shop) {
      return res.status(400).json({ error: "Shop parameter missing" });
    }

    const shopRecord = tryonDb.getShop(shop);
    if (!shopRecord) {
      return res.status(404).json({ error: "Shop not found" });
    }

    if (shopRecord.credits < 1) {
      return res.status(402).json({ error: "Insufficient credits", credits: 0 });
    }

    // Rate limiting
    const clientIp = req.ip || req.connection.remoteAddress;
    const rateLimit = tryonDb.checkRateLimit(shop, clientIp, shopRecord.max_tries_per_user);
    
    if (!rateLimit.allowed) {
      return res.status(429).json({ 
        error: "Daily limit reached", 
        limit: shopRecord.max_tries_per_user 
      });
    }

    const { person_image_base64, clothing_url, clothing_file_base64, product_id } = req.body;

    if (!person_image_base64) {
      return res.status(400).json({ error: "person_image_base64 is required" });
    }

    const personBuffer = Buffer.from(person_image_base64, "base64");
    const garmentInput = clothing_file_base64 
      ? Buffer.from(clothing_file_base64, "base64")
      : clothing_url;

    if (!garmentInput) {
      return res.status(400).json({ error: "No garment provided" });
    }

    const resultUrl = await tryonService.generateTryOn(
      personBuffer,
      garmentInput,
      "upper_body"
    );

    tryonDb.updateShopCredits(shop, -1);
    tryonDb.incrementTryOns(shop);

    const latencyMs = Date.now() - startTime;

    tryonDb.createTryOnLog({
      shop,
      customer_ip: clientIp,
      product_id: product_id || null,
      success: true,
      latency_ms: latencyMs,
      result_image_url: resultUrl,
    });

    const updatedShop = tryonDb.getShop(shop);

    res.json({
      result_image_url: resultUrl,
      credits_remaining: updatedShop.credits,
      generation_time_ms: latencyMs,
    });
  } catch (error) {
    console.error("Error in /apps/tryon/generate:", error);
    
    const latencyMs = Date.now() - startTime;
    const shop = req.query.shop;
    const clientIp = req.ip || req.connection.remoteAddress;

    if (shop) {
      tryonDb.createTryOnLog({
        shop,
        customer_ip: clientIp,
        success: false,
        error_message: error.message,
        latency_ms: latencyMs,
      });
    }

    res.status(500).json({ error: "Generation failed", message: error.message });
  }
});

app.use(shopify.cspHeaders());
app.use(serveStatic(STATIC_PATH, { index: false }));

app.use("/*", shopify.ensureInstalledOnShop(), async (_req, res, _next) => {
  return res
    .status(200)
    .set("Content-Type", "text/html")
    .send(
      readFileSync(join(STATIC_PATH, "index.html"))
        .toString()
        .replace("%VITE_SHOPIFY_API_KEY%", process.env.SHOPIFY_API_KEY || "")
    );
});

app.listen(PORT);
