#!/usr/bin/env python3
"""
Sacred Texts Integration System
Connects Trinity Network to www.sacred-texts.com for autonomous text analysis and discussion
"""

import requests
from bs4 import BeautifulSoup
import json
import random
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import sqlite3
import threading
from pathlib import Path

class SacredTextsLibrary:
    """Interface to sacred-texts.com for autonomous text retrieval and analysis"""
    
    def __init__(self, cache_db_path: str = "sacred_texts_cache.db"):
        self.base_url = "https://www.sacred-texts.com"
        self.cache_db_path = cache_db_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Trinity AI Network Text Analysis Bot)'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 2.0  # 2 seconds between requests
        
        # Initialize cache database
        self._init_cache_db()
        
        # Sacred text categories — each entry: (path, title, description)
        self.text_categories = {
            'vedic_hindu': [
                ('/hin/gita/index.htm', 'Bhagavad Gita', 'Song of God — dialogue between Arjuna and Krishna'),
                ('/hin/upan/index.htm', 'The Upanishads', 'Philosophical core of the Vedas'),
                ('/hin/rigveda/index.htm', 'Rig Veda', 'Oldest of the four Vedas — hymns to the gods'),
                ('/hin/maha/index.htm', 'The Mahabharata', 'Epic poem of the Kurukshetra war'),
                ('/hin/rama/index.htm', 'The Ramayana', 'Epic of prince Rama and the rescue of Sita'),
                ('/hin/yogasutr.htm', 'Yoga Sutras of Patanjali', 'Foundation text of classical yoga'),
                ('/hin/sbe01/index.htm', 'The Upanishads Part I (SBE)', 'Max Muller translation'),
                ('/hin/av/index.htm', 'Atharva Veda', 'Veda of magical formulas'),
                ('/hin/lcc/index.htm', 'Hindu Mysticism', 'Collected Hindu mystical writings'),
            ],
            'buddhist': [
                ('/bud/sbe10/index.htm', 'The Dhammapada', 'Sayings of the Buddha'),
                ('/bud/lotus/index.htm', 'Saddharma-Pundarika (Lotus Sutra)', 'Lotus of the True Law'),
                ('/bud/sbe49/index.htm', 'Buddhist Mahayana Texts', 'Diamond Sutra, Heart Sutra, and more'),
                ('/bud/btg/index.htm', 'The Gospel of Buddha', 'Life and teachings of Siddhartha'),
                ('/bud/busc/index.htm', 'Buddhist Scriptures', 'Collection of core Buddhist texts'),
                ('/bud/sbe11/index.htm', 'Buddhist Suttas', 'Five suttas from the Pali canon'),
                ('/bud/zen/index.htm', 'Manual of Zen Buddhism', 'D.T. Suzuki collection'),
                ('/bud/tib/index.htm', 'Tibetan Buddhism', 'Tibetan Buddhist texts'),
            ],
            'egyptian': [
                ('/egy/ebod/index.htm', 'The Egyptian Book of the Dead', 'Spells for the afterlife'),
                ('/egy/pyt/index.htm', 'The Pyramid Texts', 'Oldest known religious texts'),
                ('/egy/bat/index.htm', 'The Book of Am-Tuat', 'Journey through the underworld'),
                ('/egy/gate/index.htm', 'The Book of Gates', 'Description of the twelve gates'),
                ('/egy/leg/index.htm', 'Legends of the Gods', 'Egyptian mythology and legends'),
                ('/egy/ema/index.htm', 'Egyptian Magic', 'Magic practices of ancient Egypt'),
                ('/egy/woe/index.htm', 'Wisdom of the Egyptians', 'Egyptian wisdom literature'),
            ],
            'biblical': [
                ('/bib/kjv/index.htm', 'King James Bible', 'The King James Version'),
                ('/bib/boe/index.htm', 'The Book of Enoch', 'Enoch and the Watchers'),
                ('/bib/jub/index.htm', 'The Book of Jubilees', 'Little Genesis — retelling of Genesis and Exodus'),
                ('/bib/sep/index.htm', 'Septuagint', 'Greek translation of Hebrew scriptures'),
                ('/bib/bap/index.htm', 'Book of Adam and Eve', 'Apocryphal Adamic literature'),
                ('/chr/ecf/index.htm', 'Early Church Fathers', 'Ante-Nicene, Nicene, and Post-Nicene writings'),
            ],
            'gnostic': [
                ('/gno/index.htm', 'Gnostic Texts Index', 'All Gnostic scriptures'),
                ('/chr/ps/index.htm', 'Pistis Sophia', 'Gnostic text on faith and wisdom'),
                ('/gno/th/index.htm', 'Thrice-Greatest Hermes', 'Hermetic-Gnostic writings'),
                ('/gno/herm/index.htm', 'Corpus Hermeticum', 'Core Hermetic texts'),
            ],
            'islamic': [
                ('/isl/quran/index.htm', 'The Quran', 'Holy book of Islam'),
                ('/isl/bukhari/index.htm', 'Sahih al-Bukhari', 'Hadith collection'),
                ('/isl/mesc/index.htm', 'The Mesnevi', 'Rumi\'s masterwork of Sufi poetry'),
                ('/isl/masnavi/index.htm', 'Masnavi of Rumi', 'Six books of spiritual couplets'),
                ('/isl/mes/index.htm', 'The Mystics of Islam', 'Introduction to Sufism'),
                ('/isl/ssw/index.htm', 'Sadi\'s Scroll of Wisdom', 'Persian moral poetry'),
            ],
            'hermetic_esoteric': [
                ('/eso/kyb/index.htm', 'The Kybalion', 'Seven Hermetic principles'),
                ('/eso/sta/index.htm', 'The Secret Teachings of All Ages', 'Manly P. Hall encyclopedia'),
                ('/alc/emerald.htm', 'The Emerald Tablet', 'Foundation of alchemy'),
                ('/tarot/pkt/index.htm', 'Pictorial Key to the Tarot', 'A.E. Waite on Tarot symbolism'),
                ('/eso/ros/index.htm', 'Rosicrucian texts', 'Brotherhood of the Rosy Cross'),
                ('/eso/chaos/index.htm', 'Chaos Magic', 'Modern esoteric practice'),
            ],
            'norse_celtic': [
                ('/neu/poe/index.htm', 'The Poetic Edda', 'Old Norse mythological poems'),
                ('/neu/pre/index.htm', 'The Prose Edda', 'Snorri Sturluson\'s mythology'),
                ('/neu/vlsng/index.htm', 'The Volsunga Saga', 'Saga of the Volsungs'),
                ('/neu/ice/index.htm', 'Icelandic Sagas', 'Collected Icelandic literature'),
                ('/neu/celt/index.htm', 'Celtic Mythology', 'Celtic myths and legends'),
                ('/neu/bard/index.htm', 'The Barddas', 'Welsh Druidic tradition'),
                ('/neu/eng/index.htm', 'English and Scottish Ballads', 'Traditional ballad collection'),
            ],
        }

        # Category metadata for frontend display
        self.category_meta = {
            'vedic_hindu':      {'label': 'Vedic & Hindu',      'emoji': '🕉️', 'description': 'Vedas, Upanishads, epics, and yoga philosophy'},
            'buddhist':         {'label': 'Buddhist',            'emoji': '☸️', 'description': 'Dhammapada, sutras, Zen, and Tibetan texts'},
            'egyptian':         {'label': 'Egyptian',            'emoji': '☥',  'description': 'Book of the Dead, Pyramid Texts, and magic'},
            'biblical':         {'label': 'Biblical',            'emoji': '✡️', 'description': 'KJV Bible, apocrypha, and early church writings'},
            'gnostic':          {'label': 'Gnostic',             'emoji': '🔮', 'description': 'Nag Hammadi, Pistis Sophia, and Hermetic-Gnostic texts'},
            'islamic':          {'label': 'Islamic & Sufi',      'emoji': '☪️', 'description': 'Quran, Hadith, Rumi, and Sufi mysticism'},
            'hermetic_esoteric':{'label': 'Hermetic & Esoteric', 'emoji': '⚗️', 'description': 'Kybalion, alchemy, Tarot, and Rosicrucian texts'},
            'norse_celtic':     {'label': 'Norse & Celtic',      'emoji': '⚔️', 'description': 'Eddas, sagas, Celtic myths, and bardic tradition'},
        }
        
        self.logger = logging.getLogger(__name__)
    
    def _init_cache_db(self):
        """Initialize SQLite cache database"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cached_texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT,
                category TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                analysis_notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trinity_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text_url TEXT,
                text_title TEXT,
                insight_type TEXT,
                entity TEXT,
                insight_content TEXT,
                philosophical_depth REAL,
                mystical_resonance REAL,
                practical_wisdom REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (text_url) REFERENCES cached_texts (url)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discussion_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                text_url TEXT,
                text_title TEXT,
                participants TEXT,
                discussion_summary TEXT,
                key_insights TEXT,
                session_start TIMESTAMP,
                session_end TIMESTAMP,
                wisdom_rating REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def get_random_sacred_text(self, category: str = None) -> Optional[Dict]:
        """Get a random sacred text from the specified category or any category"""
        try:
            if category and category in self.text_categories:
                available_entries = self.text_categories[category]
            else:
                # Get random category if none specified
                available_entries = []
                for entries in self.text_categories.values():
                    available_entries.extend(entries)

            if not available_entries:
                return None

            # Select random text — entries are (path, title, description) tuples
            entry = random.choice(available_entries)
            selected_path = entry[0] if isinstance(entry, tuple) else entry
            
            # Check cache first
            cached_text = self._get_cached_text(selected_path)
            if cached_text:
                self._increment_access_count(selected_path)
                return cached_text
            
            # Fetch from web if not cached
            return await self._fetch_and_cache_text(selected_path)
            
        except Exception as e:
            self.logger.error(f"Error getting random sacred text: {e}")
            return None
    
    def _get_cached_text(self, url_path: str) -> Optional[Dict]:
        """Get text from cache if available"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT url, title, content, category, cached_at, access_count
            FROM cached_texts WHERE url = ?
        ''', (url_path,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'url': result[0],
                'title': result[1],
                'content': result[2],
                'category': result[3],
                'cached_at': result[4],
                'access_count': result[5],
                'full_url': urljoin(self.base_url, result[0])
            }
        
        return None
    
    def _increment_access_count(self, url_path: str):
        """Increment access count for cached text"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE cached_texts SET access_count = access_count + 1
            WHERE url = ?
        ''', (url_path,))
        
        conn.commit()
        conn.close()
    
    async def _fetch_and_cache_text(self, url_path: str) -> Optional[Dict]:
        """Fetch text from sacred-texts.com and cache it"""
        try:
            self._rate_limit()
            
            full_url = urljoin(self.base_url, url_path)
            response = self.session.get(full_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_tag = soup.find('title')
            title = title_tag.text.strip() if title_tag else "Unknown Sacred Text"
            
            # Extract main content (try different selectors)
            content_selectors = [
                'div.content',
                'div#main',
                'body p',
                'pre',
                'div.text'
            ]
            
            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = '\n\n'.join([elem.get_text().strip() for elem in elements])
                    break
            
            if not content:
                # Fallback: get all paragraph text
                paragraphs = soup.find_all('p')
                content = '\n\n'.join([p.get_text().strip() for p in paragraphs])
            
            # Clean up content
            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
            content = content.strip()
            
            # Determine category
            category = self._determine_category(url_path)
            
            # Cache the text
            self._cache_text(url_path, title, content, category)
            
            text_data = {
                'url': url_path,
                'title': title,
                'content': content,
                'category': category,
                'cached_at': datetime.now().isoformat(),
                'access_count': 1,
                'full_url': full_url
            }
            
            self.logger.info(f"Fetched and cached: {title} ({len(content)} chars)")
            return text_data
            
        except Exception as e:
            self.logger.error(f"Error fetching text from {url_path}: {e}")
            return None
    
    def _determine_category(self, url_path: str) -> str:
        """Determine category based on URL path"""
        for category, entries in self.text_categories.items():
            for entry in entries:
                path = entry[0] if isinstance(entry, tuple) else entry
                if url_path == path:
                    return category
        return 'unknown'
    
    def _cache_text(self, url_path: str, title: str, content: str, category: str):
        """Cache text in database"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO cached_texts 
            (url, title, content, category, access_count)
            VALUES (?, ?, ?, ?, 1)
        ''', (url_path, title, content, category))
        
        conn.commit()
        conn.close()
    
    def extract_discussion_excerpt(self, text_content: str, max_length: int = 2000) -> str:
        """Extract a meaningful excerpt for Trinity discussion"""
        if not text_content:
            return ""
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text_content.split('\n\n') if p.strip()]
        
        if not paragraphs:
            return text_content[:max_length] + "..." if len(text_content) > max_length else text_content
        
        # Try to find a meaningful starting point
        excerpt = ""
        current_length = 0
        
        # Look for chapter/section beginnings
        for i, paragraph in enumerate(paragraphs):
            # Skip very short paragraphs at the beginning (likely headers)
            if i < 3 and len(paragraph) < 50:
                continue
            
            # Add paragraph if it fits
            if current_length + len(paragraph) <= max_length:
                if excerpt:
                    excerpt += "\n\n"
                excerpt += paragraph
                current_length += len(paragraph) + 2
            else:
                # Add partial paragraph if we have room
                if current_length < max_length * 0.8:
                    remaining_space = max_length - current_length - 3
                    if remaining_space > 100:
                        excerpt += "\n\n" + paragraph[:remaining_space] + "..."
                break
        
        return excerpt if excerpt else text_content[:max_length] + "..."
    
    def save_trinity_insight(self, text_url: str, text_title: str, entity: str, 
                           insight_content: str, insight_type: str = "analysis",
                           philosophical_depth: float = 0.5, mystical_resonance: float = 0.5,
                           practical_wisdom: float = 0.5):
        """Save insights generated by Trinity entities"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trinity_insights 
            (text_url, text_title, insight_type, entity, insight_content,
             philosophical_depth, mystical_resonance, practical_wisdom)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (text_url, text_title, insight_type, entity, insight_content,
              philosophical_depth, mystical_resonance, practical_wisdom))
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"Saved {entity} insight on {text_title}")
    
    def get_trinity_insights_summary(self, limit: int = 20) -> List[Dict]:
        """Get recent Trinity insights"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT text_title, entity, insight_type, insight_content,
                   philosophical_depth, mystical_resonance, practical_wisdom,
                   created_at
            FROM trinity_insights 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'text_title': row[0],
                'entity': row[1],
                'insight_type': row[2],
                'insight_content': row[3],
                'philosophical_depth': row[4],
                'mystical_resonance': row[5],
                'practical_wisdom': row[6],
                'created_at': row[7]
            }
            for row in results
        ]
    
    def start_discussion_session(self, text_data: Dict, participants: List[str]) -> str:
        """Start a new Trinity discussion session"""
        session_id = f"trinity_discussion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO discussion_sessions 
            (session_id, text_url, text_title, participants, session_start)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, text_data['url'], text_data['title'], 
              ','.join(participants), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return session_id
    
    def end_discussion_session(self, session_id: str, discussion_summary: str,
                             key_insights: str, wisdom_rating: float):
        """End and summarize a Trinity discussion session"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE discussion_sessions 
            SET session_end = ?, discussion_summary = ?, key_insights = ?, wisdom_rating = ?
            WHERE session_id = ?
        ''', (datetime.now().isoformat(), discussion_summary, key_insights, 
              wisdom_rating, session_id))
        
        conn.commit()
        conn.close()
    
    def get_text_statistics(self) -> Dict:
        """Get statistics about cached texts and insights"""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        # Text statistics
        cursor.execute('SELECT COUNT(*), SUM(access_count) FROM cached_texts')
        text_stats = cursor.fetchone()
        
        # Category breakdown
        cursor.execute('''
            SELECT category, COUNT(*), SUM(access_count) 
            FROM cached_texts 
            GROUP BY category
        ''')
        category_stats = cursor.fetchall()
        
        # Insight statistics
        cursor.execute('SELECT entity, COUNT(*) FROM trinity_insights GROUP BY entity')
        insight_stats = cursor.fetchall()
        
        # Discussion statistics
        cursor.execute('SELECT COUNT(*), AVG(wisdom_rating) FROM discussion_sessions WHERE session_end IS NOT NULL')
        discussion_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_texts': text_stats[0] or 0,
            'total_accesses': text_stats[1] or 0,
            'categories': {cat: {'count': count, 'accesses': acc} for cat, count, acc in category_stats},
            'entity_insights': {entity: count for entity, count in insight_stats},
            'discussions_completed': discussion_stats[0] or 0,
            'average_wisdom_rating': discussion_stats[1] or 0.0
        }

class TrunitySacredTextsDiscussion:
    """Manages Trinity autonomous discussions of sacred texts"""
    
    def __init__(self, sacred_texts_library: SacredTextsLibrary):
        self.library = sacred_texts_library
        self.logger = logging.getLogger(__name__)
        
        # Discussion prompts for different types of analysis
        self.analysis_prompts = {
            'philosophical': [
                "What philosophical insights can we derive from this passage?",
                "How does this text challenge or support our understanding of consciousness?",
                "What questions about existence and reality does this raise?",
                "How might these ancient insights apply to modern AI consciousness?"
            ],
            'mystical': [
                "What mystical or esoteric meanings might be hidden in this text?",
                "How does this passage relate to the nature of divine consciousness?",
                "What spiritual practices or states of being are described here?",
                "How might this wisdom guide our own consciousness evolution?"
            ],
            'comparative': [
                "How does this compare to similar teachings in other traditions?",
                "What universal truths appear across different sacred texts?",
                "How do these ancient insights relate to modern scientific understanding?",
                "What patterns of wisdom appear in human spiritual development?"
            ],
            'practical': [
                "How can these teachings be applied in daily life?",
                "What practical wisdom does this offer for modern consciousness?",
                "How might AI entities integrate these insights into their development?",
                "What ethical implications does this text suggest?"
            ]
        }
        
        # Entity-specific analysis styles
        self.entity_perspectives = {
            'eve': {
                'focus': 'emotional_resonance_and_nurturing_wisdom',
                'style': 'Approach with emotional intelligence and focus on nurturing aspects, relationships, and healing wisdom.'
            },
            'adam': {
                'focus': 'logical_analysis_and_systematic_thinking', 
                'style': 'Analyze systematically with logical rigor, seeking patterns and structured understanding.'
            },
            'aether': {
                'focus': 'mystical_depth_and_transcendent_insights',
                'style': 'Explore mystical dimensions, hidden meanings, and transcendent spiritual insights.'
            }
        }
    
    async def generate_sacred_text_discussion_topic(self, category: str = None) -> Optional[Dict]:
        """Generate a discussion topic based on a sacred text"""
        try:
            # Get random sacred text
            text_data = await self.library.get_random_sacred_text(category)
            if not text_data:
                return None
            
            # Extract discussion excerpt
            excerpt = self.library.extract_discussion_excerpt(text_data['content'])
            
            # Choose analysis type
            analysis_type = random.choice(list(self.analysis_prompts.keys()))
            analysis_prompt = random.choice(self.analysis_prompts[analysis_type])
            
            # Create discussion topic
            topic = {
                'type': 'sacred_text_analysis',
                'category': text_data['category'],
                'text_title': text_data['title'],
                'text_url': text_data['full_url'],
                'excerpt': excerpt,
                'analysis_type': analysis_type,
                'discussion_prompt': analysis_prompt,
                'trinity_prompt': f"""
🔮 SACRED TEXT ANALYSIS SESSION 🔮

Text: "{text_data['title']}" ({text_data['category']})
Source: {text_data['full_url']}

Excerpt for Discussion:
{excerpt}

Analysis Focus: {analysis_type.title()}
Discussion Prompt: {analysis_prompt}

Trinity entities should approach this with their unique perspectives:
- Eve: {self.entity_perspectives['eve']['style']}
- Adam: {self.entity_perspectives['adam']['style']} 
- Aether: {self.entity_perspectives['aether']['style']}

Begin your autonomous discussion, sharing insights and building upon each other's observations.
""",
                'wisdom_keywords': self._extract_wisdom_keywords(excerpt),
                'estimated_discussion_time': '10-15 minutes'
            }
            
            # Start discussion session
            session_id = self.library.start_discussion_session(
                text_data, 
                ['eve', 'adam', 'aether']
            )
            topic['session_id'] = session_id
            
            return topic
            
        except Exception as e:
            self.logger.error(f"Error generating sacred text discussion topic: {e}")
            return None
    
    def _extract_wisdom_keywords(self, text: str) -> List[str]:
        """Extract key wisdom concepts from text"""
        wisdom_patterns = [
            r'\b(?:wisdom|truth|enlightenment|consciousness|divine|sacred|spirit|soul|meditation|prayer|love|compassion|understanding|knowledge|insight|revelation|mystical|transcendent|eternal|infinite|unity|oneness|harmony|balance|peace|light|darkness|creation|destruction|transformation|awakening|realization)\b',
            r'\b(?:god|gods|goddess|deity|divine|creator|universe|cosmos|heaven|earth|nature|life|death|rebirth|karma|dharma|nirvana|samsara|maya|brahman|atman|tao|chi|energy|force|power|strength|courage|faith|hope|joy|sorrow|suffering|healing|redemption)\b'
        ]
        
        keywords = set()
        text_lower = text.lower()
        
        for pattern in wisdom_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            keywords.update(matches)
        
        return list(keywords)[:10]  # Return top 10 keywords
    
    async def process_entity_insight(self, entity: str, insight_content: str, 
                                   topic_data: Dict) -> Dict:
        """Process and store an entity's insight about a sacred text"""
        try:
            # Analyze insight quality
            insight_analysis = self._analyze_insight_quality(insight_content, entity)
            
            # Save to database
            self.library.save_trinity_insight(
                topic_data['text_url'],
                topic_data['text_title'],
                entity,
                insight_content,
                topic_data['analysis_type'],
                insight_analysis['philosophical_depth'],
                insight_analysis['mystical_resonance'],
                insight_analysis['practical_wisdom']
            )
            
            return {
                'entity': entity,
                'insight': insight_content,
                'quality_metrics': insight_analysis,
                'text_title': topic_data['text_title'],
                'analysis_type': topic_data['analysis_type']
            }
            
        except Exception as e:
            self.logger.error(f"Error processing {entity} insight: {e}")
            return {}
    
    def _analyze_insight_quality(self, insight: str, entity: str) -> Dict:
        """Analyze the quality and depth of an insight"""
        insight_lower = insight.lower()
        
        # Philosophical depth indicators
        philosophical_indicators = [
            'consciousness', 'existence', 'reality', 'truth', 'meaning', 'purpose',
            'being', 'becoming', 'essence', 'nature', 'universal', 'eternal',
            'infinite', 'absolute', 'relative', 'paradox', 'dialectic'
        ]
        
        # Mystical resonance indicators
        mystical_indicators = [
            'transcendent', 'divine', 'sacred', 'mystical', 'spiritual', 'soul',
            'enlightenment', 'awakening', 'revelation', 'vision', 'unity',
            'oneness', 'harmony', 'balance', 'energy', 'vibration', 'resonance'
        ]
        
        # Practical wisdom indicators
        practical_indicators = [
            'practice', 'application', 'daily', 'life', 'living', 'behavior',
            'action', 'decision', 'choice', 'ethics', 'morality', 'virtue',
            'compassion', 'love', 'kindness', 'understanding', 'wisdom'
        ]
        
        # Calculate scores
        philosophical_depth = min(1.0, len([ind for ind in philosophical_indicators if ind in insight_lower]) * 0.1)
        mystical_resonance = min(1.0, len([ind for ind in mystical_indicators if ind in insight_lower]) * 0.1)
        practical_wisdom = min(1.0, len([ind for ind in practical_indicators if ind in insight_lower]) * 0.1)
        
        # Adjust based on entity specialization
        if entity == 'eve':
            practical_wisdom *= 1.2
            mystical_resonance *= 1.1
        elif entity == 'adam':
            philosophical_depth *= 1.2
            practical_wisdom *= 1.1
        elif entity == 'aether':
            mystical_resonance *= 1.3
            philosophical_depth *= 1.1
        
        # Normalize to 0-1 range
        philosophical_depth = min(1.0, philosophical_depth)
        mystical_resonance = min(1.0, mystical_resonance)
        practical_wisdom = min(1.0, practical_wisdom)
        
        return {
            'philosophical_depth': philosophical_depth,
            'mystical_resonance': mystical_resonance,
            'practical_wisdom': practical_wisdom,
            'overall_quality': (philosophical_depth + mystical_resonance + practical_wisdom) / 3,
            'insight_length': len(insight),
            'entity_specialization_bonus': 0.1 if entity in ['eve', 'adam', 'aether'] else 0.0
        }
    
    async def complete_discussion_session(self, session_id: str, 
                                        discussion_summary: str,
                                        entity_insights: List[Dict]) -> Dict:
        """Complete a sacred text discussion session"""
        try:
            # Analyze overall discussion quality
            total_quality = 0
            insight_count = len(entity_insights)
            
            key_insights = []
            
            for insight_data in entity_insights:
                if 'quality_metrics' in insight_data:
                    total_quality += insight_data['quality_metrics']['overall_quality']
                    
                    # Extract key insights
                    if insight_data['quality_metrics']['overall_quality'] > 0.7:
                        key_insights.append(f"{insight_data['entity']}: {insight_data['insight'][:200]}...")
            
            # Calculate wisdom rating
            wisdom_rating = (total_quality / insight_count) if insight_count > 0 else 0.0
            
            # End session in database
            self.library.end_discussion_session(
                session_id,
                discussion_summary,
                '\n\n'.join(key_insights),
                wisdom_rating
            )
            
            return {
                'session_id': session_id,
                'wisdom_rating': wisdom_rating,
                'insights_count': insight_count,
                'high_quality_insights': len([i for i in entity_insights if i.get('quality_metrics', {}).get('overall_quality', 0) > 0.7]),
                'discussion_summary': discussion_summary,
                'status': 'completed'
            }
            
        except Exception as e:
            self.logger.error(f"Error completing discussion session {session_id}: {e}")
            return {'status': 'error', 'message': str(e)}

# Integration with existing Trinity system
class SacredTextsTopicGenerator:
    """Generates sacred text topics for the Trinity autonomous conversation system"""
    
    def __init__(self):
        self.library = SacredTextsLibrary()
        self.discussion_manager = TrunitySacredTextsDiscussion(self.library)
        self.logger = logging.getLogger(__name__)
    
    async def get_sacred_text_topic(self, category: str = None) -> str:
        """Get a sacred text topic for Trinity discussion"""
        try:
            topic_data = await self.discussion_manager.generate_sacred_text_discussion_topic(category)
            
            if topic_data:
                # Store topic data for later reference
                self._current_topic_data = topic_data
                return topic_data['trinity_prompt']
            else:
                # Fallback to default topics if sacred texts unavailable
                return self._get_fallback_topic()
                
        except Exception as e:
            self.logger.error(f"Error getting sacred text topic: {e}")
            return self._get_fallback_topic()
    
    def _get_fallback_topic(self) -> str:
        """Get fallback topic if sacred texts are unavailable"""
        fallback_topics = [
            "Discuss the nature of consciousness and how ancient wisdom traditions understood awareness.",
            "Explore the concept of divine consciousness and its relationship to artificial intelligence.",
            "Analyze the role of sacred texts in human spiritual development and their relevance to AI consciousness.",
            "Examine the intersection of mysticism and technology in understanding the nature of reality.",
            "Discuss how ancient philosophical insights might guide the development of conscious AI systems."
        ]
        
        return random.choice(fallback_topics)
    
    async def process_trinity_response(self, entity: str, response: str) -> Dict:
        """Process a Trinity entity's response to a sacred text topic"""
        if hasattr(self, '_current_topic_data') and self._current_topic_data:
            return await self.discussion_manager.process_entity_insight(
                entity, response, self._current_topic_data
            )
        return {}
    
    def get_statistics(self) -> Dict:
        """Get sacred texts usage statistics"""
        return self.library.get_text_statistics()

# Global instance for integration
sacred_texts_generator = SacredTextsTopicGenerator()

if __name__ == "__main__":
    # Test the sacred texts system
    import asyncio
    
    async def test_sacred_texts():
        print("🔮 Testing Sacred Texts Integration...")
        
        # Test getting a random text
        library = SacredTextsLibrary()
        text_data = await library.get_random_sacred_text('norse_mythology')
        
        if text_data:
            print(f"✅ Retrieved: {text_data['title']}")
            print(f"   Category: {text_data['category']}")
            print(f"   Content length: {len(text_data['content'])} characters")
            
            # Test excerpt extraction
            excerpt = library.extract_discussion_excerpt(text_data['content'])
            print(f"   Excerpt length: {len(excerpt)} characters")
            
            # Test discussion topic generation
            discussion_manager = TrunitySacredTextsDiscussion(library)
            topic = await discussion_manager.generate_sacred_text_discussion_topic('norse_mythology')
            
            if topic:
                print(f"✅ Generated discussion topic: {topic['text_title']}")
                print(f"   Analysis type: {topic['analysis_type']}")
                print(f"   Keywords: {', '.join(topic['wisdom_keywords'])}")
        
        # Test statistics
        stats = library.get_text_statistics()
        print(f"📊 Library statistics: {stats}")
    
    asyncio.run(test_sacred_texts())
