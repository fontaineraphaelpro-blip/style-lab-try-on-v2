/**
 * Frontend JavaScript pour le Dashboard Admin
 * ============================================
 * 
 * INTÉGRATION DANS LE TEMPLATE :
 * - Utilise App Bridge automatiquement injecté par Shopify
 * - Les routes API utilisent res.locals.shopify.session du template
 * - Ne modifie PAS le flow OAuth/tokens
 */

document.addEventListener("DOMContentLoaded", function() {
    console.log("🚀 VTON Dashboard loaded");

    // Récupérer le shop depuis la session (géré par le template)
    const shop = window.location.search.match(/shop=([^&]+)/)?.[1] || 
                 document.body.getAttribute('data-shop');

    // App Bridge est automatiquement disponible via le template
    let shopifyApp = window.shopify;

    async function getSessionToken() {
        try {
            if (shopifyApp?.id) {
                return await shopifyApp.id.getToken();
            }
        } catch (e) {
            console.warn("⚠️ Error getting session token:", e);
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
            if (shop && !url.includes('shop=')) {
                const separator = url.includes('?') ? '&' : '?';
                url = `${url}${separator}shop=${encodeURIComponent(shop)}`;
            }
            return await fetch(url, { 
                ...options, 
                headers,
                mode: 'cors',
                credentials: 'include'
            });
        } catch (error) {
            console.error("❌ Fetch error:", error);
            throw error;
        }
    }

    // Initialiser le dashboard
    if (shop) {
        initAdminMode(shop);
    }

    async function initAdminMode(s) {
        console.log("🚀 Initializing admin mode for:", s);
        
        document.body.style.display = 'block';
        const adminZone = document.getElementById('admin-only-zone');
        if (adminZone) {
            adminZone.style.display = 'block';
        }
        
        try {
            const res = await authenticatedFetch('/api/get-data');
            
            if (res && res.ok) {
                const data = await res.json();
                console.log("✅ Dashboard data:", data);

                updateDashboardStats(data.credits || 0);
                updateVIPStatus(data.lifetime || 0);

                const tryEl = document.getElementById('stat-tryons');
                const atcEl = document.getElementById('stat-atc');
                if (tryEl) tryEl.innerText = data.usage || 0;
                if (atcEl) atcEl.innerText = data.atc || 0;

                if (data.widget) {
                    document.getElementById('ws-text').value = data.widget.text || "Try It On Now ✨";
                    document.getElementById('ws-color').value = data.widget.bg || "#000000";
                    document.getElementById('ws-text-color').value = data.widget.color || "#ffffff";
                    if (data.security) {
                        document.getElementById('ws-limit').value = data.security.max_tries || 5;
                    }
                    updateWidgetPreview();
                }
            } else {
                console.error("❌ Error loading dashboard data");
                updateDashboardStats(0);
                updateVIPStatus(0);
            }
        } catch (error) {
            console.error("❌ Error initializing dashboard:", error);
            updateDashboardStats(0);
            updateVIPStatus(0);
        }
    }

    function updateDashboardStats(credits) {
        const el = document.getElementById('credits');
        if (el) el.innerText = credits;
        const supplyCard = document.querySelector('.smart-supply-card');
        const alertBadge = document.querySelector('.alert-badge');
        const daysEl = document.querySelector('.rs-value');
        if (supplyCard && daysEl) {
            let daysLeft = Math.floor(credits / 8);
            if (daysLeft < 1) daysLeft = "< 1";
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
        if (percent > 100) percent = 100;
        if (fill) fill.style.width = percent + "%";
        if (marker) marker.style.left = percent + "%";
        if (lifetime >= 500) {
            const title = document.querySelector('.vip-title strong');
            if (title) title.innerText = "Gold Member";
        }
    }

    // Save Settings
    window.saveSettings = async function(btn) {
        const oldText = btn.innerText;
        btn.innerText = "Saving...";
        btn.disabled = true;
        
        const settings = {
            text: document.getElementById('ws-text').value,
            bg: document.getElementById('ws-color').value,
            color: document.getElementById('ws-text-color').value,
            max_tries: parseInt(document.getElementById('ws-limit').value) || 5
        };
        
        try {
            const res = await authenticatedFetch('/api/save-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            
            if (res && res.ok) {
                btn.innerText = "Saved! ✅";
                setTimeout(() => btn.innerText = oldText, 2000);
            } else {
                alert("Save failed");
            }
        } catch (e) {
            console.error(e);
            alert("Error saving");
        } finally {
            btn.disabled = false;
        }
    };

    // Track Add to Cart
    window.trackATC = async function() {
        if (shop) {
            try {
                await authenticatedFetch('/api/track-atc', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
            } catch (e) {
                console.error("Tracking Error", e);
            }
        }
    };

    // Preview image
    window.preview = function(inputId, imgId) {
        const file = document.getElementById(inputId).files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = e => {
                const img = document.getElementById(imgId);
                img.src = e.target.result;
                img.style.display = 'block';
                const content = img.parentElement.querySelector('.empty-state');
                if (content) content.style.display = 'none';
            };
            reader.readAsDataURL(file);
        }
    };

    // Update widget preview
    window.updateWidgetPreview = function() {
        const text = document.getElementById('ws-text').value;
        const color = document.getElementById('ws-color').value;
        const textColor = document.getElementById('ws-text-color').value;
        const btn = document.getElementById('ws-preview-btn');
        if (btn) {
            btn.style.backgroundColor = color;
            btn.style.color = textColor;
            const span = btn.querySelector('span');
            if (span) span.innerText = text;
        }
    };

    // Generate try-on
    window.generate = async function(event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        if (!shop) {
            alert("Configuration error: Shop information missing.");
            return;
        }

        const uFile = document.getElementById('uImg').files[0];
        const cFile = document.getElementById('cImg').files[0];
        const btn = document.getElementById('btnGo');

        if (!uFile) {
            alert("Please upload your photo.");
            return;
        }

        if (!cFile) {
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

        try {
            const personBase64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(uFile);
            });

            const clothingBase64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(cFile);
            });

            const payload = {
                person_image_base64: personBase64,
                clothing_file_base64: clothingBase64,
                category: "upper_body"
            };

            const res = await authenticatedFetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.error || "Server Error");
            }

            const data = await res.json();

            if (data.result_image_url) {
                const ri = document.getElementById('resImg');
                ri.src = data.result_image_url;
                ri.onload = () => {
                    ri.style.display = 'block';
                    document.getElementById('loader').style.display = 'none';
                    document.getElementById('post-actions').style.display = 'block';
                };
            } else {
                throw new Error("No image URL received");
            }
        } catch (e) {
            console.error("❌ Generation error:", e);
            alert("Error: " + e.message);
            document.getElementById('loader').style.display = 'none';
        } finally {
            btn.disabled = false;
            btn.innerHTML = oldText;
        }
    };

    // Buy credits
    window.buy = async function(packId, customAmount, btnElement, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        if (!shop) {
            alert("Shop not detected! Please reload the page.");
            return;
        }

        const originalContent = btnElement ? btnElement.innerHTML : "Buy";
        if (btnElement) {
            btnElement.innerHTML = "Processing...";
            btnElement.disabled = true;
        }

        try {
            const payload = {
                pack_id: packId,
                custom_amount: customAmount || 0
            };

            const res = await authenticatedFetch('/api/buy-credits', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res && res.ok) {
                const data = await res.json();
                if (data.confirmation_url) {
                    if (window.top !== window.self) {
                        window.top.location.href = data.confirmation_url;
                    } else {
                        window.location.href = data.confirmation_url;
                    }
                } else {
                    alert("Error: No confirmation URL received");
                }
            } else {
                const errorData = await res.json().catch(() => ({ error: "Unknown error" }));
                alert("Purchase failed: " + (errorData.error || errorData.detail));
            }
        } catch (e) {
            console.error("❌ Buy Error:", e);
            alert("Network error during purchase: " + e.message);
        } finally {
            if (btnElement) {
                btnElement.innerHTML = originalContent;
                btnElement.disabled = false;
            }
        }
    };

    // Buy custom amount
    window.buyCustom = async function(btn) {
        const customAmountInput = document.getElementById('customAmount');
        const amount = parseInt(customAmountInput.value);

        if (!amount || amount < 10) {
            return alert("Please enter at least 10 credits");
        }

        if (amount > 10000) {
            return alert("Maximum 10,000 credits per order.");
        }

        const originalText = btn.innerHTML;
        btn.innerHTML = "Processing...";
        btn.disabled = true;

        try {
            const payload = {
                pack_id: 'pack_custom',
                custom_amount: amount
            };

            const res = await authenticatedFetch('/api/buy-credits', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res && res.ok) {
                const data = await res.json();
                if (data.confirmation_url) {
                    window.top.location.href = data.confirmation_url;
                } else {
                    alert("Error: No confirmation URL received");
                }
            } else {
                const errorData = await res.json().catch(() => ({}));
                alert("Purchase failed: " + (errorData.error || "Unknown error"));
            }
        } catch (e) {
            console.error("Custom Buy Error:", e);
            alert("Network error during purchase");
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    };
});

