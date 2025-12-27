# 🚂 Configuration Railway - Guide Rapide

## ✅ Fichiers créés:
- `Procfile` - Commande de démarrage
- `runtime.txt` - Version Python

## 🔧 Variables d'environnement à configurer sur Railway:

1. **SHOPIFY_API_KEY** - Votre clé API Shopify
2. **SHOPIFY_API_SECRET** - Votre secret Shopify
3. **REPLICATE_API_TOKEN** - Token Replicate
4. **DATABASE_URL** - URL PostgreSQL (Railway peut créer une DB automatiquement)
5. **APPLICATION_URL** - URL publique de votre app Railway (ex: `https://style-lab-try-on-v2.up.railway.app`)
6. **ENVIRONMENT** - `production`

## 📋 Configuration Railway:

1. **Root Directory:** Laissez vide (ou `/`)

2. **Build Command:** Laissez vide (Railway détecte automatiquement Python)

3. **Start Command:** Laissez vide (utilise le Procfile)

4. **Port:** Railway définit automatiquement `$PORT`

## ⚠️ Erreurs courantes:

### Erreur: "Module not found"
- Vérifiez que le Root Directory est bien `/` (racine du repo)
- Le Procfile utilise `cd backend` pour aller dans le bon dossier

### Erreur: "Port already in use"
- Railway définit automatiquement `$PORT`
- Ne hardcodez pas de port dans le code

### Erreur: "Database connection failed"
- Créez une base PostgreSQL sur Railway
- Copiez l'URL de connexion dans `DATABASE_URL`
- Format: `postgresql://user:password@host:port/dbname`

### Erreur: "Application crashed"
- Vérifiez les logs Railway
- Assurez-vous que toutes les variables d'env sont configurées
- Vérifiez que `DATABASE_URL` est correcte

## 🔍 Vérifier les logs:

Dans Railway Dashboard → Votre service → Logs

Cherchez:
- ✅ "Starting VTON AI Backend..."
- ✅ "Database initialized"
- ❌ Toute erreur en rouge

