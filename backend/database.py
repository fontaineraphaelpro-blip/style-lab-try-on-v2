"""
Database Configuration & Models
================================
SQLAlchemy setup pour PostgreSQL sur Render.
"""

import os
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================

DATABASE_URL = os.getenv("DATABASE_URL")

# Fix pour Render (remplace postgres:// par postgresql://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"🔧 Database URL: {DATABASE_URL[:50]}..." if DATABASE_URL else "⚠️ No DATABASE_URL")

# Engine SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False  # Mettre à True pour debug SQL
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour les modèles
Base = declarative_base()


# ==========================================
# MODELS (TABLES)
# ==========================================

class Shop(Base):
    """
    Table des shops Shopify installés.
    """
    __tablename__ = "shops"
    
    domain = Column(String(255), primary_key=True)
    access_token = Column(Text, nullable=False)
    
    # Billing
    credits = Column(Integer, default=0)
    lifetime_credits = Column(Integer, default=0)
    
    # Usage
    total_tryons = Column(Integer, default=0)
    total_atc = Column(Integer, default=0)
    
    # Widget settings
    widget_text = Column(String(255), default='Try It On Now ✨')
    widget_bg = Column(String(7), default='#000000')
    widget_color = Column(String(7), default='#ffffff')
    max_tries_per_user = Column(Integer, default=5)
    
    # Metadata
    installed_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    uninstalled_at = Column(DateTime, nullable=True)


class TryOnLog(Base):
    """
    Table des logs de try-on (analytics).
    """
    __tablename__ = "tryon_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shop = Column(String(255), nullable=False, index=True)
    
    # Customer (anonymisé)
    customer_ip = Column(String(45))
    customer_id = Column(String(255))
    
    # Product
    product_id = Column(String(255))
    product_title = Column(Text)
    
    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    latency_ms = Column(Integer)
    result_image_url = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class RateLimit(Base):
    """
    Table de rate limiting par IP (anti-abus).
    """
    __tablename__ = "rate_limits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shop = Column(String(255), nullable=False, index=True)
    customer_ip = Column(String(45), nullable=False)
    date = Column(String(10), nullable=False)  # Format: YYYY-MM-DD
    count = Column(Integer, default=0)


class CreditPurchase(Base):
    """
    Table des achats de crédits.
    """
    __tablename__ = "credit_purchases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shop = Column(String(255), nullable=False, index=True)
    
    charge_id = Column(String(255), unique=True)
    amount_usd = Column(DECIMAL(10, 2))
    credits_purchased = Column(Integer)
    
    status = Column(String(50), default='pending')  # pending, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime)


# ==========================================
# FUNCTIONS
# ==========================================

def init_db():
    """
    Crée toutes les tables dans la base de données.
    """
    try:
        print("🔧 Initializing database...")
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise


def get_db():
    """
    Dependency pour FastAPI.
    Fournit une session DB pour chaque requête.
    
    Usage:
        @app.get("/endpoint")
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    """
    Teste la connexion à la base de données.
    """
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


# ==========================================
# EXPORTS
# ==========================================

__all__ = [
    'engine',
    'SessionLocal',
    'Base',
    'Shop',
    'TryOnLog',
    'RateLimit',
    'CreditPurchase',
    'init_db',
    'get_db',
    'test_connection'
]
