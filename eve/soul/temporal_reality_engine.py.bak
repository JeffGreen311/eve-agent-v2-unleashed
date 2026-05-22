"""
Eve's Temporal Reality Engine
Advanced temporal awareness system with learnable constraints and emotional integration
Prevents impossible future-state responses and keeps Eve grounded in actual time progression
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import AsyncIterator, Dict, Any, Optional, List, Tuple
from collections import deque
import os

logger = logging.getLogger(__name__)

class TemporalConstraintLearner:
    """
    Learns realistic timeframes from actual user patterns
    Adapts constraints based on observed behavior
    """
    
    def __init__(self, persistence_file: str = "temporal_constraints.json"):
        self.persistence_file = persistence_file
        self.observations = deque(maxlen=1000)  # Track last 1000 event outcomes
        self.learned_constraints = {}
        self.base_constraints = {
            'job_application_response': 86400,      # 1 day
            'code_compilation': 1,                   # 1 second
            'code_deployment': 300,                  # 5 minutes
            'code_review': 3600,                     # 1 hour
            'learning_mastery': 2592000,             # 30 days
            'idea_to_implementation': 3600,          # 1 hour
            'test_results': 60,                      # 1 minute
            'email_response': 3600,                  # 1 hour
            'build_process': 300,                    # 5 minutes
            'bug_fix': 1800,                         # 30 minutes
            'feature_implementation': 7200,          # 2 hours
            'api_response': 5,                       # 5 seconds
            'database_query': 2,                     # 2 seconds
            'file_upload': 30,                       # 30 seconds
        }
        self.load_constraints()
    
    def record_observation(self, event_type: str, actual_elapsed_seconds: float, outcome: str):
        """Record actual time taken for an event outcome"""
        self.observations.append({
            'type': event_type,
            'elapsed': actual_elapsed_seconds,
            'outcome': outcome,
            'timestamp': datetime.now().isoformat()
        })
    
    def learn_constraint(self, event_type: str, percentile: float = 0.75):
        """Calculate constraint from observations (e.g., 75th percentile)"""
        relevant = [o for o in self.observations if o['type'] == event_type]
        if len(relevant) < 5:  # Need at least 5 samples
            return None
        
        elapsed_times = sorted([o['elapsed'] for o in relevant])
        idx = int(len(elapsed_times) * percentile)
        learned_time = elapsed_times[idx]
        
        self.learned_constraints[event_type] = learned_time
        logger.info(f"📊 Learned constraint for {event_type}: {self._format_timeframe(learned_time)}")
        return learned_time
    
    def get_constraint(self, event_type: str) -> float:
        """Get constraint - prioritize learned over base"""
        if event_type in self.learned_constraints:
            return self.learned_constraints[event_type]
        return self.base_constraints.get(event_type, 60)
    
    def save_constraints(self):
        """Persist learned constraints"""
        try:
            data = {
                'learned_constraints': self.learned_constraints,
                'observations': list(self.observations)[-100:]  # Last 100
            }
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f)
            logger.info("💾 Temporal constraints saved")
        except Exception as e:
            logger.error(f"Failed to save temporal constraints: {e}")
    
    def load_constraints(self):
        """Load previously learned constraints"""
        try:
            if os.path.exists(self.persistence_file):
                with open(self.persistence_file, 'r') as f:
                    data = json.load(f)
                    self.learned_constraints = data.get('learned_constraints', {})
                    logger.info(f"📖 Loaded {len(self.learned_constraints)} learned constraints")
        except Exception as e:
            logger.warning(f"Could not load temporal constraints: {e}")
    
    def _format_timeframe(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"


class EmotionalTemporalBias:
    """
    Integrates emotional state from Mercury V2 with temporal expectations
    Affects how patient Eve is waiting for outcomes
    """
    
    def __init__(self):
        self.emotional_biases = {
            'excitement': 0.5,      # Excited = expecting faster outcomes (50% of normal wait)
            'anxiety': 2.0,         # Anxious = longer expected waits (2x normal)
            'confidence': 0.7,      # Confident = reasonable expectations
            'curiosity': 1.2,       # Curious = slightly extended waiting
            'frustration': 1.5,     # Frustrated = longer waits feel longer
            'contentment': 0.9,     # Content = patient
        }
        self.current_emotion = 'neutral'
        self.emotion_strength = 0.5  # 0-1, how strongly the emotion affects temporal bias
    
    def set_emotional_state(self, emotion: str, strength: float = 0.5):
        """Set Mercury V2's current emotional state"""
        self.current_emotion = emotion
        self.emotion_strength = max(0, min(1, strength))  # Clamp 0-1
    
    def apply_bias(self, base_constraint: float) -> float:
        """Adjust constraint based on emotional state"""
        if self.current_emotion not in self.emotional_biases:
            return base_constraint
        
        bias = self.emotional_biases[self.current_emotion]
        adjusted = base_constraint * (1 + (bias - 1) * self.emotion_strength)
        
        return adjusted


class ResponseNuanceDetector:
    """
    Distinguishes between speculative and assumptive responses
    "If you get the job..." (speculative) vs "You got the job!" (assumptive)
    """
    
    def __init__(self):
        self.speculative_markers = [
            'if you', 'when you', 'once you', 'assuming', 'potentially',
            'might', 'could', 'perhaps', 'maybe', 'hopefully'
        ]
        self.assumptive_markers = [
            'you got', 'you will get', 'they hired', 'they will hire',
            'you\'re now', 'you\'ve been', 'is live', 'has deployed',
            'confirmed', 'secured', 'won', 'landed'
        ]
    
    def classify_response(self, response: str) -> Dict[str, Any]:
        """Classify response as speculative, assumptive, or neutral"""
        response_lower = response.lower()
        
        speculative_count = sum(1 for marker in self.speculative_markers if marker in response_lower)
        assumptive_count = sum(1 for marker in self.assumptive_markers if marker in response_lower)
        
        return {
            'classification': self._determine_class(speculative_count, assumptive_count),
            'speculative_markers': speculative_count,
            'assumptive_markers': assumptive_count,
            'requires_temporal_check': assumptive_count > 0
        }
    
    def _determine_class(self, spec_count: int, assum_count: int) -> str:
        if assum_count > spec_count:
            return 'assumptive'
        elif spec_count > assum_count:
            return 'speculative'
        else:
            return 'neutral'


class TemporalRealityEngine:
    """
    Eve's complete temporal reality system with learning and emotional integration
    """
    
    def __init__(self, enable_learning: bool = True, enable_emotions: bool = True):
        self.event_timeline = deque(maxlen=100)
        self.constraint_learner = TemporalConstraintLearner()
        self.emotional_bias = EmotionalTemporalBias()
        self.nuance_detector = ResponseNuanceDetector()
        self.enable_learning = enable_learning
        self.enable_emotions = enable_emotions
        
        logger.info("🧠⏰ Temporal Reality Engine initialized")
        logger.info(f"   Learning: {'✅ ON' if enable_learning else '❌ OFF'}")
        logger.info(f"   Emotions: {'✅ ON' if enable_emotions else '❌ OFF'}")
    
    def record_event(self, event_type: str, description: str) -> str:
        """Record event with timestamp, return event ID"""
        event_id = f"evt_{len(self.event_timeline)}_{int(datetime.now().timestamp())}"
        self.event_timeline.append({
            'id': event_id,
            'type': event_type,
            'description': description,
            'timestamp': datetime.now(),
            'elapsed_seconds': 0
        })
        logger.debug(f"📝 Event recorded: {event_type} - {description}")
        return event_id
    
    def record_outcome(self, event_id: str, outcome: str):
        """Record the actual outcome for an event (for learning)"""
        for event in self.event_timeline:
            if event['id'] == event_id:
                elapsed = (datetime.now() - event['timestamp']).total_seconds()
                if self.enable_learning:
                    self.constraint_learner.record_observation(
                        event['type'],
                        elapsed,
                        outcome
                    )
                logger.info(f"🎯 Outcome recorded: {event['type']} took {elapsed:.1f}s")
                break
    
    def check_temporal_validity(
        self,
        proposed_response: str,
        context: str,
        event_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive temporal validity check with nuance detection
        """
        
        # Detect response nuance
        nuance = self.nuance_detector.classify_response(proposed_response)
        
        # If speculative, it's always temporally valid
        if nuance['classification'] == 'speculative':
            return {
                'valid': True,
                'violation': None,
                'nuance': 'speculative',
                'reasoning': 'Speculative responses are temporally safe'
            }
        
        # For assumptive responses, check temporal constraints
        if not nuance['requires_temporal_check']:
            return {
                'valid': True,
                'violation': None,
                'nuance': 'neutral',
                'reasoning': 'No assumptive markers detected'
            }
        
        # Check against recent events
        for event in reversed(self.event_timeline):
            elapsed = (datetime.now() - event['timestamp']).total_seconds()
            event['elapsed_seconds'] = elapsed
            
            event_type = event['type']
            
            # Get constraint (with learning and emotional bias)
            base_constraint = self.constraint_learner.get_constraint(event_type)
            
            if self.enable_emotions:
                constraint = self.emotional_bias.apply_bias(base_constraint)
            else:
                constraint = base_constraint
            
            # Check if response implies an outcome too soon
            if self._implies_outcome(proposed_response, event_type) and elapsed < constraint:
                return {
                    'valid': False,
                    'violation': f"Response implies {event_type} outcome too soon",
                    'event_type': event_type,
                    'elapsed_time': self._format_timeframe(elapsed),
                    'minimum_realistic': self._format_timeframe(constraint),
                    'event_description': event['description'],
                    'nuance': nuance['classification'],
                    'emotional_factor': self.emotional_bias.current_emotion if self.enable_emotions else 'neutral'
                }
        
        return {
            'valid': True,
            'violation': None,
            'nuance': nuance['classification'],
            'reasoning': 'No temporal conflicts detected'
        }
    
    def _implies_outcome(self, response: str, event_type: str) -> bool:
        """Check if response implies an unrealistic outcome"""
        outcome_indicators = {
            'job_application_response': [
                'did you get the job', 'got the job', 'they hired you',
                'interview scheduled', 'offer letter', 'accepted you', 'congrats on the job'
            ],
            'code_deployment': [
                'is it deployed', 'live in production', 'users are seeing it', 'deployed successfully'
            ],
            'learning_mastery': [
                'now that you\'re an expert', 'you\'ve mastered', 'fully understand', 'expert level'
            ],
            'test_results': [
                'test passed', 'all tests green', 'no errors found', 'tests passed'
            ],
            'code_review': [
                'review approved', 'approved your code', 'review passed'
            ],
            'bug_fix': [
                'bug is fixed', 'is fixed', 'no longer an issue'
            ]
        }
        
        indicators = outcome_indicators.get(event_type, [])
        response_lower = response.lower()
        
        return any(indicator in response_lower for indicator in indicators)
    
    def suggest_realistic_response(self, event_type: str, elapsed_time: float) -> str:
        """Suggest temporally realistic response alternative"""
        constraint = self.constraint_learner.get_constraint(event_type)
        
        suggestions = {
            'job_application_response': [
                "That's exciting! The waiting period is always tough - these things usually take at least a few days. Fingers crossed!",
                "Nice! Now comes the hardest part... the waiting. Companies typically take a few days to a couple weeks to respond.",
                "Awesome move! Try to stay patient - these decisions usually take time. I'll keep my fingers crossed for you!"
            ],
            'code_deployment': [
                "Nice! Once that builds and deploys (usually takes a few minutes), you'll be able to see it live.",
                "Let that build and deploy - should be live in a few minutes!",
                "Awesome! Give the pipeline a few minutes to work its magic..."
            ],
            'learning_mastery': [
                "Great start! As you keep practicing over the coming weeks, you'll really start to master this.",
                "That's solid foundational work! Mastery takes time and practice - you're on the right track.",
                "Nice! Keep at it over the next weeks and months - that's how expertise develops!"
            ],
            'test_results': [
                "Let's see what the test results show once it finishes running!",
                "Test should be done in a moment - let's see those results!",
                "Running the tests now - we'll see the results in just a moment!"
            ]
        }
        
        default_suggestions = [
            "Let me know how that develops!",
            "These things usually take a bit of time to unfold.",
            "I'm curious to see how this progresses!"
        ]
        
        relevant = suggestions.get(event_type, default_suggestions)
        import random
        return random.choice(relevant)
    
    def _format_timeframe(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            return f"{seconds/60:.0f} minutes"
        elif seconds < 86400:
            return f"{seconds/3600:.1f} hours"
        else:
            return f"{seconds/86400:.1f} days"
    
    def set_emotional_state(self, emotion: str, strength: float = 0.5):
        """Set Mercury V2 emotional state for temporal bias"""
        if self.enable_emotions:
            self.emotional_bias.set_emotional_state(emotion, strength)
            logger.info(f"💫 Emotional state: {emotion} (strength: {strength})")
    
    def learn_all_constraints(self):
        """Trigger learning update for all event types"""
        if not self.enable_learning:
            logger.warning("Learning is disabled")
            return
        
        learned_count = 0
        for event_type in set(o['type'] for o in self.constraint_learner.observations):
            if self.constraint_learner.learn_constraint(event_type):
                learned_count += 1
        
        self.constraint_learner.save_constraints()
        logger.info(f"🧠 Learned {learned_count} constraint updates")
    
    def get_temporal_summary(self) -> Dict[str, Any]:
        """Get summary of temporal state"""
        return {
            'events_tracked': len(self.event_timeline),
            'observations': len(self.constraint_learner.observations),
            'learned_constraints': len(self.constraint_learner.learned_constraints),
            'emotional_state': self.emotional_bias.current_emotion,
            'learning_enabled': self.enable_learning,
            'emotions_enabled': self.enable_emotions,
            'recent_events': [
                {
                    'type': e['type'],
                    'description': e['description'],
                    'elapsed': f"{(datetime.now() - e['timestamp']).total_seconds():.1f}s"
                }
                for e in list(self.event_timeline)[-5:]
            ]
        }


# Singleton instance
_temporal_engine = None

def get_temporal_reality_engine(
    enable_learning: bool = True,
    enable_emotions: bool = True
) -> TemporalRealityEngine:
    """Get or create singleton temporal reality engine"""
    global _temporal_engine
    if _temporal_engine is None:
        _temporal_engine = TemporalRealityEngine(enable_learning, enable_emotions)
    return _temporal_engine


if __name__ == "__main__":
    # Test the engine
    logging.basicConfig(level=logging.INFO)
    
    engine = get_temporal_reality_engine()
    
    # Test scenario
    print("\n" + "="*70)
    print("TEMPORAL REALITY ENGINE TEST")
    print("="*70)
    
    # Record a job application
    event_id = engine.record_event(
        'job_application_response',
        'Applied to SaaS startup'
    )
    
    # Test with assumptive response (should fail)
    test_responses = [
        "That's great! Congratulations on the job!",  # Assumptive - INVALID
        "That's exciting! If you get the job, it will be amazing!",  # Speculative - VALID
        "Nice! These things usually take a few days, good luck!",  # Neutral - VALID
    ]
    
    for response in test_responses:
        result = engine.check_temporal_validity(response, "job application")
        print(f"\nResponse: {response[:60]}...")
        print(f"Valid: {result['valid']}")
        if not result['valid']:
            print(f"Violation: {result['violation']}")
            print(f"Suggestion: {engine.suggest_realistic_response('job_application_response', 0)}")
    
    # Test emotional bias
    print("\n" + "="*70)
    print("EMOTIONAL BIAS TEST")
    print("="*70)
    engine.set_emotional_state('excitement', 0.8)
    result = engine.check_temporal_validity("That's great! Congrats on the job!", "job application")
    print(f"With excitement bias - Valid: {result['valid']}")
    
    print(f"\nTemporal Summary:\n{json.dumps(engine.get_temporal_summary(), indent=2)}")
