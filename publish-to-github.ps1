# Script PowerShell pour publier sur GitHub
# ============================================

Write-Host "🚀 Publication sur GitHub" -ForegroundColor Cyan
Write-Host ""

# Demander les informations
$username = Read-Host "Entrez votre nom d'utilisateur GitHub"
$repoName = Read-Host "Entrez le nom du dépôt GitHub (ou appuyez sur Entrée pour 'style-lab-try-on-v2')"

if ([string]::IsNullOrWhiteSpace($repoName)) {
    $repoName = "style-lab-try-on-v2"
}

$repoUrl = "https://github.com/$username/$repoName.git"

Write-Host ""
Write-Host "📋 Configuration:" -ForegroundColor Yellow
Write-Host "   Username: $username"
Write-Host "   Repository: $repoName"
Write-Host "   URL: $repoUrl"
Write-Host ""

$confirm = Read-Host "Confirmez-vous? (O/N)"

if ($confirm -ne "O" -and $confirm -ne "o" -and $confirm -ne "Y" -and $confirm -ne "y") {
    Write-Host "❌ Annulé" -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "🔗 Configuration du remote..." -ForegroundColor Cyan
git remote add origin $repoUrl 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Remote ajouté" -ForegroundColor Green
} else {
    Write-Host "⚠️  Remote existe déjà, mise à jour..." -ForegroundColor Yellow
    git remote set-url origin $repoUrl
}

Write-Host ""
Write-Host "🌿 Renommage de la branche en 'main'..." -ForegroundColor Cyan
git branch -M main

Write-Host ""
Write-Host "📤 Publication sur GitHub..." -ForegroundColor Cyan
Write-Host "   (Vous devrez entrer vos identifiants GitHub)" -ForegroundColor Yellow
Write-Host ""

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Publication réussie! 🎉" -ForegroundColor Green
    Write-Host "   Votre code est maintenant sur: $repoUrl" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "❌ Erreur lors de la publication" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Solutions possibles:" -ForegroundColor Yellow
    Write-Host "   1. Vérifiez que le dépôt existe sur GitHub"
    Write-Host "   2. Utilisez un Personal Access Token comme mot de passe"
    Write-Host "   3. Vérifiez votre connexion internet"
}

