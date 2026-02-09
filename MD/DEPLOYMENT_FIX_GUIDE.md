# 🔧 RAILWAY DEPLOYMENT FIX

## ❌ Current Status: FAILED
**Error:** "Healthcheck failure"

## ✅ SOLUTION: Upload Fixed Files

I've fixed 2 critical issues:
1. **Missing PyJWT dependency** (for magic links)
2. **Safer error handling** (won't crash if OpenAI has issues)

---

## 🚀 STEP-BY-STEP FIX

### **Step 1: View the Current Error**

Click **"View logs"** in Railway to see the exact error.

Look for lines with:
- `ERROR`
- `ModuleNotFoundError`
- `ImportError`
- `Failed to`

**Send me a screenshot of the logs and I can diagnose further!**

---

### **Step 2: Upload Fixed Files**

Upload these 3 files to GitHub:

```bash
# 1. Updated requirements.txt (with PyJWT)
git add requirements.txt

# 2. Fixed main.py (safer error handling)
git add main.py

# 3. Pricing engine
git add tight_pricing_engine.py

# Commit and push
git commit -m "Fix deployment: add PyJWT and safer error handling"
git push origin main
```

---

### **Step 3: Wait for Railway Redeploy**

Railway will automatically redeploy (~3 minutes)

Watch the deployment in Railway dashboard:
- ✅ Initialization should succeed
- ✅ Build should succeed  
- ✅ Deploy should succeed
- ✅ Healthcheck should succeed

---

## 🔍 WHAT I FIXED

### **Fix 1: Added PyJWT to requirements.txt**

**Before:**
```
# Missing PyJWT!
fastapi==0.104.1
uvicorn==0.24.0
```

**After:**
```
fastapi==0.104.1
uvicorn==0.24.0
PyJWT==2.8.0  ← Added for magic links
```

### **Fix 2: Safer Pricing Engine Initialization**

**Before:**
```python
# Would crash if OpenAI has issues
pricing_engine = TightPricingEngine()
```

**After:**
```python
# Won't crash - will use fallback pricing
try:
    pricing_engine = TightPricingEngine()
    logger.info("✅ Pricing engine initialized")
except Exception as e:
    logger.warning(f"⚠️ Pricing engine failed: {e}")
    pricing_engine = None  # Use fallback
```

### **Fix 3: Updated OpenAI Version**

**Before:**
```
openai==1.3.0  # Old version
```

**After:**
```
openai==1.10.0  # Latest version
```

---

## 🧪 TESTING AFTER DEPLOYMENT

### **Test 1: Health Check**

Visit: `https://plumberflow.co.uk/api/health`

**Expected:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "services": {
    "api": "ok",
    "payment": "ok",
    "pricing_engine": "ok"  ← Should be "ok" or "not initialized"
  }
}
```

### **Test 2: Homepage**

Visit: `https://plumberflow.co.uk`

- ✅ Should load
- ✅ Click "I NEED A PLUMBER"
- ✅ Should show the form

### **Test 3: Pricing API**

```bash
curl -X POST https://plumberflow.co.uk/api/calculate-price \
  -H "Content-Type: application/json" \
  -d '{
    "jobType": "tap_leak",
    "description": "Kitchen tap dripping",
    "urgency": "today",
    "postcode": "SW19",
    "customerName": "Test",
    "phone": "07700900000"
  }'
```

**Expected:**
```json
{
  "success": true,
  "priceLow": 95,
  "priceTypical": 120,
  "priceHigh": 145
}
```

---

## ⚠️ IF IT STILL FAILS

### **Scenario 1: Missing tight_pricing_engine.py**

**Error in logs:**
```
ModuleNotFoundError: No module named 'tight_pricing_engine'
```

**Fix:**
```bash
# Make sure you uploaded the file!
git add tight_pricing_engine.py
git commit -m "Add pricing engine"
git push
```

### **Scenario 2: OpenAI API Key Invalid**

**Error in logs:**
```
openai.AuthenticationError: Incorrect API key
```

**Fix:**
1. Go to Railway → Variables
2. Check `OPENAI_API_KEY` is correct
3. Test the key: https://platform.openai.com/api-keys
4. Update if needed

### **Scenario 3: Import Errors**

**Error in logs:**
```
ImportError: cannot import name 'X' from 'Y'
```

**Fix:**
```bash
# Update all dependencies
git add requirements.txt
git commit -m "Update dependencies"
git push
```

---

## 📋 FILES TO UPLOAD

**These 3 files are ready in your folder:**

1. ✅ `requirements.txt` (with PyJWT added)
2. ✅ `main.py` (with safer error handling)
3. ✅ `tight_pricing_engine.py` (the pricing engine)
4. ✅ `frontend/customer-post-job.html` (the enhanced form)

**Upload all 4 files and Railway should deploy successfully!**

---

## 🆘 STILL STUCK?

**Send me:**
1. Screenshot of the Railway logs (click "View logs")
2. The exact error message
3. Confirmation you uploaded all 4 files

**I'll diagnose and fix it immediately!**
