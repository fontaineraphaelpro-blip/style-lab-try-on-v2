# 🎨 VTON AI - Virtual Try-On for Shopify

AI-powered virtual try-on app for Shopify merchants. Powered by Replicate's IDM-VTON model.

## 🚀 Features

- ✨ **Realistic Virtual Try-On**: State-of-the-art AI model
- 📊 **Analytics Dashboard**: Track usage, conversions, performance
- 🎨 **Customizable Widget**: Brand-aligned storefront integration
- 💳 **Flexible Billing**: Pay-as-you-go credit system
- 🔒 **GDPR Compliant**: Full data privacy controls
- ⚡ **Fast**: Optimized for < 4s generation time

## 📁 Project Structure

```
vton-shopify-app/
├── backend/              # FastAPI backend
│   ├── main.py          # Main entry point
│   ├── database.py      # DB configuration
│   ├── routes/          # API routes
│   │   ├── admin.py     # Admin dashboard API
│   │   ├── proxy.py     # App Proxy (storefront)
│   │   └── webhooks.py  # Shopify webhooks
│   ├── services/        # Business logic
│   └── migrations/      # Database schemas
├── widget/              # Storefront widget
├── docs/                # Documentation
└── shopify.app.toml     # Shopify app config
```

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **AI**: Replicate (IDM-VTON)
- **Hosting**: Render
- **Frontend**: React (coming soon)

## 🏃 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL
- Shopify Partner account
- Replicate API token

### Installation

1. **Clone the repository**
```bash
git clone <your-repo>
cd vton-shopify-app
```

2. **Set up backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. **Initialize database**
```bash
# Apply schema
psql $DATABASE_URL < migrations/schema.sql
```

5. **Run server**
```bash
python main.py
```

Server runs on http://localhost:8000

## 🌐 API Endpoints

### Admin API (Authenticated)
- `GET /api/admin/dashboard` - Get dashboard data
- `POST /api/admin/settings` - Save widget settings
- `GET /api/admin/stats/daily` - Daily statistics
- `GET /api/admin/products/top` - Top tried products

### App Proxy (Public Storefront)
- `GET /apps/tryon/widget.js` - Widget JavaScript
- `POST /apps/tryon/generate` - Generate try-on

### Webhooks
- `POST /webhooks/customers/data_request` - GDPR data request
- `POST /webhooks/customers/redact` - GDPR redaction
- `POST /webhooks/shop/redact` - Shop data deletion
- `POST /webhooks/app/uninstalled` - App uninstalled

## 📊 Database Schema

### Tables
- `shops` - Shop configurations and credits
- `tryon_logs` - Try-on generation history
- `rate_limits` - Per-IP rate limiting
- `credit_purchases` - Billing history

See `backend/migrations/schema.sql` for full schema.

## 🚢 Deployment (Render)

### Automatic Deployment
```bash
git push origin main
# Render auto-deploys
```

### Manual Setup
1. Create PostgreSQL database on Render
2. Create Web Service linked to repo
3. Set environment variables:
   - `DATABASE_URL`
   - `SHOPIFY_API_KEY`
   - `SHOPIFY_API_SECRET`
   - `REPLICATE_API_TOKEN`

## 🧪 Testing

### Health Check
```bash
curl http://localhost:8000/health
```

### API Documentation
Visit http://localhost:8000/docs for interactive Swagger docs.

## 📈 Monitoring

- Health endpoint: `/health`
- Logs: Check Render dashboard
- Database: Monitor via Render PostgreSQL dashboard

## 🔐 Security

- Session Token authentication for admin routes
- Rate limiting per IP
- HMAC verification for webhooks (TODO)
- Input validation with Pydantic

## 📝 TODO

- [ ] Implement JWT Session Token verification
- [ ] Add Redis caching layer
- [ ] Build React admin dashboard
- [ ] Implement webhook HMAC verification
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Set up CI/CD pipeline
- [ ] Add monitoring (Sentry)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 License

Proprietary - All rights reserved

## 🆘 Support

- Email: support@yourdomain.com
- Documentation: docs/
- Issues: GitHub Issues

## 🎯 Roadmap

### v2.1 (Next)
- React Admin Dashboard
- Session Token auth
- Enhanced analytics

### v2.2
- Multi-language support
- Mobile app widget
- Batch processing

### v3.0
- Custom AI model training
- Real-time try-on
- AR integration

---

Built with ❤️ for Shopify merchants