"""
Routes Package
==============
Contient toutes les routes de l'API organisées par domaine.
"""

from .admin import router as admin_router
from .proxy import router as proxy_router
from .webhooks import router as webhooks_router

__all__ = ['admin_router', 'proxy_router', 'webhooks_router']