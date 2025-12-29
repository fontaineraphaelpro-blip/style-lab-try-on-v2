-- ==========================================
-- VTON AI - Database Schema
-- ==========================================

-- Table des shops
CREATE TABLE IF NOT EXISTS shops (
    domain VARCHAR(255) PRIMARY KEY,
    access_token TEXT NOT NULL,
    
    -- Billing
    credits INTEGER DEFAULT 0,
    lifetime_credits INTEGER DEFAULT 0,
    
    -- Usage
    total_tryons INTEGER DEFAULT 0,
    total_atc INTEGER DEFAULT 0,
    
    -- Widget settings
    widget_text VARCHAR(255) DEFAULT 'Try It On Now ✨',
    widget_bg VARCHAR(7) DEFAULT '#000000',
    widget_color VARCHAR(7) DEFAULT '#ffffff',
    max_tries_per_user INTEGER DEFAULT 5,
    
    -- Metadata
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    uninstalled_at TIMESTAMP NULL
);

-- Table des logs de try-on
CREATE TABLE IF NOT EXISTS tryon_logs (
    id SERIAL PRIMARY KEY,
    shop VARCHAR(255) NOT NULL,
    
    -- Customer
    customer_ip VARCHAR(45),
    customer_id VARCHAR(255),
    
    -- Product
    product_id VARCHAR(255),
    product_title TEXT,
    
    -- Result
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    latency_ms INTEGER,
    result_image_url TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table de rate limiting
CREATE TABLE IF NOT EXISTS rate_limits (
    id SERIAL PRIMARY KEY,
    shop VARCHAR(255) NOT NULL,
    customer_ip VARCHAR(45) NOT NULL,
    date VARCHAR(10) NOT NULL,
    count INTEGER DEFAULT 0,
    
    UNIQUE(shop, customer_ip, date)
);

-- Table des achats de crédits
CREATE TABLE IF NOT EXISTS credit_purchases (
    id SERIAL PRIMARY KEY,
    shop VARCHAR(255) NOT NULL,
    
    charge_id VARCHAR(255) UNIQUE,
    amount_usd DECIMAL(10, 2),
    credits_purchased INTEGER,
    
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP
);

-- Index pour performances
CREATE INDEX IF NOT EXISTS idx_tryon_logs_shop ON tryon_logs(shop, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tryon_logs_success ON tryon_logs(shop, success);
CREATE INDEX IF NOT EXISTS idx_rate_limits_lookup ON rate_limits(shop, customer_ip, date);