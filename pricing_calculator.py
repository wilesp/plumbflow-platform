"""
AUTOMATED PRICING CALCULATOR
Calculates job prices based on job type, plumber rates, and location
"""

import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class JobAnalysis:
    """AI analysis of job from scraped ad"""
    job_type: str
    urgency: str  # emergency, today, this_week, flexible
    complexity: str  # easy, medium, hard
    estimated_hours: float
    estimated_parts_cost: float
    confidence: float
    keywords: list
    
@dataclass
class PlumberProfile:
    """Plumber's rates and info"""
    id: int
    name: str
    base_postcode: str
    hourly_rate: float
    emergency_rate: float
    minimum_callout: float
    travel_rate: float
    gas_safe_certified: bool
    specialties: list

@dataclass
class PricingCard:
    """Template pricing for job type"""
    job_type: str
    base_time_hours: float
    complexity_multipliers: dict
    parts_cost_range: tuple
    skill_level: str
    gas_safe_required: bool
    urgency_multiplier: float


class PricingCalculator:
    """
    Main pricing engine that calculates:
    - Customer total price
    - Plumber earnings
    - Platform finder's fee
    """
    
    # Constants
    DEFAULT_MARGIN_PERCENTAGE = 0.12  # 12% contingency buffer
    FUEL_COST_PER_KM = 0.45  # £0.45 per km
    
    def __init__(self):
        self.pricing_cards = self._load_pricing_cards()
    
    def _load_pricing_cards(self) -> Dict[str, PricingCard]:
        """Load pricing templates for all job types"""
        return {
            'leaking_tap': PricingCard(
                job_type='leaking_tap',
                base_time_hours=0.5,
                complexity_multipliers={'easy': 1.0, 'medium': 1.3, 'hard': 1.8},
                parts_cost_range=(5, 15),
                skill_level='basic',
                gas_safe_required=False,
                urgency_multiplier=1.0
            ),
            'toilet_flush': PricingCard(
                job_type='toilet_flush',
                base_time_hours=0.75,
                complexity_multipliers={'easy': 1.0, 'medium': 1.4, 'hard': 2.0},
                parts_cost_range=(15, 35),
                skill_level='basic',
                gas_safe_required=False,
                urgency_multiplier=1.0
            ),
            'unblock_sink': PricingCard(
                job_type='unblock_sink',
                base_time_hours=0.75,
                complexity_multipliers={'easy': 1.0, 'medium': 1.5, 'hard': 2.5},
                parts_cost_range=(10, 40),
                skill_level='basic',
                gas_safe_required=False,
                urgency_multiplier=1.2
            ),
            'replace_tap': PricingCard(
                job_type='replace_tap',
                base_time_hours=1.0,
                complexity_multipliers={'easy': 1.0, 'medium': 1.4, 'hard': 2.0},
                parts_cost_range=(30, 80),
                skill_level='basic',
                gas_safe_required=False,
                urgency_multiplier=1.0
            ),
            'burst_pipe': PricingCard(
                job_type='burst_pipe',
                base_time_hours=1.5,
                complexity_multipliers={'easy': 1.0, 'medium': 1.6, 'hard': 2.5},
                parts_cost_range=(20, 60),
                skill_level='medium',
                gas_safe_required=False,
                urgency_multiplier=1.8  # Usually emergency
            ),
            'toilet_replacement': PricingCard(
                job_type='toilet_replacement',
                base_time_hours=2.0,
                complexity_multipliers={'easy': 1.0, 'medium': 1.5, 'hard': 2.2},
                parts_cost_range=(100, 250),
                skill_level='medium',
                gas_safe_required=False,
                urgency_multiplier=1.0
            ),
            'radiator_replacement': PricingCard(
                job_type='radiator_replacement',
                base_time_hours=2.5,
                complexity_multipliers={'easy': 1.0, 'medium': 1.4, 'hard': 2.0},
                parts_cost_range=(80, 180),
                skill_level='medium',
                gas_safe_required=False,
                urgency_multiplier=1.0
            ),
            'boiler_repair': PricingCard(
                job_type='boiler_repair',
                base_time_hours=2.5,
                complexity_multipliers={'easy': 1.0, 'medium': 1.6, 'hard': 2.5},
                parts_cost_range=(50, 300),
                skill_level='advanced',
                gas_safe_required=True,
                urgency_multiplier=1.5
            ),
            'shower_installation': PricingCard(
                job_type='shower_installation',
                base_time_hours=5.0,
                complexity_multipliers={'easy': 1.0, 'medium': 1.8, 'hard': 3.0},
                parts_cost_range=(400, 1200),
                skill_level='advanced',
                gas_safe_required=False,
                urgency_multiplier=1.0
            ),
        }
    
    def calculate_finder_fee(self, subtotal: float) -> float:
        """
        Dynamic finder's fee based on job size
        
        Under £75: £10
        £75-150: £15
        £150-300: £25 (sweet spot)
        Over £300: 10% capped at £50
        """
        if subtotal < 75:
            return 10.00
        elif subtotal < 150:
            return 15.00
        elif subtotal < 300:
            return 25.00
        else:
            return min(subtotal * 0.10, 50.00)
    
    def get_effective_hourly_rate(
        self, 
        plumber: PlumberProfile, 
        urgency: str,
        job_type: str,
        is_evening: bool = False,
        is_weekend: bool = False
    ) -> float:
        """Calculate effective hourly rate with all multipliers"""
        
        # Start with base rate
        if urgency == 'emergency':
            rate = plumber.emergency_rate
        else:
            rate = plumber.hourly_rate
        
        # Urgency boost for non-emergency urgent jobs
        if urgency == 'today' and rate == plumber.hourly_rate:
            rate *= 1.2  # 20% boost for same-day
        
        # Time of day premiums
        if is_evening or is_weekend:
            rate *= 1.25
        
        # Specialty premium
        if job_type in plumber.specialties:
            rate += 10.00
        
        return round(rate, 2)
    
    def calculate_travel_cost(
        self,
        plumber_postcode: str,
        job_postcode: str,
        plumber_hourly_rate: float,
        distance_km: Optional[float] = None,
        travel_time_mins: Optional[int] = None
    ) -> Dict:
        """
        Calculate travel time and cost
        
        If distance/time not provided, estimates based on postcode proximity
        In production, this would call Google Maps API
        """
        
        if distance_km is None or travel_time_mins is None:
            # Estimate based on postcode (simplified)
            # In real system, use Google Maps Distance Matrix API
            distance_km, travel_time_mins = self._estimate_distance(
                plumber_postcode, 
                job_postcode
            )
        
        # Calculate costs
        travel_time_hours = travel_time_mins / 60
        travel_time_cost = travel_time_hours * plumber_hourly_rate
        fuel_cost = distance_km * self.FUEL_COST_PER_KM
        
        # Round trip
        total_distance = distance_km * 2
        total_time = travel_time_hours * 2
        total_cost = (travel_time_cost + fuel_cost) * 2
        
        return {
            'distance_km': round(total_distance, 1),
            'time_hours': round(total_time, 2),
            'time_cost': round(travel_time_cost * 2, 2),
            'fuel_cost': round(fuel_cost * 2, 2),
            'total_cost': round(total_cost, 2)
        }
    
    def _estimate_distance(self, postcode1: str, postcode2: str) -> Tuple[float, int]:
        """
        Estimate distance between postcodes
        Simplified - in production use Google Maps API
        """
        # Extract postcode areas (SW18, SW19, etc.)
        area1 = postcode1[:4].upper()
        area2 = postcode2[:4].upper()
        
        # Very rough estimation
        if area1 == area2:
            return (2.0, 15)  # Same area: 2km, 15 mins
        elif area1[:3] == area2[:3]:
            return (5.0, 25)  # Adjacent areas: 5km, 25 mins
        else:
            return (10.0, 40)  # Different areas: 10km, 40 mins
    
    def calculate_job_price(
        self,
        job_analysis: JobAnalysis,
        plumber: PlumberProfile,
        job_postcode: str,
        distance_km: Optional[float] = None,
        travel_time_mins: Optional[int] = None
    ) -> Dict:
        """
        Main pricing calculation
        
        Returns complete pricing breakdown including:
        - Customer total
        - Plumber earnings
        - Platform fee
        """
        
        # Get pricing card for this job type
        pricing_card = self.pricing_cards.get(
            job_analysis.job_type,
            self._get_generic_pricing_card(job_analysis)
        )
        
        # Validate plumber can do this job
        if pricing_card.gas_safe_required and not plumber.gas_safe_certified:
            raise ValueError(f"Plumber must be Gas Safe certified for {job_analysis.job_type}")
        
        # 1. Calculate effective hourly rate
        now = datetime.now()
        is_evening = now.hour >= 18 or now.hour < 8
        is_weekend = now.weekday() >= 5
        
        hourly_rate = self.get_effective_hourly_rate(
            plumber,
            job_analysis.urgency,
            job_analysis.job_type,
            is_evening,
            is_weekend
        )
        
        # 2. Calculate job time with complexity multiplier
        complexity_multiplier = pricing_card.complexity_multipliers.get(
            job_analysis.complexity, 
            1.5
        )
        
        job_hours = pricing_card.base_time_hours * complexity_multiplier
        
        # Use AI estimate if available and different
        if job_analysis.estimated_hours:
            job_hours = max(job_hours, job_analysis.estimated_hours)
        
        # 3. Calculate labour cost
        labour_cost = job_hours * hourly_rate
        
        # Apply minimum callout
        if labour_cost < plumber.minimum_callout:
            labour_cost = plumber.minimum_callout
            job_hours = labour_cost / hourly_rate  # Recalc hours for display
        
        # 4. Calculate travel cost
        travel = self.calculate_travel_cost(
            plumber.base_postcode,
            job_postcode,
            hourly_rate,
            distance_km,
            travel_time_mins
        )
        
        # 5. Materials cost
        if job_analysis.estimated_parts_cost:
            materials_cost = job_analysis.estimated_parts_cost
        else:
            # Use midpoint of typical range
            min_parts, max_parts = pricing_card.parts_cost_range
            materials_cost = (min_parts + max_parts) / 2
        
        # 6. Calculate subtotal
        subtotal = labour_cost + travel['total_cost'] + materials_cost
        
        # 7. Add margin for complexity/contingency
        margin = subtotal * self.DEFAULT_MARGIN_PERCENTAGE
        
        # 8. Calculate finder's fee
        finder_fee = self.calculate_finder_fee(subtotal)
        
        # 9. Total customer price
        total_customer_price = subtotal + margin + finder_fee
        
        # 10. Plumber's take-home (everything except finder's fee)
        plumber_earnings = subtotal + margin
        
        # 11. Calculate price range (±15%)
        price_range_min = total_customer_price * 0.85
        price_range_max = total_customer_price * 1.15
        
        return {
            'breakdown': {
                'labour': {
                    'hours': round(job_hours, 2),
                    'rate_per_hour': round(hourly_rate, 2),
                    'cost': round(labour_cost, 2),
                    'minimum_callout_applied': labour_cost == plumber.minimum_callout
                },
                'travel': {
                    'distance_km': travel['distance_km'],
                    'time_hours': travel['time_hours'],
                    'time_cost': travel['time_cost'],
                    'fuel_cost': travel['fuel_cost'],
                    'total_cost': travel['total_cost']
                },
                'materials': {
                    'cost': round(materials_cost, 2),
                    'estimated': not bool(job_analysis.estimated_parts_cost)
                },
                'subtotal': round(subtotal, 2),
                'margin': round(margin, 2),
                'margin_percentage': self.DEFAULT_MARGIN_PERCENTAGE * 100,
                'finder_fee': round(finder_fee, 2)
            },
            'pricing': {
                'customer_pays': round(total_customer_price, 2),
                'plumber_earns': round(plumber_earnings, 2),
                'platform_fee': round(finder_fee, 2),
                'price_range_min': round(price_range_min, 2),
                'price_range_max': round(price_range_max, 2)
            },
            'metadata': {
                'job_type': job_analysis.job_type,
                'urgency': job_analysis.urgency,
                'complexity': job_analysis.complexity,
                'ai_confidence': job_analysis.confidence,
                'calculated_at': datetime.now().isoformat()
            }
        }
    
    def _get_generic_pricing_card(self, job_analysis: JobAnalysis) -> PricingCard:
        """Fallback pricing card for unknown job types"""
        return PricingCard(
            job_type='generic',
            base_time_hours=job_analysis.estimated_hours or 1.5,
            complexity_multipliers={'easy': 1.0, 'medium': 1.5, 'hard': 2.0},
            parts_cost_range=(20, 100),
            skill_level='medium',
            gas_safe_required=False,
            urgency_multiplier=1.0
        )
    
    def format_quote_for_customer(self, pricing: Dict) -> str:
        """Format pricing as customer-friendly message"""
        p = pricing['pricing']
        b = pricing['breakdown']
        
        return f"""
🔧 Job Quote Estimate

Estimated Cost: £{p['price_range_min']:.0f} - £{p['price_range_max']:.0f}
Typical Price: £{p['customer_pays']:.2f}

Breakdown:
• Labour: {b['labour']['hours']}hrs @ £{b['labour']['rate_per_hour']}/hr = £{b['labour']['cost']:.2f}
• Travel: {b['travel']['distance_km']}km = £{b['travel']['total_cost']:.2f}
• Materials: £{b['materials']['cost']:.2f}
• Service Fee: £{b['finder_fee']:.2f}

Total: £{p['customer_pays']:.2f}

Includes: 
✓ All labour and travel
✓ Materials and parts
✓ 12-month workmanship guarantee
✓ Fully insured plumber
        """.strip()
    
    def format_quote_for_plumber(self, pricing: Dict, job_title: str, postcode: str) -> str:
        """Format pricing as plumber notification"""
        p = pricing['pricing']
        b = pricing['breakdown']
        
        return f"""
🔔 New Lead Available

Job: {job_title}
Location: {postcode}

Your Earnings: £{p['plumber_earns']:.2f}
Work Time: ~{b['labour']['hours'] + b['travel']['time_hours']:.1f} hours
Travel: {b['travel']['distance_km']}km

Customer Pays: £{p['customer_pays']:.2f}
Lead Fee: £{b['finder_fee']:.2f}

Accept this lead?
        """.strip()


# ================================================================
# USAGE EXAMPLE
# ================================================================

if __name__ == "__main__":
    # Sample job from scraped ad
    job = JobAnalysis(
        job_type='leaking_tap',
        urgency='this_week',
        complexity='easy',
        estimated_hours=0.5,
        estimated_parts_cost=8.00,
        confidence=0.92,
        keywords=['tap', 'drip', 'leak']
    )
    
    # Sample plumber
    plumber = PlumberProfile(
        id=1,
        name='John Smith',
        base_postcode='SW18',
        hourly_rate=60.00,
        emergency_rate=90.00,
        minimum_callout=75.00,
        travel_rate=60.00,
        gas_safe_certified=True,
        specialties=['leaking_tap', 'boiler_repair']
    )
    
    # Calculate pricing
    calculator = PricingCalculator()
    pricing = calculator.calculate_job_price(
        job_analysis=job,
        plumber=plumber,
        job_postcode='SW19 2AB'
    )
    
    # Display results
    print("="*60)
    print("CUSTOMER QUOTE:")
    print("="*60)
    print(calculator.format_quote_for_customer(pricing))
    
    print("\n" + "="*60)
    print("PLUMBER NOTIFICATION:")
    print("="*60)
    print(calculator.format_quote_for_plumber(pricing, "Leaking kitchen tap", "SW19 2AB"))
    
    print("\n" + "="*60)
    print("DETAILED BREAKDOWN:")
    print("="*60)
    import json
    print(json.dumps(pricing, indent=2))
