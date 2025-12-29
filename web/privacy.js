import { DeliveryMethod } from "@shopify/shopify-api";
import * as tryonDb from "./tryon-db.js";

/**
 * @type {{[key: string]: import("@shopify/shopify-api").WebhookHandler}}
 */
export default {
  /**
   * Customers can request their data from a store owner. When this happens,
   * Shopify invokes this privacy webhook.
   *
   * https://shopify.dev/docs/apps/webhooks/configuration/mandatory-webhooks#customers-data_request
   */
  CUSTOMERS_DATA_REQUEST: {
    deliveryMethod: DeliveryMethod.Http,
    callbackUrl: "/api/webhooks",
    callback: async (topic, shop, body, webhookId) => {
      const payload = JSON.parse(body);
      // Payload has the following shape:
      // {
      //   "shop_id": 954889,
      //   "shop_domain": "{shop}.myshopify.com",
      //   "orders_requested": [
      //     299938,
      //     280263,
      //     220458
      //   ],
      //   "customer": {
      //     "id": 191167,
      //     "email": "john@example.com",
      //     "phone": "555-625-1199"
      //   },
      //   "data_request": {
      //     "id": 9999
      //   }
      // }
    },
  },

  /**
   * Store owners can request that data is deleted on behalf of a customer. When
   * this happens, Shopify invokes this privacy webhook.
   *
   * https://shopify.dev/docs/apps/webhooks/configuration/mandatory-webhooks#customers-redact
   */
  CUSTOMERS_REDACT: {
    deliveryMethod: DeliveryMethod.Http,
    callbackUrl: "/api/webhooks",
    callback: async (topic, shop, body, webhookId) => {
      const payload = JSON.parse(body);
      // Payload has the following shape:
      // {
      //   "shop_id": 954889,
      //   "shop_domain": "{shop}.myshopify.com",
      //   "customer": {
      //     "id": 191167,
      //     "email": "john@example.com",
      //     "phone": "555-625-1199"
      //   },
      //   "orders_to_redact": [
      //     299938,
      //     280263,
      //     220458
      //   ]
      // }
    },
  },

  /**
   * 48 hours after a store owner uninstalls your app, Shopify invokes this
   * privacy webhook.
   *
   * https://shopify.dev/docs/apps/webhooks/configuration/mandatory-webhooks#shop-redact
   */
  SHOP_REDACT: {
    deliveryMethod: DeliveryMethod.Http,
    callbackUrl: "/api/webhooks",
    callback: async (topic, shop, body, webhookId) => {
      const payload = JSON.parse(body);
      // Payload has the following shape:
      // {
      //   "shop_id": 954889,
      //   "shop_domain": "{shop}.myshopify.com"
      // }
    },
  },

  /**
   * App Uninstalled Webhook
   * Appelé quand l'app est désinstallée
   */
  APP_UNINSTALLED: {
    deliveryMethod: DeliveryMethod.Http,
    callbackUrl: "/api/webhooks",
    callback: async (topic, shop, body, webhookId) => {
      const payload = JSON.parse(body);
      // Marquer le shop comme désinstallé dans la DB try-on
      try {
        const shopRecord = tryonDb.getShop(shop);
        if (shopRecord) {
          // Mettre à jour le statut (on garde les données pour analytics)
          // Mais on peut marquer is_active = 0 si nécessaire
          console.log(`App uninstalled for shop: ${shop}`);
        }
      } catch (error) {
        console.error(`Error handling app/uninstalled for ${shop}:`, error);
      }
    },
  },

  /**
   * App Charges Activate Webhook
   * Appelé quand une charge est activée (paiement accepté)
   */
  APP_CHARGES_ACTIVATE: {
    deliveryMethod: DeliveryMethod.Http,
    callbackUrl: "/api/webhooks",
    callback: async (topic, shop, body, webhookId) => {
      const payload = JSON.parse(body);
      // Activer automatiquement les crédits
      try {
        const chargeId = payload.charge_id?.toString();
        if (chargeId) {
          const purchase = tryonDb.getPurchase(null, chargeId);
          if (purchase && purchase.status === "pending") {
            tryonDb.updateShopCredits(purchase.shop, purchase.credits_purchased);
            tryonDb.updatePurchaseStatus(purchase.id, "completed", new Date().toISOString());
            console.log(`Credits activated for shop: ${shop}, purchase: ${purchase.id}`);
          }
        }
      } catch (error) {
        console.error(`Error handling app_charges/activate for ${shop}:`, error);
      }
    },
  },
};
