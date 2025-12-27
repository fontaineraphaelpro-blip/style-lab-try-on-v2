# ⚠️ IMPORTANT: URL Railway

## 🔍 Vérification de l'URL Publique

L'URL `style-lab-try-on-v2.railway.internal` est une **URL interne Railway** (pour communication entre services).

L'URL **publique** que Shopify doit utiliser est généralement:
```
https://style-lab-try-on-v2.up.railway.app
```

## ✅ Comment trouver votre URL publique Railway:

1. Allez sur votre dashboard Railway
2. Sélectionnez votre projet
3. Cliquez sur votre service
4. Dans l'onglet **"Settings"** → **"Networking"**
5. Vous verrez votre **"Public Domain"** (ex: `style-lab-try-on-v2.up.railway.app`)

## 🔧 Si votre URL est différente:

Si votre URL publique Railway est différente de `style-lab-try-on-v2.up.railway.app`, vous devez:

1. **Mettre à jour `shopify.app.toml`:**
   - Remplacer toutes les occurrences de `https://style-lab-try-on-v2.up.railway.app` par votre URL

2. **Configurer la variable d'environnement sur Railway:**
   ```bash
   APPLICATION_URL=https://VOTRE-URL-RAILWAY.up.railway.app
   ```

3. **Mettre à jour les URLs dans Shopify Partner Dashboard:**
   - Allez sur https://partners.shopify.com
   - Sélectionnez votre app
   - Mettez à jour les **App URL** et **Allowed redirection URLs**

## 📝 Fichiers modifiés:

- ✅ `shopify.app.toml` - URLs mises à jour
- ✅ `backend/routes/auth.py` - APPLICATION_URL par défaut
- ✅ `backend/routes/admin.py` - APPLICATION_URL par défaut

## 🚀 Prochaines étapes:

1. Vérifiez votre URL publique dans Railway
2. Si différente, mettez à jour `shopify.app.toml`
3. Configurez `APPLICATION_URL` sur Railway
4. Mettez à jour les URLs dans Shopify Partner Dashboard
5. Redéployez si nécessaire

---

**Note:** L'URL `.railway.internal` est uniquement pour la communication interne Railway et ne doit PAS être utilisée dans `shopify.app.toml`.

