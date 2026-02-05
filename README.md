# Plumber Matching Platform - Complete System

**Automated lead aggregation and distribution platform for plumbers in London & South East England**

## 🎯 What This Does

This platform automatically:
1. **Scrapes** plumbing job ads from Gumtree, Facebook, and other platforms
2. **Analyzes** ads using AI to extract job details (type, urgency, location)
3. **Calculates** dynamic pricing based on job complexity and plumber rates
4. **Matches** jobs to the best available plumbers using intelligent algorithm
5. **Notifies** plumbers via SMS, email, and push notifications
6. **Charges** £10-25 finder's fee per lead automatically
7. **Manages** plumber credits and payment processing

**You earn £25 per successful job match with ZERO manual intervention.**

---

## 📁 Project Structure

```
plumber-platform/
├── database_schema.sql          # PostgreSQL database schema
├── ad_scraper.py               # Automated ad scraping from multiple platforms
├── pricing_calculator.py       # Dynamic pricing engine
├── matching_engine.py          # Plumber-job matching algorithm
├── notification_service.py     # SMS/Email/Push notifications
├── payment_system.py           # Stripe payment & credit management
├── main_orchestrator.py        # Main automation orchestrator
├── plumber_dashboard.html      # Web dashboard for plumbers
└── README.md                   # This file
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AD SCRAPING LAYER                         │
│  Gumtree │ Facebook │ Nextdoor │ Email Forwarding            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  AI PROCESSING                               │
│  • Extract job type, urgency, location                       │
│  • Validate quality                                          │
│  • Deduplicate                                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                MATCHING ENGINE                               │
│  • Score plumbers (distance 40%, availability 25%, etc)      │
│  • Rank top 3 matches                                        │
│  • Calculate custom pricing for each                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              NOTIFICATION SYSTEM                             │
│  • Push notification (instant)                               │
│  • SMS (instant)                                            │
│  • Email (backup)                                           │
│  • Voice call (emergency only)                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              PAYMENT PROCESSING                              │
│  • Deduct finder's fee from plumber credits                  │
│  • Auto-reload when low                                      │
│  • Track all transactions                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 14+
- Stripe account (for payments)
- Twilio account (for SMS)
- SendGrid account (for email)

### 1. Install Dependencies

```bash
# Install Python packages
pip install psycopg2-binary requests beautifulsoup4 openai stripe twilio sendgrid schedule

# Install database
# macOS:
brew install postgresql
# Ubuntu:
sudo apt install postgresql
```

### 2. Set Up Database

```bash
# Start PostgreSQL
psql postgres

# Create database
CREATE DATABASE plumber_platform;

# Run schema
psql plumber_platform < database_schema.sql
```

### 3. Configure Environment Variables

Create a `.env` file:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/plumber_platform

# OpenAI (for AI analysis)
OPENAI_API_KEY=sk-...

# Stripe (for payments)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# Twilio (for SMS)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+44...

# SendGrid (for email)
SENDGRID_API_KEY=SG...
FROM_EMAIL=noreply@yourplatform.com
```

### 4. Run Platform

```bash
# Single test cycle
python main_orchestrator.py

# Continuous operation (scrapes every 15 mins)
# Edit main_orchestrator.py and uncomment:
# platform.start_continuous_operation(interval_minutes=15)
```

### 5. Open Plumber Dashboard

```bash
# Open in browser
open plumber_dashboard.html
```

---

## 💰 Pricing Structure

### Dynamic Finder's Fee

| Job Value    | Finder's Fee | Example Jobs            |
|--------------|--------------|-------------------------|
| Under £75    | £10          | Washer replacement      |
| £75-£150     | £15          | Tap repair, sink unblock|
| £150-£300    | £25 ⭐       | Toilet replacement      |
| Over £300    | 10% (max £50)| Shower installation     |

### Plumber Credit Packages

| Purchase | Bonus  | Total   | Est. Leads |
|----------|--------|---------|------------|
| £100     | £0     | £100    | 4-10       |
| £250     | £12.50 | £262.50 | 10-25 ⭐    |
| £500     | £37.50 | £537.50 | 20-50      |
| £1000    | £100   | £1,100  | 40-100     |

---

## 🎯 Matching Algorithm

### Scoring Weights

1. **Distance (40%)**: Proximity to job location
   - Primary area (< 5km): 100 points
   - Secondary area (5-10km): 70 points
   - Extended area (10-20km): 40 points

2. **Availability (25%)**: Current workload & urgency match
   - Available today + low workload: 100 points
   - Busy but available: 50 points
   - Fully booked: 10 points

3. **Specialty (20%)**: Skill match for job type
   - Exact skill match: 100 points
   - Related skill: 70 points
   - General plumbing: 40 points

4. **Performance (10%)**: Historical metrics
   - 90%+ contact rate: +25 points
   - 50%+ conversion rate: +15 points
   - <50% contact rate: -20 points

5. **Rating (5%)**: Customer reviews
   - 4.8+ stars: 100 points
   - 4.0-4.5 stars: 75 points
   - <4.0 stars: 50 points

**Example:** Plumber scoring 85/100 is ranked #1 and gets first chance at lead.

---

## 📊 Sample Workflow

### Complete Job Flow (Automated)

**10:15 AM** - Ad scraped from Gumtree
```
"Urgent - kitchen tap won't stop dripping, SW19"
```

**10:15 AM** - AI analyzes ad
```
Job type: leaking_tap
Urgency: today
Complexity: easy
Estimated time: 0.5 hrs
Estimated parts: £8
```

**10:16 AM** - System finds 3 matching plumbers
```
#1: John Smith (SW18) - Score: 92/100 - Distance: 2.1km
#2: Sarah Johnson (SW19) - Score: 84/100 - Distance: 1.8km
#3: Mike Williams (CR4) - Score: 71/100 - Distance: 8.4km
```

**10:16 AM** - Pricing calculated for John
```
Labour: 0.5hrs × £65/hr = £75 (minimum callout)
Travel: 2.1km × £0.45 + 15min × £65/hr = £18
Materials: £8
Subtotal: £101
Margin (12%): £12
Finder's fee: £15
───────────────────
Customer pays: £128
Plumber earns: £113
Platform fee: £15
```

**10:16 AM** - Notifications sent to John
```
📱 Push: "New lead: Leaking tap - SW19 - £113 earnings"
📨 SMS: "New lead available! Tap dripping, SW19..."
📧 Email: Detailed lead with customer info
```

**10:18 AM** - John accepts lead (via app)
```
✓ Lead accepted
✓ £15 deducted from credits (new balance: £235)
```

**10:18 AM** - Customer notified
```
📨 SMS to customer: "Plumber found! John Smith will contact you shortly..."
```

**10:20 AM** - John calls customer, arranges visit

**11:00 AM** - Job completed

**Result:**
- Customer: Happy, paid £128
- Plumber: Earned £113 for 1hr work
- Platform: Earned £15 automatically

---

## 🔧 Customization

### Add New Job Types

Edit `pricing_calculator.py`:

```python
'toilet_replacement': PricingCard(
    job_type='toilet_replacement',
    base_time_hours=2.0,
    complexity_multipliers={'easy': 1.0, 'medium': 1.5, 'hard': 2.2},
    parts_cost_range=(100, 250),
    skill_level='medium',
    gas_safe_required=False,
    urgency_multiplier=1.0
)
```

### Adjust Finder's Fee

Edit `pricing_calculator.py`:

```python
def calculate_finder_fee(self, subtotal: float) -> float:
    if subtotal < 75:
        return 10.00  # Change this
    elif subtotal < 150:
        return 15.00  # Change this
    # etc...
```

### Change Matching Weights

Edit `matching_engine.py`:

```python
WEIGHT_DISTANCE = 0.40      # Change these
WEIGHT_AVAILABILITY = 0.25
WEIGHT_SPECIALTY = 0.20
WEIGHT_PERFORMANCE = 0.10
WEIGHT_RATING = 0.05
```

---

## 📱 Plumber Mobile App

The platform includes a web-based dashboard (`plumber_dashboard.html`), but for production you should build native mobile apps:

### Features Needed

1. **Lead Notifications**
   - Push notifications for new leads
   - Accept/decline within app
   - Countdown timer showing expiration

2. **Job Management**
   - View active jobs
   - Update job status
   - Upload photos

3. **Credit Management**
   - View balance
   - Top up credits
   - Transaction history

4. **Performance Analytics**
   - Earnings this week/month
   - Acceptance rate
   - Customer ratings

### Tech Stack Recommendation

- **React Native** (iOS + Android from single codebase)
- **Firebase** (push notifications, authentication)
- **Stripe SDK** (in-app purchases)

---

## 🚨 Legal Considerations

### Web Scraping

**Risks:**
- Terms of Service violations
- IP bans
- Legal action from platforms

**Mitigations:**
1. Use official APIs where available (Facebook Graph API)
2. Implement rate limiting (max 1 request/2 seconds)
3. Rotate IP addresses using proxy service
4. Only scrape public data (no login required)
5. Respect robots.txt

**Alternative Approach (Lower Risk):**
- Build browser extension that plumbers install
- Plumbers manually submit leads they find
- You provide matching and payment services
- 100% legal, no scraping

### Data Protection (GDPR)

Required:
- Privacy policy
- Terms of service
- Cookie consent
- Data retention policy
- Right to be forgotten

### Payment Licensing

If holding customer payments >24 hours:
- May need FCA registration (UK)
- Or use Stripe Connect (they handle licensing)

### Plumber Relationship

**Recommended:** Treat plumbers as independent contractors, not employees
- They choose which leads to accept
- Set their own rates
- Operate their own business

---

## 💳 Payment Processing

### Stripe Integration

```python
# Plumber purchases credits
payment_intent = stripe.PaymentIntent.create(
    amount=25000,  # £250.00 in pence
    currency='gbp',
    metadata={'plumber_id': 1}
)

# Charge lead fee (from plumber credits)
credit_manager.charge_lead_fee(
    plumber_id=1,
    job_id=12345,
    fee_amount=Decimal('25.00'),
    job_title="Leaking tap - SW19"
)

# Payout plumber for completed job
stripe.Transfer.create(
    amount=11300,  # £113.00 in pence
    currency='gbp',
    destination=plumber_stripe_account_id
)
```

---

## 📈 Scaling Strategy

### Phase 1: MVP (Months 1-3)
- Manual lead submission (not scraping)
- 10-20 plumbers in SW London
- £10k initial funding
- Goal: 50 jobs/month

### Phase 2: Semi-Automated (Months 4-6)
- Basic scraping (Gumtree only)
- 50 plumbers across London
- Prove unit economics
- Goal: 200 jobs/month

### Phase 3: Full Automation (Months 7-12)
- Multi-platform scraping
- 100+ plumbers
- AI optimization
- Goal: 1,000 jobs/month

### Phase 4: Profitability (Year 2)
- 200+ plumbers
- Partnership deals with platforms
- Goal: 3,000 jobs/month = £75k revenue/month

---

## 🐛 Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
pg_ctl status

# Restart if needed
pg_ctl restart
```

### SMS Not Sending
```bash
# Verify Twilio credentials
echo $TWILIO_ACCOUNT_SID
echo $TWILIO_AUTH_TOKEN

# Test directly
curl -X POST https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID/Messages.json \
  --data-urlencode "To=+447700900000" \
  --data-urlencode "From=$TWILIO_PHONE_NUMBER" \
  --data-urlencode "Body=Test message" \
  -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN
```

### Scraper Getting Blocked
```bash
# Add delays between requests
time.sleep(5)  # Wait 5 seconds

# Use rotating proxies
# Sign up for Bright Data or ScraperAPI
```

---

## 📞 Support

For issues or questions:
- Email: support@yourplatform.com
- Documentation: docs.yourplatform.com
- Status: status.yourplatform.com

---

## 📄 License

Proprietary - All rights reserved

---

## 🎉 Next Steps

1. **Set up database** (30 mins)
2. **Configure API keys** (20 mins)
3. **Run test cycle** (10 mins)
4. **Recruit 10 plumbers** (1 week)
5. **Launch pilot** (1 month)
6. **Iterate and scale** (ongoing)

**Good luck! You're about to automate your way to success.** 🚀
