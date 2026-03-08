# Best Trade - UK's #1 All-Trades Marketplace

**Subscription-based marketplace connecting UK homeowners with verified trade professionals.**

## Live Site
https://besttrade.uk

## What is Best Trade?

Best Trade connects customers with verified tradespeople across all trades through a subscription model.

### For Customers
- Post jobs for free
- Get quotes from verified professionals
- Review and rate tradespeople

### For Tradespeople
- Subscribe for lead access (£20-£200/year)
- Receive job alerts via email and SMS
- Manage jobs through dashboard
- Grow your business

## Subscription Tiers

| Tier | Price | Coverage | Features |
|------|-------|----------|----------|
| **Basic** | £20/month | 10 miles | Email alerts, unlimited quotes |
| **Pro** | £30/month | 20 miles | Email + SMS alerts, priority listing |
| **Premium** | £200/year | UK-wide | Top listing, verified badge, featured |

## Technology Stack

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL
- **Payments:** Stripe
- **SMS:** Twilio
- **Email:** SendGrid
- **Hosting:** Railway.app

## Repository Structure

```
besttrade-platform/
├── main.py                          # FastAPI backend
├── database.py                      # Database connection
├── notification_service.py          # SMS/Email notifications
├── subscription_endpoints.py        # Stripe subscription logic
├── database_migration_v2.sql        # Database schema
├── requirements.txt                 # Python dependencies
├── Procfile                         # Railway deployment
├── railway.json                     # Railway config
└── frontend/
    ├── index.html                   # Homepage
    ├── about.html                   # About page
    ├── pricing.html                 # Subscription pricing
    ├── tradesperson-register.html   # Registration
    ├── tradesperson-dashboard.html  # Dashboard
    └── customer-post-job.html       # Job posting
```

## Deployment

Platform auto-deploys from this repository to Railway.
Push to `main` branch triggers automatic deployment.

**Live:** https://besttrade.uk  
**Status:** Production

## Environment Variables

Set these in Railway dashboard:

```
DATABASE_URL=postgresql://...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+44...
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=hello@besttrade.uk
APP_URL=https://besttrade.uk
```

## Current Status

**Platform:** Live at besttrade.uk  
**Next Milestone:** 100 paying subscribers  
**Target Revenue:** £2,267/month MRR

## License

Proprietary - All rights reserved
