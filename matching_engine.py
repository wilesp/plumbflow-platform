"""
PLUMBER MATCHING ENGINE
Automatically matches scraped job ads to the best available plumbers
"""

import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

@dataclass
class Job:
    """Processed job from scraped ad"""
    id: int
    title: str
    description: str
    job_type: str
    postcode: str
    urgency: str  # emergency, today, this_week, flexible
    complexity: str  # easy, medium, hard
    estimated_value: float
    ai_confidence: float
    gas_safe_required: bool

@dataclass
class Plumber:
    """Plumber profile"""
    id: int
    name: str
    base_postcode: str
    hourly_rate: float
    status: str
    credit_balance: float
    gas_safe_certified: bool
    skills: List[str]
    service_postcodes: List[Dict]  # {prefix, priority, min_job_value}
    performance_metrics: Dict
    current_jobs_count: int
    available_today: bool

@dataclass
class Match:
    """Match between job and plumber"""
    job_id: int
    plumber_id: int
    match_score: float
    distance_km: float
    travel_time_mins: int
    ranking: int  # 1st choice, 2nd choice, etc.
    reasoning: Dict  # Why this score


class PlumberMatcher:
    """
    Main matching algorithm that ranks plumbers for each job
    
    Scoring weights:
    - Distance: 40%
    - Availability: 25%
    - Specialty: 20%
    - Performance: 10%
    - Rating: 5%
    """
    
    # Scoring weights
    WEIGHT_DISTANCE = 0.40
    WEIGHT_AVAILABILITY = 0.25
    WEIGHT_SPECIALTY = 0.20
    WEIGHT_PERFORMANCE = 0.10
    WEIGHT_RATING = 0.05
    
    def __init__(self):
        self.postcode_distances = self._load_postcode_distances()
    
    def _load_postcode_distances(self) -> Dict:
        """
        Load postcode distance matrix
        In production, use Google Maps Distance Matrix API
        This is a simplified version
        """
        # Simplified: Distance based on postcode area similarity
        return {}
    
    def calculate_distance(self, postcode1: str, postcode2: str) -> Tuple[float, int]:
        """
        Calculate distance and travel time between postcodes
        
        Returns: (distance_km, travel_time_minutes)
        
        In production: Use Google Maps Distance Matrix API
        """
        # Extract postcode areas
        area1 = postcode1[:4].strip().upper()
        area2 = postcode2[:4].strip().upper()
        
        # Simplified distance calculation
        if area1 == area2:
            return (2.0, 15)  # Same area
        elif area1[:3] == area2[:3]:
            return (5.0, 25)  # Adjacent areas
        elif area1[:2] == area2[:2]:
            return (8.0, 35)  # Same region
        else:
            return (15.0, 50)  # Different regions
    
    def score_distance(self, job: Job, plumber: Plumber) -> Tuple[float, Dict]:
        """
        Score based on geographic proximity
        
        Returns: (score 0-100, reasoning)
        """
        distance_km, travel_mins = self.calculate_distance(job.postcode, plumber.base_postcode)
        
        # Check if plumber covers this area
        covers_area = False
        priority = 'none'
        min_job_value = 0
        
        job_prefix = job.postcode[:4].strip().upper()
        
        for area in plumber.service_postcodes:
            if job_prefix.startswith(area['prefix']):
                covers_area = True
                priority = area['priority']
                min_job_value = area['min_job_value']
                break
        
        # If plumber doesn't cover this area, very low score
        if not covers_area:
            return (5.0, {
                'distance_km': distance_km,
                'covers_area': False,
                'reason': 'Outside service area'
            })
        
        # Check minimum job value for this area
        if job.estimated_value < min_job_value:
            return (20.0, {
                'distance_km': distance_km,
                'covers_area': True,
                'priority': priority,
                'reason': f'Job value £{job.estimated_value:.0f} below minimum £{min_job_value:.0f}'
            })
        
        # Score based on distance and priority
        if priority == 'primary':
            if distance_km <= 5:
                score = 100
            elif distance_km <= 10:
                score = 85
            else:
                score = 70
        elif priority == 'secondary':
            if distance_km <= 5:
                score = 80
            elif distance_km <= 10:
                score = 70
            else:
                score = 50
        else:  # extended
            if distance_km <= 10:
                score = 60
            else:
                score = 40
        
        return (score, {
            'distance_km': distance_km,
            'travel_mins': travel_mins,
            'priority': priority,
            'covers_area': True
        })
    
    def score_availability(self, job: Job, plumber: Plumber) -> Tuple[float, Dict]:
        """
        Score based on plumber availability
        
        Returns: (score 0-100, reasoning)
        """
        # Check if plumber is active
        if plumber.status != 'active':
            return (0, {'reason': f'Plumber status: {plumber.status}'})
        
        # Check credit balance
        if plumber.credit_balance < 25:
            return (0, {'reason': 'Insufficient credits', 'balance': plumber.credit_balance})
        
        # Check current workload
        if plumber.current_jobs_count >= 10:
            return (10, {'reason': 'Fully booked', 'current_jobs': plumber.current_jobs_count})
        
        # Score based on urgency vs availability
        if job.urgency == 'emergency':
            if plumber.available_today and plumber.current_jobs_count < 5:
                score = 100
            elif plumber.available_today:
                score = 70
            else:
                score = 30
        elif job.urgency == 'today':
            if plumber.available_today and plumber.current_jobs_count < 3:
                score = 100
            elif plumber.available_today:
                score = 80
            else:
                score = 40
        elif job.urgency == 'this_week':
            if plumber.current_jobs_count < 5:
                score = 100
            elif plumber.current_jobs_count < 8:
                score = 70
            else:
                score = 40
        else:  # flexible
            if plumber.current_jobs_count < 5:
                score = 100
            elif plumber.current_jobs_count < 8:
                score = 80
            else:
                score = 50
        
        return (score, {
            'available_today': plumber.available_today,
            'current_jobs': plumber.current_jobs_count,
            'urgency_match': job.urgency
        })
    
    def score_specialty(self, job: Job, plumber: Plumber) -> Tuple[float, Dict]:
        """
        Score based on skill/specialty match
        
        Returns: (score 0-100, reasoning)
        """
        # Check Gas Safe requirement
        if job.gas_safe_required and not plumber.gas_safe_certified:
            return (0, {'reason': 'Gas Safe certification required but not held'})
        
        # Check if plumber has this skill
        if job.job_type in plumber.skills:
            # Exact match
            score = 100
            match_level = 'expert'
        elif any(skill in job.job_type for skill in plumber.skills):
            # Partial match
            score = 70
            match_level = 'competent'
        else:
            # No specific skill, but general plumbing
            score = 40
            match_level = 'general'
        
        # Bonus for Gas Safe when needed
        if job.gas_safe_required and plumber.gas_safe_certified:
            score = min(score + 10, 100)
        
        return (score, {
            'has_skill': job.job_type in plumber.skills,
            'match_level': match_level,
            'gas_safe_match': job.gas_safe_required == plumber.gas_safe_certified
        })
    
    def score_performance(self, job: Job, plumber: Plumber) -> Tuple[float, Dict]:
        """
        Score based on historical performance
        
        Returns: (score 0-100, reasoning)
        """
        metrics = plumber.performance_metrics
        
        score = 50  # baseline
        
        # Contact rate (did they call customers?)
        contact_rate = metrics.get('contact_rate', 0)
        if contact_rate > 0.9:
            score += 25
        elif contact_rate > 0.7:
            score += 15
        elif contact_rate < 0.5:
            score -= 20
        
        # Conversion rate (did they win jobs?)
        conversion_rate = metrics.get('conversion_rate', 0)
        if conversion_rate > 0.5:
            score += 15
        elif conversion_rate > 0.3:
            score += 5
        elif conversion_rate < 0.2:
            score -= 10
        
        # Quick response
        # avg_response_mins = metrics.get('avg_response_mins', 30)
        # if avg_response_mins < 10:
        #     score += 10
        
        score = max(min(score, 100), 0)  # Clamp 0-100
        
        return (score, {
            'contact_rate': contact_rate,
            'conversion_rate': conversion_rate,
            'total_jobs': metrics.get('total_jobs_completed', 0)
        })
    
    def score_rating(self, job: Job, plumber: Plumber) -> Tuple[float, Dict]:
        """
        Score based on customer ratings
        
        Returns: (score 0-100, reasoning)
        """
        rating = plumber.performance_metrics.get('average_rating', 0)
        
        if rating >= 4.8:
            score = 100
        elif rating >= 4.5:
            score = 90
        elif rating >= 4.0:
            score = 75
        elif rating >= 3.5:
            score = 50
        else:
            score = 25
        
        return (score, {
            'rating': rating,
            'rating_count': plumber.performance_metrics.get('rating_count', 0)
        })
    
    def calculate_match_score(self, job: Job, plumber: Plumber) -> Match:
        """
        Calculate overall match score for job-plumber pair
        
        Returns: Match object with score and reasoning
        """
        # Calculate component scores
        distance_score, distance_reason = self.score_distance(job, plumber)
        availability_score, availability_reason = self.score_availability(job, plumber)
        specialty_score, specialty_reason = self.score_specialty(job, plumber)
        performance_score, performance_reason = self.score_performance(job, plumber)
        rating_score, rating_reason = self.score_rating(job, plumber)
        
        # Calculate weighted total
        total_score = (
            distance_score * self.WEIGHT_DISTANCE +
            availability_score * self.WEIGHT_AVAILABILITY +
            specialty_score * self.WEIGHT_SPECIALTY +
            performance_score * self.WEIGHT_PERFORMANCE +
            rating_score * self.WEIGHT_RATING
        )
        
        # Get distance details
        distance_km = distance_reason.get('distance_km', 0)
        travel_mins = distance_reason.get('travel_mins', 0)
        
        return Match(
            job_id=job.id,
            plumber_id=plumber.id,
            match_score=round(total_score, 2),
            distance_km=distance_km,
            travel_time_mins=travel_mins,
            ranking=0,  # Will be set later
            reasoning={
                'total_score': round(total_score, 2),
                'components': {
                    'distance': {
                        'score': round(distance_score, 1),
                        'weight': self.WEIGHT_DISTANCE,
                        'weighted': round(distance_score * self.WEIGHT_DISTANCE, 1),
                        'details': distance_reason
                    },
                    'availability': {
                        'score': round(availability_score, 1),
                        'weight': self.WEIGHT_AVAILABILITY,
                        'weighted': round(availability_score * self.WEIGHT_AVAILABILITY, 1),
                        'details': availability_reason
                    },
                    'specialty': {
                        'score': round(specialty_score, 1),
                        'weight': self.WEIGHT_SPECIALTY,
                        'weighted': round(specialty_score * self.WEIGHT_SPECIALTY, 1),
                        'details': specialty_reason
                    },
                    'performance': {
                        'score': round(performance_score, 1),
                        'weight': self.WEIGHT_PERFORMANCE,
                        'weighted': round(performance_score * self.WEIGHT_PERFORMANCE, 1),
                        'details': performance_reason
                    },
                    'rating': {
                        'score': round(rating_score, 1),
                        'weight': self.WEIGHT_RATING,
                        'weighted': round(rating_score * self.WEIGHT_RATING, 1),
                        'details': rating_reason
                    }
                }
            }
        )
    
    def find_matches(self, job: Job, available_plumbers: List[Plumber], top_n: int = 5) -> List[Match]:
        """
        Find and rank best plumbers for a job
        
        Args:
            job: The job to match
            available_plumbers: List of all plumbers
            top_n: How many top matches to return
        
        Returns:
            List of Match objects, sorted by score (best first)
        """
        matches = []
        
        for plumber in available_plumbers:
            match = self.calculate_match_score(job, plumber)
            
            # Only include if score is above minimum threshold
            if match.match_score >= 30:  # Minimum 30/100 to be considered
                matches.append(match)
        
        # Sort by score (highest first)
        matches.sort(key=lambda m: m.match_score, reverse=True)
        
        # Assign rankings
        for i, match in enumerate(matches[:top_n], 1):
            match.ranking = i
        
        return matches[:top_n]


# ================================================================
# USAGE EXAMPLE
# ================================================================

if __name__ == "__main__":
    print("PLUMBER MATCHING ENGINE - DEMO")
    print("="*60)
    
    # Sample job
    job = Job(
        id=1,
        title="Kitchen tap leaking",
        description="Tap dripping constantly in kitchen",
        job_type="leaking_tap",
        postcode="SW19 2AB",
        urgency="this_week",
        complexity="easy",
        estimated_value=120.0,
        ai_confidence=0.92,
        gas_safe_required=False
    )
    
    # Sample plumbers
    plumbers = [
        Plumber(
            id=1,
            name="John Smith",
            base_postcode="SW18",
            hourly_rate=65.0,
            status="active",
            credit_balance=250.0,
            gas_safe_certified=True,
            skills=["leaking_tap", "boiler_repair", "burst_pipe"],
            service_postcodes=[
                {'prefix': 'SW18', 'priority': 'primary', 'min_job_value': 0},
                {'prefix': 'SW19', 'priority': 'primary', 'min_job_value': 0},
                {'prefix': 'SW17', 'priority': 'secondary', 'min_job_value': 100}
            ],
            performance_metrics={
                'contact_rate': 0.92,
                'conversion_rate': 0.58,
                'average_rating': 4.8,
                'rating_count': 127,
                'total_jobs_completed': 89
            },
            current_jobs_count=3,
            available_today=True
        ),
        Plumber(
            id=2,
            name="Sarah Johnson",
            base_postcode="SW19",
            hourly_rate=60.0,
            status="active",
            credit_balance=180.0,
            gas_safe_certified=False,
            skills=["leaking_tap", "toilet_replacement", "unblock_sink"],
            service_postcodes=[
                {'prefix': 'SW19', 'priority': 'primary', 'min_job_value': 0},
                {'prefix': 'SW20', 'priority': 'primary', 'min_job_value': 0}
            ],
            performance_metrics={
                'contact_rate': 0.78,
                'conversion_rate': 0.45,
                'average_rating': 4.6,
                'rating_count': 64,
                'total_jobs_completed': 42
            },
            current_jobs_count=5,
            available_today=True
        ),
        Plumber(
            id=3,
            name="Mike Williams",
            base_postcode="CR4",
            hourly_rate=70.0,
            status="active",
            credit_balance=320.0,
            gas_safe_certified=True,
            skills=["boiler_repair", "shower_installation"],
            service_postcodes=[
                {'prefix': 'CR4', 'priority': 'primary', 'min_job_value': 0},
                {'prefix': 'SM4', 'priority': 'secondary', 'min_job_value': 150}
            ],
            performance_metrics={
                'contact_rate': 0.95,
                'conversion_rate': 0.72,
                'average_rating': 4.9,
                'rating_count': 203,
                'total_jobs_completed': 156
            },
            current_jobs_count=7,
            available_today=False
        )
    ]
    
    # Run matching
    matcher = PlumberMatcher()
    matches = matcher.find_matches(job, plumbers, top_n=3)
    
    # Display results
    print(f"\nJob: {job.title}")
    print(f"Location: {job.postcode}")
    print(f"Type: {job.job_type}")
    print(f"Urgency: {job.urgency}")
    print(f"\nTop {len(matches)} matches:\n")
    
    for match in matches:
        plumber = next(p for p in plumbers if p.id == match.plumber_id)
        print(f"{'='*60}")
        print(f"Rank #{match.ranking}: {plumber.name}")
        print(f"Overall Score: {match.match_score:.1f}/100")
        print(f"Distance: {match.distance_km}km ({match.travel_time_mins} mins)")
        print(f"\nScore Breakdown:")
        
        for component, details in match.reasoning['components'].items():
            print(f"  {component.title():15} {details['score']:5.1f} × {details['weight']:.0%} = {details['weighted']:5.1f}")
        
        print(f"\nKey Factors:")
        for component, details in match.reasoning['components'].items():
            if 'reason' in details['details']:
                print(f"  • {component.title()}: {details['details']['reason']}")
        
        print()
    
    print("="*60)
    print("\nREASONING DETAIL FOR TOP MATCH:")
    print(json.dumps(matches[0].reasoning, indent=2))
