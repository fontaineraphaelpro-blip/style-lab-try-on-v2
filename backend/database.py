"""
Database Configuration & Models
================================
SQLAlchemy setup pour PostgreSQL sur Render.
"""

import os
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, DECIMAL, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================

DATABASE_URL = os.getenv("DATABASE_URL")

# DEBUG: Afficher l'URL complète pour debug
if DATABASE_URL:
    print(f"🔍 DEBUG: Raw DATABASE_URL from env: {DATABASE_URL[:100]}...")

# Fix pour Render (remplace postgres:// par postgresql://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Vérifier si l'URL contient un hostname Render (dpg-*) et l'ignorer
if DATABASE_URL and "dpg-" in DATABASE_URL:
    print(f"⚠️  WARNING: Detected Render database URL (dpg-*), ignoring it")
    print(f"   Full URL: {DATABASE_URL}")
    DATABASE_URL = None  # Ignorer l'URL Render
    print("✅ DATABASE_URL set to None - app will start without database")

print(f"🔧 Database URL: {DATABASE_URL[:50]}..." if DATABASE_URL else "⚠️ No DATABASE_URL (will skip DB initialization)")

# Engine SQLAlchemy (créé lazy - seulement si DATABASE_URL existe)
engine = None
SessionLocal = None

def _init_engine():
    """Initialise l'engine de manière lazy"""
    global engine, SessionLocal
    if engine is not None:
        return engine
    
    if not DATABASE_URL:
        return None
    
    # Vérifier à nouveau si l'URL est Render (double sécurité)
    if "dpg-" in DATABASE_URL:
        print(f"⚠️  WARNING: Render URL detected in _init_engine, ignoring")
        return None
    
    try:
        # Créer l'engine avec connect_args pour éviter les erreurs immédiates
        # Railway internal URLs fonctionnent si les services sont dans le même projet
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=300,
            echo=False,  # Mettre à True pour debug SQL
            connect_args={
                "connect_timeout": 10,  # Timeout de 10 secondes
                "sslmode": "prefer"  # SSL optionnel pour Railway
            }
        )
        # Ne pas tester la connexion immédiatement - laisser init_db() le faire
        # Cela évite de faire crash l'app si la DB n'est pas accessible
        print("✅ Database engine created (connection will be tested in init_db)")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return engine
    except Exception as e:
        print(f"⚠️  Failed to create database engine: {e}")
        print(f"   DATABASE_URL: {DATABASE_URL[:50]}...")
        engine = None
        SessionLocal = None
        return None

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
    global engine, SessionLocal
    
    if not DATABASE_URL:
        print("⚠️  DATABASE_URL not set, skipping database initialization")
        return
    
    # Initialiser l'engine de manière lazy
    _init_engine()
    
    if not engine:
        print("⚠️  Database engine not available, skipping initialization")
        return
    
    try:
        print("🔧 Initializing database...")
        # Tester la connexion d'abord avant de créer les tables
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
        # Créer les tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        # Ne pas faire crash l'app si la DB n'est pas accessible
        print("⚠️  Continuing without database...")
        # Réinitialiser engine pour éviter les tentatives futures
        global engine, SessionLocal
        engine = None
        SessionLocal = None
        # Ne PAS propager l'exception - l'app doit démarrer quand même
        return


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
