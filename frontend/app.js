document.addEventListener("DOMContentLoaded", function() {
    console.log("🚀 DOM Content Loaded");
    console.log("📍 URL:", window.location.href);
    console.log("🔍 Query params:", window.location.search);

    document.body.classList.add('loaded');
    document.body.style.opacity = "1";
    document.body.style.display = "block";

    // Récupérer le shop depuis plusieurs sources
    const params = new URLSearchParams(window.location.search);
    const mode = params.get('mode');
    let shop = params.get('shop') || 
               sessionStorage.getItem('shop') ||
               document.body.getAttribute('data-shop') ||
               (window.Shopify && window.Shopify.shop);
    const autoProductImage = params.get('product_image');
    
    // Si on est dans une app embedded Shopify, utiliser App Bridge
    if (window.shopify && window.shopify.config) {
        const config = window.shopify.config;
        if (config.apiKey) {
            console.log("✅ App Bridge détecté");
        }
    }

    // === RÉCUPÉRATION DU SHOP EN MODE CLIENT ===
    if (mode === 'client' && !shop) {
        console.log("⚠️ Mode client détecté, recherche du shop...");
        
        const hash = window.location.hash;
        if (hash.includes('shop=')) {
            const match = hash.match(/shop=([^&]+)/);
            if (match) shop = match[1];
        }
        
        if (!shop && window.Shopify && window.Shopify.shop) {
            shop = window.Shopify.shop;
            console.log("✅ Shop depuis Shopify.shop:", shop);
        }
        
        if (!shop) {
            try {
                const parentUrl = document.referrer || window.location.ancestorOrigins?.[0];
                if (parentUrl && parentUrl.includes('.myshopify.com')) {
                    const match = parentUrl.match(/https?:\/\/([^\/]+)/);
                    if (match) shop = match[1];
                    console.log("✅ Shop depuis referrer:", shop);
                }
            } catch(e) {
                console.error("Erreur extraction shop:", e);
            }
        }

        if (!shop) {
            try {
                if (window.parent !== window) {
                    const parentShop = window.parent.location.hostname;
                    if (parentShop.includes('.myshopify.com')) {
                        shop = parentShop;
                        console.log("✅ Shop depuis parent:", shop);
                    }
                }
            } catch(e) {
                console.log("Cannot access parent (CORS)");
            }
        }
    }

    // FIX SESSION
    try {
        if(!shop) shop = sessionStorage.getItem('shop');
        if(shop) sessionStorage.setItem('shop', shop);
    } catch(e) {}

    console.log("🪧 Shop actif:", shop, "| Mode:", mode);

    if (!shop) {
        console.error("❌ ERREUR: Shop introuvable!");
        if (mode !== 'client') {
            alert("Configuration error: Shop not found. Please reload the page.");
        }
    }

    // Initialiser App Bridge si disponible
    let shopifyApp = null;
    console.log("🔍 Vérification App Bridge...");
    console.log("   window.shopify:", window.shopify);
    console.log("   window.shopify?.config:", window.shopify?.config);
    
    if (window.shopify) {
        try {
            // App Bridge v3 - window.shopify est directement disponible
            shopifyApp = window.shopify;
            console.log("✅ App Bridge détecté:", shopifyApp);
            if (shopifyApp.id) {
                console.log("✅ App Bridge ID disponible");
            } else {
                console.warn("⚠️  App Bridge ID non disponible");
            }
        } catch (e) {
            console.warn("⚠️  Erreur App Bridge:", e);
        }
    } else {
        console.warn("⚠️  App Bridge non disponible (window.shopify est undefined)");
    }

    async function getSessionToken() {
        try {
            if (shopifyApp && shopifyApp.id) {
                console.log("🔑 Récupération du Session Token...");
                const token = await shopifyApp.id.getToken();
                console.log("✅ Session Token récupéré:", token ? "Oui" : "Non");
                return token;
            } else {
                console.warn("⚠️  App Bridge ID non disponible pour récupérer le token");
            }
        } catch (e) {
            console.warn("⚠️  Erreur lors de la récupération du Session Token:", e);
        }
        return null;
    }

    async function authenticatedFetch(url, options = {}) {
        try {
            const token = await getSessionToken();
            const headers = options.headers || {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            // Ajouter le shop dans les query params si disponible
            if (shop && !url.includes('shop=')) {
                const separator = '?' if '?' not in url else '&';
                url = `${url}${separator}shop=${encodeURIComponent(shop)}`;
            }
            const res = await fetch(url, { 
                ...options, 
                headers,
                mode: 'cors',
                credentials: 'include'
            });
            if (res.status === 401 && shop && mode !== 'client') { 
                // Rediriger vers login si non authentifié
                if (window.top && window.top !== window) {
                    window.top.location.href = `/login?shop=${shop}`;
                } else {
                    window.location.href = `/login?shop=${shop}`;
                }
                return null; 
            }
            return res;
        } catch (error) { 
            console.error("❌ Fetch error:", error);
            throw error; 
        }
    }

    // Toujours initialiser, même si shop n'est pas trouvé (pour debug)
    if(shop) {
        console.log("✅ Shop trouvé, initialisation...");
        if (mode === 'client') {
            console.log("🔄 Mode client");
            initClientMode();
        } else {
            console.log("🔄 Mode admin");
            initAdminMode(shop);
        }
    } else {
        console.error("❌ Shop non trouvé - Affichage du message d'erreur");
        // Afficher un message d'erreur visible même si shop n'est pas trouvé
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = 'padding: 20px; background: #fee; border: 2px solid #f00; margin: 20px; border-radius: 8px;';
        errorDiv.innerHTML = '<h2>⚠️ Configuration Error</h2><p>Shop parameter not found. Please reload the page or contact support.</p><p>URL: ' + window.location.href + '</p>';
        document.body.appendChild(errorDiv);
    }

    // --- DASHBOARD ---
    async function initAdminMode(s) {
        console.log("🚀 Initialisation mode admin pour:", s);
        
        // Afficher le contenu même si l'API échoue
        document.body.style.display = 'block';
        const adminZone = document.getElementById('admin-only-zone');
        if (adminZone) {
            adminZone.style.display = 'block';
        }
        
        try {
            const res = await authenticatedFetch(`/api/get-data?shop=${s}`);
            console.log("📥 Réponse /api/get-data:", res);
            
            if (res && res.ok) {
                const data = await res.json();
                console.log("✅ Données reçues:", data);

                updateDashboardStats(data.credits || 0);
                updateVIPStatus(data.lifetime || 0);

                const tryEl = document.getElementById('stat-tryons');
                const atcEl = document.getElementById('stat-atc');
                if(tryEl) tryEl.innerText = data.usage || 0;
                if(atcEl) atcEl.innerText = data.atc || 0;

                if(data.widget) {
                    document.getElementById('ws-text').value = data.widget.text || "Try It On Now ✨";
                    document.getElementById('ws-color').value = data.widget.bg || "#000000";
                    document.getElementById('ws-text-color').value = data.widget.color || "#ffffff";
                    if(data.security) document.getElementById('ws-limit').value = data.security.max_tries || 5;
                    window.updateWidgetPreview();
                }
            } else {
                console.error("❌ Erreur API /api/get-data:", res?.status, res?.statusText);
                // Afficher des valeurs par défaut
                updateDashboardStats(0);
                updateVIPStatus(0);
            }
        } catch (error) {
            console.error("❌ Erreur lors de l'initialisation:", error);
            // Afficher des valeurs par défaut même en cas d'erreur
            updateDashboardStats(0);
            updateVIPStatus(0);
        }
    }

    function updateDashboardStats(credits) {
        const el = document.getElementById('credits');
        if(el) el.innerText = credits;
        const supplyCard = document.querySelector('.smart-supply-card');
        const alertBadge = document.querySelector('.alert-badge');
        const daysEl = document.querySelector('.rs-value');
        if (supplyCard && daysEl) {
            let daysLeft = Math.floor(credits / 8); 
            if(daysLeft < 1) daysLeft = "< 1";
            daysEl.innerText = daysLeft + (daysLeft === "< 1" ? " Day" : " Days");
            if (credits < 20) {
                supplyCard.style.background = "#fff0f0";
                alertBadge.innerText = "CRITICAL";
                alertBadge.style.background = "#dc2626";
            } else {
                supplyCard.style.background = "#f0fdf4";
                alertBadge.innerText = "HEALTHY";
                alertBadge.style.background = "#16a34a";
            }
        }
    }

    function updateVIPStatus(lifetime) {
        const fill = document.querySelector('.vip-fill');
        const marker = document.querySelector('.vip-marker');
        let percent = (lifetime / 500) * 100;
        if(percent > 100) percent = 100;
        if(fill) fill.style.width = percent + "%";
        if(marker) marker.style.left = percent + "%";
        if(lifetime >= 500) {
            const title = document.querySelector('.vip-title strong');
            if(title) title.innerText = "Gold Member";
        }
    }

    // --- SAVE SETTINGS ---
    window.saveSettings = async function(btn) {
        const oldText = btn.innerText;
        btn.innerText = "Saving..."; 
        btn.disabled = true;
        const settings = {
            shop: shop,
            text: document.getElementById('ws-text').value,
            bg: document.getElementById('ws-color').value,
            color: document.getElementById('ws-text-color').value,
            max_tries: parseInt(document.getElementById('ws-limit').value) || 5
        };
        try {
            const res = await authenticatedFetch('/api/save-settings', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(settings)
            });
            if(res && res.ok) { 
                btn.innerText = "Saved! ✅"; 
                setTimeout(() => btn.innerText = oldText, 2000); 
            } else { 
                alert("Save failed"); 
            }
        } catch(e) { 
            console.error(e); 
            alert("Error saving"); 
        } finally { 
            btn.disabled = false; 
        }
    };

    // --- TRACK ADD TO CART ---
    window.trackATC = async function() {
        if(shop) {
            try {
                await fetch('/api/track-atc', {
                    method: 'POST', 
                    headers: {'Content-Type': 'application/json'}, 
                    body: JSON.stringify({ shop: shop })
                });
            } catch(e) { 
                console.error("Tracking Error", e); 
            }
        }
    };

    // --- INIT CLIENT MODE ---
    function initClientMode() {
        console.log("🌍 Mode CLIENT activé");
        document.body.classList.add('client-mode');
        const adminZone = document.getElementById('admin-only-zone');
        if(adminZone) adminZone.style.display = 'none';
        
        if (autoProductImage) {
            console.log("📸 Image produit auto:", autoProductImage);
            const img = document.getElementById('prevC');
            if(img) {
                img.src = autoProductImage;
                img.style.display = 'block';
                if(img.parentElement) {
                    const emptyState = img.parentElement.querySelector('.empty-state');
                    if(emptyState) emptyState.style.display = 'none';
                }
            }
        }
    }

    // --- IMAGE PREVIEW ---
    window.preview = function(inputId, imgId) {
        const file = document.getElementById(inputId).files[0];
        if(file) {
            const reader = new FileReader();
            reader.onload = e => {
                const img = document.getElementById(imgId);
                img.src = e.target.result;
                img.style.display = 'block';
                const content = img.parentElement.querySelector('.empty-state');
                if(content) content.style.display = 'none';
            };
            reader.readAsDataURL(file);
        }
    };

    // --- UPDATE WIDGET PREVIEW ---
    window.updateWidgetPreview = function() {
        const text = document.getElementById('ws-text').value;
        const color = document.getElementById('ws-color').value;
        const textColor = document.getElementById('ws-text-color').value;
        const btn = document.getElementById('ws-preview-btn');
        if(btn) {
            btn.style.backgroundColor = color;
            btn.style.color = textColor;
            const span = btn.querySelector('span');
            if(span) span.innerText = text;
        }
    }

    // --- TEST CORS (TEMPORAIRE) ---
    window.testCORS = async function() {
        console.log("🧪 TEST CORS/PROXY DÉMARRÉ");
        
        let testUrl;
        if (mode === 'client' || window.self !== window.top) {
            // En mode client, utiliser le proxy Shopify
            testUrl = `https://${shop}/apps/tryon/test`;
            console.log("   Mode: PROXY via Shopify");
        } else {
            // En mode admin, utiliser l'URL actuelle
            testUrl = `${window.location.origin}/api/test-cors`;
            console.log("   Mode: DIRECT");
        }
        
        console.log("   URL:", testUrl);
        
        try {
            const response = await fetch(testUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ test: true })
            });
            
            console.log("✅ Réponse reçue:", response.status);
            const data = await response.json();
            console.log("   Data:", data);
            alert(`✅ CONNECTION OK: ${data.message}`);
        } catch (error) {
            console.error("❌ Erreur:", error);
            alert(`❌ CONNECTION FAILED: ${error.message}`);
        }
    }

    // --- GENERATE (VERSION CORRIGÉE CORS) ---
    window.generate = async function(event) {
        // EMPÊCHER toute navigation par défaut
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        
        console.log("🚀 ========== DÉBUT GÉNÉRATION ==========");
        console.log("   📍 Shop:", shop);
        console.log("   📍 Mode:", mode);
        
        // VALIDATION SHOP
        if (!shop) {
            console.error("❌ SHOP MANQUANT - ARRÊT");
            alert("Configuration error: Shop information missing. Please contact support.");
            return;
        }
        
        const uFile = document.getElementById('uImg').files[0];
        const cFile = document.getElementById('cImg').files[0];
        const btn = document.getElementById('btnGo');
        
        console.log("📂 Fichiers détectés:");
        console.log("   - Photo utilisateur:", uFile ? uFile.name : "MANQUANT");
        console.log("   - Vêtement (fichier):", cFile ? cFile.name : "non fourni");
        console.log("   - Vêtement (URL):", autoProductImage || "non fourni");
        
        if (!uFile) {
            alert("Please upload your photo.");
            return;
        }
        
        if (!autoProductImage && !cFile) {
            alert("Please upload a garment.");
            return;
        }

        const oldText = btn.innerHTML;
        btn.disabled = true; 
        btn.innerHTML = "Generating...";

        document.getElementById('resZone').style.display = 'block';
        document.getElementById('loader').style.display = 'block';
        document.getElementById('resImg').style.display = 'none';
        document.getElementById('post-actions').style.display = 'none';

        const textEl = document.getElementById('loader-text');
        const texts = [
            "Analyzing silhouette...", 
            "Matching fabrics...", 
            "Simulating drape...", 
            "Rendering lighting..."
        ];
        let step = 0;
        const interval = setInterval(() => { 
            if(step < texts.length) textEl.innerText = texts[step++]; 
        }, 2500);

        try {
            console.log("📦 Conversion des images en Base64...");
            
            // Convertir l'image utilisateur en Base64
            const personBase64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(uFile);
            });
            console.log("   ✅ Photo utilisateur convertie:", personBase64.substring(0, 50) + "...");
            
            // Préparer le payload JSON
            const payload = {
                shop: shop,
                person_image_base64: personBase64,
                category: "upper_body"
            };
            
            if(cFile) {
                const clothingBase64 = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result.split(',')[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(cFile);
                });
                payload.clothing_file_base64 = clothingBase64;
                console.log("   ✅ Fichier vêtement converti");
            } else if (autoProductImage) {
                payload.clothing_url = autoProductImage;
                console.log("   ✅ URL vêtement ajoutée:", autoProductImage);
            }
            
            console.log("📋 Payload prêt:", {
                shop: payload.shop,
                person_image_length: payload.person_image_base64?.length || 0,
                clothing_url: payload.clothing_url || 'fichier',
                category: payload.category
            });

            // DÉTECTION DU BON ENDPOINT selon le contexte
            let apiUrl;
            
            // Si on est en iframe Shopify (mode client), utiliser le PROXY Shopify
            if (mode === 'client' || window.self !== window.top) {
                apiUrl = `https://${shop}/apps/tryon/generate`;
                console.log("🔄 Mode iframe - Utilisation du Proxy Shopify");
            } else {
                // Sinon, URL directe (admin mode) - utiliser l'URL actuelle
                apiUrl = `${window.location.origin}/api/generate`;
                console.log("🏠 Mode admin - URL directe");
            }
            
            console.log("🎯 URL cible:", apiUrl);
            console.log("📤 Envoi de la requête POST (JSON)...");
            
            const fetchStartTime = Date.now();
            
            // FETCH avec CORS et credentials
            let res;
            try {
                // Utiliser authenticatedFetch pour les requêtes admin
                if (mode !== 'client') {
                    res = await authenticatedFetch(apiUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        },
                        body: JSON.stringify(payload)
                    });
                } else {
                    // Mode client (storefront) - fetch normal
                    res = await fetch(apiUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        },
                        body: JSON.stringify(payload),
                        mode: 'cors',
                        credentials: 'include',
                        cache: 'no-cache'
                    });
                }
                console.log("✅ Fetch returned successfully");
            } catch (fetchError) {
                console.error("❌ Fetch exception:", fetchError);
                console.error("   - Name:", fetchError.name);
                console.error("   - Message:", fetchError.message);
                
                // Diagnostic supplémentaire
                if (fetchError.name === 'TypeError' && fetchError.message.includes('Failed to fetch')) {
                    console.error("⚠️ PROBABLE: Blocage CORS ou réseau");
                    alert("Network error: Unable to reach server. Please check your connection or contact support.");
                } else {
                    alert(`Network error: ${fetchError.message}`);
                }
                
                throw fetchError;
            }
            
            const fetchDuration = Date.now() - fetchStartTime;
            console.log(`📡 Réponse reçue en ${fetchDuration}ms`);
            console.log("   - Status:", res.status);
            console.log("   - Status Text:", res.statusText);

            clearInterval(interval);

            if (!res) {
                console.error("❌ Pas de réponse du serveur");
                document.getElementById('loader').style.display = 'none';
                alert("Network error: No response from server");
                return;
            }
            
            if (res.status === 429) { 
                console.warn("⚠️ Rate limit atteint");
                alert("Daily limit reached. Please try again tomorrow."); 
                document.getElementById('loader').style.display = 'none'; 
                return; 
            }
            
            if (res.status === 402) { 
                console.warn("⚠️ Crédits insuffisants");
                alert("This shop has run out of credits!"); 
                btn.disabled = false; 
                btn.innerHTML = oldText; 
                document.getElementById('loader').style.display = 'none';
                return; 
            }
            
            if (!res.ok) {
                const errorText = await res.text();
                console.error("❌ Erreur serveur:", errorText);
                
                try {
                    const errorData = JSON.parse(errorText);
                    throw new Error(errorData.error || "Server Error");
                } catch(e) {
                    throw new Error(`Server Error (${res.status}): ${errorText.substring(0, 200)}`);
                }
            }

            console.log("📥 Parsing de la réponse JSON...");
            const data = await res.json();
            console.log("✅ Données reçues:", data);
            
            if(data.result_image_url){
                console.log("🖼️ Chargement de l'image:", data.result_image_url);
                const ri = document.getElementById('resImg');
                ri.src = data.result_image_url;
                ri.onload = () => { 
                    ri.style.display = 'block'; 
                    document.getElementById('loader').style.display = 'none'; 
                    document.getElementById('post-actions').style.display = 'block';
                    console.log("✅ ========== IMAGE AFFICHÉE ==========");
                };
                ri.onerror = () => {
                    console.error("❌ Erreur chargement image:", data.result_image_url);
                    alert("Error loading result image");
                    document.getElementById('loader').style.display = 'none';
                };
            } else { 
                console.error("❌ Pas d'URL d'image dans la réponse");
                alert("Error: " + (data.error || "No image URL received")); 
                document.getElementById('loader').style.display = 'none'; 
            }
        } catch(e) { 
            clearInterval(interval); 
            console.error("❌ ========== EXCEPTION ==========");
            console.error("Type:", e.name);
            console.error("Message:", e.message);
            console.error("Stack:", e.stack);
            alert("Error: " + e.message); 
            document.getElementById('loader').style.display = 'none'; 
        } finally { 
            btn.disabled = false; 
            btn.innerHTML = oldText; 
            console.log("🏁 ========== FIN GÉNÉRATION ==========");
        }
    };

    // --- BUY CREDITS (PACKS) ---
    window.buy = async function(packId, customAmount, btnElement, event) {
        // Empêcher la propagation de l'événement
        if(event) {
            event.preventDefault();
            event.stopPropagation();
        }
        
        if(!shop) {
            alert("Shop not detected! Please reload the page.");
            return;
        }
        
        console.log("🛒 Achat de crédits:", { packId, customAmount, shop });
        
        const originalContent = btnElement ? btnElement.innerHTML : "Buy";
        if(btnElement) {
            btnElement.innerHTML = "Processing...";
            btnElement.disabled = true;
        }

        try {
            const payload = {
                shop: shop,
                pack_id: packId,
                custom_amount: customAmount || 0
            };

            console.log("📤 Envoi requête:", payload);

            const res = await authenticatedFetch('/api/buy-credits', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            console.log("📥 Réponse reçue:", res);

            if(res && res.ok) {
                const data = await res.json();
                console.log("✅ Données reçues:", data);
                
                if(data.confirmation_url) {
                    console.log("🔄 Redirection vers:", data.confirmation_url);
                    // Utiliser window.top pour sortir de l'iframe si nécessaire
                    if(window.top !== window.self) {
                        window.top.location.href = data.confirmation_url;
                    } else {
                        window.location.href = data.confirmation_url;
                    }
                } else {
                    console.error("❌ Pas de confirmation_url dans la réponse");
                    alert("Error: No confirmation URL received. Response: " + JSON.stringify(data));
                }
            } else {
                const errorData = await res.json().catch(() => ({ error: "Failed to parse error response" }));
                console.error("❌ Erreur:", errorData);
                alert("Purchase failed: " + (errorData.error || errorData.detail || "Unknown error"));
            }
        } catch(e) {
            console.error("❌ Buy Error:", e);
            alert("Network error during purchase: " + e.message);
        } finally {
            if(btnElement) {
                btnElement.innerHTML = originalContent;
                btnElement.disabled = false;
            }
        }
    };

    // --- BUY CUSTOM AMOUNT ---
    window.buyCustom = async function(btn) {
        const customAmountInput = document.getElementById('customAmount');
        const amount = parseInt(customAmountInput.value);

        if(!amount || amount < 10) {
            return alert("Please enter at least 10 credits");
        }

        if(amount > 10000) {
            return alert("Maximum 10,000 credits per order. Contact support for larger volumes.");
        }

        const originalText = btn.innerHTML;
        btn.innerHTML = "Processing...";
        btn.disabled = true;

        try {
            const payload = {
                shop: shop,
                pack_id: 'pack_custom',
                custom_amount: amount
            };

            const res = await authenticatedFetch('/api/buy-credits', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            if(res && res.ok) {
                const data = await res.json();
                if(data.confirmation_url) {
                    window.top.location.href = data.confirmation_url;
                } else {
                    alert("Error: No confirmation URL received");
                }
            } else {
                const errorData = await res.json().catch(() => ({}));
                alert("Purchase failed: " + (errorData.error || "Unknown error"));
            }
        } catch(e) {
            console.error("Custom Buy Error:", e);
            alert("Network error during purchase");
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    };

});
