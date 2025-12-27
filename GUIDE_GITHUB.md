# 📤 Guide: Publier sur GitHub

## ✅ Étape 1: Commit créé!

Votre commit initial a été créé avec succès. Tous vos fichiers sont maintenant versionnés.

---

## 🚀 Étape 2: Créer un dépôt sur GitHub

1. **Allez sur GitHub.com** et connectez-vous
2. Cliquez sur le **"+"** en haut à droite → **"New repository"**
3. Remplissez:
   - **Repository name:** `style-lab-try-on-v2` (ou le nom de votre choix)
   - **Description:** "Shopify Virtual Try-On App - AI-powered fashion try-on"
   - **Visibilité:** Public ou Private (selon votre choix)
   - ⚠️ **NE COCHEZ PAS** "Initialize with README" (on a déjà les fichiers)
4. Cliquez sur **"Create repository"**

---

## 🔗 Étape 3: Connecter votre repo local à GitHub

Une fois le dépôt créé sur GitHub, vous verrez des instructions. Utilisez ces commandes:

### Si c'est un nouveau dépôt (première fois):

```bash
cd "C:\Users\jeanr\Downloads\style-lab-try-on-v2-main\style-lab-try-on-v2-main"
git remote add origin https://github.com/VOTRE_USERNAME/style-lab-try-on-v2.git
git branch -M main
git push -u origin main
```

**Remplacez `VOTRE_USERNAME`** par votre nom d'utilisateur GitHub.

### Si vous avez déjà un dépôt GitHub existant:

```bash
cd "C:\Users\jeanr\Downloads\style-lab-try-on-v2-main\style-lab-try-on-v2-main"
git remote add origin https://github.com/VOTRE_USERNAME/NOM_DU_REPO.git
git push -u origin master
```

---

## 🔐 Étape 4: Authentification GitHub

GitHub peut demander votre authentification. Options:

### Option A: Personal Access Token (Recommandé)
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. Sélectionnez les scopes: `repo` (tous les droits)
4. Copiez le token
5. Utilisez-le comme mot de passe quand Git le demande

### Option B: GitHub CLI
```bash
gh auth login
```

### Option C: SSH (Pour usage fréquent)
```bash
# Générer une clé SSH
ssh-keygen -t ed25519 -C "votre_email@example.com"

# Ajouter la clé à GitHub
# (Copiez le contenu de ~/.ssh/id_ed25519.pub et ajoutez-le dans GitHub Settings → SSH keys)

# Utiliser SSH au lieu de HTTPS
git remote set-url origin git@github.com:VOTRE_USERNAME/style-lab-try-on-v2.git
```

---

## 📝 Commandes Git Utiles

### Voir l'état actuel:
```bash
git status
```

### Ajouter des fichiers modifiés:
```bash
git add .
# ou pour un fichier spécifique:
git add backend/main.py
```

### Créer un commit:
```bash
git commit -m "Description de vos changements"
```

### Publier sur GitHub:
```bash
git push
```

### Voir l'historique:
```bash
git log --oneline
```

### Créer une nouvelle branche:
```bash
git checkout -b nom-de-la-branche
```

---

## ⚠️ Fichiers à NE PAS commiter

Assurez-vous que votre `.gitignore` contient:
- `.env` (variables d'environnement)
- `__pycache__/`
- `*.pyc`
- `.venv/` ou `venv/`
- `node_modules/`
- Fichiers de logs

---

## 🎯 Prochaines Étapes Après le Push

1. **Configurer les secrets sur Render/Heroku:**
   - `SHOPIFY_API_KEY`
   - `SHOPIFY_API_SECRET`
   - `REPLICATE_API_TOKEN`
   - `DATABASE_URL`
   - `APPLICATION_URL`

2. **Connecter le repo GitHub à votre service de déploiement**

3. **Déployer!** 🚀

---

## 💡 Astuce

Pour automatiser les futurs commits:
```bash
# Alias utile (optionnel)
git config --global alias.s "status"
git config --global alias.c "commit -m"
git config --global alias.p "push"
```

Ensuite vous pouvez utiliser:
```bash
git s    # au lieu de git status
git c "message"  # au lieu de git commit -m "message"
git p    # au lieu de git push
```

---

**Bon push! 🚀**

