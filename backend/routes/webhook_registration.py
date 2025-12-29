"""
Shopify Webhook Registration
============================
Enregistre automatiquement les webhooks Shopify via l'API.
"""

import os
import requests
from typing import List, Dict, Optional

SHOPIFY_API_VERSION = "2025-01"
APP_URL = os.getenv("APP_URL", "https://style-lab-try-on-v2-production.up.railway.app")


# Liste des webhooks à enregistrer
WEBHOOKS_TO_REGISTER = [
    {
        "topic": "app/uninstalled",
        "address": f"{APP_URL}/webhooks/app/uninstalled",
        "format": "json"
    },
    {
        "topic": "products/update",
        "address": f"{APP_URL}/webhooks/products/update",
        "format": "json"
    },
    {
        "topic": "app_charges/activate",
        "address": f"{APP_URL}/webhooks/billing/charges/activate",
        "format": "json"
    },
    {
        "topic": "customers/data_request",
        "address": f"{APP_URL}/webhooks/customers/data_request",
        "format": "json"
    },
    {
        "topic": "customers/redact",
        "address": f"{APP_URL}/webhooks/customers/redact",
        "format": "json"
    },
    {
        "topic": "shop/redact",
        "address": f"{APP_URL}/webhooks/shop/redact",
        "format": "json"
    }
]


def get_existing_webhooks(shop_domain: str, access_token: str) -> List[Dict]:
    """
    Récupère la liste des webhooks existants pour un shop.
    """
    try:
        url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/webhooks.json"
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return data.get("webhooks", [])
    except Exception as e:
        print(f"❌ Error fetching webhooks for {shop_domain}: {e}")
        return []


def register_webhook(shop_domain: str, access_token: str, topic: str, address: str, format: str = "json") -> bool:
    """
    Enregistre un webhook Shopify.
    
    Returns:
        bool: True si le webhook a été créé ou existe déjà, False en cas d'erreur
    """
    try:
        # Vérifier si le webhook existe déjà
        existing_webhooks = get_existing_webhooks(shop_domain, access_token)
        
        for webhook in existing_webhooks:
            if webhook.get("topic") == topic and webhook.get("address") == address:
                print(f"✅ Webhook {topic} already exists for {shop_domain}")
                return True
        
        # Créer le webhook
        url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/webhooks.json"
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        
        webhook_data = {
            "webhook": {
                "topic": topic,
                "address": address,
                "format": format
            }
        }
        
        response = requests.post(url, json=webhook_data, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        webhook_id = result.get("webhook", {}).get("id")
        
        if webhook_id:
            print(f"✅ Webhook {topic} registered successfully for {shop_domain} (ID: {webhook_id})")
            return True
        else:
            print(f"⚠️  Webhook {topic} registration response: {result}")
            return False
            
    except requests.exceptions.HTTPError as e:
        error_text = e.response.text if hasattr(e, 'response') else str(e)
        print(f"❌ Error registering webhook {topic} for {shop_domain}: {e.response.status_code} - {error_text}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error registering webhook {topic} for {shop_domain}: {e}")
        return False


def register_all_webhooks(shop_domain: str, access_token: str) -> Dict[str, bool]:
    """
    Enregistre tous les webhooks nécessaires pour un shop.
    
    Returns:
        dict: Résultat pour chaque webhook {topic: success}
    """
    print(f"🔧 Registering webhooks for {shop_domain}...")
    
    results = {}
    
    for webhook_config in WEBHOOKS_TO_REGISTER:
        topic = webhook_config["topic"]
        address = webhook_config["address"]
        format_type = webhook_config.get("format", "json")
        
        success = register_webhook(shop_domain, access_token, topic, address, format_type)
        results[topic] = success
    
    # Résumé
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"📊 Webhook registration summary: {successful}/{total} successful")
    
    return results


def delete_webhook(shop_domain: str, access_token: str, webhook_id: int) -> bool:
    """
    Supprime un webhook Shopify.
    """
    try:
        url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/webhooks/{webhook_id}.json"
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        
        response = requests.delete(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        print(f"✅ Webhook {webhook_id} deleted for {shop_domain}")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting webhook {webhook_id} for {shop_domain}: {e}")
        return False

