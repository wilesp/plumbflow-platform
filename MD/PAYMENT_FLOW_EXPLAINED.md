# 💳 PAYMENT FLOW - COMPLETE EXPLANATION

## 🎯 BUSINESS MODEL SUMMARY

**PlumberFlow Revenue Model:**
- Customers post jobs: **FREE** ✅
- Plumbers register: **FREE** ✅
- **We charge plumbers for LEADS, not jobs**
- Revenue: £15-25 per accepted lead

---

## 📊 COMPLETE PAYMENT FLOW

### **STEP 1: Customer Posts Job (FREE)**

```
Customer → PlumberFlow Website → Posts Job
↓
NO PAYMENT REQUIRED
↓
Job saved to database
```

**What happens:**
- Customer fills form (name, phone, postcode, job description)
- Job saved in `jobs` table with status: `pending`
- Customer pays NOTHING
- We find plumbers to match

---

### **STEP 2: We Match Plumber**

```
Our Matching Engine finds best plumber
↓
SMS sent to plumber with job details:
"New lead: Kitchen tap repair, SW19
Customer: Sarah M.
Fee: £18 | Est. job value: £180
Accept? Yes/No"
```

**Job details shown to plumber:**
- Job type & description
- Customer location (postcode)
- **Lead fee: £15-25** ← What we charge
- Estimated job value: £150-300 ← What customer will pay THEM

---

### **STEP 3: Plumber Accepts Lead**

```
Plumber clicks "Accept" in their dashboard
↓
💳 STRIPE CHARGES PLUMBER £18 (lead fee)
↓
Plumber's card is charged immediately
↓
We get £18 revenue
↓
Customer gets plumber's contact details
```

**This is when WE get paid:**
- ✅ Plumber accepts lead
- ✅ Stripe charges their card automatically
- ✅ £18 goes to our Stripe account
- ✅ Customer is notified plumber is coming

---

### **STEP 4: Plumber Does The Job**

```
Plumber arrives at customer's house
↓
Fixes the tap (or whatever the job is)
↓
Plumber invoices customer directly: £180
↓
💷 CUSTOMER PAYS PLUMBER £180 (cash, bank transfer, card - THEIR CHOICE)
```

**Important:**
- Customer pays plumber DIRECTLY
- We do NOT process this payment
- We do NOT take a cut of the £180
- Plumber keeps full £180

**Plumber's calculation:**
- Paid us: £18 (lead fee)
- Customer paid them: £180 (job fee)
- **Plumber's profit: £162**

---

## 💳 STRIPE INTEGRATION - TECHNICAL

### **When Plumber Registers:**

**1. Create Stripe Customer**
```python
import stripe

# When plumber completes registration
stripe.api_key = STRIPE_SECRET_KEY

customer = stripe.Customer.create(
    email=plumber.email,
    name=plumber.business_name,
    description=f"Plumber: {plumber.business_name}",
    metadata={
        'plumber_id': plumber.id,
        'phone': plumber.phone,
        'postcode': plumber.postcode
    }
)

# Save Stripe customer ID to database
plumber.stripe_customer_id = customer.id
db.save(plumber)
```

**2. Collect Payment Method**

Option A: **During registration (recommended):**
```python
# Add payment method form to registration
setup_intent = stripe.SetupIntent.create(
    customer=customer.id,
    payment_method_types=['card']
)

# Return setup_intent.client_secret to frontend
# Frontend uses Stripe.js to collect card details
```

Option B: **When they accept first lead:**
```python
# Redirect to payment method page when they click Accept
# Collect card details
# Then process lead acceptance
```

**Recommendation: Option A** - Get payment method during registration so leads can be accepted instantly.

---

### **When Plumber Accepts Lead:**

**Charge them immediately:**

```python
def plumber_accepts_lead(job_id, plumber_id):
    """
    Process lead acceptance and charge plumber
    """
    
    # Get job and plumber
    job = db.get_job(job_id)
    plumber = db.get_plumber(plumber_id)
    
    # Calculate lead fee based on job urgency/type
    lead_fee = calculate_lead_fee(job)
    # Example: Emergency = £25, Standard = £15, Same-day = £20
    
    # Charge plumber via Stripe
    try:
        charge = stripe.PaymentIntent.create(
            amount=lead_fee * 100,  # Stripe uses pence, so £18 = 1800
            currency='gbp',
            customer=plumber.stripe_customer_id,
            payment_method=plumber.stripe_payment_method_id,
            off_session=True,  # Charge without customer present
            confirm=True,
            description=f"Lead fee: {job.title} - {job.postcode}",
            metadata={
                'job_id': job.id,
                'plumber_id': plumber.id,
                'lead_fee': lead_fee,
                'job_type': job.job_type
            }
        )
        
        # Success! Save transaction
        transaction = {
            'plumber_id': plumber.id,
            'job_id': job.id,
            'amount': lead_fee,
            'stripe_payment_intent_id': charge.id,
            'status': 'completed',
            'created_at': datetime.now()
        }
        db.save_transaction(transaction)
        
        # Assign job to plumber
        assignment = {
            'job_id': job.id,
            'plumber_id': plumber.id,
            'lead_fee': lead_fee,
            'status': 'accepted',
            'accepted_at': datetime.now()
        }
        db.save_job_assignment(assignment)
        
        # Update job status
        job.status = 'matched'
        job.matched_at = datetime.now()
        db.save_job(job)
        
        # Notify customer
        send_sms(
            job.customer_phone,
            f"Great news! {plumber.business_name} has accepted your job. They'll be in touch shortly. Ph: {plumber.phone}"
        )
        
        # Notify plumber
        send_sms(
            plumber.phone,
            f"Lead accepted! Customer: {job.customer_name}, Ph: {job.customer_phone}. Address details sent via email."
        )
        
        return {'success': True, 'charge_id': charge.id}
        
    except stripe.error.CardError as e:
        # Card was declined
        return {'success': False, 'error': 'Card declined'}
        
    except stripe.error.StripeError as e:
        # Other Stripe error
        return {'success': False, 'error': 'Payment failed'}
```

---

## 💰 PRICING LOGIC

### **Lead Fee Calculator:**

```python
def calculate_lead_fee(job):
    """
    Calculate lead fee based on job characteristics
    """
    
    base_fee = 15  # £15 base
    
    # Urgency multiplier
    urgency_fees = {
        'emergency': 25,    # £25 for emergency (within 2 hours)
        'today': 20,        # £20 for same-day
        'this_week': 15,    # £15 standard
        'flexible': 12      # £12 for flexible timing
    }
    
    fee = urgency_fees.get(job.urgency, 15)
    
    # Job complexity
    if job.job_type in ['boiler_repair', 'bathroom_fitting', 'kitchen_fitting']:
        fee += 5  # High-value jobs = higher lead fee
    
    # Location (Central London = premium)
    if is_central_london(job.postcode):
        fee += 3
    
    # Cap at £25
    return min(fee, 25)
```

---

## 🔄 COMPLETE WORKFLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                    CUSTOMER JOURNEY (FREE)                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    Customer posts job
                              ↓
                    Job saved to database
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    OUR MATCHING ENGINE                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    Find best plumber (location, skills, rating)
                              ↓
                    Send SMS to plumber with job details + fee
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    PLUMBER ACCEPTS LEAD                      │
│                   💳 STRIPE CHARGES £18                      │
│                   ✅ WE GET PAID £18                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    Customer notified: "Plumber on the way!"
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    PLUMBER DOES THE JOB                      │
│                    Invoices customer £180                    │
│              💷 CUSTOMER PAYS PLUMBER DIRECTLY               │
│                    (We don't touch this)                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    Job complete
                              ↓
                    Plumber's net profit: £180 - £18 = £162
                    Our revenue: £18
```

---

## ❓ FREQUENTLY ASKED QUESTIONS

### **Q: Why don't we take a cut of the job payment?**
**A:** Simpler! Plumber pays fixed lead fee upfront. They quote customer whatever they want. Less accounting, cleaner business model.

### **Q: What if plumber accepts lead but doesn't do the job?**
**A:** They still paid the lead fee. We track this - too many no-shows = ban from platform.

### **Q: What if customer doesn't like the price plumber quotes?**
**A:** Not our problem. Plumber still paid lead fee. Customer can decline and post again.

### **Q: What if plumber's card declines when they accept?**
**A:** Lead acceptance fails. Job goes to next plumber in queue. First plumber gets email: "Update your payment method."

### **Q: How do we handle refunds?**
**A:** Rarely. Only if our fault (e.g., bad customer contact details). Handled via Stripe dashboard or API.

---

## 🚀 IMPLEMENTATION CHECKLIST

### **Phase 1: Stripe Setup**
- [ ] Create Stripe account
- [ ] Get API keys (test + live)
- [ ] Add Stripe SDK to requirements.txt
- [ ] Configure webhook endpoint

### **Phase 2: Registration**
- [ ] Add Stripe.js to plumber-register.html
- [ ] Collect payment method during signup
- [ ] Save stripe_customer_id to database
- [ ] Test card entry and validation

### **Phase 3: Lead Acceptance**
- [ ] Add "Accept Lead" button to dashboard
- [ ] Implement charge_plumber_lead_fee() function
- [ ] Save transactions to database
- [ ] Send confirmation notifications

### **Phase 4: Testing**
- [ ] Test with Stripe test cards
- [ ] Verify charges appear in Stripe dashboard
- [ ] Test declined cards
- [ ] Test full customer→plumber flow

### **Phase 5: Go Live**
- [ ] Switch to live API keys
- [ ] Enable webhook verification
- [ ] Monitor first real transactions
- [ ] Set up daily revenue reports

---

## 💡 KEY TAKEAWAYS

1. **Customer posts job** = FREE
2. **Plumber registers** = FREE (but must add payment method)
3. **Plumber accepts lead** = **WE CHARGE £15-25** via Stripe
4. **Customer pays plumber** = Direct payment (we don't touch it)
5. **Our revenue** = Lead fees only

**Simple. Clean. Profitable.** ✅
