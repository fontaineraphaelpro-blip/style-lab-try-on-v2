# 🔧 Correction des problèmes OAuth et Billing

## ❌ Problème 1 : OAuth Error "redirect_uri is not whitelisted"

### Solution :

Vous devez ajouter les URLs de redirection dans votre **Shopify Partner Dashboard** :

1. Allez sur https://partners.shopify.com
2. Sélectionnez votre app "Try-On StyleLab"
3. Allez dans **App setup** → **App URL**
4. Dans la section **Allowed redirection URL(s)**, ajoutez ces URLs :

```
https://style-lab-try-on-v2-production.up.railway.app/auth/callback
https://style-lab-try-on-v2-production.up.railway.app/auth/shopify/callback
https://style-lab-try-on-v2-production.up.railway.app/api/auth/callback
```

5. Cliquez sur **Save**

### ⚠️ Important :
- Les URLs doivent correspondre **exactement** à celles dans `shopify.app.toml`
- Pas d'espace, pas de slash final
- Utilisez `https://` (pas `http://`)

---

## ❌ Problème 2 : Network Error lors de la génération

### Solutions possibles :

#### 1. Vérifier les variables d'environnement dans Railway :

Assurez-vous que ces variables sont configurées :
- `SHOPIFY_API_KEY`
- `SHOPIFY_API_SECRET`
- `REPLICATE_API_TOKEN`
- `DATABASE_URL`
- `APP_URL` = `https://style-lab-try-on-v2-production.up.railway.app`

#### 2. Vérifier que le shop est bien installé :

Après l'installation OAuth, le shop doit être dans la base de données. Vérifiez :
- Que l'OAuth s'est bien terminé
- Que vous avez été redirigé vers l'app après l'installation

#### 3. Vérifier les crédits :

L'erreur peut venir d'un manque de crédits. Vérifiez dans le dashboard que vous avez des crédits disponibles.

---

## 🔄 Après les corrections :

1. **Redéployez l'app sur Railway** (si déploiement automatique, c'est déjà fait)
2. **Réinstallez l'app sur Shopify** :
   - Désinstallez l'app de votre boutique de test
   - Réinstallez-la depuis le Partner Dashboard
   - Les nouvelles URLs de redirection seront utilisées

3. **Testez l'achat de crédits** :
   - Allez dans le dashboard
   - Cliquez sur "Buy Credits"
   - La redirection Shopify devrait fonctionner

4. **Testez la génération** :
   - Uploadez une photo et un vêtement
   - Cliquez sur "Try It On Now"
   - La génération devrait fonctionner

---

## 📝 Notes :

- Le fichier `shopify.app.toml` a été mis à jour avec l'URL Railway
- Les routes d'authentification utilisent maintenant l'URL Railway par défaut
- Les erreurs sont mieux gérées et affichent plus de détails en mode développement

---

## 🆘 Si ça ne fonctionne toujours pas :

1. Vérifiez les logs Railway pour voir les erreurs exactes
2. Vérifiez la console du navigateur (F12) pour les erreurs JavaScript
3. Assurez-vous que toutes les variables d'environnement sont correctes
4. Vérifiez que la base de données est accessible depuis Railway

