"""
AI-Powered Tight Pricing Engine
Maximum range spread: 40% (e.g., £85-120, NOT £50-300)

Uses OpenAI GPT-4 + price validation rules to ensure realistic, tight estimates
"""

import openai
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

# UK Plumbing Industry Pricing Database (2025 rates)
PRICING_DATABASE = {
    'callout_fees': {
        'standard': {'min': 50, 'max': 70, 'typical': 60},
        'emergency': {'min': 70, 'max': 100, 'typical': 85},
        'london': {'min': 70, 'max': 90, 'typical': 80},
        'london_emergency': {'min': 90, 'max': 120, 'typical': 105}
    },
    'hourly_rates': {
        'standard': {'min': 40, 'max': 60, 'typical': 50},
        'london': {'min': 60, 'max': 80, 'typical': 70},
        'emergency': {'min': 60, 'max': 90, 'typical': 75}
    },
    'common_jobs': {
        'tap_washer_replace': {
            'time_hours': 0.5,
            'parts': {'min': 5, 'max': 15, 'typical': 10},
            'total': {'min': 75, 'max': 105, 'typical': 90}
        },
        'tap_full_replace': {
            'time_hours': 1.0,
            'parts': {'min': 30, 'max': 100, 'typical': 60},
            'total': {'min': 120, 'max': 180, 'typical': 150}
        },
        'toilet_cistern_repair': {
            'time_hours': 0.75,
            'parts': {'min': 20, 'max': 50, 'typical': 35},
            'total': {'min': 90, 'max': 135, 'typical': 110}
        },
        'blocked_sink_simple': {
            'time_hours': 0.5,
            'parts': {'min': 0, 'max': 20, 'typical': 5},
            'total': {'min': 70, 'max': 100, 'typical': 85}
        },
        'blocked_drain_rod': {
            'time_hours': 1.0,
            'parts': {'min': 0, 'max': 30, 'typical': 10},
            'total': {'min': 100, 'max': 150, 'typical': 120}
        },
        'radiator_bleed': {
            'time_hours': 0.5,
            'parts': {'min': 0, 'max': 10, 'typical': 0},
            'total': {'min': 70, 'max': 95, 'typical': 80}
        },
        'radiator_replace': {
            'time_hours': 2.0,
            'parts': {'min': 80, 'max': 200, 'typical': 120},
            'total': {'min': 200, 'max': 320, 'typical': 260}
        }
    }
}

class TightPricingEngine:
    """
    Generates tight, realistic price estimates with max 40% spread
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if self.api_key:
            openai.api_key = self.api_key
    
    def calculate_price(self, job_data: Dict) -> Dict:
        """
        Calculate tight price range for a plumbing job
        
        Returns:
            {
                'priceLow': int,
                'priceTypical': int,
                'priceHigh': int,
                'calloutFee': int,
                'laborHours': float,
                'laborCost': int,
                'partsCost': int,
                'confidence': str,  # 'high', 'medium', 'low'
                'reasoning': str,
                'complications': List[str],
                'range_spread_pct': float  # Should be ≤ 40%
            }
        """
        
        # Step 1: Get AI analysis
        ai_analysis = self._get_ai_analysis(job_data)
        
        # Step 2: Validate against database
        validated_pricing = self._validate_and_tighten(ai_analysis, job_data)
        
        # Step 3: Ensure tight range (max 40% spread)
        final_pricing = self._enforce_tight_range(validated_pricing)
        
        # Step 4: Add confidence score
        final_pricing['confidence'] = self._calculate_confidence(job_data, final_pricing)
        
        return final_pricing
    
    def _get_ai_analysis(self, job_data: Dict) -> Dict:
        """
        Use GPT-4 to analyze the job and suggest pricing
        """
        
        prompt = f"""You are a UK plumbing pricing expert with 20 years of experience.

Analyze this plumbing job and provide a TIGHT price estimate.

CRITICAL RULES:
1. Price range must be TIGHT - maximum 40% spread between low and high
2. Use 2025 UK market rates
3. Be realistic and specific
4. Consider all provided details

JOB DETAILS:
- Type: {job_data.get('jobType', 'Unknown')}
- Description: {job_data.get('description', 'Not provided')}
- Urgency: {job_data.get('urgency', 'standard')}
- Location: {job_data.get('postcode', 'Unknown')}
- Property Type: {job_data.get('propertyType', 'Unknown')}
- Property Age: {job_data.get('propertyAge', 'Unknown')}

CONDITIONAL DETAILS:
{self._format_conditional_details(job_data)}

RESPOND IN JSON FORMAT ONLY:
{{
    "job_classification": "exact type of job (e.g., 'tap washer replacement')",
    "complexity": 1-10,
    "estimated_time_hours": float,
    "callout_fee": int,
    "hourly_rate": int,
    "parts_cost_low": int,
    "parts_cost_typical": int,
    "parts_cost_high": int,
    "price_low": int,
    "price_typical": int,
    "price_high": int,
    "reasoning": "brief explanation of pricing",
    "complications": ["potential issue 1", "potential issue 2"],
    "confidence_factors": {{
        "detail_level": "high/medium/low",
        "photo_provided": true/false,
        "job_clarity": "high/medium/low"
    }}
}}

PRICING CONTEXT (UK 2025):
- Standard callout: £50-70
- Emergency callout: £70-100
- London callout: +£10-20
- Hourly rate: £40-60 (London: £60-80)
- Emergency premium: +50%

EXAMPLES OF TIGHT RANGES:
✓ GOOD: £85-120 (41% spread - acceptable)
✓ GOOD: £100-135 (35% spread)
✗ BAD: £50-300 (500% spread - too wide!)
✗ BAD: £80-200 (150% spread - too wide!)

Remember: Customer needs to know what to expect. Wide ranges are unhelpful!
"""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a UK plumbing pricing expert. Always respond with valid JSON only, no markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for consistent pricing
                max_tokens=800
            )
            
            # Extract JSON from response
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            analysis = json.loads(response_text)
            return analysis
            
        except Exception as e:
            print(f"AI pricing error: {e}")
            # Fallback to rule-based pricing
            return self._fallback_pricing(job_data)
    
    def _format_conditional_details(self, job_data: Dict) -> str:
        """Format conditional details for AI prompt"""
        details = []
        
        if 'tapLocation' in job_data:
            details.append(f"- Tap location: {job_data['tapLocation']}")
        if 'tapType' in job_data:
            details.append(f"- Tap type: {job_data['tapType']}")
        if 'leakType' in job_data:
            details.append(f"- Leak severity: {job_data['leakType']}")
        if 'tapAge' in job_data:
            details.append(f"- Tap age: {job_data['tapAge']}")
        if 'waterOff' in job_data:
            details.append(f"- Water supply status: {job_data['waterOff']}")
        if 'photo' in job_data and job_data['photo']:
            details.append(f"- Photo provided: YES (visual context available)")
        
        return '\n'.join(details) if details else "No additional details provided"
    
    def _validate_and_tighten(self, ai_analysis: Dict, job_data: Dict) -> Dict:
        """
        Validate AI pricing against database and tighten if needed
        """
        
        # Check if job matches a known pattern
        job_type = job_data.get('jobType', '')
        known_job = None
        
        for known_type, pricing in PRICING_DATABASE['common_jobs'].items():
            if known_type in job_type.lower() or job_type.lower() in known_type:
                known_job = pricing
                break
        
        if known_job:
            # Use database pricing as baseline, adjust with AI insights
            price_low = known_job['total']['min']
            price_typical = known_job['total']['typical']
            price_high = known_job['total']['max']
            
            # Adjust for urgency
            urgency = job_data.get('urgency', 'standard')
            if urgency == 'emergency':
                price_low = int(price_low * 1.4)
                price_typical = int(price_typical * 1.5)
                price_high = int(price_high * 1.6)
            elif urgency == 'today':
                price_low = int(price_low * 1.1)
                price_typical = int(price_typical * 1.15)
                price_high = int(price_high * 1.2)
            
            # Adjust for location (London)
            postcode = job_data.get('postcode', '').upper()
            london_postcodes = ['E', 'EC', 'N', 'NW', 'SE', 'SW', 'W', 'WC']
            if any(postcode.startswith(prefix) for prefix in london_postcodes):
                price_low = int(price_low * 1.15)
                price_typical = int(price_typical * 1.2)
                price_high = int(price_high * 1.25)
            
            return {
                'price_low': price_low,
                'price_typical': price_typical,
                'price_high': price_high,
                'callout_fee': self._get_callout_fee(job_data),
                'labor_hours': known_job['time_hours'],
                'labor_cost': int(known_job['time_hours'] * self._get_hourly_rate(job_data)),
                'parts_cost': known_job['parts']['typical'],
                'reasoning': f"Based on standard {known_job} rates, adjusted for {urgency} urgency",
                'complications': ai_analysis.get('complications', [])
            }
        else:
            # Use AI pricing but validate range
            return {
                'price_low': ai_analysis['price_low'],
                'price_typical': ai_analysis['price_typical'],
                'price_high': ai_analysis['price_high'],
                'callout_fee': ai_analysis['callout_fee'],
                'labor_hours': ai_analysis['estimated_time_hours'],
                'labor_cost': int(ai_analysis['estimated_time_hours'] * ai_analysis['hourly_rate']),
                'parts_cost': ai_analysis['parts_cost_typical'],
                'reasoning': ai_analysis['reasoning'],
                'complications': ai_analysis['complications']
            }
    
    def _enforce_tight_range(self, pricing: Dict) -> Dict:
        """
        Ensure price range is tight (max 40% spread)
        
        Formula: ((high - low) / typical) * 100 ≤ 40%
        """
        
        low = pricing['price_low']
        typical = pricing['price_typical']
        high = pricing['price_high']
        
        # Calculate current spread
        spread_pct = ((high - low) / typical) * 100
        
        if spread_pct > 40:
            # Range too wide - tighten around typical price
            # New range: typical ± 20%
            new_low = int(typical * 0.85)
            new_high = int(typical * 1.15)
            
            pricing['price_low'] = new_low
            pricing['price_high'] = new_high
            pricing['range_tightened'] = True
            pricing['original_spread'] = spread_pct
            pricing['new_spread'] = ((new_high - new_low) / typical) * 100
        else:
            pricing['range_tightened'] = False
            pricing['spread_pct'] = spread_pct
        
        return pricing
    
    def _calculate_confidence(self, job_data: Dict, pricing: Dict) -> str:
        """
        Calculate confidence level: high, medium, or low
        """
        
        confidence_score = 0
        
        # Factor 1: Detail level (0-3 points)
        if job_data.get('description') and len(job_data['description']) > 50:
            confidence_score += 2
        if len(job_data.get('description', '')) > 150:
            confidence_score += 1
        
        # Factor 2: Conditional details (0-2 points)
        conditional_fields = ['tapLocation', 'tapType', 'leakType', 'tapAge', 'waterOff']
        provided = sum(1 for field in conditional_fields if field in job_data)
        if provided >= 3:
            confidence_score += 2
        elif provided >= 1:
            confidence_score += 1
        
        # Factor 3: Photo (0-2 points)
        if job_data.get('photo'):
            confidence_score += 2
        
        # Factor 4: Known job pattern (0-2 points)
        job_type = job_data.get('jobType', '')
        for known_type in PRICING_DATABASE['common_jobs'].keys():
            if known_type in job_type.lower() or job_type.lower() in known_type:
                confidence_score += 2
                break
        
        # Factor 5: Tight range (0-1 point)
        if pricing.get('spread_pct', 100) <= 35:
            confidence_score += 1
        
        # Total possible: 10 points
        if confidence_score >= 8:
            return 'high'
        elif confidence_score >= 5:
            return 'medium'
        else:
            return 'low'
    
    def _get_callout_fee(self, job_data: Dict) -> int:
        """Get appropriate callout fee"""
        urgency = job_data.get('urgency', 'standard')
        postcode = job_data.get('postcode', '').upper()
        
        london_postcodes = ['E', 'EC', 'N', 'NW', 'SE', 'SW', 'W', 'WC']
        is_london = any(postcode.startswith(prefix) for prefix in london_postcodes)
        
        if urgency == 'emergency' and is_london:
            return PRICING_DATABASE['callout_fees']['london_emergency']['typical']
        elif urgency == 'emergency':
            return PRICING_DATABASE['callout_fees']['emergency']['typical']
        elif is_london:
            return PRICING_DATABASE['callout_fees']['london']['typical']
        else:
            return PRICING_DATABASE['callout_fees']['standard']['typical']
    
    def _get_hourly_rate(self, job_data: Dict) -> int:
        """Get appropriate hourly rate"""
        urgency = job_data.get('urgency', 'standard')
        postcode = job_data.get('postcode', '').upper()
        
        london_postcodes = ['E', 'EC', 'N', 'NW', 'SE', 'SW', 'W', 'WC']
        is_london = any(postcode.startswith(prefix) for prefix in london_postcodes)
        
        if urgency == 'emergency':
            return PRICING_DATABASE['hourly_rates']['emergency']['typical']
        elif is_london:
            return PRICING_DATABASE['hourly_rates']['london']['typical']
        else:
            return PRICING_DATABASE['hourly_rates']['standard']['typical']
    
    def _fallback_pricing(self, job_data: Dict) -> Dict:
        """
        Fallback pricing if AI fails
        Uses conservative estimates from database
        """
        
        callout = self._get_callout_fee(job_data)
        hourly = self._get_hourly_rate(job_data)
        
        # Conservative estimate: 1 hour + parts
        hours = 1.0
        parts = 30
        
        labor = int(hours * hourly)
        typical = callout + labor + parts
        
        # Tight range: ±15%
        low = int(typical * 0.85)
        high = int(typical * 1.15)
        
        return {
            'job_classification': 'general plumbing work',
            'complexity': 5,
            'estimated_time_hours': hours,
            'callout_fee': callout,
            'hourly_rate': hourly,
            'parts_cost_low': int(parts * 0.7),
            'parts_cost_typical': parts,
            'parts_cost_high': int(parts * 1.3),
            'price_low': low,
            'price_typical': typical,
            'price_high': high,
            'reasoning': 'Conservative estimate based on standard rates (AI unavailable)',
            'complications': [
                'Actual price depends on inspection',
                'May require additional parts',
                'Time may vary based on access'
            ],
            'confidence_factors': {
                'detail_level': 'low',
                'photo_provided': bool(job_data.get('photo')),
                'job_clarity': 'medium'
            }
        }


# Example usage and testing
if __name__ == "__main__":
    # Test the pricing engine
    
    engine = TightPricingEngine()
    
    # Test case 1: Detailed tap leak (should be HIGH confidence, TIGHT range)
    test_job_detailed = {
        'jobType': 'tap_leak',
        'description': 'Kitchen mixer tap dripping constantly. Started yesterday. Already turned off water under sink but still dripping from spout. Tap is about 8 years old.',
        'urgency': 'today',
        'postcode': 'SW19 2AB',
        'propertyType': 'terraced',
        'propertyAge': 'modern',
        'tapLocation': 'kitchen_sink',
        'tapType': 'mixer',
        'leakType': 'constant_stream',
        'tapAge': 'old',
        'waterOff': 'yes_off',
        'photo': True
    }
    
    print("TEST 1: Detailed tap leak (HIGH confidence expected)")
    print("=" * 60)
    pricing1 = engine.calculate_price(test_job_detailed)
    print(f"Price range: £{pricing1['price_low']} - £{pricing1['price_typical']} - £{pricing1['price_high']}")
    print(f"Range spread: {pricing1.get('spread_pct', 0):.1f}%")
    print(f"Confidence: {pricing1['confidence']}")
    print(f"Reasoning: {pricing1['reasoning']}")
    print()
    
    # Test case 2: Vague description (should be MEDIUM confidence, TIGHT but wider range)
    test_job_vague = {
        'jobType': 'tap_leak',
        'description': 'tap broken need fix',
        'urgency': 'flexible',
        'postcode': 'M1 1AA',
        'propertyType': 'flat',
        'propertyAge': 'dont_know'
    }
    
    print("TEST 2: Vague tap leak (MEDIUM confidence expected)")
    print("=" * 60)
    pricing2 = engine.calculate_price(test_job_vague)
    print(f"Price range: £{pricing2['price_low']} - £{pricing2['price_typical']} - £{pricing2['price_high']}")
    print(f"Range spread: {pricing2.get('spread_pct', 0):.1f}%")
    print(f"Confidence: {pricing2['confidence']}")
    print(f"Reasoning: {pricing2['reasoning']}")
    print()
    
    # Test case 3: Emergency burst pipe (should have tight range despite urgency)
    test_job_emergency = {
        'jobType': 'burst_pipe',
        'description': 'Pipe burst under kitchen sink. Water everywhere! Turned off mains.',
        'urgency': 'emergency',
        'postcode': 'E1 6AN',  # London
        'propertyType': 'flat',
        'propertyAge': 'very_old',
        'photo': True
    }
    
    print("TEST 3: Emergency burst pipe in London (tight range with premium)")
    print("=" * 60)
    pricing3 = engine.calculate_price(test_job_emergency)
    print(f"Price range: £{pricing3['price_low']} - £{pricing3['price_typical']} - £{pricing3['price_high']}")
    print(f"Range spread: {pricing3.get('spread_pct', 0):.1f}%")
    print(f"Confidence: {pricing3['confidence']}")
    print(f"Callout fee: £{pricing3['calloutFee']} (emergency + London)")
    print(f"Reasoning: {pricing3['reasoning']}")
