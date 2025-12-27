"""
Database Configuration
======================
Gère la connexion PostgreSQL et les modèles.
"""

import os
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/vton")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ==========================================
# MODELS
# ==========================================

class Shop(Base):
    __tablename__ = "shops"
    
    domain = Column(String(255), primary_key=True)
    access_token = Column(Text, nullable=False)
    
    credits = Column(Integer, default=0)
    lifetime_credits = Column(Integer, default=0)
    
    total_tryons = Column(Integer, default=0)
    total_atc = Column(Integer, default=0)
    
    widget_text = Column(String(255), default="Try It On Now ✨")
    widget_bg = Column(String(7), default="#000000")
    widget_color = Column(String(7), default="#ffffff")
    max_tries_per_user = Column(Integer, default=5)
    
    installed_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    uninstalled_at = Column(DateTime, nullable=True)


class TryOnLog(Base):
    __tablename__ = "tryon_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shop = Column(String(255), nullable=False)
    
    customer_ip = Column(String(45))
    customer_id = Column(String(255))
    
    product_id = Column(String(255))
    product_title = Column(Text)
    
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    latency_ms = Column(Integer)
    result_image_url = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class RateLimit(Base):
    __tablename__ = "rate_limits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shop = Column(String(255), nullable=False)
    customer_ip = Column(String(45), nullable=False)
    date = Column(String(10), nullable=False)
    count = Column(Integer, default=0)


class CreditPurchase(Base):
    __tablename__ = "credit_purchases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shop = Column(String(255), nullable=False)
    
    charge_id = Column(String(255), unique=True)
    amount_usd = Column(DECIMAL(10, 2))
    credits_purchased = Column(Integer)
    
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime)


# ==========================================
# FUNCTIONS
# ==========================================

def init_db():
    """Initialise la base de données."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")


def get_db():
    """Dependency pour obtenir une session DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_shop(db, domain: str):
    """Helper pour récupérer un shop"""
    return db.query(Shop).filter(Shop.domain == domain).first()


def create_shop(db, domain: str, access_token: str):
    """Helper pour créer un nouveau shop"""
    shop = Shop(domain=domain, access_token=access_token)
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop