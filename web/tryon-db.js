/**
 * Try-On Database
 * ===============
 * Base de données pour les données try-on (Shop, TryOnLog, etc.)
 * 
 * IMPORTANT : Cette DB est SÉPARÉE de la session storage du template.
 * Le template utilise SQLite pour les sessions OAuth (shopify-app-session-storage-sqlite).
 * Cette DB gère uniquement les données métier try-on.
 * 
 * INTÉGRATION DANS LE TEMPLATE :
 * - Ne modifie PAS la gestion des sessions OAuth
 * - Utilise la session du template (res.locals.shopify.session) pour obtenir le shop
 */

import Database from "better-sqlite3";
import { join } from "path";

const DB_PATH = join(process.cwd(), "tryon-database.sqlite");

const db = new Database(DB_PATH);

// Créer les tables si elles n'existent pas
db.exec(`
  CREATE TABLE IF NOT EXISTS shops (
    domain TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    credits INTEGER DEFAULT 0,
    lifetime_credits INTEGER DEFAULT 0,
    total_tryons INTEGER DEFAULT 0,
    total_atc INTEGER DEFAULT 0,
    widget_text TEXT DEFAULT 'Try It On Now ✨',
    widget_bg TEXT DEFAULT '#000000',
    widget_color TEXT DEFAULT '#ffffff',
    max_tries_per_user INTEGER DEFAULT 5,
    installed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    uninstalled_at DATETIME
  );

  CREATE TABLE IF NOT EXISTS tryon_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop TEXT NOT NULL,
    customer_ip TEXT,
    customer_id TEXT,
    product_id TEXT,
    product_title TEXT,
    success INTEGER DEFAULT 1,
    error_message TEXT,
    latency_ms INTEGER,
    result_image_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop TEXT NOT NULL,
    customer_ip TEXT NOT NULL,
    date TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    UNIQUE(shop, customer_ip, date)
  );

  CREATE TABLE IF NOT EXISTS credit_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop TEXT NOT NULL,
    charge_id TEXT UNIQUE,
    amount_usd REAL,
    credits_purchased INTEGER,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    activated_at DATETIME
  );

  CREATE INDEX IF NOT EXISTS idx_tryon_logs_shop ON tryon_logs(shop);
  CREATE INDEX IF NOT EXISTS idx_tryon_logs_created_at ON tryon_logs(created_at);
  CREATE INDEX IF NOT EXISTS idx_rate_limits_shop_ip_date ON rate_limits(shop, customer_ip, date);
`);

/**
 * Récupère ou crée un shop
 * @param {string} domain - Domaine du shop (ex: mystore.myshopify.com)
 * @param {string} accessToken - Access token Shopify
 * @returns {Object} Shop record
 */
export function getOrCreateShop(domain, accessToken) {
  let shop = db.prepare("SELECT * FROM shops WHERE domain = ?").get(domain);

  if (!shop) {
    // Nouveau shop : 10 crédits gratuits
    db.prepare(`
      INSERT INTO shops (domain, access_token, credits, installed_at, last_active_at)
      VALUES (?, ?, 10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    `).run(domain, accessToken);
    shop = db.prepare("SELECT * FROM shops WHERE domain = ?").get(domain);
  } else {
    // Mettre à jour l'access token et last_active_at
    db.prepare(`
      UPDATE shops 
      SET access_token = ?, last_active_at = CURRENT_TIMESTAMP 
      WHERE domain = ?
    `).run(accessToken, domain);
    shop = db.prepare("SELECT * FROM shops WHERE domain = ?").get(domain);
  }

  return shop;
}

/**
 * Récupère un shop par domaine
 */
export function getShop(domain) {
  return db.prepare("SELECT * FROM shops WHERE domain = ? AND is_active = 1").get(domain);
}

/**
 * Met à jour les crédits d'un shop
 */
export function updateShopCredits(domain, creditsDelta) {
  const shop = getShop(domain);
  if (!shop) return null;

  const newCredits = Math.max(0, shop.credits + creditsDelta);
  db.prepare("UPDATE shops SET credits = ? WHERE domain = ?").run(newCredits, domain);
  
  if (creditsDelta > 0) {
    db.prepare("UPDATE shops SET lifetime_credits = lifetime_credits + ? WHERE domain = ?").run(creditsDelta, domain);
  }

  return getShop(domain);
}

/**
 * Incrémente le compteur de try-ons
 */
export function incrementTryOns(domain) {
  db.prepare("UPDATE shops SET total_tryons = total_tryons + 1 WHERE domain = ?").run(domain);
}

/**
 * Incrémente le compteur Add to Cart
 */
export function incrementATC(domain) {
  db.prepare("UPDATE shops SET total_atc = total_atc + 1 WHERE domain = ?").run(domain);
}

/**
 * Met à jour les paramètres du widget
 */
export function updateWidgetSettings(domain, settings) {
  db.prepare(`
    UPDATE shops 
    SET widget_text = ?, widget_bg = ?, widget_color = ?, max_tries_per_user = ?
    WHERE domain = ?
  `).run(
    settings.text,
    settings.bg,
    settings.color,
    settings.max_tries,
    domain
  );
}

/**
 * Crée un log de try-on
 */
export function createTryOnLog(log) {
  db.prepare(`
    INSERT INTO tryon_logs (
      shop, customer_ip, customer_id, product_id, product_title,
      success, error_message, latency_ms, result_image_url
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    log.shop,
    log.customer_ip || null,
    log.customer_id || null,
    log.product_id || null,
    log.product_title || null,
    log.success ? 1 : 0,
    log.error_message || null,
    log.latency_ms || null,
    log.result_image_url || null
  );
}

/**
 * Vérifie et incrémente le rate limit
 * @returns {Object} { allowed: boolean, count: number }
 */
export function checkRateLimit(shop, customerIp, maxTries) {
  const today = new Date().toISOString().split("T")[0];
  
  let rateLimit = db.prepare(`
    SELECT * FROM rate_limits 
    WHERE shop = ? AND customer_ip = ? AND date = ?
  `).get(shop, customerIp, today);

  if (!rateLimit) {
    db.prepare(`
      INSERT INTO rate_limits (shop, customer_ip, date, count)
      VALUES (?, ?, ?, 0)
    `).run(shop, customerIp, today);
    rateLimit = { count: 0 };
  }

  if (rateLimit.count >= maxTries) {
    return { allowed: false, count: rateLimit.count };
  }

  db.prepare(`
    UPDATE rate_limits SET count = count + 1
    WHERE shop = ? AND customer_ip = ? AND date = ?
  `).run(shop, customerIp, today);

  return { allowed: true, count: rateLimit.count + 1 };
}

/**
 * Crée un enregistrement d'achat de crédits
 */
export function createCreditPurchase(purchase) {
  const result = db.prepare(`
    INSERT INTO credit_purchases (shop, charge_id, amount_usd, credits_purchased, status)
    VALUES (?, ?, ?, ?, ?)
  `).run(
    purchase.shop,
    purchase.charge_id || null,
    purchase.amount_usd,
    purchase.credits_purchased,
    purchase.status || "pending"
  );

  return db.prepare("SELECT * FROM credit_purchases WHERE id = ?").get(result.lastInsertRowid);
}

/**
 * Met à jour le statut d'un achat
 */
export function updatePurchaseStatus(purchaseId, status, activatedAt = null) {
  if (activatedAt) {
    db.prepare(`
      UPDATE credit_purchases 
      SET status = ?, activated_at = ?
      WHERE id = ?
    `).run(status, activatedAt, purchaseId);
  } else {
    db.prepare(`
      UPDATE credit_purchases 
      SET status = ?
      WHERE id = ?
    `).run(status, purchaseId);
  }
}

/**
 * Récupère un achat par ID ou charge_id
 */
export function getPurchase(purchaseId, chargeId) {
  if (purchaseId) {
    return db.prepare("SELECT * FROM credit_purchases WHERE id = ?").get(purchaseId);
  }
  if (chargeId) {
    return db.prepare("SELECT * FROM credit_purchases WHERE charge_id = ?").get(chargeId);
  }
  return null;
}

/**
 * Récupère les stats du dashboard
 */
export function getDashboardStats(domain) {
  const shop = getShop(domain);
  if (!shop) return null;

  const now = new Date();
  const today = now.toISOString().split("T")[0];
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
  const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];

  const tryonsToday = db.prepare(`
    SELECT COUNT(*) as count FROM tryon_logs 
    WHERE shop = ? AND DATE(created_at) = ?
  `).get(domain, today);

  const tryonsWeek = db.prepare(`
    SELECT COUNT(*) as count FROM tryon_logs 
    WHERE shop = ? AND DATE(created_at) >= ?
  `).get(domain, weekAgo);

  const tryonsMonth = db.prepare(`
    SELECT COUNT(*) as count FROM tryon_logs 
    WHERE shop = ? AND DATE(created_at) >= ?
  `).get(domain, monthAgo);

  const avgLatency = db.prepare(`
    SELECT AVG(latency_ms) as avg FROM tryon_logs 
    WHERE shop = ? AND DATE(created_at) >= ? AND latency_ms IS NOT NULL
  `).get(domain, monthAgo);

  const errorRate = db.prepare(`
    SELECT 
      COUNT(*) as total,
      SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
    FROM tryon_logs 
    WHERE shop = ? AND DATE(created_at) >= ?
  `).get(domain, monthAgo);

  return {
    shop: {
      domain: shop.domain,
      installed_at: shop.installed_at,
      is_vip: shop.lifetime_credits >= 500,
    },
    billing: {
      credits: shop.credits,
      lifetime_credits: shop.lifetime_credits,
      daily_burn_rate: tryonsMonth.count / 30,
      days_remaining: shop.credits / (tryonsMonth.count / 30 || 1),
      vip_progress: Math.min((shop.lifetime_credits / 500) * 100, 100),
    },
    usage: {
      total_tryons: shop.total_tryons,
      total_atc: shop.total_atc,
      conversion_rate: shop.total_tryons > 0 ? (shop.total_atc / shop.total_tryons) * 100 : 0,
      tryons_today: tryonsToday.count,
      tryons_week: tryonsWeek.count,
      tryons_month: tryonsMonth.count,
    },
    performance: {
      avg_latency_ms: Math.round(avgLatency.avg || 0),
      error_rate: errorRate.total > 0 ? (errorRate.failed / errorRate.total) * 100 : 0,
      success_rate: errorRate.total > 0 ? ((errorRate.total - errorRate.failed) / errorRate.total) * 100 : 100,
    },
    widget: {
      text: shop.widget_text,
      bg: shop.widget_bg,
      color: shop.widget_color,
    },
    settings: {
      max_tries_per_user: shop.max_tries_per_user,
    },
  };
}

export default db;

