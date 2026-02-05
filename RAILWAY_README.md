# 🚀 PlumbFlow - Deploy to Railway

## Quick Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

## What's Included

This repository contains the complete PlumbFlow platform:

- ✅ Frontend (6 mobile-responsive HTML pages)
- ✅ Backend API (FastAPI)
- ✅ Job scraping automation
- ✅ Plumber matching engine
- ✅ Payment processing (Stripe)
- ✅ SMS notifications (Twilio)
- ✅ Email service (SendGrid)
- ✅ AI job analysis (OpenAI)

## Prerequisites

You need accounts with:

1. **Stripe** (https://stripe.com) - Free
2. **Twilio** (https://twilio.com) - £15 free credit
3. **SendGrid** (https://sendgrid.com) - Free tier
4. **OpenAI** (https://platform.openai.com) - $5 free credit

## Railway Deployment Steps

### 1. Fork or Upload This Repo to GitHub

```bash
# Option A: Fork this repo on GitHub

# Option B: Upload to your own repo
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/plumbflow-platform
git push -u origin main
```

### 2. Deploy to Railway

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `plumbflow-platform`
5. Click "Deploy"

### 3. Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database"
3. Choose "PostgreSQL"
4. Wait for provisioning

### 4. Set Environment Variables

In Railway → Variables, add these:

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
TWILIO_ACCOUNT_SID=YOUR_SID_HERE
TWILIO_AUTH_TOKEN=YOUR_TOKEN_HERE
TWILIO_PHONE_NUMBER=+44XXXXXXXXXX
SENDGRID_API_KEY=SG.YOUR_KEY_HERE
SENDGRID_FROM_EMAIL=hello@plumbflow.co.uk
OPENAI_API_KEY=sk-YOUR_KEY_HERE
APP_NAME=PlumbFlow
APP_URL=https://plumbflow.co.uk
SECRET_KEY=generate-a-random-string-here
```

### 5. Initialize Database

**Option A - Railway CLI:**

```bash
npm install -g @railway/cli
railway login
railway link
railway run psql $DATABASE_URL < database_schema.sql
```

**Option B - TablePlus (GUI):**

1. Download TablePlus (https://tableplus.com)
2. Connect using Railway's DATABASE_URL
3. Import `database_schema.sql`

### 6. Add Custom Domain

1. Railway → Settings → Domains
2. Click "Custom Domain"
3. Enter: `plumbflow.co.uk`
4. Add DNS records to your domain registrar:

```
Type: CNAME
Host: www
Value: your-app.up.railway.app

Type: A
Host: @
Value: [Railway's IP]
```

### 7. Verify Deployment

Visit: `https://your-app.up.railway.app`

You should see the PlumbFlow homepage!

## File Structure

```
plumbflow-platform/
├── frontend/              # Web interface
│   ├── index.html        # Landing page
│   ├── plumber-login.html
│   ├── plumber-register.html
│   ├── plumber-dashboard.html
│   ├── customer-post-job.html
│   └── admin-login.html
├── main.py               # FastAPI application
├── ad_scraper.py         # Job scraping
├── plumber_scraper.py    # Plumber recruitment
├── matching_engine.py    # Job matching
├── pay_per_lead.py       # Payment processing
├── database_schema.sql   # Database structure
├── requirements.txt      # Python dependencies
├── railway.json          # Railway config
└── .env.example          # Environment template
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Run database migrations
psql $DATABASE_URL < database_schema.sql

# Start the server
uvicorn main:app --reload

# Visit http://localhost:8000
```

## Features

### For Customers
- Post plumbing jobs for free
- Get matched with local plumbers
- Receive quotes within 15 minutes

### For Plumbers
- Register and create profile
- Receive instant lead notifications
- Accept/decline leads
- Pay only for accepted leads (£10-25)

### For Admin
- View all scraped ads
- Monitor platform statistics
- Track revenue and matches
- Manage plumbers and jobs

## Environment Variables Explained

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `DATABASE_URL` | PostgreSQL connection | Railway auto-provides |
| `STRIPE_SECRET_KEY` | Stripe API secret | stripe.com → API Keys |
| `STRIPE_PUBLISHABLE_KEY` | Stripe public key | stripe.com → API Keys |
| `TWILIO_ACCOUNT_SID` | Twilio account ID | twilio.com → Console |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | twilio.com → Console |
| `TWILIO_PHONE_NUMBER` | Your Twilio number | Buy in Twilio console |
| `SENDGRID_API_KEY` | SendGrid API key | sendgrid.com → API Keys |
| `OPENAI_API_KEY` | OpenAI API key | platform.openai.com |

## Scaling

Railway automatically scales based on your usage:

- **Starter**: Free $5 credit
- **Pro**: $20/month (2GB RAM)
- **Scale**: Pay as you grow

Expected costs at different scales:

| Jobs/Day | Railway Cost | Twilio | SendGrid | Total/Month |
|----------|--------------|--------|----------|-------------|
| 0-50 | Free | £5 | Free | £5 |
| 50-200 | $20 | £15 | Free | £31 |
| 200-1000 | $50 | £50 | £20 | £87 |

## Support

For issues:
1. Check Railway logs
2. Verify environment variables
3. Check database connection
4. Review the guides in the repo

## License

Proprietary - PlumbFlow Platform

---

**Ready to launch?** Follow the guide above or check `LAUNCH_NOW_PLUMBFLOW.md` for detailed step-by-step instructions!
