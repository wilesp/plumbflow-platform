# 🔍 SCRAPING SOURCES - Current & Recommended for Phase 1

## 📊 Current Status: What We're Scraping NOW

We have **2 separate scrapers** for different purposes:

---

## 1️⃣ JOB AD SCRAPER (Finding Customers)

**Purpose:** Find people who need plumbers

**Current Sources:**
```
✅ Gumtree (implemented)
   - URL: gumtree.com/services/plumbing
   - Coverage: All UK, strong in London
   - Volume: ~50-100 ads/day in London
   - Quality: Medium (some stale ads)

✅ Facebook Marketplace (implemented)
   - URL: facebook.com/marketplace/london/search/?query=plumber
   - Coverage: Excellent in London
   - Volume: ~30-50 ads/day
   - Quality: High (recent posts)

❌ Other sources: Not yet implemented
```

**File:** `ad_scraper.py`

---

## 2️⃣ PLUMBER REGISTRY SCRAPER (Recruiting Plumbers)

**Purpose:** Build database of plumbers to recruit

**Current Sources:**
```
✅ WaterSafe (implemented)
   - URL: watersafe.org.uk
   - Type: Official water regulations registry
   - Plumbers: ~2,000 in London/SE
   
✅ CIPHE (implemented)
   - URL: ciphe.org.uk
   - Type: Chartered plumbers institute
   - Plumbers: ~1,500 in London/SE

✅ APHC (implemented)
   - URL: aphc.co.uk
   - Type: Plumbing contractors association
   - Plumbers: ~1,800 in London/SE

✅ Gas Safe Register (implemented)
   - URL: gassaferegister.co.uk
   - Type: Mandatory for gas work
   - Plumbers: ~3,000 in London/SE

✅ Yell.com (implemented)
   - URL: yell.com/s/plumbers
   - Type: Business directory
   - Plumbers: ~10,000 in London/SE
```

**File:** `plumber_scraper.py`

---

## 🎯 PHASE 1 EXPANSION - London & Home Counties

### Geographic Coverage:

**London Postcodes:**
- All 120+ London areas (N, S, E, W, NW, SE, SW, EC, WC)

**Home Counties (South East England):**
- **Surrey:** GU, KT, RH, SM postcodes
- **Kent:** BR, DA, ME, TN postcodes  
- **Essex:** CM, CO, RM, SS postcodes
- **Hertfordshire:** AL, EN, SG, WD postcodes
- **Berkshire:** RG, SL postcodes
- **Buckinghamshire:** HP, MK, SL postcodes

---

## 🆕 RECOMMENDED ADDITIONS - Job Ad Sources

### HIGH PRIORITY (Add Immediately):

#### 1. **Nextdoor** 🏘️ ⭐⭐⭐⭐⭐
```
URL: nextdoor.co.uk
Why: Hyperlocal community platform
Volume: 20-40 jobs/day in London
Quality: EXCELLENT (real neighbors, urgent needs)
Legal: Grey area but commonly scraped
Setup: Requires account per neighborhood

Pros:
✅ Very high quality leads (real people, real urgency)
✅ Hyperlocal (exact postcodes)
✅ Often emergency jobs (£25 fees)
✅ Less competition (not everyone scrapes this)

Cons:
⚠️ Need multiple accounts (one per area)
⚠️ More anti-bot protection

Implementation:
- Create accounts for 10-15 London neighborhoods
- Scrape "Recommendations" section
- Search keywords: "plumber", "leaking", "boiler", "emergency"
```

#### 2. **Checkatrade "Get a Quote"** 🔨 ⭐⭐⭐⭐⭐
```
URL: checkatrade.com/trades/find-a-plumber
Why: People actively looking for plumbers
Volume: 30-50 leads/day
Quality: EXCELLENT (pre-qualified, ready to buy)

How it works:
- Customers post job requests
- You can see them in search results
- Or partner with Checkatrade (affiliate)

Option A (Scraping):
- Scrape public job listings
- High quality but legal grey area

Option B (Partnership):
- Become Checkatrade affiliate
- They send you leads (100% legal)
- You pay per lead received
- Then charge plumber when accepted

Recommended: Start with Option B (legal, high quality)
```

#### 3. **MyBuilder** 🏗️ ⭐⭐⭐⭐
```
URL: mybuilder.com/find-a-plumber
Why: Dedicated trades platform
Volume: 25-40 leads/day
Quality: HIGH (serious customers)

Similar to Checkatrade:
- Option A: Scrape (grey area)
- Option B: Become affiliate (legal)

Recommended: Affiliate partnership
```

#### 4. **Local Facebook Groups** 📱 ⭐⭐⭐⭐
```
Target groups in each area:
- "Wimbledon Community"
- "Clapham Residents"
- "Hackney Neighbours"
- etc. (100+ groups)

Volume: 50-100 posts/week total
Quality: HIGH (local communities)

How to scrape:
- Join 20-30 local groups
- Monitor posts with keywords
- Extract contact details from posts

Pros:
✅ Very high quality (community recommendations)
✅ Often urgent needs
✅ Less competitive

Cons:
⚠️ Must join groups manually
⚠️ Some groups are private
```

#### 5. **Reddit r/LondonSocialClub, r/AskUK** 💬 ⭐⭐⭐
```
Subreddits to monitor:
- r/london
- r/AskUK  
- r/HomeImprovement
- r/DIYUK
- Local area subreddits

Volume: 5-10 posts/week
Quality: MEDIUM-HIGH

Search for:
- "need a plumber london"
- "emergency plumber"
- "plumber recommendation"

Setup:
- Use Reddit API (free, legal)
- Monitor keywords in real-time
- Extract from posts/comments
```

---

### MEDIUM PRIORITY (Add Month 2):

#### 6. **Bark.com Reverse Engineer** ⭐⭐⭐⭐
```
URL: bark.com
Why: Massive lead platform
Volume: 100+ leads/day
Quality: HIGH

How it works:
- Customers post jobs on Bark
- Bark shows jobs to tradespeople
- You could scrape the job board

Legal: Grey area
Alternative: Just use Bark as customer (pay per lead)
```

#### 7. **Google Local Services Ads** ⭐⭐⭐
```
Type: Google's trade platform
Why: High intent customers

Access: 
- Monitor "Plumber near me" searches
- Scrape business review requests
- Track Local Service ad responses
```

#### 8. **Trustpilot / Reviews.co.uk** ⭐⭐⭐
```
Why: Find unhappy customers

Search for:
- 1-2 star reviews of plumbers
- "never showed up"
- "still waiting"

Contact them: "Need a reliable plumber?"
```

#### 9. **Freecycle / Freegle** ⭐⭐
```
URL: freecycle.org
Why: Free community groups
Volume: Low (5-10/week)
Quality: MEDIUM

People post: "Wanted: Plumber recommendation"
```

#### 10. **Mumsnet Local** 👶 ⭐⭐⭐
```
URL: mumsnet.com/Talk/local
Why: Active parent community
Volume: 10-20/week
Quality: HIGH (family homes, willing to pay)

Search: "plumber recommendation" in local sections
```

---

### LOW PRIORITY (Consider Later):

#### 11. **Rightmove / Zoopla Forums** ⭐⭐
```
Why: New homeowners need work
Volume: Low
Quality: Medium
```

#### 12. **LinkedIn Local Groups** ⭐⭐
```
Why: Professional homeowners
Volume: Very low
Quality: High (willing to pay more)
```

#### 13. **Twitter/X Search** ⭐⭐
```
Search: "need plumber london" OR "emergency plumber"
Volume: 5-10/day
Quality: LOW-MEDIUM
```

---

## 📋 PHASE 1 IMPLEMENTATION PLAN

### Week 1: High Priority Sources

**Add to Job Ad Scraper:**

```python
# Priority order:

1. Nextdoor ⭐⭐⭐⭐⭐
   - ROI: Very high
   - Difficulty: Medium
   - Expected: +30 leads/day
   - Legal: Grey area

2. Facebook Groups ⭐⭐⭐⭐
   - ROI: High  
   - Difficulty: Easy
   - Expected: +20 leads/day
   - Legal: Grey area

3. Reddit ⭐⭐⭐
   - ROI: Medium
   - Difficulty: Easy
   - Expected: +5 leads/day
   - Legal: 100% legal (API)

4. Checkatrade (Partnership) ⭐⭐⭐⭐⭐
   - ROI: Very high
   - Difficulty: Easy (just sign up)
   - Expected: +40 leads/day
   - Legal: 100% legal

5. MyBuilder (Partnership) ⭐⭐⭐⭐
   - ROI: High
   - Difficulty: Easy
   - Expected: +30 leads/day
   - Legal: 100% legal
```

---

## 🎯 RECOMMENDED PHASE 1 STACK

### Option A: Scraping Focus (Higher Volume, Legal Risk)

**Job Ad Sources:**
1. ✅ Gumtree (current)
2. ✅ Facebook Marketplace (current)
3. 🆕 Nextdoor
4. 🆕 Facebook Groups (20-30 local groups)
5. 🆕 Reddit (API)

**Expected Results:**
- Volume: 150-200 leads/day
- Match rate: 30-40%
- Matched: 50-70 jobs/day
- Revenue: £900-1,260/day (£27k-£38k/month)
- Legal risk: Medium

---

### Option B: Partnership Focus (Lower Volume, Zero Legal Risk)

**Job Ad Sources:**
1. 🆕 Checkatrade (affiliate)
2. 🆕 MyBuilder (affiliate)
3. 🆕 Bark (pay-per-lead)
4. ✅ Customer Portal (your website)
5. 🆕 Reddit (API - free, legal)

**Expected Results:**
- Volume: 80-120 leads/day
- Match rate: 60% (higher quality)
- Matched: 50-70 jobs/day
- Revenue: £900-1,260/day (£27k-£38k/month)
- Legal risk: ZERO

---

### Option C: HYBRID (Best of Both) ⭐ RECOMMENDED

**Mix legal and scraping:**

**100% Legal Sources (70% of volume):**
1. Checkatrade affiliate
2. MyBuilder affiliate
3. Customer Portal
4. Reddit API

**Grey Area Sources (30% of volume):**
1. Gumtree scraping
2. Facebook Marketplace scraping
3. Nextdoor scraping

**Expected Results:**
- Volume: 180-250 leads/day
- Match rate: 45-50%
- Matched: 80-125 jobs/day
- Revenue: £1,440-2,250/day (£43k-£68k/month)
- Legal risk: LOW (most volume is legal)

---

## 🗺️ GEOGRAPHIC EXPANSION - Home Counties

### Phase 1 Focus Areas:

**Immediate (Month 1-2):**
```
✅ Central London (all postcodes)
✅ South West London (SW postcodes) - High density
✅ South East London (SE postcodes) - High density
✅ North London (N postcodes)
```

**Phase 2 (Month 3-4):**
```
🆕 Surrey (Guildford, Woking, Epsom)
   - Affluent area, higher job values
   - GU, KT postcodes
   
🆕 Kent (Bromley, Dartford, Sevenoaks)
   - Good density, London commuter belt
   - BR, DA, TN postcodes
```

**Phase 3 (Month 5-6):**
```
🆕 Essex (Chelmsford, Brentwood, Romford)
🆕 Hertfordshire (St Albans, Watford, Stevenage)
🆕 Berkshire (Reading, Slough, Windsor)
```

---

## 💰 EXPECTED VOLUME BY SOURCE

### Current Setup:
```
Source                Volume/Day    Match Rate    Matched/Day    Revenue/Day
─────────────────────────────────────────────────────────────────────────
Gumtree              60            30%           18             £270
Facebook             40            35%           14             £210
─────────────────────────────────────────────────────────────────────────
TOTAL                100           32%           32             £480/day
```

### Phase 1 Expansion (Recommended Hybrid):
```
Source                Volume/Day    Match Rate    Matched/Day    Revenue/Day
─────────────────────────────────────────────────────────────────────────
Gumtree              60            30%           18             £270
Facebook Market      40            35%           14             £210
Nextdoor             30            50%           15             £300
Facebook Groups      20            45%           9              £180
Checkatrade          40            70%           28             £560
MyBuilder            30            65%           20             £400
Reddit               5             40%           2              £40
Customer Portal      25            60%           15             £300
─────────────────────────────────────────────────────────────────────────
TOTAL                250           48%           121            £2,260/day
                                                                £68k/month
```

---

## 🚀 IMPLEMENTATION PRIORITY

### Immediate (This Week):

1. **Enable Reddit scraping** (easiest, 100% legal)
   - Use PRAW library
   - Monitor 5-10 subreddits
   - Expected: +5 leads/day

2. **Sign up as Checkatrade affiliate** (legal, high ROI)
   - Apply online
   - Get API access
   - Expected: +40 leads/day

3. **Launch customer portal** (already built, zero cost)
   - Upload website
   - SEO optimize
   - Expected: +5-10 leads/day initially

### Week 2:

4. **Add Nextdoor scraper**
   - Create 10 neighborhood accounts
   - Automated monitoring
   - Expected: +30 leads/day

5. **Join Facebook Groups**
   - Join 20 local groups
   - Monitor posts
   - Expected: +20 leads/day

### Month 2:

6. **MyBuilder partnership**
7. **Expand to Surrey/Kent**

---

## ✅ FINAL RECOMMENDATION

**Phase 1 Source Mix:**

**Priority 1 (Do Now):**
- ✅ Gumtree (keep current)
- ✅ Facebook Marketplace (keep current)
- 🆕 Reddit (add - easy, legal, free)
- 🆕 Checkatrade (add - legal, high quality)
- 🆕 Customer Portal (add - already built)

**Priority 2 (Add Week 2):**
- 🆕 Nextdoor (high quality, worth the setup effort)
- 🆕 Facebook Groups (good volume, manual setup)

**Priority 3 (Add Month 2):**
- 🆕 MyBuilder (legal partnership)
- Expand to Surrey/Kent postcodes

This gives you a **balanced mix** of:
- Legal sources (60% of volume)
- High-quality leads (50% match rate)
- Diversified risk
- Scalable revenue (£50k+/month potential)

---

## 📂 Files to Update

**To add new sources:**

1. Edit `ad_scraper.py`:
   - Add `scrape_nextdoor()` function
   - Add `scrape_reddit()` function
   - Add `scrape_facebook_groups()` function

2. Edit `plumber_scraper.py`:
   - Already has all main sources ✅

3. Add new file `partnership_leads.py`:
   - Handle Checkatrade API
   - Handle MyBuilder API
   - Unified interface

All feed into the **same automation** - no extra work for you!
