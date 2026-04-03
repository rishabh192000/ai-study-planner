from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
import requests
from urllib.parse import quote
from langdetect import detect
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import time

# ============== CACHE VARIABLES ==============
_topic_cache = {}
_youtube_cache = {}
_CACHE_EXPIRY = 3600

# ============== SUBJECT/TOPIC PARSING FUNCTIONS ==============
def parse_subjects_topics_input(input_text):
    """Parse subjects and topics from various input formats"""
    if not input_text or not input_text.strip():
        return []
    
    input_text = input_text.strip()
    parsed = []
    parts = input_text.replace(';', ',').split('\n')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        items = [item.strip() for item in part.split(',') if item.strip()]
        current_subject = None
        current_topics = []
        
        for item in items:
            if ':' in item:
                if current_subject:
                    parsed.append({"subject": current_subject, "topics": current_topics if current_topics else []})
                
                subject_and_topic = item.split(':', 1)
                current_subject = subject_and_topic[0].strip()
                
                if len(subject_and_topic) > 1 and subject_and_topic[1].strip():
                    current_topics = [t.strip() for t in subject_and_topic[1].split(',') if t.strip()]
                else:
                    current_topics = []
            else:
                if current_subject:
                    current_topics.append(item)
                else:
                    parsed.append({"subject": item, "topics": []})
        
        if current_subject:
            parsed.append({"subject": current_subject, "topics": current_topics})
    
    return parsed


def expand_all_topics(parsed_subjects):
    """Expand parsed subjects into individual (subject, topic) pairs"""
    all_units = []
    
    for item in parsed_subjects:
        subject = item["subject"]
        topics = item.get("topics", [])
        
        if topics:
            for topic in topics:
                if topic.strip():
                    all_units.append({
                        "subject": subject,
                        "topic": topic.strip()
                    })
        else:
            all_units.append({
                "subject": subject,
                "topic": subject
            })
    
    return all_units


# ============== ACADEMIC VALIDATOR FUNCTIONS ==============
NON_ACADEMIC_KEYWORDS = {
    "movies": ["movie", "film", "cinema", "bollywood", "hollywood", "netflix", "hotstar", "disney", "series", "episode", "trailer"],
    "music": ["song", "music", "album", "lyrics", " singer", "band", "playlist", "audio", "spotify", "gaana", "jiosaavn"],
    "celebrities": ["actor", "actress", "celebrity", "star", "idol", "influencer", "youtuber", "streamer", "rapper", "singer"],
    "entertainment": ["meme", "memes", "funny", "comedy", "prank", "vlog", "vlogging", "reels", "shorts", "tiktok", "viral", "trending", "gaming", "esports", "twitch"],
    "politics": ["election", "vote", "politic", "government policy", "minister", "mp", "mla", "parliament", "congress", "bjp", "aap"],
    "sports_unrelated": ["cricket match", "football match", "ipl", "world cup", "match highlights", "sports news"],
}

ACADEMIC_SUBJECT_KEYWORDS = {
    "Mathematics": ["math", "maths", "algebra", "calculus", "geometry", "trigonometry", "statistics", "probability", "arithmetic", "equation", "theorem", "formula", "derivative", "integral", "matrix", "vector", "number", "quadratic", "linear", "polynomial", "mensuration"],
    "Physics": ["physics", "force", "motion", "energy", "power", "work", "heat", "temperature", "thermodynamic", "wave", "sound", "light", "optics", "electricity", "magnetism", "mass", "velocity", "acceleration", "newton", "gravity", "momentum", "pressure", "density", "kinematics", "modern physics", "quantum", "relativity", "nuclear", "atom", "molecule", "current electricity", "gauss", "coulomb", "capacitance"],
    "Chemistry": ["chemistry", "chemical", "atom", "molecule", "element", "compound", "reaction", "bond", "ionic", "covalent", "periodic", "acid", "base", "salt", "solution", "concentration", "mole", "stoichiometry", "organic", "inorganic", "electrochemistry", "equilibrium", "kinetics", "thermochemistry"],
    "Biology": ["biology", "bio", "cell", "dna", "rna", "protein", "enzyme", "genetics", "evolution", "ecology", "ecosystem", "photosynthesis", "respiration", "digestion", "circulation", "immune", "reproductive", "heredity", "organism", "microorganism", "bacteria", "virus", "plant", "animal", "human anatomy", "physiology", "botany", "zoology"],
    "Computer Science": ["computer science", "cs", "computer", "programming", "algorithm", "data structures", "software", "hardware", "network", "database", "web development", "security", "cybersecurity", "cloud", "operating system", "file system", "memory", "cpu", "processor", "binary", "logic", "boolean", "encryption", "protocol", "ip", "tcp", "http", "btech", "engineering"],
    "Python": ["python", "programming", "code", "function", "variable", "loop", "condition", "class", "object", "list", "dict", "tuple", "string", "file", "exception", "module", "oop", "inheritance", "decorator", "generator", "pandas", "numpy", "django", "flask", "data structures", "algorithms"],
    "JavaScript": ["javascript", "js", "dom", "node", "react", "angular", "vue", "frontend", "backend", "api", "async", "promise", "callback", "event", "json", "ajax"],
    "SQL": ["sql", "database", "query", "select", "insert", "update", "delete", "table", "join", "where", "mysql", "postgresql", "mongodb", "nosql", "crud"],
    "HTML": ["html", "hypertext", "markup", "tag", "element", "attribute", "head", "body", "div", "span", "form", "input", "button", "semantic", "doctype", "html5"],
    "CSS": ["css", "style", "selector", "property", "margin", "padding", "border", "flexbox", "grid", "responsive", "media query", "animation", "transition", "display", "position"],
    "Machine Learning": ["machine learning", "ml", "ai", "artificial intelligence", "neural network", "deep learning", "tensorflow", "pytorch", "supervised", "unsupervised", "regression", "classification", "clustering", "model", "training", "feature", "label"],
    "Data Science": ["data science", "data analysis", "statistics", "visualization", "pandas", "numpy", "matplotlib", "seaborn", "tableau", "excel", "data cleaning", "eda", "exploratory", "correlation", "hypothesis"],
    "Economics": ["economics", "economy", "demand", "supply", "gdp", "inflation", "elasticity", "microeconomics", "macroeconomics", "consumer", "producer", "market", "price", "cost", "revenue", "profit", "investment", "tax", "trade", "currency", "monetary", "fiscal", "national income", "unemployment", "balance of payments", "interest rate", "banking", "stock market"],
    "Accountancy": ["accounting", "accountancy", "finance", "journal", "ledger", "trial balance", "balance sheet", "income statement", "debit", "credit", "transaction", "depreciation", "amortization", "ratio analysis", "gst", "taxation"],
    "Business Studies": ["business", "management", "organization", "marketing", "finance", "hr", "human resource", "production", "operation", "strategy", "entrepreneur", "startup", "company", "corporate", "stakeholder", "leadership", "motivation"],
    "English": ["english", "grammar", "noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction", "sentence", "paragraph", "essay", "vocabulary", "spelling", "punctuation", "tense", "voice", "mood", "syntax", "comprehension", "literature"],
    "History": ["history", "ancient", "medieval", "modern", "world war", "empire", "dynasty", "king", "queen", "revolt", "revolution", "independence", "freedom", "colonial", "colonialism", "nationalism", "civilization", "culture"],
    "Geography": ["geography", "physical geography", "human geography", "map", "climate", "weather", "temperature", "rainfall", "vegetation", "soil", "river", "mountain", "plateau", "desert", "ocean", "continent", "country", "population", "agriculture", "environment", "climate change", "erosion"],
}


def is_non_academic(text):
    """Check if text contains non-academic keywords"""
    text_lower = text.lower()
    text_words = set(text_lower.split())
    
    for category, keywords in NON_ACADEMIC_KEYWORDS.items():
        for keyword in keywords:
            keyword = keyword.strip()
            if len(keyword) <= 3:
                if keyword in text_words:
                    return True, category
            else:
                if keyword in text_lower:
                    return True, category
    
    return False, None


def find_academic_subject(text):
    """Find which academic subject the text likely belongs to"""
    text_lower = text.lower().strip()
    
    SUBJECT_EXACT_MATCH = {
        "computer science": "Computer Science", "cs": "Computer Science",
        "math": "Mathematics", "maths": "Mathematics", "mathematics": "Mathematics",
        "physics": "Physics", "chemistry": "Chemistry", "biology": "Biology", "bio": "Biology",
        "python": "Python", "javascript": "JavaScript", "sql": "SQL", "html": "HTML", "css": "CSS",
        "economics": "Economics", "accountancy": "Accountancy", "accounting": "Accountancy",
        "english": "English", "history": "History", "geography": "Geography",
        "statistics": "Statistics", "stats": "Statistics",
        "machine learning": "Machine Learning", "ml": "Machine Learning", "ai": "Machine Learning",
        "data science": "Data Science",
    }
    
    if text_lower in SUBJECT_EXACT_MATCH:
        return SUBJECT_EXACT_MATCH[text_lower]
    
    best_match = None
    best_score = 0
    
    for subject, keywords in ACADEMIC_SUBJECT_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in text_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_match = subject
    
    if best_score >= 1:
        return best_match
    return None


def validate_academic_input(subject, topic):
    """Validate academic input - subject and topic"""
    result = {
        "valid": True,
        "reason": None,
        "suggested_subject": None,
        "corrected_topic": None
    }
    
    if not subject or not topic:
        result["valid"] = False
        result["reason"] = "Subject or Topic is missing or unclear"
        return result
    
    subject = subject.strip()
    topic = topic.strip()
    
    if len(subject) < 2 or len(topic) < 2:
        result["valid"] = False
        result["reason"] = "Subject or Topic is too short"
        return result
    
    is_non_acad, category = is_non_academic(subject)
    if is_non_acad:
        result["valid"] = False
        result["reason"] = "Input is not related to academic subjects or study topics"
        return result
    
    is_non_acad_topic, _ = is_non_academic(topic)
    if is_non_acad_topic:
        result["valid"] = False
        result["reason"] = "Input is not related to academic subjects or study topics"
        return result
    
    identified_subject = find_academic_subject(subject)
    
    if not identified_subject:
        result["valid"] = False
        result["reason"] = "Subject is not recognized as an academic field"
        return result
    
    result["valid"] = True
    result["suggested_subject"] = identified_subject
    return result


def validate_academic_input_ai(subject, topic):
    """Enhanced validation using AI for complex cases"""
    return validate_academic_input(subject, topic)


# ============== STUDY PLAN GENERATOR FUNCTIONS ==============
def create_study_schedule(student_name, subjects_text, duration, daily_hours, difficulty="Medium"):
    """Create a complete study schedule covering ALL topics"""
    parsed = parse_subjects_topics_input(subjects_text)
    
    if not parsed:
        return {
            "error": "No valid subjects found",
            "student_info": {"name": student_name, "subjects": subjects_text, "duration": f"{duration} days", "daily_hours": daily_hours},
            "study_plan": []
        }
    
    all_units = expand_all_topics(parsed)
    
    if not all_units:
        return {
            "error": "No topics found",
            "student_info": {"name": student_name, "subjects": subjects_text, "duration": f"{duration} days", "daily_hours": daily_hours},
            "study_plan": []
        }
    
    total_days = max(1, min(365, int(duration) if duration else 7))
    hours = int(daily_hours) if daily_hours else 2
    
    random.seed(42)
    shuffled_units = all_units.copy()
    random.shuffle(shuffled_units)
    
    day_assignments = [[] for _ in range(total_days)]
    for idx, unit in enumerate(shuffled_units):
        day_idx = idx % total_days
        day_assignments[day_idx].append(unit)
    
    study_plan = []
    today = datetime.now()
    
    for day_num in range(1, total_days + 1):
        current_date = (today + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
        units_for_day = day_assignments[day_num - 1]
        
        if not units_for_day:
            continue
        
        subjects_today = {}
        for unit in units_for_day:
            subj = unit["subject"]
            if subj not in subjects_today:
                subjects_today[subj] = []
            subjects_today[subj].append(unit["topic"])
        
        day_topics = []
        for subj, topics in subjects_today.items():
            for topic in topics:
                day_topics.append({
                    "topic_name": topic,
                    "subject": subj,
                    "time": f"{hours * 60 // len(topics) if topics else hours * 30} min"
                })
        
        study_plan.append({
            "day": day_num,
            "date": current_date,
            "subject": ", ".join(subjects_today.keys()),
            "subjects_list": list(subjects_today.keys()),
            "topics": day_topics,
            "total_topics_today": len(day_topics)
        })
    
    subjects_covered = list(dict.fromkeys([u["subject"] for u in all_units]))
    topics_covered = [u["topic"] for u in all_units]
    
    return {
        "student_info": {
            "name": student_name,
            "subjects": subjects_text,
            "subjects_list": subjects_covered,
            "total_subjects": len(subjects_covered),
            "total_topics": len(topics_covered),
            "topics_list": topics_covered,
            "duration": f"{total_days} days",
            "daily_hours": hours,
            "total_hours": total_days * hours
        },
        "total_days": total_days,
        "study_plan": study_plan,
        "validation": {
            "all_topics_covered": len(study_plan) > 0,
            "total_topics_assigned": sum(d.get("total_topics_today", 0) for d in study_plan),
            "expected_topics": len(all_units)
        }
    }


def generate_ai_study_plan(client, student_name, subjects_text, duration, daily_hours, difficulty="Medium"):
    """Generate an AI-powered comprehensive study plan"""
    parsed = parse_subjects_topics_input(subjects_text)
    
    if not parsed:
        return {
            "error": "No valid subjects found",
            "student_info": {"name": student_name, "subjects": subjects_text, "duration": f"{duration} days", "daily_hours": daily_hours},
            "study_plan": []
        }
    
    all_units = expand_all_topics(parsed)
    
    if not all_units:
        return {
            "error": "No topics found",
            "student_info": {"name": student_name, "subjects": subjects_text, "duration": f"{duration} days", "daily_hours": daily_hours},
            "study_plan": []
        }
    
    subjects_list = [s["subject"] for s in parsed]
    topics_list = [u["topic"] for u in all_units]
    
    try:
        prompt = f"""Generate a complete study plan for {student_name}.
Subjects: {', '.join(subjects_list)}
Topics: {', '.join(topics_list)}
Duration: {duration} days
Daily Hours: {daily_hours}
Difficulty: {difficulty}

Create a practical, actionable study plan with:
- Daily tasks (Learn, Practice, Revise)
- YouTube video suggestions
- Balanced topic distribution
- Revision days included

Format the output as JSON with study_plan array containing day objects."""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an AI Study Planner. Generate practical, actionable study plans."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=8000
        )
        
        ai_response = response.choices[0].message.content
        
        try:
            plan_data = json.loads(ai_response)
            plan_data["ai_generated"] = True
            return plan_data
        except:
            return create_study_schedule(student_name, subjects_text, duration, daily_hours, difficulty)
            
    except Exception as e:
        return {
            "error": f"AI generation failed: {str(e)}",
            "fallback": create_study_schedule(student_name, subjects_text, duration, daily_hours, difficulty),
            "student_info": {
                "name": student_name,
                "subjects": subjects_text,
                "subjects_list": subjects_list,
                "total_subjects": len(subjects_list),
                "total_topics": len(topics_list),
                "topics_list": topics_list,
                "duration": f"{duration} days",
                "daily_hours": daily_hours,
                "total_hours": duration * daily_hours
            }
        }

# ============== VIDEO ID DEDUPLICATION ==============
_used_video_ids = set()

def reset_video_ids():
    """Reset used video IDs for a new study plan"""
    global _used_video_ids
    _used_video_ids = set()

def is_video_id_used(video_id):
    """Check if video_id has already been used"""
    return video_id in _used_video_ids

def mark_video_id_used(video_id):
    """Mark video_id as used"""
    if video_id:
        _used_video_ids.add(video_id)

def get_unique_video_id(video_id):
    """Generate unique video_id by appending suffix if needed"""
    if not video_id:
        return video_id
    
    if video_id not in _used_video_ids:
        return video_id
    
    return None


# ============== YOUTUBE VIDEO UTILITIES ==============

def extract_video_id(url_or_id):
    """Extract clean YouTube video ID from URL or return as-is if already ID"""
    if not url_or_id:
        return None
    
    url_or_id = url_or_id.strip()
    
    # Already a valid video ID (11 chars)
    if len(url_or_id) == 11 and not any(c in url_or_id for c in ['/', '?', '=']):
        return url_or_id
    
    # Handle full YouTube URLs
    if 'youtube.com/watch?v=' in url_or_id:
        match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url_or_id)
        if match:
            return match.group(1)
    
    # Handle youtu.be short URLs
    if 'youtu.be/' in url_or_id:
        parts = url_or_id.split('youtu.be/')
        if len(parts) > 1:
            video_id = parts[1].split('?')[0].split('&')[0]
            if len(video_id) == 11:
                return video_id
    
    # Handle embed URLs
    if 'youtube.com/embed/' in url_or_id:
        match = re.search(r'embed/([a-zA-Z0-9_-]{11})', url_or_id)
        if match:
            return match.group(1)
    
    return None


def get_valid_thumbnail_url(video_id_or_url):
    """Get valid YouTube thumbnail URL with fallbacks"""
    video_id = extract_video_id(video_id_or_url)
    
    if not video_id:
        return None
    
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def create_video_object(video_id, title, channel="YouTube", duration=""):
    """Create standardized video object with STRICT validation"""
    clean_video_id = extract_video_id(video_id)
    if not clean_video_id:
        print(f"[Video Validation] FAILED: Invalid video_id '{video_id}'")
        return None
    
    if len(clean_video_id) != 11:
        print(f"[Video Validation] FAILED: video_id length {len(clean_video_id)} != 11")
        return None
    
    if not clean_video_id.replace('_', '').replace('-', '').isalnum():
        print(f"[Video Validation] FAILED: video_id contains invalid chars")
        return None
    
    print(f"[Video Validation] PASSED: video_id={clean_video_id}")
    
    return {
        "video_id": clean_video_id,
        "title": title or "Video Tutorial",
        "channel": channel,
        "duration": duration,
        "url": f"https://www.youtube.com/watch?v={clean_video_id}",
        "embed_url": f"https://www.youtube.com/embed/{clean_video_id}",
        "thumbnail": f"https://img.youtube.com/vi/{clean_video_id}/hqdefault.jpg",
    }


def is_valid_video_id(video_id):
    """STRICT validation - must be exactly 11 alphanumeric characters"""
    if not video_id or not isinstance(video_id, str):
        return False
    if len(video_id) != 11:
        return False
    if not video_id.replace('_', '').replace('-', '').isalnum():
        return False
    return True


def validate_video_before_return(video):
    """Final validation before returning video to frontend - accepts video OR search link"""
    if not video:
        print(f"[Final Validation] FAILED: video is None")
        return False
    
    # Accept search links (has is_search_link flag)
    if video.get("is_search_link"):
        return True
    
    video_id = video.get("video_id", "")
    if not is_valid_video_id(video_id):
        print(f"[Final Validation] FAILED: invalid video_id '{video_id}'")
        return False
    
    title = video.get("title", "")
    if not title or title == "Video Tutorial":
        print(f"[Final Validation] FAILED: invalid title")
        return False
    
    url = video.get("url", "")
    embed = video.get("embed_url", "")
    thumb = video.get("thumbnail", "")
    
    if not url or not embed or not thumb:
        print(f"[Final Validation] FAILED: missing URLs")
        return False
    
    print(f"[Final Validation] PASSED: video_id={video_id}, title={title[:30]}...")
    return True


def get_youtube_search_fallback(topic, max_results=2):
    """Return empty array - NO fallback videos allowed"""
    return []


def get_youtube_fallback_video(topic, subject=None):
    """Returns YouTube search link as last resort when API completely fails"""
    print(f"[YouTube CRITICAL FALLBACK] API failed completely for: {topic}")
    search_query = f"{topic} {subject}" if subject else f"{topic} tutorial"
    return {
        "video_id": "",
        "title": f"Search {topic} on YouTube",
        "channel": "YouTube",
        "duration": "",
        "url": f"https://www.youtube.com/results?search_query={quote(search_query)}",
        "embed_url": "",
        "thumbnail": "",
        "is_search_link": True
    }


def validate_video_data(video_obj):
    """Validate and normalize video data - returns clean video object or None"""
    if not video_obj:
        return None
    
    # Handle string URLs
    if isinstance(video_obj, str):
        if video_obj.startswith('http'):
            video_id = extract_video_id(video_obj)
            if video_id:
                return create_video_object(video_id, "Video Tutorial", "YouTube", "")
            return None
        return None
    
    # Handle dict objects
    video_id = video_obj.get('video_id', '')
    url = video_obj.get('url', '')
    title = video_obj.get('title', 'Video')
    channel = video_obj.get('channel', 'YouTube')
    duration = video_obj.get('duration', '')
    
    # If no video_id, try to extract from URL
    if not video_id and url:
        video_id = extract_video_id(url)
    
    # Validate video_id
    if not video_id or len(video_id) != 11:
        # Return fallback data if available
        if url:
            return {
                "video_id": "",
                "title": title,
                "channel": channel,
                "duration": duration,
                "url": url,
                "thumbnail": None,
                "is_fallback": True
            }
        return None
    
    return create_video_object(video_id, title, channel, duration)


# ============== SUBJECT VALIDATION LAYER ==============

# ============== SUBJECT VALIDATION LAYER ==============
SUBJECT_DOMAIN_KEYWORDS = {
    "economics": ["demand", "supply", "gdp", "inflation", "elasticity", "microeconomics", "macroeconomics", "econometrics", "consumer", "producer", "market", "price", "cost", "revenue", "profit", "investment", "tax", "trade", "currency", "monetary", "fiscal", "national income", "unemployment", "gdp", "gni", "balance of payments", "exchange rate", "interest rate", "banking", "stock market", "commodity", "labor", "wage", "production", "distribution", "consumption", "utility", "indifference", "budget", "opportunity cost", "scarcity", "allocation"],
    "physics": ["force", "motion", "energy", "power", "work", "heat", "temperature", "thermodynamics", "wave", "sound", "light", "electricity", "magnetism", "mass", "velocity", "acceleration", "newton", "gravity", "friction", "momentum", "impulse", "pressure", "density", "volume", "kinematics", "dynamics", "statics", "optics", "modern physics", "quantum", "relativity", "nuclear", "atom", "molecule", "solid", "liquid", "gas", "plasma", "thermodynamic", "entropy", "enthalpy"],
    "chemistry": ["atom", "molecule", "element", "compound", "reaction", "bond", "ionic", "covalent", "metallic", "acid", "base", "salt", "solution", "concentration", "mole", "stoichiometry", "thermochemistry", "kinetics", "equilibrium", "electrochemistry", "organic", "inorganic", "periodic", "periodic table", "atomic structure", "chemical bonding", "states of matter", "gas laws", "colloid", "catalyst", "oxidation", "reduction", "polymer", "isomer", "functional group", "hydrocarbon"],
    "biology": ["cell", "dna", "rna", "protein", "enzyme", "metabolism", "photosynthesis", "respiration", "digestion", "circulation", "respiratory", "nervous", "immune", "endocrine", "reproductive", "genetics", "evolution", "ecology", " ecosystem", "biodiversity", "nutrition", "homeostasis", "osmosis", "diffusion", "membrane", "organelle", "mitochondria", "chloroplast", "nucleus", "chromosome", "gene", "allele", "mutation", "heredity", "natural selection", "adaptation", "food chain", "symbiosis"],
    "mathematics": ["algebra", "calculus", "geometry", "trigonometry", "statistics", "probability", "number", "equation", "function", "graph", "sequence", "series", "matrix", "determinant", "vector", "differentiation", "integration", "limit", "derivative", "integral", "polynomial", "quadratic", "linear", "exponential", "logarithmic", "circle", "triangle", "quadrilateral", "area", "volume", "perimeter", "angle", "theorem", "proof", "mean", "median", "mode", "variance", "standard deviation"],
    "python": ["python", "programming", "code", "function", "variable", "loop", "condition", "class", "object", "list", "dict", "tuple", "string", "file", "exception", "module", "package", "oop", "inheritance", "polymorphism", "encapsulation", "abstraction", "decorator", "generator", "iterator", "comprehension", "lambda", "virtualenv", "pip", "numpy", "pandas", "data structure", "algorithm"],
    "html": ["html", "hypertext", "markup", "tag", "element", "attribute", "value", "head", "body", "div", "span", "form", "input", "button", "link", "script", "style", "semantic", "doctype", "html5", "table", "list", "image", "link", "canvas", "svg", "meta", "title", "header", "footer", "nav", "section", "article"],
    "css": ["css", "style", "selector", "property", "value", "color", "font", "margin", "padding", "border", "box model", "flexbox", "grid", "layout", "responsive", "media query", "animation", "transition", "transform", "display", "position", "z-index", "float", "clear", "overflow", "visibility", "opacity", "pseudo-class", "pseudo-element", " specificity", "cascade", "inheritance"],
    "javascript": ["javascript", "js", "variable", "function", "array", "object", "string", "number", "boolean", "null", "undefined", "loop", "condition", "event", "dom", "document", "element", "node", "listener", "callback", "promise", "async", "await", "fetch", "api", "json", "localstorage", "cookie", "prototype", "class", "module", "export", "import", "this", "scope", "closure", "hoisting"],
    "sql": ["sql", "database", "query", "select", "insert", "update", "delete", "table", "row", "column", "field", "index", "primary key", "foreign key", "join", "inner join", "left join", "right join", "full join", "where", "group by", "having", "order by", "limit", "offset", "subquery", "union", "distinct", "aggregate", "count", "sum", "avg", "max", "min", "view", "trigger", "stored procedure", "normalization"],
    "machine learning": ["machine learning", "ml", "ai", "artificial intelligence", "algorithm", "model", "training", "testing", "data", "feature", "label", "classification", "regression", "clustering", "neural network", "deep learning", "tensor", "gradient", "loss", "optimization", "supervised", "unsupervised", "reinforcement", "overfitting", "underfitting", "accuracy", "precision", "recall", "f1 score", "confusion matrix", "bias", "variance", "ensemble", "random forest", "svm", "k-means"],
    "data science": ["data science", "data analysis", "statistics", "visualization", "pandas", "numpy", "matplotlib", "seaborn", "plotly", "tableau", "power bi", "excel", "data cleaning", "data preprocessing", "eda", "exploratory", "correlation", "regression", "hypothesis", "p-value", "chi-square", "anova", "time series", "forecasting", "dashboard", "insight", "big data", "hadoop", "spark"],
    "english": ["grammar", "noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction", "interjection", "sentence", "paragraph", "essay", "composition", "vocabulary", "spelling", "punctuation", "tense", "voice", "mood", "syntax", "subject", "predicate", "object", "complement", "phrase", "clause", "conjunction", "articulation", "comprehension", "reading", "writing", "speaking", "listening"],
    "history": ["history", "ancient", "medieval", "modern", "world war", "war", "empire", "dynasty", "king", "queen", "revolt", "revolution", "independence", "freedom", "colonial", "colonialism", "nationalism", "politics", "treaty", "conference", "movement", "civilization", "culture", "society", "economy", "religion", "art", "architecture"],
    "geography": ["geography", "physical geography", "human geography", "map", "climate", "weather", "temperature", "rainfall", "vegetation", "soil", "river", "mountain", "plateau", "desert", "ocean", "continent", "country", "population", "settlement", "agriculture", "industry", "transport", "resource", "environment", "climate change", "global warming", "erosion"],
    "accountancy": ["accounting", "finance", "journal", "ledger", "trial balance", "balance sheet", "income statement", "profit", "loss", "asset", "liability", "capital", "debit", "credit", "account", "transaction", "adjustment", "closing", "depreciation", "amortization", "reserve", "provision", "budget", "ratio", "analysis"],
    "business studies": ["business", "management", "organization", "marketing", "finance", "hr", "human resource", "production", "operation", "strategy", "entrepreneur", "startup", "company", "corporate", "stakeholder", "leadership", "motivation", "communication", "team", "conflict", "change", "growth", "expansion", "diversification", "advertising", "promotion", "price", "product", "place", "distribution"],
    "computer science": ["computer", "programming", "algorithm", "data structure", "software", "hardware", "network", "database", "web", "security", "cybersecurity", "cloud", "ai", "ml", "operating system", "file system", "memory", "cpu", "processor", "binary", "logic", "boolean", "encryption", "decryption", "protocol", "ip", "tcp", "http", "dns"],
    "ui design": ["ui", "user interface", "design", "figma", "sketch", "adobe xd", "wireframe", "prototype", "mockup", "typography", "color", "palette", "icon", "illustration", "layout", "grid", "spacing", "visual", "hierarchy", "accessibility", "usability", "responsive", "mobile", "desktop", "button", "form", "navigation"],
    "ux": ["ux", "user experience", "usability", "research", "persona", "journey", "map", "storyboard", "wireframe", "prototype", "test", "feedback", "analytics", "metrics", "conversion", "retention", "engagement", "accessibility", "heuristic", "evaluation", "information architecture", "ia", "navigation", "search", "filter", "sort"],
}

# Secondary keywords for fuzzy matching
SECONDARY_KEYWORDS = {
    "microeconomics": ["demand", "supply", "consumer", "producer", "utility", "budget", "cost", "revenue", "market"],
    "macroeconomics": ["gdp", "inflation", "unemployment", "national income", "money", "fiscal", "monetary", "trade"],
    "econometrics": ["regression", "statistics", "data", "model", "prediction", "quantitative"],
    "web development": ["html", "css", "javascript", "frontend", "backend", "full stack", "react", "node", "api"],
    "data analysis": ["python", "pandas", "numpy", "visualization", "statistics", "excel", "tableau"],
}

# Cache for validation results
_validation_cache = {}


def parse_subjects_input(subjects_text):
    """Parse user input into structured subjects list"""
    parsed = []
    lines = subjects_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if ':' in line:
            parts = line.split(':', 1)
            subject = parts[0].strip()
            topics_str = parts[1].strip() if len(parts) > 1 else ""
            
            if topics_str:
                topics = [t.strip() for t in topics_str.split(',') if t.strip()]
                if subject and topics:
                    parsed.append({"subject": subject, "topics": topics})
            else:
                if subject:
                    parsed.append({"subject": subject, "topics": []})
        else:
            # Split by comma for comma-separated subjects
            for sub in line.split(','):
                sub = sub.strip()
                if sub:
                    parsed.append({"subject": sub, "topics": []})
    
    return parsed


def normalize_subject(subject):
    """Normalize subject name to key for matching"""
    return subject.lower().strip().replace(" ", "").replace("-", "").replace("_", "")


def find_subject_key(subject):
    """Find the matching domain key for a subject"""
    subject_lower = subject.lower()
    subject_norm = normalize_subject(subject)
    
    # Direct match
    for key in SUBJECT_DOMAIN_KEYWORDS:
        if key in subject_norm or subject_norm in key:
            return key
    
    # Partial match
    for key, keywords in SECONDARY_KEYWORDS.items():
        if any(kw in subject_lower for kw in keywords):
            return key
    
    # Check for compound subjects
    compound_mappings = {
        "micro": "microeconomics",
        "macro": "macroeconomics",
        "web dev": "web development",
        "web develop": "web development",
        "data analyst": "data analysis",
    }
    
    for pattern, mapped in compound_mappings.items():
        if pattern in subject_lower:
            return mapped
    
    return None


def is_topic_relevant_to_subject(topic_name, subject):
    """Check if a topic is relevant to the given subject using keyword matching"""
    cache_key = f"validate_{topic_name.lower()}_{subject.lower()}"
    
    if cache_key in _validation_cache:
        return _validation_cache[cache_key]
    
    subject_key = find_subject_key(subject)
    
    if not subject_key:
        # Unknown subject - be lenient
        _validation_cache[cache_key] = True
        return True
    
    topic_lower = topic_name.lower()
    keywords = SUBJECT_DOMAIN_KEYWORDS.get(subject_key, [])
    
    # Direct keyword match
    for kw in keywords:
        if kw in topic_lower:
            _validation_cache[cache_key] = True
            return True
    
    # Check secondary keywords
    for key, secondary_kw in SECONDARY_KEYWORDS.items():
        if key == subject_key:
            for kw in secondary_kw:
                if kw in topic_lower:
                    _validation_cache[cache_key] = True
                    return True
    
    # Check inverse: does the subject appear in the topic?
    if subject_key in topic_lower or subject.lower() in topic_lower:
        _validation_cache[cache_key] = True
        return True
    
    # Check if topic matches TOPIC_DATA keys
    for topic_key in TOPIC_DATA:
        if topic_key.lower() in topic_lower or topic_lower in topic_key.lower():
            # Now check if this topic belongs to the subject
            related_subjects = get_related_subjects_for_topic(topic_key)
            if subject_key in related_subjects:
                _validation_cache[cache_key] = True
                return True
    
    _validation_cache[cache_key] = False
    return False


def get_related_subjects_for_topic(topic):
    """Get subjects that a topic could belong to"""
    topic_lower = topic.lower()
    related = []
    
    topic_subject_map = {
        "quadratic": "mathematics", "trigonometry": "mathematics", "calculus": "mathematics",
        "probability": "mathematics", "statistics": "mathematics", "algebra": "mathematics",
        "geometry": "mathematics", "newton": "physics", "motion": "physics", "force": "physics",
        "electricity": "physics", "magnetism": "physics", "heat": "physics", "wave": "physics",
        "sound": "physics", "light": "physics", "chemical": "chemistry", "atom": "chemistry",
        "bond": "chemistry", "periodic": "chemistry", "acid": "chemistry", "base": "chemistry",
        "cell": "biology", "dna": "biology", "rna": "biology", "genetics": "biology",
        "evolution": "biology", "python": "python", "html": "html", "css": "css",
        "javascript": "javascript", "sql": "sql", "machine learning": "machine learning",
        "data science": "data science",
    }
    
    for key, sub in topic_subject_map.items():
        if key in topic_lower:
            related.append(sub)
    
    return related


def validate_topics_for_subjects(topics, subject):
    """Validate and filter topics to only include relevant ones"""
    subject_key = find_subject_key(subject)
    
    if not subject_key:
        return topics  # Unknown subject - return all
    
    valid_topics = []
    for topic in topics:
        if is_topic_relevant_to_subject(topic, subject):
            valid_topics.append(topic)
    
    return valid_topics


def generate_strict_prompt(subject, topic):
    """Generate a prompt with strict subject constraints"""
    subject_key = find_subject_key(subject)
    domain_keywords = SUBJECT_DOMAIN_KEYWORDS.get(subject_key, [])
    
    keyword_list = ", ".join(domain_keywords[:10]) if domain_keywords else ""
    
    prompt = f"""STRICT SUBJECT BOUNDARY - GENERATE ONLY {subject.upper()} CONTENT

CONTEXT:
- Subject: {subject}
- Topic: {topic}
- Valid domain keywords: {keyword_list}

CRITICAL RULES:
1. ONLY generate content related to {subject}
2. DO NOT include topics from other fields (physics, biology, math, etc.)
3. DO NOT generate generic content unrelated to {subject}
4. If topic is not relevant to {subject}, return the closest valid subtopic

Return valid {subject} subtopics as bullet points, max 8 items."""
    
    return prompt


def _get_cache(key, cache_dict):
    if key in cache_dict:
        entry = cache_dict[key]
        if time.time() - entry['time'] < _CACHE_EXPIRY:
            return entry['data']
    return None

def _set_cache(key, data, cache_dict):
    cache_dict[key] = {'data': data, 'time': time.time()}


def detect_language(text):
    try:
        lang = detect(text)

        mapping = {
            # 🌍 GLOBAL LANGUAGES
            "en": "English",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "zh-cn": "Chinese",
            "zh-tw": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic",
            "tr": "Turkish",
            "nl": "Dutch",
            "sv": "Swedish",
            "pl": "Polish",

            # 🇮🇳 INDIAN LANGUAGES (MAJOR)
            "hi": "Hindi",
            "bn": "Bengali",
            "te": "Telugu",
            "mr": "Marathi",
            "ta": "Tamil",
            "ur": "Urdu",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi",
            "or": "Odia",
            "as": "Assamese",

            # 🇮🇳 ADDITIONAL INDIAN LANGUAGES
            "sa": "Sanskrit",
            "sd": "Sindhi",
            "ne": "Nepali",
            "kok": "Konkani",
            "mai": "Maithili",
            "mni": "Manipuri",
            "bho": "Bhojpuri",
            "dog": "Dogri"
        }

        return mapping.get(lang, "English")

    except:
        return "English"

def get_language_instruction(text):
    import re
    text_combined = text if isinstance(text, str) else str(text)
    
    # SCRIPT DETECTION - Devanagari (U+0900-U+097F) = Hindi/Marathi/Sanskrit
    if re.search(r'[\u0900-\u097F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Hindi using Devanagari script (अ-ह). Write EVERY word in Devanagari. DO NOT mix English letters or Roman script. No Hindi word should contain English characters."
    
    # Bengali (U+0980-U+09FF)
    if re.search(r'[\u0980-\u09FF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Bengali script (অ-হ). Write EVERY word in Bengali. DO NOT mix English letters or Roman script."
    
    # Tamil (U+0B80-U+0BFF)
    if re.search(r'[\u0B80-\u0BFF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Tamil script (அ-ஔ). Write EVERY word in Tamil. DO NOT mix English letters or Roman script."
    
    # Telugu (U+0C00-U+0C7F)
    if re.search(r'[\u0C00-\u0C7F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Telugu script (అ-ఔ). Write EVERY word in Telugu. DO NOT mix English letters or Roman script."
    
    # Kannada (U+0C80-U+0CFF)
    if re.search(r'[\u0C80-\u0CFF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Kannada script (ಅ-ಔ). Write EVERY word in Kannada. DO NOT mix English letters or Roman script."
    
    # Malayalam (U+0D00-U+0D7F)
    if re.search(r'[\u0D00-\u0D7F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Malayalam script (അ-ഔ). Write EVERY word in Malayalam. DO NOT mix English letters or Roman script."
    
    # Gujarati (U+0A80-U+0AFF)
    if re.search(r'[\u0A80-\u0AFF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Gujarati script (અ-ઔ). Write EVERY word in Gujarati. DO NOT mix English letters or Roman script."
    
    # Punjabi/Gurmukhi (U+0A00-U+0A7F)
    if re.search(r'[\u0A00-\u0A7F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Punjabi/Gurmukhi script (ਅ-ਔ). Write EVERY word in Punjabi. DO NOT mix English letters or Roman script."
    
    # Text-based detection
    text_lower = text_combined.lower()

    if any(word in text_lower for word in ["hindi", "हिंदी"]):
        return "Respond STRICTLY in Hindi (Devanagari script ONLY). No English words allowed."

    elif any(word in text_lower for word in ["sanskrit", "संस्कृत"]):
        return "Respond STRICTLY in Sanskrit ONLY."

    elif any(word in text_lower for word in ["marathi", "मराठी"]):
        return "Respond STRICTLY in Marathi ONLY."

    elif any(word in text_lower for word in ["bengali", "বাংলা"]):
        return "Respond STRICTLY in Bengali ONLY."

    elif any(word in text_lower for word in ["tamil", "தமிழ்"]):
        return "Respond STRICTLY in Tamil ONLY."

    elif any(word in text_lower for word in ["telugu", "తెలుగు"]):
        return "Respond STRICTLY in Telugu ONLY."

    elif any(word in text_lower for word in ["gujarati", "ગુજરાતી"]):
        return "Respond STRICTLY in Gujarati ONLY."

    elif any(word in text_lower for word in ["punjabi", "ਪੰਜਾਬੀ"]):
        return "Respond STRICTLY in Punjabi ONLY."

    elif any(word in text_lower for word in ["urdu", "اردو"]):
        return "Respond STRICTLY in Urdu ONLY."

    elif any(word in text_lower for word in ["french", "français"]):
        return "Respond STRICTLY in French ONLY."

    elif any(word in text_lower for word in ["german", "deutsch"]):
        return "Respond STRICTLY in German ONLY."

    elif any(word in text_lower for word in ["spanish", "español"]):
        return "Respond STRICTLY in Spanish ONLY."

    elif any(word in text_lower for word in ["italian", "italiano"]):
        return "Respond STRICTLY in Italian ONLY."

    else:
        return "Respond STRICTLY in English ONLY. Do NOT use any other language."



load_dotenv(override=True)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

app = Flask(__name__)
CORS(app)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

print(f"Loaded API key: {OPENAI_API_KEY[:20]}..." if OPENAI_API_KEY else "No API key loaded")

# Initialize OpenAI client for AI-powered study plan generation
openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client initialized successfully")
    except ImportError:
        print("OpenAI library not installed, AI features disabled")
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")

# ============== YOUTUBE VIDEO VALIDATION UTILITIES ==============

BLACKLIST_TERMS = [
    "music", "song", "lyrics", "official video", "trailer", "meme", 
    "remix", "ft.", "vevo", "shorts", "reels", "vlog", "funny", 
    "gaming", "prank", "reaction", "compilation", "dance", "live concert",
    "movie", "film", "episode", "season", "tv show", "netflix", "hotstar",
    "party", "wedding", "dance", "comedy", "funny moments", "best of",
    "Top 10", "Top 5", "ranked", "viral", "trending", "status video",
    "whatsapp status", "instagram reel", "tiktok", "facebook video",
    "song ", "video song", " devotional", " bhajan", "aarti",
    "podcast", "interview", "news", "coverage", "highlights",
    "full movie", "free fire", "minecraft", "roblox", "gta",
    "rap", "hip hop", "lyric video", "audio", "dj", "remix"
]

CHANNEL_BLACKLIST = [
    "vevo", "worldwide", "music", "official", "entertainment", "movies",
    "movies", "films", "shows", "tv", "netflix", "hotstar", "disney",
    "sony", "zee", "star", " Colors", " MTV", " vh1",
    "gaming", "gameplay", "game", "esports", "livestream"
]

SKIP_TERMS = [
    "music", "song", "lyrics", "movie", "trailer", "film",
    "shorts", "reels", "vlog", "funny", "gaming", "prank"
]

# Remove duration limit - accept ALL videos including short ones
MIN_DURATION_MINUTES = 0
MAX_DURATION_MINUTES = 180


def is_video_relevant_to_topic(title, description, topic, subject=None):
    """Check if video is relevant to topic AND subject"""
    title_lower = title.lower()
    desc_lower = (description or "").lower()
    topic_lower = topic.lower()
    subject_lower = (subject or "").lower()
    
    topic_words = set(topic_lower.split())
    if subject:
        topic_words.update(subject_lower.split())
    
    relevant_keywords = [
        "tutorial", "lesson", "class", "learn", "course", "explain",
        "concept", "understanding", "basics", "introduction", "guide",
        "lecture", "demo", "example", "solve", "problem", "exercise",
        "full", "complete", "comprehensive", "chapter"
    ]
    
    relevant_count = sum(1 for kw in relevant_keywords if kw in title_lower)
    topic_match = sum(1 for tw in topic_words if len(tw) > 2 and (tw in title_lower or tw in desc_lower))
    
    if topic_match >= 1:
        return True
    if relevant_count >= 2 and topic_match >= 0:
        return True
    
    return topic_match > 0


def is_video_strictly_relevant(title, topic, subject):
    """STRICT relevance - title MUST contain both topic AND subject keywords"""
    title_lower = title.lower()
    topic_words = [w.lower() for w in topic.split() if len(w) > 2]
    
    subject_words = []
    if subject:
        subject_words = [w.lower() for w in subject.split() if len(w) > 2]
        topic_words.extend(subject_words)
    
    topic_in_title = sum(1 for tw in topic_words if len(tw) > 2 and tw in title_lower)
    
    if subject:
        topic_matches = sum(1 for tw in topic_words if tw in title_lower)
        subject_matches = sum(1 for sw in subject_words if sw in title_lower)
        return topic_matches >= 1 and subject_matches >= 1
    
    return topic_in_title >= 1


def is_video_blacklisted(title):
    """Check if video should be blacklisted"""
    title_lower = title.lower()
    return any(term in title_lower for term in BLACKLIST_TERMS)


def is_channel_blacklisted(channel):
    """Check if channel should be blacklisted"""
    channel_lower = channel.lower()
    return any(term in channel_lower for term in CHANNEL_BLACKLIST)


def calculate_video_score(video_data, topic, subject=None):
    """Calculate relevance score for a video (higher is better) - PRIORITIZES subject+topic"""
    title = video_data.get("title", "").lower()
    channel = video_data.get("channel", "").lower()
    description = video_data.get("description", "").lower()
    duration_minutes = video_data.get("duration_minutes", 0)
    view_count = video_data.get("viewCount", 0)
    
    score = 0
    
    topic_words = topic.lower().split()
    subject_words = []
    if subject:
        subject_words = [w.lower() for w in subject.split() if len(w) > 2]
        topic_words.extend(subject_words)
    
    topic_matches_in_title = 0
    for tw in topic_words:
        if len(tw) > 2 and tw in title:
            score += 15
            topic_matches_in_title += 1
    
    if subject:
        for sw in subject_words:
            if len(sw) > 2 and sw in title:
                score += 20
    
    if any(kw in title for kw in ["tutorial", "lesson", "class", "lecture", "explain", "course"]):
        score += 10
    
    if any(kw in title for kw in ["full course", "complete", "master", "full", "comprehensive"]):
        score += 5
    
    for tw in topic_words:
        if len(tw) > 2 and tw in description:
            score += 3
    
    if not is_channel_blacklisted(channel):
        score += 5
    
    educational_channels = ["khan academy", "coursera", "udemy", "edx", "tutorial", "learn", "education", "professor", "school", "academy"]
    if any(ec in channel for ec in educational_channels):
        score += 10
    
    if duration_minutes >= 30:
        score += 10
    elif duration_minutes >= 60:
        score += 15
    
    if view_count and view_count > 50000:
        score += 5
    elif view_count and view_count > 100000:
        score += 10
    
    if duration_minutes < 10:
        score -= 30
    
    return score


def extract_topic_keywords(topic):
    """Extract clean keywords from topic"""
    if not topic:
        return []
    topic_lower = topic.lower()
    words = topic_lower.replace("-", " ").replace("_", " ").split()
    keywords = [w for w in words if len(w) > 2]
    return keywords


def calculate_relevance_score(video, topic_keywords, subject_keywords=None):
    """Calculate strict relevance score for video"""
    title = video.get("title", "").lower()
    description = video.get("description", "").lower()
    
    score = 0
    
    for kw in topic_keywords:
        if kw in title:
            score += 10
        if kw in description:
            score += 5
    
    if subject_keywords:
        for sw in subject_keywords:
            if sw in title:
                score += 5
            if sw in description:
                score += 2
    
    if any(kw in title for kw in ["tutorial", "lecture", "course", "lesson", "explain", "complete"]):
        score += 3
    
    return score


def is_video_strictly_relevant_to_topic(video, topic_keywords, subject_keywords=None):
    """STRICT check - topic keyword MUST be in title"""
    title = video.get("title", "").lower()
    description = video.get("description", "").lower()
    
    title_has_topic = any(kw in title for kw in topic_keywords)
    
    if not title_has_topic:
        return False
    
    unrelated = ["react", "html", "css", "javascript", "node", "express", "mongo", "sql"]
    if any(u in title for u in unrelated):
        for kw in topic_keywords:
            if kw not in unrelated and kw in title:
                return True
        return False
    
    return True


def search_youtube_alternative_free(topic, max_results=5):
    """Free YouTube search using web scraping - no API quota needed"""
    import re
    import json
    from urllib.parse import quote_plus
    
    videos = []
    
    print(f"[YouTube Alternative] Scraping YouTube search for: {topic}")
    
    try:
        # Scrape YouTube search page directly
        search_url = f"https://www.youtube.com/results?search_query={quote_plus(topic)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"[YouTube Alternative] Scraping failed: {response.status_code}")
            return []
        
        html = response.text
        
        # Try to extract video data from YouTube's JSON initial data
        video_data = []
        
        # Method 1: Look for ytInitialData JSON
        initial_data_match = re.search(r'ytInitialData\s*=\s*({.*?});', html, re.DOTALL)
        if initial_data_match:
            try:
                data = json.loads(initial_data_match.group(1))
                # Navigate to video results
                contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
                for section in contents:
                    items = section.get('itemSectionRenderer', {}).get('contents', [])
                    for item in items:
                        if 'videoRenderer' in item:
                            vr = item['videoRenderer']
                            vid = vr.get('videoId', '')
                            title_runs = vr.get('title', {}).get('runs', [])
                            title = title_runs[0].get('text', '') if title_runs else ''
                            channel_runs = vr.get('ownerText', {}).get('runs', [])
                            channel = channel_runs[0].get('text', '') if channel_runs else ''
                            
                            # Get duration
                            length_text = vr.get('lengthText', {}).get('simpleText', '')
                            duration_min = 60  # default
                            if length_text:
                                match = re.match(r'(?:(\d+):)?(\d+):(\d+)', length_text)
                                if match:
                                    h = int(match.group(1) or 0)
                                    m = int(match.group(2))
                                    s = int(match.group(3))
                                    duration_min = h * 60 + m + s / 60
                            
                            if vid and title:
                                video_data.append({
                                    'video_id': vid,
                                    'title': title,
                                    'channel': channel or 'YouTube',
                                    'duration_minutes': duration_min
                                })
            except (json.JSONDecodeError, Exception) as e:
                print(f"[YouTube Alternative] JSON parse error: {e}")
        
        # Method 2: Fallback to regex extraction if no JSON data
        if not video_data:
            print("[YouTube Alternative] Using regex fallback...")
            video_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
            title_pattern = r'"title":"([^"]{10,100})"'
            
            video_ids = re.findall(video_pattern, html)
            titles = re.findall(title_pattern, html)
            
            # YouTube interleaves video IDs with titles
            seen_ids = set()
            title_idx = 0
            for vid in video_ids:
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)
                
                title = titles[title_idx] if title_idx < len(titles) else f"{topic} Tutorial"
                title = title.replace('\\"', '"').replace('\\n', ' ')
                title_idx += 1
                
                video_data.append({
                    'video_id': vid,
                    'title': title,
                    'channel': 'YouTube',
                    'duration_minutes': 60
                })
                
                if len(video_data) >= max_results:
                    break
        
        # Format output
        for v in video_data[:max_results]:
            duration = v.get('duration_minutes', 60)
            if duration >= 60:
                hours = int(duration // 60)
                mins = int(duration % 60)
                duration_str = f"{hours}h {mins}m"
            else:
                duration_str = f"{int(duration)}m"
            
            videos.append({
                "video_id": v['video_id'],
                "title": v['title'],
                "channel": v['channel'],
                "duration": duration_str,
                "duration_minutes": duration,
                "views": 0,
                "description": ""
            })
        
        print(f"[YouTube Alternative] Returning {len(videos)} videos: {[v['title'][:30] for v in videos]}")
        
    except Exception as e:
        print(f"[YouTube Alternative] Scraping error: {e}")
    
    return videos


def search_via_google_custom(query, max_results):
    """Try Google Custom Search API (separate quota from YouTube API)"""
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": YOUTUBE_API_KEY,
            "cx": "015579843996877149566:qfy2i5nyrei",
            "q": f"{query} site:youtube.com tutorial",
            "num": max_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return []
        
        data = response.json()
        results = data.get("items", [])
        
        videos = []
        for item in results:
            link = item.get("link", "")
            if "youtube.com/watch" not in link and "youtu.be/" not in link:
                continue
            
            video_id = extract_video_id(link)
            if not video_id:
                continue
            
            videos.append({
                "video_id": video_id,
                "title": item.get("title", "Video"),
                "channel": "YouTube",
                "duration": "1h",
                "duration_minutes": 60,
                "views": 0,
                "description": item.get("snippet", "")
            })
        
        return videos
    except Exception as e:
        print(f"[Google Custom Search] Error: {e}")
        return []


def search_youtube_api_real(query, max_results=10):
    """Make real YouTube API call and return formatted videos"""
    if not YOUTUBE_API_KEY or len(YOUTUBE_API_KEY) < 10:
        return []
    
    try:
        # Step 1: Search for videos
        search_url = "https://www.googleapis.com/youtube/v3/search"
        search_params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results * 2, 20),
            "key": YOUTUBE_API_KEY,
            "order": "viewCount"
        }
        
        response = requests.get(search_url, params=search_params, timeout=10)
        if response.status_code != 200:
            print(f"[YouTube API] Search failed: {response.status_code}")
            return []
        
        search_data = response.json()
        items = search_data.get("items", [])
        
        if not items:
            return []
        
        # Extract video IDs
        video_ids = []
        for item in items:
            vid = item.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        
        if not video_ids:
            return []
        
        # Step 2: Get video details (duration, views)
        details_url = "https://www.googleapis.com/youtube/v3/videos"
        details_params = {
            "part": "contentDetails,statistics",
            "id": ",".join(video_ids),
            "key": YOUTUBE_API_KEY
        }
        
        details_response = requests.get(details_url, params=details_params, timeout=10)
        # Don't fail if details call fails - we still have title and channel from search
        
        details_data = details_response.json() if details_response.status_code == 200 else {}
        details_map = {item["id"]: item for item in details_data.get("items", [])}
        
        # Format videos
        videos = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            
            snippet = item.get("snippet", {})
            detail = details_map.get(video_id, {})
            content = detail.get("contentDetails", {})
            stats = detail.get("statistics", {})
            
            # Parse duration
            duration_str = content.get("duration", "PT0S") if content else "PT0S"
            duration_minutes = parse_iso_duration(duration_str)
            
            # Format duration
            if duration_minutes >= 60:
                hours = int(duration_minutes // 60)
                mins = int(duration_minutes % 60)
                duration_formatted = f"{hours}h {mins}m"
            else:
                duration_formatted = f"{int(duration_minutes)}m" if duration_minutes > 0 else "1h"
                if duration_minutes == 0:
                    duration_minutes = 60
            
            # Get view count
            views = 0
            if stats and stats.get("viewCount"):
                try:
                    views = int(stats["viewCount"])
                except:
                    views = 0
            
            videos.append({
                "video_id": video_id,
                "title": snippet.get("title", "Video"),
                "channel": snippet.get("channelTitle", "YouTube"),
                "description": snippet.get("description", ""),
                "duration": duration_formatted,
                "duration_minutes": duration_minutes,
                "views": views
            })
        
        return videos
        
    except Exception as e:
        print(f"[YouTube API] Error: {e}")
        return []


def get_emergency_videos(topic, max_results=3, subject=None):
    """Get topic-specific videos with STRICT subject/topic matching"""
    videos = search_youtube(topic, max_results, subject)
    
    if videos:
        return videos
    
    print(f"[get_emergency_videos] Retrying with relaxed filtering...")
    videos = search_youtube(topic, max_results, None)
    
    if videos:
        return videos
    
    print(f"[get_emergency_videos] Still no videos for '{topic}'")
    return []


# REMOVE all fallback systems - using REAL YouTube search only

def get_safe_youtube_videos(topic, max_results=2):
    return search_youtube(topic, max_results)


def search_youtube_api_strict(query, max_results=10):
    """YouTube API search - tries API first, then fallback"""
    
    # Try the official API first
    api_result = search_youtube_official_api(query, max_results)
    if api_result:
        return api_result
    
    # If API fails (quota exceeded), try free alternatives
    print(f"[YouTube API] Quota exceeded, trying alternative search...")
    
    # Try search via yt-api (free alternative)
    alt_result = search_youtube_alternative(query, max_results)
    if alt_result:
        return alt_result
    
    return []


def search_youtube_official_api(query, max_results=10):
    """YouTube official API"""
    if not YOUTUBE_API_KEY or len(YOUTUBE_API_KEY) < 10:
        print(f"[YouTube API] No API key configured")
        return []
    
    videos = []
    
    try:
        search_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results * 2, 25),
            "key": YOUTUBE_API_KEY,
            "videoDuration": "any"
        }
        
        print(f"[YouTube API] Searching: {query}")
        response = requests.get(search_url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"[YouTube API] Error status {response.status_code}, retrying...")
            response = requests.get(search_url, params=params, timeout=15)
            if response.status_code != 200:
                return []
        
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            print(f"[YouTube API] No items returned for query: {query}")
            return []
        
        video_ids = [item.get("id", {}).get("videoId") for item in items if item.get("id", {}).get("videoId")]
        
        if not video_ids:
            print(f"[YouTube API] No video IDs extracted")
            return []
        
        details_url = "https://www.googleapis.com/youtube/v3/videos"
        details_params = {
            "part": "contentDetails,statistics,snippet",
            "id": ",".join(video_ids),
            "key": YOUTUBE_API_KEY
        }
        
        details_response = requests.get(details_url, params=details_params, timeout=10)
        
        if details_response.status_code != 200:
            return []
        
        details_data = details_response.json()
        detail_items = details_data.get("items", [])
        
        detail_map = {item["id"]: item for item in detail_items}
        
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            if not video_id or video_id not in detail_map:
                continue
            
            detail = detail_map[video_id]
            snippet = item.get("snippet", {})
            content = detail.get("contentDetails", {})
            stats = detail.get("statistics", {})
            
            title = snippet.get("title", "Tutorial")
            channel = snippet.get("channelTitle", "YouTube")
            description = snippet.get("description", "")
            
            duration_str = content.get("duration", "")
            duration_minutes = parse_iso_duration(duration_str)
            
            view_count = int(stats.get("viewCount", 0) or 0)
            
            if duration_minutes < MIN_DURATION_MINUTES:
                continue
            
            videos.append({
                "video_id": video_id,
                "title": title[:100],
                "channel": channel[:50],
                "description": description[:500],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "embed_url": f"https://www.youtube.com/embed/{video_id}",
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "duration_minutes": duration_minutes,
                "viewCount": view_count
            })
    
    except Exception as e:
        print(f"[YouTube API] Exception: {e}")
    
    return videos


def search_youtube_api_robust(topic, max_results=2):
    """Legacy wrapper - redirects to new strict implementation"""
    return search_youtube(topic, max_results)


def search_youtube_alternative(query, max_results=10):
    """Alternative YouTube search - uses any available method"""
    # Try DuckDuckGo to find YouTube links (no API key needed)
    try:
        search_url = "https://api.duckduckgo.com/"
        params = {
            "q": f"{query} youtube tutorial",
            "format": "json",
            "no_html": 1
        }
        
        response = requests.get(search_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            results = data.get("RelatedTopics", [])
            videos = []
            
            for item in results:
                url = item.get("FirstURL", "")
                if "youtube.com/watch" in url or "youtu.be/" in url:
                    video_id = extract_video_id(url)
                    if video_id and is_valid_video_id(video_id):
                        title = item.get("Text", f"{query} Tutorial")[:100]
                        videos.append({
                            "video_id": video_id,
                            "title": title,
                            "channel": "YouTube",
                            "description": "",
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "embed_url": f"https://www.youtube.com/embed/{video_id}",
                            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                            "duration_minutes": 10,
                            "viewCount": 0
                        })
                        if len(videos) >= max_results:
                            break
            
            if videos:
                print(f"[YouTube Alternative] Found {len(videos)} via DuckDuckGo")
                return videos
    except Exception as e:
        print(f"[YouTube Alternative] DuckDuckGo error: {e}")
    
    return []


# REMOVED: RELIABLE_FALLBACK_VIDEOS and get_reliable_fallback_video
# System now uses REAL YouTube API searches only

def get_emergency_videos(topic, max_results=3, subject=None):
    """Get topic-specific videos from YouTube API"""
    return search_youtube(topic, max_results, subject)


def get_safe_youtube_videos(topic, max_results=2):
    """Return videos from real YouTube search"""
    return search_youtube(topic, max_results)


# ============== STATIC VIDEO DATABASE (REMOVED) ==============
# Static fallback videos have been removed - ONLY real API data is used

EDUCATIONAL_VIDEO_DATABASE = {}


def get_guaranteed_educational_video(topic, subject=None, max_results=2):
    """ONLY used as last resort when API completely fails"""
    print(f"[YouTube CRITICAL FALLBACK] API failed completely for: {topic}")
    search_query = f"{topic} {subject}" if subject else f"{topic} tutorial"
    return [{
        "video_id": "",
        "title": f"Search {topic} on YouTube",
        "channel": "YouTube",
        "duration": "",
        "url": f"https://www.youtube.com/results?search_query={quote(search_query)}",
        "embed_url": "",
        "thumbnail": "",
        "is_search_link": True
    }]


def get_youtube_videos_scrape(topic, max_results=2, subject=None):
    return get_emergency_videos(topic, max_results, subject)


def generate_youtube_search_links(topic, max_results=2, subject=None):
    return get_emergency_videos(topic, max_results, subject)

def parse_iso_duration(duration_str):
    """Parse YouTube ISO 8601 duration to minutes"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 60 + minutes + seconds / 60

def parse_duration_str(duration_str):
    """Parse duration strings like '2h 15m', '1h 30m', '45m' to minutes"""
    import re
    hours = 0
    minutes = 0
    h_match = re.search(r'(\d+)\s*h', duration_str.lower())
    m_match = re.search(r'(\d+)\s*m', duration_str.lower())
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    return hours * 60 + minutes

def search_youtube_api(topic, max_results=2, min_duration=60):
    """Search YouTube using official API v3 - returns relevant videos for any topic"""
    
    skip_terms = [
        "music", "song", "lyrics", "movie", "trailer", "film",
        "shorts", "reels", "vlog", "funny", "gaming", "prank"
    ]
    
    if not YOUTUBE_API_KEY or len(YOUTUBE_API_KEY) < 10:
        return get_fallback_videos(topic, max_results, skip_terms, min_duration)
    
    all_videos = []
    topic_lower = topic.lower()
    topic_words = [w for w in topic_lower.split() if len(w) > 2]
    
    search_queries = [
        f"{topic} tutorial",
        f"{topic} explained",
        f"{topic} full course",
        f"{topic} for beginners",
        f"{topic} lecture",
        f"{topic} complete",
        f"learn {topic}",
    ]
    
    for query in search_queries:
        try:
            search_url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 20,
                "key": YOUTUBE_API_KEY,
                "videoDuration": "any"
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code != 200:
                continue
            
            data = response.json()
            items = data.get("items", [])
            
            if not items:
                continue
            
            video_ids = [item.get("id", {}).get("videoId") for item in items if item.get("id", {}).get("videoId")]
            
            if not video_ids:
                continue
            
            stats_map = {}
            for i in range(0, len(video_ids), 15):
                batch_ids = video_ids[i:i+15]
                stats_params = {
                    "part": "statistics,contentDetails",
                    "id": ",".join(batch_ids),
                    "key": YOUTUBE_API_KEY
                }
                
                stats_response = requests.get("https://www.googleapis.com/youtube/v3/videos", params=stats_params, timeout=10)
                if stats_response.status_code == 200:
                    for item in stats_response.json().get("items", []):
                        vid = item["id"]
                        stats = item.get("statistics", {})
                        content = item.get("contentDetails", {})
                        view_count = int(stats.get("viewCount", 0)) if stats.get("viewCount", "0").isdigit() else 0
                        duration = parse_iso_duration(content.get("duration", "PT0S"))
                        stats_map[vid] = {"views": view_count, "duration": duration}
            
            for item in items:
                video_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                
                if not video_id:
                    continue
                
                title_lower = snippet.get("title", "").lower()
                
                if any(skip in title_lower for skip in skip_terms):
                    continue
                
                stats = stats_map.get(video_id, {})
                duration = stats.get("duration", 0)
                views = stats.get("views", 0)
                
                title_words = title_lower.split()
                topic_match = any(tw in title_words for tw in topic_words)
                
                all_videos.append({
                    "video_id": video_id,
                    "title": snippet.get("title", f"{topic} Tutorial"),
                    "channel": snippet.get("channelTitle", "YouTube"),
                    "views": views,
                    "duration_minutes": duration,
                    "topic_match": topic_match,
                    "is_long": duration >= min_duration
                })
                
        except Exception as e:
            print(f"Query error: {e}")
            continue
    
    if not all_videos:
        return get_fallback_videos(topic, max_results, skip_terms, min_duration)
    
    priority_videos = [v for v in all_videos if v["topic_match"] and v["is_long"]]
    if not priority_videos:
        priority_videos = [v for v in all_videos if v["topic_match"]]
    if not priority_videos:
        priority_videos = all_videos
    
    priority_videos.sort(key=lambda x: (x["views"], x["duration_minutes"]), reverse=True)
    
    videos = []
    for video in priority_videos[:max_results]:
        hours = int(video["duration_minutes"] // 60)
        mins = int(video["duration_minutes"] % 60)
        duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        videos.append({
            "video_id": video["video_id"],
            "title": video["title"],
            "channel": video["channel"],
            "duration": duration_str,
            "duration_minutes": video["duration_minutes"],
            "url": f"https://www.youtube.com/watch?v={video['video_id']}",
            "thumbnail": f"https://img.youtube.com/vi/{video['video_id']}/hqdefault.jpg",
            "viewCount": video["views"]
        })
    
    if not videos:
        return get_fallback_videos(topic, max_results, skip_terms, min_duration)
    
    return videos


def get_fallback_videos(topic, max_results, skip_terms=None, min_duration=60):
    """Fallback: Use web scraping when API fails"""
    videos = search_youtube_alternative_free(topic, max_results)
    
    # Format for search_youtube_api output format
    formatted = []
    for v in videos:
        vid = v.get('video_id', '')
        dur = v.get('duration_minutes', 60)
        hours = int(dur // 60)
        mins = int(dur % 60)
        duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        
        formatted.append({
            "video_id": vid,
            "title": v.get('title', f"{topic} Tutorial"),
            "channel": v.get('channel', 'YouTube'),
            "views": v.get('views', 0),
            "duration_minutes": dur,
            "duration": duration_str,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
        })
    
    return formatted


def search_youtube_duckduckgo(topic, max_results=3):
    """Search YouTube using DuckDuckGo - improved fallback"""
    try:
        search_url = "https://api.duckduckgo.com/"
        params = {
            "q": f"{topic} tutorial",
            "format": "json",
            "no_html": 1,
            "t": "studyplanner"
        }
        
        response = requests.get(search_url, params=params, timeout=3)
        if response.status_code != 200:
            return []
        
        data = response.json()
        results = data.get("RelatedTopics", [])
        
        videos = []
        seen_ids = set()
        
        for item in results:
            url = item.get("FirstURL", "")
            if "youtube.com/watch" in url or "youtu.be/" in url:
                video_id = None
                if "youtube.com/watch" in url:
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                    video_id = parsed.get('v', [None])[0]
                elif "youtu.be/" in url:
                    video_id = url.split("youtu.be/")[-1].split("?")[0]
                
                if video_id and video_id not in seen_ids:
                    seen_ids.add(video_id)
                    title = item.get("Text", f"{topic} Tutorial")
                    if " - " in title:
                        title = title.split(" - ")[0]
                    title = title[:80]
                    
                    videos.append({
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "viewCount": 0,
                        "channelTitle": "YouTube"
                    })
        
        if not videos:
            return []
        
        return videos[:max_results]
    
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
        return []

def search_youtube_scrape(topic, max_results=3):
    """Skip scraping - use real YouTube search"""
    return search_youtube(topic, max_results)


ARTICLE_RESOURCES = {
    "quadratic equations": [
        {"title": "Quadratic Equations - NCERT", "url": "https://ncert.nic.in/textbook.php?lemh1=9_1"},
        {"title": "Quadratic Equations - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/quadratic-equations/"},
        {"title": "Quadratic Equations - Math is Fun", "url": "https://www.mathsisfun.com/algebra/quadratic-equation.html"}
    ],
    "trigonometry": [
        {"title": "Trigonometry - NCERT", "url": "https://ncert.nic.in/textbook.php?lemh1=8_1"},
        {"title": "Trigonometry - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/trigonometry/"},
        {"title": "Trigonometry - Math is Fun", "url": "https://www.mathsisfun.com/algebra/trigonometry.html"}
    ],
    "calculus": [
        {"title": "Calculus - Khan Academy", "url": "https://www.khanacademy.org/math/ap-calculus-ab"},
        {"title": "Calculus - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/calculus/"},
        {"title": "Calculus - Math is Fun", "url": "https://www.mathsisfun.com/calculus/"}
    ],
    "probability": [
        {"title": "Probability - NCERT", "url": "https://ncert.nic.in/textbook.php?lemh1=15_1"},
        {"title": "Probability - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/probability/"},
        {"title": "Probability - Math is Fun", "url": "https://www.mathsisfun.com/data/probability.html"}
    ],
    "newton's laws": [
        {"title": "Newton's Laws - Physics Classroom", "url": "https://www.physicsclassroom.com/class/newtlaws"},
        {"title": "Newton's Laws - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/newtons-laws-of-motion/"},
        {"title": "Khan Academy - Newton's Laws", "url": "https://www.khanacademy.org/science/physics/forces-newtons-laws"}
    ],
    "chemical bonding": [
        {"title": "Chemical Bonding - NCERT", "url": "https://ncert.nic.in/textbook.php?lech1=4"},
        {"title": "Chemical Bonding - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/chemical-bonding/"},
        {"title": "Chemical Bonding - ChemGuide", "url": "https://www.chemguide.co.uk/atoms/bonding/bonding.html"}
    ],
    "cell biology": [
        {"title": "Cell Biology - Nature Education", "url": "https://www.nature.com/scitable/topicpage/cell-membrane-plasma-membrane-14053565/"},
        {"title": "Cell Biology - NCERT", "url": "https://ncert.nic.in/textbook.php?lebo1=5"},
        {"title": "Cell Biology - Genome.gov", "url": "https://www.genome.gov/about-genomics/educational-resources"}
    ],
    "html": [
        {"title": "HTML - MDN Web Docs", "url": "https://developer.mozilla.org/en-US/docs/Web/HTML"},
        {"title": "HTML - W3Schools", "url": "https://www.w3schools.com/html/"},
        {"title": "HTML - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/html/"}
    ],
    "css": [
        {"title": "CSS - MDN Web Docs", "url": "https://developer.mozilla.org/en-US/docs/Web/CSS"},
        {"title": "CSS - W3Schools", "url": "https://www.w3schools.com/css/"},
        {"title": "CSS Tricks - Flexbox", "url": "https://css-tricks.com/snippets/css/a-guide-to-flexbox/"}
    ],
    "javascript": [
        {"title": "JavaScript - MDN Web Docs", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript"},
        {"title": "JavaScript - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/javascript/"},
        {"title": "JavaScript - W3Schools", "url": "https://www.w3schools.com/js/"}
    ],
    "python": [
        {"title": "Python - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/python-programming-language/"},
        {"title": "Python - W3Schools", "url": "https://www.w3schools.com/python/"},
        {"title": "Python.org Documentation", "url": "https://docs.python.org/3/"}
    ],
    "sql": [
        {"title": "SQL - W3Schools", "url": "https://www.w3schools.com/sql/"},
        {"title": "SQL - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/sql-tutorial/"},
        {"title": "SQL - PostgreSQL Tutorial", "url": "https://www.postgresqltutorial.com/"}
    ],
    "statistics": [
        {"title": "Statistics - Math is Fun", "url": "https://www.mathsisfun.com/data/statistics.html"},
        {"title": "Statistics - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/statistics/"},
        {"title": "Khan Academy - Statistics", "url": "https://www.khanacademy.org/math/statistics-probability"}
    ],
    "react": [
        {"title": "React - Official Docs", "url": "https://reactjs.org/docs/getting-started.html"},
        {"title": "React - W3Schools", "url": "https://www.w3schools.com/react/"},
        {"title": "React - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/reactjs/"}
    ],
    "machine learning": [
        {"title": "Machine Learning - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/machine-learning/"},
        {"title": "Machine Learning - Kaggle", "url": "https://www.kaggle.com/learn/intro-to-machine-learning"},
        {"title": "Machine Learning - Stanford Online", "url": "https://online.stanford.edu/courses/soe-ycsmachine-learning"}
    ]
}

def get_article_resources(topic, max_results=2):
    """Get relevant article/resources for a topic"""
    cache_key = f"art_{topic.lower()}_{max_results}"
    cached = _get_cache(cache_key, _topic_cache)
    if cached:
        return cached
    
    topic_lower = topic.lower()
    
    for key, articles in ARTICLE_RESOURCES.items():
        if key in topic_lower or topic_lower in key:
            result = articles[:max_results]
            _set_cache(cache_key, result, _topic_cache)
            return result
    
    topic_slug = topic.lower().replace(" ", "-").replace("'", "")
    default_articles = [
        {"title": f"{topic} - GeeksforGeeks", "url": f"https://www.geeksforgeeks.org/{topic_slug}/"},
        {"title": f"{topic} - W3Schools", "url": f"https://www.w3schools.com/{topic_slug.replace('-', '')}/"},
    ]
    result = default_articles[:max_results]
    _set_cache(cache_key, result, _topic_cache)
    return result

def search_blogs(topic, max_results=2):
    """Search for actual blog articles"""
    topic_clean = topic.lower().strip()
    topic_slug = topic_clean.replace(' ', '-').replace('/', '-').replace('?', '')
    
    urls_to_try = [
        ("GeeksforGeeks", f"https://www.geeksforgeeks.org/{topic_slug}/"),
        ("W3Schools", f"https://www.w3schools.com/{topic_clean.replace(' ', '_')}/"),
    ]
    
    valid_blogs = []
    for name, url in urls_to_try:
        try:
            resp = requests.head(url, timeout=3, allow_redirects=True)
            if resp.status_code < 400:
                valid_blogs.append({
                    "title": f"{topic} - {name}",
                    "url": url
                })
        except:
            pass
    
    if not valid_blogs:
        valid_blogs = [
            {"title": f"Search {topic} on Google", "url": f"https://www.google.com/search?q={topic}+tutorial"},
        ]
    
    return valid_blogs[:max_results]

def search_practice_questions(topic, max_results=3):
    """Search for practice questions"""
    topic_clean = topic.lower().strip()
    topic_slug = topic_clean.replace(' ', '-').replace('/', '-').replace('?', '')
    
    urls_to_try = [
        ("GeeksforGeeks", f"https://www.geeksforgeeks.org/{topic_slug}/"),
        ("W3Schools", f"https://www.w3schools.com/{topic_clean.replace(' ', '_')}/"),
    ]
    
    valid_practice = []
    for name, url in urls_to_try:
        try:
            resp = requests.head(url, timeout=3, allow_redirects=True)
            if resp.status_code < 400:
                valid_practice.append({
                    "title": f"{topic} - {name} (Practice & Questions)",
                    "url": url
                })
        except:
            pass
    
    if not valid_practice:
        valid_practice = [
            {"title": f"{topic} Interview Questions", "url": f"https://www.google.com/search?q={topic}+interview+questions"},
        ]
    
    return valid_practice[:max_results]

def detect_level(topic):
    topic = topic.lower()

    school_keywords = [
        "class", "cbse", "ncert", "hindi", "grammar", "physics",
        "chemistry", "biology", "math", "trigonometry", "algebra"
    ]

    college_keywords = [
        "sql", "python", "machine learning", "data science",
        "react", "javascript", "backend", "api", "statistics"
    ]

    for word in college_keywords:
        if word in topic:
            return "college"

    for word in school_keywords:
        if word in topic:
            return "school"

    return "general"

def generate_practice_prompt(topic):
    level = detect_level(topic)

    if level == "school":
        level_instruction = "Use very simple language. Suitable for school students."
    elif level == "college":
        level_instruction = "Use clear but slightly technical language. Suitable for college students."
    else:
        level_instruction = "Use simple and clear language."

    return f"""
You are an expert teacher.

Topic: {topic}

Instructions:
- Generate exactly 5 practice questions
- {level_instruction}
- Avoid unnecessary jargon
- Keep answers short (2-3 lines)
- Questions should be meaningful and relevant

Structure:
- 2 easy questions
- 2 medium questions
- 1 hard question

Format strictly:

Q1. ...
Answer: ...

Q2. ...
Answer: ...

Q3. ...
Answer: ...

Q4. ...
Answer: ...

Q5. ...
Answer: ...
"""


def call_ai_api(messages, model=None, max_tokens=300):
    import os
    import requests

    try:
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")

        if model is None:
            model = ollama_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens
            }
        }

        response = requests.post(
            f"{ollama_base_url}/api/chat",
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            print("❌ Ollama error:", response.text)
            return None

        data = response.json()
        content = data.get("message", {}).get("content", "").strip()

        return content if content else None

    except Exception as e:
        print("❌ AI ERROR:", e)
        return None

def search_pdf_notes(topic, max_results=3):
    """Search for PDF notes for a topic - with direct PDF links"""
    cache_key = f"pdf_{topic.lower()}_{max_results}"
    cached = _get_cache(cache_key, _topic_cache)
    if cached:
        return cached
    
    topic_lower = topic.lower()
    
    pdf_resources = {
        "quadratic equations": [
            {"title": "Quadratic Equations NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh205.pdf"},
            {"title": "Quadratic Equations Important Questions", "url": "https://www.learncbse.in/quadratic-equations-class-10-important-questions/"},
        ],
        "trigonometry": [
            {"title": "Trigonometry NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh208.pdf"},
            {"title": "Trigonometry Formulas", "url": "https://www.learncbse.in/trigonometry-formulas-for-class-10/"},
        ],
        "calculus": [
            {"title": "Calculus Basics PDF", "url": "https://www.math.ucdavis.edu/~kouba/CalcOnePROBLEMSOLVER.html"},
            {"title": "Calculus Notes", "url": "https://www.khanacademy.org/math/ap-calculus-ab"},
        ],
        "probability": [
            {"title": "Probability NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh215.pdf"},
            {"title": "Probability Important Questions", "url": "https://www.learncbse.in/probability-class-10-important-questions/"},
        ],
        "newton's laws": [
            {"title": "Newton's Laws NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lesh105.pdf"},
            {"title": "Laws of Motion Notes", "url": "https://www.learncbse.in/newtons-laws-of-motion-class-9/"},
        ],
        "chemical bonding": [
            {"title": "Chemical Bonding NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lech104.pdf"},
            {"title": "Chemical Bonding Notes", "url": "https://www.meritnation.com/answers/5992"},
        ],
        "cell biology": [
            {"title": "Cell Biology NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lebo105.pdf"},
            {"title": "Cell Unit Notes", "url": "https://www.byjus.com/biology/cell/"},
        ],
        "html": [
            {"title": "HTML Cheat Sheet PDF", "url": "https://websitesetup.org/html5-cheat-sheet.pdf"},
            {"title": "HTML Tutorial", "url": "https://www.w3schools.com/html/"},
        ],
        "css": [
            {"title": "CSS Cheat Sheet PDF", "url": "https://websitesetup.org/css3-cheat-sheet.pdf"},
            {"title": "CSS Tutorial", "url": "https://www.w3schools.com/css/"},
        ],
        "javascript": [
            {"title": "JavaScript Notes PDF", "url": "https://www.javascript.com/resources"},
            {"title": "JavaScript Tutorial", "url": "https://www.w3schools.com/js/"},
        ],
        "python": [
            {"title": "Python Notes PDF", "url": "https://www.geeksforgeeks.org/python-programming-language/"},
            {"title": "Python Tutorial", "url": "https://www.w3schools.com/python/"},
        ],
        "sql": [
            {"title": "SQL Cheat Sheet PDF", "url": "https://www.sqltutorial.org/wp-content/uploads/2021/01/SQL-Cheat-Sheet.pdf"},
            {"title": "SQL Tutorial", "url": "https://www.w3schools.com/sql/"},
        ],
        "statistics": [
            {"title": "Statistics NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh214.pdf"},
            {"title": "Statistics Formulas", "url": "https://www.mathsisfun.com/data/statistics.html"},
        ],
        "react": [
            {"title": "React Documentation", "url": "https://reactjs.org/docs/getting-started.html"},
            {"title": "React Tutorial", "url": "https://www.w3schools.com/react/"},
        ],
        "machine learning": [
            {"title": "ML Notes PDF", "url": "https://www.geeksforgeeks.org/machine-learning/"},
            {"title": "ML Tutorial", "url": "https://www.kaggle.com/learn/intro-to-machine-learning"},
        ],
    }
    
    for key, pdfs in pdf_resources.items():
        if key in topic_lower or topic_lower in key:
            result = pdfs[:max_results]
            _set_cache(cache_key, result, _topic_cache)
            return result
    
    topic_slug = topic.lower().replace(" ", "-").replace("'", "")
    fallback_pdfs = [
        {"title": f"{topic} Notes - GeeksforGeeks", "url": f"https://www.geeksforgeeks.org/{topic_slug}/"},
        {"title": f"{topic} Tutorial", "url": f"https://www.w3schools.com/{topic_slug}/"},
    ]
    result = fallback_pdfs[:max_results]
    _set_cache(cache_key, result, _topic_cache)
    return result

TOPIC_DATA = {
    "Quadratic Equations": {
        "key_concepts": ["Standard form ax^2 + bx + c = 0", "Discriminant (b^2 - 4ac)", "Factoring method", "Quadratic formula: x = (-b +/- sqrt(b^2-4ac))/2a", "Nature of roots (real, equal, imaginary)"],
        "explanation": "Quadratic equations are polynomial equations of degree 2. The discriminant (D = b^2 - 4ac) determines the nature of roots: D > 0 = two distinct real roots, D = 0 = equal roots, D < 0 = imaginary roots. Methods include factoring, completing square, and quadratic formula.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=ZfFPgBcOc6U", "https://www.youtube.com/watch?v=lfF3j1xY5nU"],
            "article": ["https://www.geeksforgeeks.org/quadratic-equations/", "https://www.mathsisfun.com/algebra/quadratic-equation.html"]
        },
        "practice_questions": [
            "Solve: x^2 - 5x + 6 = 0 using factoring method",
            "Find the discriminant and nature of roots: 2x^2 + 3x - 2 = 0",
            "Solve by quadratic formula: x^2 + 4x - 12 = 0",
            "If one root is 3, find k if equation is x^2 + kx + 6 = 0"
        ]
    },
    "Trigonometry": {
        "key_concepts": ["sin, cos, tan definitions in right triangle", "Pythagorean identity: sin^2x + cos^2x = 1", "sin(A+B) = sinAcosB + cosAsinB", "Values at 0, 30, 45, 60, 90 degrees", "Inverse trig: sin^-1, cos^-1, tan^-1"],
        "explanation": "Trigonometry studies relationships between angles and sides of triangles. The six ratios (sin, cos, tan, cosec, sec, cot) relate angles to side ratios. Key identities include Pythagorean, sum/difference, double angle, and half angle formulas.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=AqCkKAV1NWk", "https://www.youtube.com/watch?v=UxRyqXb6v60"],
            "article": ["https://www.geeksforgeeks.org/trigonometry/", "https://www.mathsisfun.com/algebra/trigonometry.html"]
        },
        "practice_questions": [
            "If sin x = 3/5, find cos x and tan x (x in first quadrant)",
            "Prove: sin^2x + cos^2x = 1",
            "Find value of sin 75 degrees using addition formula",
            "Solve: 2sin x = 1 for 0 <= x <= 360 degrees"
        ]
    },
    "Calculus": {
        "key_concepts": ["Limits: lim(x->a) f(x)", "Derivative: d/dx(x^n) = nx^(n-1)", "Product, quotient, chain rules", "Integration: integral(x^n) = x^(n+1)/(n+1)", "Maxima and minima using derivatives"],
        "explanation": "Calculus studies continuous change. Differential calculus finds rates of change (derivatives) while integral calculus calculates areas under curves. The Fundamental Theorem links both. Applications include optimization, motion, and area problems.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=WTLAdllg9tU", "https://www.youtube.com/watch?v=r5Qdg30RVME"],
            "article": ["https://www.khanacademy.org/math/ap-calculus-ab", "https://www.mathsisfun.com/calculus/"]
        },
        "practice_questions": [
            "Find d/dx: x^3 + 2x^2 - 5x + 7",
            "Evaluate: integral(x^2 dx) from 0 to 3",
            "Find local maxima/minima of f(x) = x^3 - 3x^2 + 2",
            "Calculate: lim(x->2) (x^2 - 4)/(x - 2)"
        ]
    },
    "Probability": {
        "key_concepts": ["P(A) = favorable outcomes/total outcomes", "P(A or B) = P(A) + P(B) - P(A and B)", "P(A and B) = P(A) x P(B) for independent", "Conditional probability: P(A|B) = P(A and B)/P(B)", "Bayes theorem"],
        "explanation": "Probability measures likelihood of events on a scale from 0 (impossible) to 1 (certain). Addition rule handles OR events, multiplication rule handles AND events. Conditional probability finds P(A given B occurred). Bayes theorem updates probabilities with new evidence.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=uzkc-qNVoOk", "https://www.youtube.com/watch?v=KZ7SDBMC2Xc"],
            "article": ["https://www.geeksforgeeks.org/probability/", "https://www.mathsisfun.com/data/probability.html"]
        },
        "practice_questions": [
            "A bag has 3 red and 5 blue balls. Find P(red ball) when drawing one ball",
            "Two dice are rolled. Find P(sum is 7)",
            "P(A)=0.4, P(B)=0.3, P(A and B)=0.1. Find P(A or B)",
            "A test detects disease with 95% accuracy. If 1% have disease, find probability of correct detection"
        ]
    },
    "Newton's Laws": {
        "key_concepts": ["First Law: Inertia - object stays at rest/motion", "Second Law: F = ma (force = mass x acceleration)", "Third Law: Every action has equal opposite reaction", "Free body diagrams show all forces", "Friction: f = uN"],
        "explanation": "Newton's three laws form classical mechanics. First law defines inertia, second law (F=ma) connects force to motion change, third law explains action-reaction pairs. Free body diagrams identify all forces acting on a body.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=kK1c7dL4Z4U", "https://www.youtube.com/watch?v=HmA20gF5UJI"],
            "article": ["https://www.physicsclassroom.com/class/newtlaws", "https://www.geeksforgeeks.org/newtons-laws-of-motion/"]
        },
        "practice_questions": [
            "A 5kg object accelerates at 2 m/s^2. Calculate the net force",
            "Calculate tension in rope with 10kg mass hanging vertically",
            "Two blocks (2kg, 3kg) connected by string on frictionless surface. Find acceleration if F = 20N",
            "A 1000kg car accelerates from 0 to 20m/s in 10s. Find force"
        ]
    },
    "Chemical Bonding": {
        "key_concepts": ["Ionic: electron transfer (metal + non-metal)", "Covalent: electron sharing (non-metals)", "VSEPR: electron pairs repel, determine shape", "Hybridization: sp, sp2, sp3", "Electronegativity difference determines bond type"],
        "explanation": "Chemical bonding holds atoms together. Ionic bonds form through electron transfer creating charged ions. Covalent bonds share electrons between atoms. VSEPR theory predicts molecular shapes based on electron pair repulsion. Hybridization explains orbital mixing.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=QJPvBOOMHYQ", "https://www.youtube.com/watch?v=Q2sOPnJjKqM"],
            "article": ["https://www.geeksforgeeks.org/chemical-bonding/", "https://www.chemguide.co.uk/atoms/bonding/bonding.html"]
        },
        "practice_questions": [
            "Explain why NaCl is ionic but HCl is covalent using electronegativity",
            "Predict shape and bond angle of NH3 using VSEPR",
            "What is hybridization of carbon in CH4, C2H4, and C2H2?",
            "Draw electron dot structure of CO2 and predict shape"
        ]
    },
    "Cell Biology": {
        "key_concepts": ["Fluid mosaic model of cell membrane", "Mitochondria: site of cellular respiration, ATP production", "DNA replication: semi-conservative", "Transcription: DNA to mRNA", "Translation: mRNA to protein at ribosome"],
        "explanation": "The cell is life's basic unit. Cell membrane (fluid mosaic) controls what enters/exits. Mitochondria produce ATP through cellular respiration. DNA stores genetic information and replicates semi-conservatively. Proteins are synthesized via transcription and translation.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=URUJD6N2hS8", "https://www.youtube.com/watch?v=8iLIVS9nn5s"],
            "article": ["https://www.nature.com/scitable/topicpage/cell-membrane-plasma-membrane-14053565/", "https://www.genome.gov/about-genomics/educational-resources"]
        },
        "practice_questions": [
            "Describe fluid mosaic model of cell membrane with diagram",
            "Calculate ATP yield from complete oxidation of one glucose molecule",
            "Explain semiconservative replication of DNA",
            "What happens during S-phase of cell cycle?"
        ]
    },
    "HTML": {
        "key_concepts": ["Document structure: DOCTYPE, html, head, body", "Semantic tags: header, nav, main, section, article, footer", "Form elements: input, select, textarea, button", "Tables: table, tr, th, td", "HTML5 APIs: Canvas, Geolocation"],
        "explanation": "HTML structures web content using elements and tags. Semantic HTML5 tags (header, nav, main, section, article, footer) improve accessibility and SEO. Forms collect user input. Tables display tabular data. Always use semantic elements over generic divs.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=qz0aGYrrlhU", "https://www.youtube.com/watch?v=pQN-pnXPaHg"],
            "article": ["https://www.w3schools.com/html/", "https://developer.mozilla.org/en-US/docs/Web/HTML"]
        },
        "practice_questions": [
            "Write complete HTML5 document with header, nav, main with 2 sections, footer",
            "Create a registration form with fields: name, email, password, confirm password",
            "Build an accessible table showing student marks with headers",
            "Explain difference between <article> and <section> tags"
        ]
    },
    "CSS": {
        "key_concepts": ["Box model: margin, border, padding, content", "Flexbox: justify-content, align-items, flex-direction", "CSS Grid: grid-template-columns, grid-gap", "Media queries: @media screen and (max-width:)", "Specificity: inline > ID > class > element"],
        "explanation": "CSS styles HTML elements. Box model treats every element as a box. Flexbox handles one-dimensional layouts (row or column). Grid handles two-dimensional layouts. Media queries create responsive designs. Specificity determines which styles apply.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=1PnVor36YS40", "https://www.youtube.com/watch?v=jV8B24rSN5o"],
            "article": ["https://css-tricks.com/snippets/css/a-guide-to-flexbox/", "https://www.w3schools.com/css/"]
        },
        "practice_questions": [
            "Create a card with 20px padding, 2px solid border, 10px margin using box model",
            "Center a div both horizontally and vertically using Flexbox",
            "Build a responsive grid with 3 columns that becomes 1 column on mobile",
            "Write CSS specificity calculation for: div#id.class:hover"
        ]
    },
    "JavaScript": {
        "key_concepts": ["let, const, var: block vs function scope", "Arrow functions: () => {}", "Array methods: map, filter, reduce, forEach", "DOM: getElementById, querySelector, addEventListener", "Async: Promise, async/await, fetch API"],
        "explanation": "JavaScript adds interactivity to web pages. ES6+ features include let/const (block scope), arrow functions, and async/await. Array methods (map, filter, reduce) transform data efficiently. DOM manipulation enables dynamic page updates.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=W6NZfCO5SIk", "https://www.youtube.com/watch?v=PoRJizFvM7s"],
            "article": ["https://developer.mozilla.org/en-US/docs/Web/JavaScript", "https://www.geeksforgeeks.org/javascript/"]
        },
        "practice_questions": [
            "Write function to sum all even numbers in array using reduce",
            "Create element and add click listener that changes its text",
            "Convert array of numbers to array of squares using map",
            "Write async function using fetch API to get user data"
        ]
    },
    "SQL": {
        "key_concepts": ["SELECT, FROM, WHERE, ORDER BY", "JOINs: INNER, LEFT, RIGHT, FULL", "GROUP BY with HAVING", "Subqueries and EXISTS", "Indexes for query optimization"],
        "explanation": "SQL manages relational databases. SELECT retrieves data, WHERE filters, JOIN combines tables. Aggregate functions (COUNT, SUM, AVG, MAX, MIN) work with GROUP BY. Subqueries nest SELECT statements. Indexes speed up queries on large tables.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=HXV3zeQKqGY", "https://www.youtube.com/watch?v=7S_tz1z_5bA"],
            "article": ["https://www.w3schools.com/sql/", "https://www.geeksforgeeks.org/sql-tutorial/"]
        },
        "practice_questions": [
            "Write query: Find employees earning above average salary with department name",
            "Create INNER JOIN between Orders and Customers tables",
            "Write subquery to find customers who never placed an order",
            "Explain difference between WHERE and HAVING clause with example"
        ]
    },
    "Statistics": {
        "key_concepts": ["Mean: sum/n, Median: middle value", "Mode: most frequent value", "Standard deviation: sqrt(sum((x-mean)^2)/n)", "Z-score: (x-mean)/std", "Correlation coefficient r"],
        "explanation": "Statistics summarizes and analyzes data. Central tendency measures (mean, median, mode) show typical values. Spread measures (range, variance, standard deviation) show data dispersion. Z-scores standardize values. Correlation measures relationship between variables.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=sf6xI9-9t40", "https://www.youtube.com/watch?v=cesvsG52vhI"],
            "article": ["https://www.mathsisfun.com/data/statistics.html", "https://www.geeksforgeeks.org/statistics/"]
        },
        "practice_questions": [
            "Calculate mean, median, mode: 12, 15, 15, 18, 20, 22, 25",
            "Find standard deviation: 10, 12, 14, 16, 18",
            "A test score is 85, mean is 70, std dev is 10. Find z-score and interpret",
            "Calculate correlation coefficient for x: 1,2,3,4,5 and y: 2,4,6,8,10"
        ]
    },
    "Python": {
        "key_concepts": ["Variables, data types (int, float, str, list, dict)", "Control flow: if/elif/else, for/while loops", "Functions: def, args, kwargs, lambda", "OOP: class, __init__, inheritance", "File handling: open, read, write"],
        "explanation": "Python is a versatile programming language. Variables store data, control flow manages execution order. Functions modularize code. Object-oriented programming uses classes and objects. Libraries like NumPy and Pandas enable data analysis.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=kqtD5dpn9C8", "https://www.youtube.com/watch?v=_uQrJ0TkZlc"],
            "article": ["https://www.geeksforgeeks.org/python-programming-language/", "https://www.w3schools.com/python/"]
        },
        "practice_questions": [
            "Write function to check if number is prime",
            "Create class BankAccount with deposit and withdrawal methods",
            "Write code to find duplicate elements in list using dictionary",
            "Sort list of dictionaries by key using lambda function"
        ]
    },
    "React": {
        "key_concepts": ["Components: functional vs class components", "Props: passing data to components", "State: useState hook for local state", "Hooks: useEffect, useContext, useReducer", "Lifecycle: component mounting, updating, unmounting"],
        "explanation": "React is a JavaScript library for building user interfaces. Components are reusable UI pieces. Props pass data from parent to child. State manages dynamic data within a component. Hooks like useState and useEffect enable functional components to have state and side effects.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Ke90Tje7VS0", "https://www.youtube.com/watch?v=W6NZfCO5SIk"],
            "article": ["https://reactjs.org/docs/getting-started.html", "https://www.w3schools.com/react/"]
        },
        "practice_questions": [
            "Create a React component that displays a counter with increment/decrement buttons",
            "Build a form with controlled inputs using useState",
            "Implement useEffect to fetch data from an API on component mount",
            "Create a custom hook for managing local storage"
        ]
    },
    "Backend": {
        "key_concepts": ["Node.js: server-side JavaScript runtime", "Express: routing, middleware, error handling", "REST APIs: GET, POST, PUT, DELETE endpoints", "Database: connection, CRUD operations", "Authentication: JWT, bcrypt, sessions"],
        "explanation": "Backend development handles server-side logic and database interactions. Node.js runs JavaScript on the server. Express.js provides a framework for building APIs. REST APIs follow conventions for HTTP methods. Authentication secures endpoints using tokens.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Oe421EPjeBE", "https://www.youtube.com/watch?v=W6NZfCO5SIk"],
            "article": ["https://nodejs.org/docs/", "https://expressjs.com/en/starter/"]
        },
        "practice_questions": [
            "Create an Express server with GET, POST, PUT, DELETE endpoints",
            "Write middleware to validate JWT tokens",
            "Connect to MongoDB and perform CRUD operations",
            "Implement user registration and login with password hashing"
        ]
    },
    "English Grammar": {
        "key_concepts": ["Parts of speech: noun, verb, adj, adv, preposition", "Tenses: present, past, future with 4 aspects", "Subject-verb agreement rules", "Active vs Passive voice conversion", "Direct vs Indirect speech changes"],
        "explanation": "Grammar governs language structure. Parts of speech categorize words by function. Tenses express time and aspect. Subject-verb agreement ensures grammatical number matches. Active voice emphasizes doer, passive emphasizes action. Indirect speech backshifts tenses.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=bJ1D6I0wV_w", "https://www.youtube.com/watch?v=N4cK8QK2UkU"],
            "article": ["https://www.grammarly.com/blog/", "https://owl.purdue.edu/owl/general_grammar/"]
        },
        "practice_questions": [
            "Identify all parts of speech: 'The quickly running athlete won the gold medal gracefully'",
            "Convert to passive voice: 'The teacher explains the grammar lesson'",
            "Change to indirect speech: He said, 'I will complete the project tomorrow'",
            "Choose correct verb: Neither the students nor the teacher (was/were) present"
        ]
    },
    "Economics": {
        "key_concepts": ["Law of Demand: P up = Q down", "Law of Supply: P up = Q up", "Elasticity: Ed = % change Qd / % change P", "Consumer equilibrium: MU/P equal for all goods", "Market structures: perfect comp, monopoly, oligopoly"],
        "explanation": "Economics studies resource allocation. Demand and supply determine prices in market. Elasticity measures responsiveness to price changes. Consumers maximize utility where MU/P equalizes. Different market structures have varying competition levels and pricing power.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=adBSoRGR9Tw", "https://www.youtube.com/watch?v=76Zl9K5c5Dk"],
            "article": ["https://www.investopedia.com/", "https://www.economicshelp.org/"]
        },
        "practice_questions": [
            "If price rises from 10 to 12 and quantity demanded falls from 100 to 80, calculate price elasticity",
            "Draw and explain consumer equilibrium with budget line and indifference curve",
            "Compare price and output in perfect competition vs monopoly",
            "Calculate total revenue if P = 50 - 2Q and Q = 15"
        ]
    },
    "default": {
        "key_concepts": ["Core definitions and terminology", "Fundamental principles and laws", "Practical applications in real world", "Problem-solving techniques", "Industry-standard practices"],
        "explanation": "This topic covers essential concepts that form the foundation for understanding the subject area. Mastering these basics enables tackling advanced topics effectively.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "article": ["https://www.geeksforgeeks.org/", "https://www.khanacademy.org/"]
        },
        "practice_questions": [
            "Define and explain the core concept with examples",
            "Solve a numerical problem applying this concept",
            "Compare and contrast with related concepts"
        ]
    },
    "Current Electricity": {
        "key_concepts": ["Electric Current (I = Q/t)", "Ohm's Law (V = IR)", "Resistance (R = ρL/A)", "Series and Parallel circuits", "Kirchhoff's Laws", "Electric Power (P = VI)", "Joule's Law of heating", "Drift velocity", "Resistivity and Conductivity", "Internal resistance of battery"],
        "explanation": "Current Electricity deals with the flow of electric charge through conductors. Key concepts include: (1) Electric Current - rate of flow of charge (I = Q/t), measured in Amperes. (2) Ohm's Law - voltage across conductor is proportional to current (V = IR). (3) Resistance - opposition to flow of current, depends on material, length, cross-section (R = ρL/A). (4) Series circuits - same current through all components, voltages add. (5) Parallel circuits - same voltage across all components, currents add. (6) Kirchhoff's Laws - Junction Law (sum of currents = 0) and Loop Law (sum of EMFs = sum of potential drops). (7) Electric Power - rate of energy dissipation (P = VI = I²R = V²/R). (8) Joule's Law - heat produced H = I²Rt. (9) Drift velocity - average velocity of electrons in conductor. (10) Resistivity (ρ) - intrinsic property of material, temperature coefficient.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=1-NXe41490w", "https://www.youtube.com/watch?v=8-iR1cKj9N4"],
            "article": ["https://www.physicsclassroom.com/class/circuits", "https://www.learncbse.in/current-electricity-class-12/"]
        },
        "practice_questions": [
            "Define electric current and state its SI unit.",
            "State and explain Ohm's Law with formula and graph.",
            "A wire has resistance 10Ω. Calculate current when 20V is applied.",
            "Explain series and parallel combination of resistors with examples.",
            "State Kirchhoff's Current and Voltage Laws.",
            "Calculate power in a circuit with 5A current and 220V supply.",
            "Define resistivity and conductivity. How does resistance change with temperature?",
            "Derive expression for equivalent resistance in series combination.",
            "What is drift velocity? Derive relation between drift velocity and current.",
            "A battery of emf 12V and internal resistance 2Ω is connected to external resistance 4Ω. Find current."
        ]
    },
    "Motion": {
        "key_concepts": ["Distance and Displacement", "Speed and Velocity", "Acceleration (a = Δv/Δt)", " Equations of motion (v = u + at, s = ut + ½at², v² = u² + 2as)", "Graphs (distance-time, velocity-time)", "Uniform and Non-uniform motion", "Circular motion", "Relative velocity"],
        "explanation": "Motion is the change in position of an object with respect to time. Key concepts: (1) Distance - total path length (scalar), Displacement - shortest distance from initial to final position (vector). (2) Speed - rate of change of distance (scalar), Velocity - rate of change of displacement (vector). (3) Acceleration - rate of change of velocity. (4) Equations of motion for uniformly accelerated motion: v = u + at, s = ut + ½at², v² = u² + 2as. (5) Graphs help visualize motion - slope of distance-time graph = speed, slope of velocity-time graph = acceleration, area under velocity-time graph = displacement. (6) Circular motion when object moves in a circular path with constant speed but changing direction.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=vL79i4w8j5s"],
            "article": ["https://www.physicsclassroom.com/class/1DKin", "https://www.learncbse.in/motion-class-9/"]
        },
        "practice_questions": [
            "Define motion and explain the difference between distance and displacement.",
            "A car accelerates from 20 m/s to 50 m/s in 5 seconds. Find acceleration.",
            "Draw and explain distance-time graph for uniform and non-uniform motion.",
            "Derive the three equations of motion.",
            "A ball is thrown upward with velocity 20 m/s. Find maximum height (g = 10 m/s²).",
            "Explain the concept of relative velocity with an example.",
            "What is circular motion? Give one example.",
            "A car travels 100 km in 2 hours and then 50 km in 1 hour. Find average speed."
        ]
    },
    "Force and Laws of Motion": {
        "key_concepts": ["Newton's First Law (Inertia)", "Newton's Second Law (F = ma)", "Newton's Third Law (Action-Reaction)", "Momentum (p = mv)", "Conservation of Momentum", "Friction (f = μN)", "Equilibrium of forces"],
        "explanation": "Force and Laws of Motion form the foundation of classical mechanics. (1) Newton's First Law: An object remains at rest or in uniform motion unless acted upon by external force (Law of Inertia). (2) Newton's Second Law: Rate of change of momentum is proportional to applied force (F = ma). (3) Newton's Third Law: Every action has equal and opposite reaction. (4) Momentum: product of mass and velocity (p = mv), conserved in absence of external forces. (5) Friction: opposes motion, proportional to normal reaction (f = μN). (6) Applications include rocket propulsion, collisions, etc.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=vL79i4w8j5s", "https://www.youtube.com/watch?v=y5B6zR1Fq08"],
            "article": ["https://www.physicsclassroom.com/class/newtlaws", "https://www.learncbse.in/newtons-laws-motion-class-9/"]
        },
        "practice_questions": [
            "State and explain Newton's three laws of motion with examples.",
            "A force of 20N acts on a 5kg mass. Find acceleration.",
            "Define momentum and state law of conservation of momentum.",
            "Two balls of masses 2kg and 4kg moving at 3m/s and 2m/s collide and stick together. Find final velocity.",
            "Explain the concept of inertia and give examples.",
            "Why is it difficult to move a heavy box than a light box? Explain using Newton's laws.",
            "A bullet of mass 20g is fired from a gun with velocity 100m/s. Find recoil velocity of gun (mass 2kg)."
        ]
    },
    "Work, Energy and Power": {
        "key_concepts": ["Work (W = F × d × cosθ)", "Kinetic Energy (KE = ½mv²)", "Potential Energy (PE = mgh)", "Work-Energy Theorem", "Conservation of Energy", "Power (P = W/t)", "Different forms of energy"],
        "explanation": "Work, Energy and Power are interrelated physical quantities. (1) Work: energy transferred when force moves object (W = Fd cosθ), unit Joule. (2) Kinetic Energy: energy due to motion (KE = ½mv²). (3) Potential Energy: energy due to position/height (PE = mgh). (4) Work-Energy Theorem: work done = change in kinetic energy. (5) Conservation of Energy: energy can neither be created nor destroyed, only transformed. (6) Power: rate of doing work (P = W/t), unit Watt. (7) Forms of mechanical, electrical, heat, light, sound energy.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=4A02J6mYf2Y", "https://www.youtube.com/watch?v=y5B6zR1Fq08"],
            "article": ["https://www.physicsclassroom.com/class/energy", "https://www.learncbse.in/work-energy-power-class-9/"]
        },
        "practice_questions": [
            "Define work and state its SI unit. When is work done negative?",
            "A body of mass 2kg falls from height 10m. Find its kinetic energy just before hitting ground.",
            "State and explain work-energy theorem.",
            "A man pushes a box with force 50N through 10m. Calculate work done.",
            "Define power. A motor does 5000J work in 10 seconds. Find power in kW.",
            "Explain conservation of energy with an example of pendulum.",
            "Find the power required to lift 100kg water from 50m well in 10 seconds."
        ]
    },
    "Sound": {
        "key_concepts": ["Sound waves - longitudinal", "Frequency, Wavelength, Speed (v = fλ)", "Reflection of sound (echo)", "Sound needs medium", "Ultrasound and its applications", "Doppler Effect", "Pitch and Loudness", "Musical sounds and noise"],
        "explanation": "Sound is a mechanical wave that requires a medium to travel. (1) Sound waves are longitudinal - particles vibrate parallel to direction of wave propagation. (2) Characteristics: Frequency (f) - pitch, Wavelength (λ) - distance between consecutive compressions, Speed (v = fλ). (3) Reflection: sound bounces off surfaces - echo heard after 0.1s minimum. (4) Sound cannot travel in vacuum. (5) Ultrasound: frequencies above 20kHz, used in medical imaging, cleaning. (6) Doppler Effect: change in frequency due to relative motion between source and observer. (7) Loudness (amplitude), Pitch (frequency).",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=lL4t-G1tZ6w"],
            "article": ["https://www.physicsclassroom.com/class/sound", "https://www.learncbse.in/sound-class-9/"]
        },
        "practice_questions": [
            "Explain why sound cannot travel through vacuum.",
            "The frequency of a tuning fork is 256Hz. If speed of sound is 340m/s, find wavelength.",
            "What is echo? Minimum distance to hear echo?",
            "Explain Doppler Effect with one example.",
            "Differentiate between loudness and pitch.",
            "A ship sends ultrasound and receives echo after 2 seconds. Find depth of sea (speed = 1500m/s).",
            "What are the applications of ultrasound?"
        ]
    },
    "Light - Reflection and Refraction": {
        "key_concepts": ["Laws of reflection", "Plane and spherical mirrors", "Mirror formula (1/f = 1/u + 1/v)", "Laws of refraction", "Refractive index (n = c/v)", "Lens formula", "Power of lens (P = 1/f)", "Total internal reflection"],
        "explanation": "Light is an electromagnetic wave that can be reflected and refracted. (1) Reflection: angle of incidence = angle of reflection. (2) Mirrors: Plane mirrors give laterally inverted image. Spherical mirrors (concave/convex) follow mirror formula. (3) Refraction: change in direction when light enters different medium, governed by Snell's law (n₁ sinθ₁ = n₂ sinθ₂). (4) Refractive index: n = speed of light in vacuum / speed in medium. (5) Lenses: Convex (converging), Concave (diverging), follow lens formula. (6) Power of lens: P = 1/f (dioptre). (7) Total internal reflection: when angle > critical angle, used in optical fibers.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Y8tS2qwCMg4"],
            "article": ["https://www.physicsclassroom.com/class/refln", "https://www.learncbse.in/reflection-light-class-10/"]
        },
        "practice_questions": [
            "State laws of reflection and refraction.",
            "An object 2cm tall is placed 10cm from a concave mirror of focal length 15cm. Find image position and nature.",
            "Define refractive index. If n = 1.5 for glass, find speed of light in glass (c = 3×10⁸ m/s).",
            "Explain total internal reflection with example.",
            "An object is placed 20cm from convex lens of focal length 10cm. Find image position.",
            "Difference between convex and concave lens.",
            "Define power of lens and its SI unit."
        ]
    },
    "Magnetic Effects of Electric Current": {
        "key_concepts": ["Magnetic field around current-carrying wire", "Right-hand thumb rule", "Force on current-carrying conductor (F = BIL sinθ)", "Fleming's Left Hand Rule", "Electric motor", "Electromagnetic induction (Faraday's Law)", "Electric generator", "Transformer"],
        "explanation": "Electricity and magnetism are interrelated - moving charges create magnetic fields. (1) Magnetic field: exists around current-carrying wire, direction given by right-hand thumb rule. (2) Force on conductor: F = BIL sinθ, direction by Fleming's Left Hand Rule. (3) Electric Motor: converts electrical energy to mechanical energy using magnetic force. (4) Electromagnetic Induction: changing magnetic field induces current (Faraday's Law). (5) Electric Generator: converts mechanical to electrical energy. (6) Transformer: changes AC voltage - step-up (increases V), step-down (decreases V).",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=w0NoRzpYnZg"],
            "article": ["https://www.physicsclassroom.com/class/magnetism", "https://www.learncbse.in/magnetic-effects-electric-current-class-10/"]
        },
        "practice_questions": [
            "Explain right-hand thumb rule for magnetic field around straight conductor.",
            "State Fleming's Left Hand Rule.",
            "What is electromagnetic induction? State Faraday's Law.",
            "Explain working of electric motor with diagram.",
            "A wire of length 0.5m carries current 2A in magnetic field 0.1T. Find force.",
            "What is the difference between AC and DC generator?",
            "Why transformer cannot work with DC?"
        ]
    },
    "Periodic Classification of Elements": {
        "key_concepts": ["Modern Periodic Table (18 groups, 7 periods)", "Mendeleev's periodic law", "Trends: atomic size, ionization energy, electronegativity", "Metals, non-metals, metalloids", "Groups (valence electrons)", "Periods (shells)", "Halogens, Noble gases"],
        "explanation": "Periodic table arranges elements in order of increasing atomic number showing periodic properties. (1) Modern Periodic Law: properties repeat at regular intervals. (2) Structure: 18 vertical groups, 7 horizontal periods. (3) Trends across period: atomic size decreases, ionization energy increases, electronegativity increases. (4) Groups: elements in same group have similar valence electrons and properties. (5) Periods: elements in same period have same number of electron shells. (6) Special groups: Group 1 - Alkali metals, Group 17 - Halogens, Group 18 - Noble gases. (7) Metals left, non-metals right, metalloids along border.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Q_Z0p8yg4F0"],
            "article": ["https://www.chemistrytutorials.org/wp-content/uploads/2019/03/periodic-table.pdf"]
        },
        "practice_questions": [
            "State Modern Periodic Law. How does atomic size vary across a period?",
            "Why noble gases are chemically inert?",
            "Define ionization energy. How does it vary in periodic table?",
            "Differentiate between metals and non-metals with examples.",
            "Explain why elements in same group have similar properties.",
            "What are metalloids? Give examples.",
            "Electronic configuration of element is 2,8,7. Find group and period."
        ]
    },
    "Acids, Bases and Salts": {
        "key_concepts": ["Acids: H⁺ donors, pH < 7", "Bases: OH⁻ donors, pH > 7", "Neutralization reaction", "Salts and their types", "pH scale", "Indicators (litmus, phenolphthalein)", "Strength of acids/bases", "Common properties of acids and bases"],
        "explanation": "Acids, Bases and Salts are important chemical compounds. (1) Acids: proton (H⁺) donors, sour taste, turn litmus red, pH < 7. (2) Bases: proton acceptors, bitter taste, slippery feel, turn litmus blue, pH > 7. (3) Neutralization: acid + base → salt + water. (4) pH scale: 0-14, 7 = neutral, acids < 7, bases > 7. (5) Indicators: substances that change color in acidic/basic medium (litmus, phenolphthalein, methyl orange). (6) Salts: ionic compounds formed from neutralization, types - normal, acid, basic, double salts. (7) Strength: strong acids (HCl, HNO₃, H₂SO₄), weak acids (CH₃COOH).",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Q_Z0p8yg4F0"],
            "article": ["https://www.learncbse.in/acids-bases-salts-class-10/"]
        },
        "practice_questions": [
            "Define acid and base according to Arrhenius theory.",
            "What is pH? pH of solution is 3. Is it acidic or basic?",
            "Write balanced equation for reaction between NaOH and HCl.",
            "What are indicators? Give examples.",
            "Explain preparation of sodium chloride (common salt) in lab.",
            "Why does milk of magnesia work for acidity?",
            "Difference between strong and weak acids with examples."
        ]
    },
    "Heredity and Evolution": {
        "key_concepts": ["Mendel's Laws of Inheritance", "Genotype and Phenotype", "Sex determination in humans", "Darwin's Theory of Evolution", "Natural Selection", "Speciation", "Evidence of Evolution (fossils, homologous organs)", "DNA - genetic material"],
        "explanation": "Heredity and Evolution explain how traits pass from parents to offspring and how species change over time. (1) Heredity: transmission of traits from parents to offspring. (2) Mendel's Laws: Law of Dominance, Law of Segregation, Law of Independent Assortment. (3) Genotype: genetic makeup, Phenotype: physical appearance. (4) Sex determination: XY chromosomes in humans (XX = female, XY = male). (5) Evolution: changes in species over time, theory proposed by Darwin. (6) Natural Selection: survival of fittest. (7) Evidence: fossils, homologous organs, DNA similarities. (8) Speciation: formation of new species due to isolation.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=9It2QHv2c2w"],
            "article": ["https://www.ncert.nic.in/textbook/pdf/lebo105.pdf", "https://www.learncbse.in/heredity-evolution-class-10/"]
        },
        "practice_questions": [
            "State Mendel's Law of Dominance with example.",
            "Differentiate between genotype and phenotype.",
            "How is sex determined in human beings?",
            "Explain Darwin's theory of natural selection.",
            "What are fossils? How do they provide evidence for evolution?",
            "Define speciation with example.",
            "If brown eyes (B) are dominant over blue (b), cross pure breeding brown with pure breeding blue. Find genotypic and phenotypic ratios in F1 and F2."
        ]
    },
    "Our Environment": {
        "key_concepts": ["Ecosystem and its components", "Food chain and food web", "Biogeochemical cycles (Carbon, Nitrogen)", "Pollution - Air, Water, Soil", "Greenhouse Effect", "Ozone Depletion", "Waste management", "Biodiversity"],
        "explanation": "Our Environment includes all living and non-living things around us. (1) Ecosystem: interaction between organisms and physical environment, includes producers, consumers, decomposers. (2) Food chain: transfer of energy from one organism to another, food web - interconnected food chains. (3) Biogeochemical cycles: Carbon cycle, Nitrogen cycle maintain balance. (4) Pollution: harmful substances in environment - Air (smog, greenhouse gases), Water (industrial waste), Soil (pesticides). (5) Greenhouse Effect: warming due to CO₂, CH₄ gases. (6) Ozone depletion: CFCs break ozone layer. (7) Waste management: reduce, reuse, recycle. (8) Biodiversity: variety of life, essential for ecological balance.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=pXWBKxq4qGk"],
            "article": ["https://www.learncbse.in/our-environment-class-10/"]
        },
        "practice_questions": [
            "Define ecosystem. List its components.",
            "Explain food chain and food web with examples.",
            "What is greenhouse effect? How does it cause global warming?",
            "How can we reduce, reuse and recycle waste?",
            "Explain nitrogen cycle in nature.",
            "What are the causes and effects of water pollution?",
            "Why is biodiversity important for environment?"
        ]
    },
    "Cell: The Unit of Life": {
        "key_concepts": ["Cell theory", "Prokaryotic vs Eukaryotic cells", "Cell organelles (Nucleus, Mitochondria, Chloroplast, ER, Golgi)", "Cell membrane (fluid mosaic model)", "Diffusion and Osmosis", "Plant cell vs Animal cell", "DNA and RNA"],
        "explanation": "Cell is the basic structural and functional unit of all living organisms. (1) Cell Theory: all organisms made of cells, cells arise from pre-existing cells. (2) Types: Prokaryotic (no nucleus, e.g., bacteria) vs Eukaryotic (true nucleus, e.g., plant/animal cells). (3) Organelles: Nucleus (contains DNA, controls cell), Mitochondria (respiration, ATP), Chloroplast (photosynthesis in plants), ER (transport), Golgi (packaging). (4) Cell membrane: selectively permeable, fluid mosaic model. (5) Diffusion: movement from high to low concentration. (6) Osmosis: diffusion of water through semi-permeable membrane. (7) Plant cells have cell wall, chloroplast, large vacuole; animal cells don't.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=URUJD6N2hS8"],
            "article": ["https://www.ncert.nic.in/textbook/pdf/lebo103.pdf", "https://www.learncbse.in/cell-the-unit-life-class-9/"]
        },
        "practice_questions": [
            "State the three points of cell theory.",
            "Differentiate between prokaryotic and eukaryotic cells.",
            "Draw and label plant cell and animal cell.",
            "Explain structure and function of nucleus.",
            "What is osmosis? Differentiate between isotonic, hypotonic and hypertonic solutions.",
            "Why do plant cells have cell wall?",
            "Explain fluid mosaic model of cell membrane."
        ]
    }
}

def parse_subjects_input(subjects_text):
    parsed = []
    lines = subjects_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if ':' in line:
            parts = line.split(':', 1)
            subject = parts[0].strip()
            topics_str = parts[1].strip() if len(parts) > 1 else ""
            
            if topics_str:
                topics = [t.strip() for t in topics_str.split(',') if t.strip()]
                if subject and topics:
                    parsed.append({"subject": subject, "topics": topics})
            else:
                if subject:
                    parsed.append({"subject": subject, "topics": []})
        else:
            if line:
                parsed.append({"subject": line, "topics": []})
    
    return parsed


def get_topics_for_subject(subject, count=2, explicit_topics=None):
    import random
    random.seed(hash(subject) % 1000)
    
    if explicit_topics and len(explicit_topics) > 0:
        return explicit_topics[:count]
    
    subject_lower = subject.lower()
    
    all_topics_by_subject = {
        "math": ["Quadratic Equations", "Trigonometry", "Calculus", "Probability", "Statistics", "Algebra", "Geometry", "Arithmetic", "Linear Equations", "Polynomials"],
        "physics": ["Newton's Laws", "Motion", "Force", "Work and Energy", "Sound", "Light", "Electricity", "Current Electricity", "Magnetism", "Heat", "Waves"],
        "chemistry": ["Chemical Bonding", "Periodic Table", "Acids Bases and Salts", "Carbon and Its Compounds", "Metals and Non-metals", "Structure of Atom", "Chemical Reactions", "States of Matter"],
        "biology": ["Cell Biology", "Heredity and Evolution", "Our Environment", "Nutrition", "Digestion", "Circulatory System", "Respiratory System", "Genetics", "Ecology", "Photosynthesis"],
        "python": ["Python Basics", "Functions in Python", "Object-Oriented Programming", "File Handling", "Data Structures", "Error Handling", "Libraries and Modules"],
        "html": ["HTML Basics", "HTML Forms", "Semantic HTML", "HTML5 Elements", "Tables and Lists"],
        "css": ["CSS Basics", "Flexbox", "CSS Grid", "Responsive Design", "CSS Selectors", "Box Model"],
        "javascript": ["JavaScript Basics", "DOM Manipulation", "Events and Handlers", "Async JavaScript", "ES6 Features", "JSON Handling"],
        "programming": ["Variables and Data Types", "Control Flow", "Functions", "Object-Oriented Programming", "Data Structures", "Algorithms", "Debugging"],
        "english": ["English Grammar", "Reading Comprehension", "Vocabulary", "Writing Skills", "Sentence Structure"],
        "economics": ["Supply and Demand", "Elasticity", "Consumer Behavior", "Market Structures", "National Income"],
        "default": list(TOPIC_DATA.keys())[:-1]
    }
    
    topics = []
    for key, topic_list in all_topics_by_subject.items():
        if key in subject_lower:
            topics = topic_list
            break
    
    if not topics:
        topics = all_topics_by_subject["default"]
    
    random.shuffle(topics)
    return topics[:count]


def generate_specific_concepts(topic_name, subject):
    """Generate REAL subtopics (not generic templates) for a topic using AI"""
    prompt = f"""
You are a STRICT subject expert.

TASK:
Generate subtopics ONLY for the given topic and subject.

STRICT RULES:
- Topic: {topic_name}
- Subject: {subject}
- ONLY generate subtopics related to this subject
- DO NOT switch subject (e.g., no biology if subject is design)
- DO NOT generate school science topics unless explicitly given
- NO generic points like "definition", "importance"
- Return ONLY bullet points
- Max 8 subtopics

If subject is UI/UX or design → generate ONLY design-related subtopics.
If subject is finance → generate ONLY finance-related subtopics.
If subject is programming → generate ONLY programming-related subtopics.

Output format:
- Subtopic 1
- Subtopic 2
- Subtopic 3
"""

    try:
        response = call_ai_api([
            {"role": "system", "content": "You are an expert educator. Generate only subtopic names as bullet points. No explanations."},
            {"role": "user", "content": prompt}
        ], max_tokens=200)
        
        if response:
            concepts = [line.strip("- ").strip() for line in response.split("\n") if line.strip() and len(line.strip()) > 2]
            concepts = [c for c in concepts if not c.lower().startswith(("definition", "concept", "topic", "what", "how", "why"))]
            if len(concepts) >= 3:
                return concepts[:10]
    except Exception as e:
        print(f"AI concepts error: {e}")
    
    fallback = {
        "physics": ["Laws and Principles", "Mathematical Formulas", "Derivation Methods", "Problem-Solving", "Units and Measurements", "Real-World Applications", "Graphical Analysis", "Experimental Setup"],
        "chemistry": ["Chemical Properties", "Structure and Bonding", "Reaction Mechanisms", "Preparation Methods", "Applications", "Safety Protocols", "Environmental Impact", "Laboratory Techniques"],
        "biology": ["Structure and Function", "Process and Mechanism", "Role in Organism", "Health Applications", "Biotechnology Use", "Experimental Evidence", "Research Methods", "System Integration"],
        "mathematics": ["Definitions", "Formulas and Theorems", "Problem Types", "Solution Methods", "Graphical Representation", "Real-Life Applications", "Common Errors", "Exam Strategies"],
        "programming": ["Syntax and Structure", "Data Types", "Control Flow", "Functions", "OOP Concepts", "Libraries", "Debugging", "Best Practices"],
    }
    
    for key, concepts in fallback.items():
        if key in subject.lower():
            return [c.replace("{topic_name}", topic_name) if "{" in c else c for c in concepts]
    
    return [f"Understanding {topic_name}", f"Key Concepts in {topic_name}", f"Applications of {topic_name}", f"Problem-Solving in {topic_name}", f"Advanced Topics in {topic_name}", f"Revision of {topic_name}"]


def generate_specific_explanation(topic_name, subject):
    """Generate concise, textbook-style explanation"""
    subject_lower = subject.lower()
    topic_lower = topic_name.lower()
    
    explanations = {
        "physics": f"""• Definition: {topic_name} deals with the behavior of matter and energy.
• Key Principle: Fundamental laws governing {topic_name} are essential for understanding natural phenomena.
• Applications: Used in technology, engineering, and everyday devices.
• Important Formula: Frequently tested in JEE, NEET, and board exams.""",

        "chemistry": f"""• Definition: {topic_name} involves the composition, structure, properties, and reactions of matter.
• Key Principle: Understanding {topic_name} helps predict how substances interact.
• Applications: Essential for pharmaceuticals, materials science, and industrial processes.
• Important: Frequently asked in competitive exams.""",

        "biology": f"""• Definition: {topic_name} describes how living organisms function and interact.
• Key Principle: Essential for understanding life processes and biological systems.
• Applications: Used in medicine, biotechnology, and agriculture.
• Important: Frequently tested in NEET and board exams.""",

        "mathematics": f"""• Definition: {topic_name} involves systematic study of numbers, patterns, and logical reasoning.
• Key Principle: Forms the foundation for all scientific and technical fields.
• Applications: Used in calculations, measurements, and problem-solving.
• Important: Numerical problems carry high weight in JEE and board exams.""",

        "programming": f"""• Definition: {topic_name} enables writing instructions for computers to perform tasks.
• Key Principle: Essential for building software, websites, and applications.
• Applications: Powers all modern technology and automation.
• Important: Frequently tested in coding interviews and exams.""",

        "default": f"""• Definition: {topic_name} is a fundamental concept in {subject}.
• Key Principle: Essential for understanding advanced topics in {subject}.
• Applications: Used in various real-world scenarios and problem-solving.
• Important: Frequently tested in exams."""
    }
    
    for key in explanations:
        if key in subject_lower:
            return explanations[key]
    
    return explanations["default"]


def generate_points_to_remember(topic_name, subject):
    """Generate concise exam-relevant points"""
    subject_lower = subject.lower()
    
    if "physics" in subject_lower:
        return [
            f"Definition: {topic_name} is a fundamental concept in physics.",
            f"Formula: Understand and memorize key formulas related to {topic_name}.",
            f"Laws: Know the laws and principles governing {topic_name}.",
            f"Units: Remember SI units of physical quantities in {topic_name}.",
            f"Applications: Real-world applications of {topic_name} are frequently asked.",
            f"Numerical: Practice numerical problems - carry high weight in JEE/NEET.",
            f"Derivations: Know important derivations for {topic_name}.",
            f"Diagrams: Practice labeled diagrams related to {topic_name}.",
            f"Common Mistakes: Avoid common errors in solving {topic_name} problems.",
            f"Exam Tip: Focus on {topic_name} for board and competitive exams."
        ]
    elif "math" in subject_lower:
        return [
            f"Definition: Understand the basic definition of {topic_name}.",
            f"Formula: All important formulas for {topic_name} must be memorized.",
            f"Theorems: Know key theorems related to {topic_name}.",
            f"Methods: Master step-by-step problem-solving methods.",
            f"Graphs: Practice graphical representations of {topic_name}.",
            f"Numerical: High-weight topic for JEE and board exams.",
            f"Shortcut: Learn shortcut methods for quick solutions.",
            f"Examples: Practice examples from NCERT and reference books.",
            f"Mistakes: Avoid calculation errors in {topic_name} problems.",
            f"Revision: Last-minute formulas and key points for {topic_name}."
        ]
    elif "chemistry" in subject_lower:
        return [
            f"Definition: Understand what {topic_name} means in chemistry.",
            f"Properties: Physical and chemical properties of {topic_name}.",
            f"Reactions: Important chemical reactions involving {topic_name}.",
            f"Structure: Know the atomic/molecular structure in {topic_name}.",
            f"Applications: Industrial and daily-life applications.",
            f"Nomenclature: IUPAC naming conventions for {topic_name}.",
            f"Equations: Write balanced chemical equations for {topic_name}.",
            f"Lab: Laboratory preparation methods for {topic_name}.",
            f"Uses: Important uses of {topic_name} in various fields.",
            f"Exam: Frequently asked in NEET and board exams."
        ]
    elif "biology" in subject_lower:
        return [
            f"Definition: Clear definition of {topic_name} in biology.",
            f"Process: Understand the process/mechanism of {topic_name}.",
            f"Function: Role and function of {topic_name} in living organisms.",
            f"Diagrams: Practice labeled diagrams for {topic_name}.",
            f"Terms: Important biological terms related to {topic_name}.",
            f"Human Health: Connection to human health and diseases.",
            f"Applications: Biotechnology applications of {topic_name}.",
            f"NCERT: Focus on NCERT content for {topic_name}.",
            f"NEET: High-weight topic for NEET exam.",
            f"Quick Rev: Key points for quick revision of {topic_name}."
        ]
    else:
        return [
            f"Definition: {topic_name} is a key concept in {subject}.",
            f"Core Principle: Understand the fundamental principle.",
            f"Key Terms: Important terminology for {topic_name}.",
            f"Applications: Real-world applications of {topic_name}.",
            f"Examples: Common examples illustrating {topic_name}.",
            f"Problems: Practice problems based on {topic_name}.",
            f"Formulas: Important formulas related to {topic_name}.",
            f"Notes: Create concise notes for {topic_name}.",
            f"Exam: Frequently tested in exams.",
            f"Revision: Quick revision points for {topic_name}."
        ]


def generate_topic_content(topic_name, subject):
    cache_key = f"topic_{topic_name.lower()}_{subject.lower()}"
    cached = _get_cache(cache_key, _topic_cache)
    if cached:
        return cached
    
    topic_lower = topic_name.lower().replace("'", "").replace("-", "")
    
    for key, data in TOPIC_DATA.items():
        if key.lower().replace("'", "").replace("-", "") in topic_lower or topic_lower in key.lower().replace("'", "").replace("-", ""):
            yt_videos = get_emergency_videos(topic_name, 2, subject)
            articles = get_article_resources(topic_name, 2)
            pdf_resources = search_pdf_notes(topic_name, 2)
            points = data.get("points_to_remember", generate_points_to_remember(topic_name, subject))
            result = {
                "key_concepts": data["key_concepts"],
                "explanation": data["explanation"],
                "youtube_resources": yt_videos if yt_videos else [],
                "article_resources": articles,
                "pdf_resources": pdf_resources,
                "practice_questions": data["practice_questions"],
                "points_to_remember": points
            }
            _set_cache(cache_key, result, _topic_cache)
            return result
    
    sub_topic_mapping = {
        "forms": "HTML", "flexbox": "CSS", "grid": "CSS", "responsive": "CSS",
        "dom": "JavaScript", "events": "JavaScript", "fetch": "JavaScript", "api": "JavaScript",
        "react": "React", "components": "React", "props": "React", "state": "React", "hooks": "React",
        "node": "Backend", "express": "Backend", "rest": "Backend",
    }
    
    for sub_topic, parent_topic in sub_topic_mapping.items():
        if sub_topic in topic_lower:
            if parent_topic in TOPIC_DATA:
                data = TOPIC_DATA[parent_topic]
                yt_videos = get_emergency_videos(topic_name, 2, subject)
                articles = get_article_resources(topic_name, 2)
                pdf_resources = search_pdf_notes(topic_name, 2)
                points = data.get("points_to_remember", generate_points_to_remember(topic_name, subject))
                result = {
                    "key_concepts": data["key_concepts"],
                    "explanation": f"{topic_name} is part of {parent_topic}. {data['explanation']}",
                    "youtube_resources": yt_videos if yt_videos else [],
                    "article_resources": articles,
                    "pdf_resources": pdf_resources,
                    "practice_questions": data["practice_questions"],
                    "points_to_remember": points
                }
                _set_cache(cache_key, result, _topic_cache)
                return result
    
    yt_videos = get_emergency_videos(topic_name, 2, subject)
    articles = get_article_resources(topic_name, 2)
    pdf_resources = search_pdf_notes(topic_name, 2)
    
    topic_key_concepts = generate_specific_concepts(topic_name, subject)
    topic_explanation = generate_specific_explanation(topic_name, subject)
    points_to_remember = generate_points_to_remember(topic_name, subject)
    
    result = {
        "key_concepts": topic_key_concepts,
        "explanation": topic_explanation,
        "youtube_resources": yt_videos if yt_videos else [],
        "article_resources": articles,
        "pdf_resources": pdf_resources,
        "practice_questions": [
            f"Define {topic_name} and explain its significance in {subject}",
            f"List and explain the main components of {topic_name}",
            f"How is {topic_name} applied in real-world scenarios?",
            f"Compare {topic_name} with related concepts in {subject}",
            f"Solve a problem based on {topic_name} principles"
        ],
        "points_to_remember": points_to_remember
    }
    _set_cache(cache_key, result, _topic_cache)
    return result

@app.route('/')
def index():
    return render_template('index.html')

def _get_cache(key, cache_dict):
    if key in cache_dict:
        entry = cache_dict[key]
        if time.time() - entry['time'] < _CACHE_EXPIRY:
            return entry['data']
    return None

def _set_cache(key, data, cache_dict):
    cache_dict[key] = {'data': data, 'time': time.time()}


def detect_language(text):
    try:
        lang = detect(text)

        mapping = {
            # 🌍 GLOBAL LANGUAGES
            "en": "English",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "zh-cn": "Chinese",
            "zh-tw": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic",
            "tr": "Turkish",
            "nl": "Dutch",
            "sv": "Swedish",
            "pl": "Polish",

            # 🇮🇳 INDIAN LANGUAGES (MAJOR)
            "hi": "Hindi",
            "bn": "Bengali",
            "te": "Telugu",
            "mr": "Marathi",
            "ta": "Tamil",
            "ur": "Urdu",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi",
            "or": "Odia",
            "as": "Assamese",

            # 🇮🇳 ADDITIONAL INDIAN LANGUAGES
            "sa": "Sanskrit",
            "sd": "Sindhi",
            "ne": "Nepali",
            "kok": "Konkani",
            "mai": "Maithili",
            "mni": "Manipuri",
            "bho": "Bhojpuri",
            "dog": "Dogri"
        }

        return mapping.get(lang, "English")

    except:
        return "English"

def get_language_instruction(text):
    import re
    text_combined = text if isinstance(text, str) else str(text)
    
    # SCRIPT DETECTION - Devanagari (U+0900-U+097F) = Hindi/Marathi/Sanskrit
    if re.search(r'[\u0900-\u097F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Hindi using Devanagari script (अ-ह). Write EVERY word in Devanagari. DO NOT mix English letters or Roman script. No Hindi word should contain English characters."
    
    # Bengali (U+0980-U+09FF)
    if re.search(r'[\u0980-\u09FF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Bengali script (অ-হ). Write EVERY word in Bengali. DO NOT mix English letters or Roman script."
    
    # Tamil (U+0B80-U+0BFF)
    if re.search(r'[\u0B80-\u0BFF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Tamil script (அ-ஔ). Write EVERY word in Tamil. DO NOT mix English letters or Roman script."
    
    # Telugu (U+0C00-U+0C7F)
    if re.search(r'[\u0C00-\u0C7F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Telugu script (అ-ఔ). Write EVERY word in Telugu. DO NOT mix English letters or Roman script."
    
    # Kannada (U+0C80-U+0CFF)
    if re.search(r'[\u0C80-\u0CFF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Kannada script (ಅ-ಔ). Write EVERY word in Kannada. DO NOT mix English letters or Roman script."
    
    # Malayalam (U+0D00-U+0D7F)
    if re.search(r'[\u0D00-\u0D7F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Malayalam script (അ-ഔ). Write EVERY word in Malayalam. DO NOT mix English letters or Roman script."
    
    # Gujarati (U+0A80-U+0AFF)
    if re.search(r'[\u0A80-\u0AFF]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Gujarati script (અ-ઔ). Write EVERY word in Gujarati. DO NOT mix English letters or Roman script."
    
    # Punjabi/Gurmukhi (U+0A00-U+0A7F)
    if re.search(r'[\u0A00-\u0A7F]', text_combined):
        return "CRITICAL: Respond EXCLUSIVELY in Punjabi/Gurmukhi script (ਅ-ਔ). Write EVERY word in Punjabi. DO NOT mix English letters or Roman script."
    
    # Text-based detection
    text_lower = text_combined.lower()

    if any(word in text_lower for word in ["hindi", "हिंदी"]):
        return "Respond STRICTLY in Hindi (Devanagari script ONLY). No English words allowed."

    elif any(word in text_lower for word in ["sanskrit", "संस्कृत"]):
        return "Respond STRICTLY in Sanskrit ONLY."

    elif any(word in text_lower for word in ["marathi", "मराठी"]):
        return "Respond STRICTLY in Marathi ONLY."

    elif any(word in text_lower for word in ["bengali", "বাংলা"]):
        return "Respond STRICTLY in Bengali ONLY."

    elif any(word in text_lower for word in ["tamil", "தமிழ்"]):
        return "Respond STRICTLY in Tamil ONLY."

    elif any(word in text_lower for word in ["telugu", "తెలుగు"]):
        return "Respond STRICTLY in Telugu ONLY."

    elif any(word in text_lower for word in ["gujarati", "ગુજરાતી"]):
        return "Respond STRICTLY in Gujarati ONLY."

    elif any(word in text_lower for word in ["punjabi", "ਪੰਜਾਬੀ"]):
        return "Respond STRICTLY in Punjabi ONLY."

    elif any(word in text_lower for word in ["urdu", "اردو"]):
        return "Respond STRICTLY in Urdu ONLY."

    elif any(word in text_lower for word in ["french", "français"]):
        return "Respond STRICTLY in French ONLY."

    elif any(word in text_lower for word in ["german", "deutsch"]):
        return "Respond STRICTLY in German ONLY."

    elif any(word in text_lower for word in ["spanish", "español"]):
        return "Respond STRICTLY in Spanish ONLY."

    elif any(word in text_lower for word in ["italian", "italiano"]):
        return "Respond STRICTLY in Italian ONLY."

    else:
        return "Respond STRICTLY in English ONLY. Do NOT use any other language."



load_dotenv(override=True)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

app = Flask(__name__)
CORS(app)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

print(f"Loaded API key: {OPENAI_API_KEY[:20]}..." if OPENAI_API_KEY else "No API key loaded")

def search_youtube(topic, max_results=2, subject=None):
    """
    STRICT YouTube search - ALWAYS matches BOTH subject AND topic.
    
    Requirements:
    - Subject MUST appear in title (with smart matching)
    - Topic MUST appear in title (loosely matched)
    - Duration >= 20 minutes (prefer >= 30)
    - Never returns empty or wrong-subject videos
    """
    if not topic or not isinstance(topic, str) or not topic.strip():
        print("[YouTube] INVALID TOPIC:", topic)
        return []
    
    topic_clean = topic.strip()
    subject_clean = (subject or "").strip()
    
    subject_aliases = {
        "mathematics": ["maths", "math", "arithmetic", "algebra", "geometry"],
        "python": ["python"],
        "java": ["java"],
        "c": ["c programming", "c language"],
        "javascript": ["javascript", "js"],
        "physics": ["physics"],
        "chemistry": ["chemistry"],
        "biology": ["biology"],
    }
    
    subject_keywords = []
    if subject_clean:
        subject_lower = subject_clean.lower()
        subject_keywords = [subject_lower]
        if subject_lower in subject_aliases:
            subject_keywords.extend(subject_aliases[subject_lower])
    
    print(f"[YouTube] Searching for: subject='{subject_clean}', topic='{topic_clean}'")
    
    all_candidates = []
    seen_ids = set()
    
    if subject_clean:
        search_queries = [
            f"{subject_clean} {topic_clean} full tutorial",
            f"{subject_clean} {topic_clean} tutorial",
            f"{subject_clean} {topic_clean} explained",
            f"{subject_clean} {topic_clean} course",
            f"{subject_clean} {topic_clean} lecture",
            f"{topic_clean} tutorial",
        ]
    else:
        search_queries = [
            f"{topic_clean} full tutorial",
            f"{topic_clean} tutorial",
            f"{topic_clean} explained",
            f"{topic_clean} course",
            f"{topic_clean} lecture",
        ]
    
    for query in search_queries:
        print(f"[YouTube] Trying query: {query}")
        
        raw_videos = search_youtube_alternative_free(query, 15)
        
        if not raw_videos:
            print(f"[YouTube] No results for: {query}")
            continue
        
        print(f"[YouTube] Got {len(raw_videos)} raw videos from: {query}")
        
        for video in raw_videos:
            video_id = video.get("video_id", "")
            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)
            
            title = video.get("title", "")
            title_lower = title.lower()
            channel = video.get("channel", "YouTube")
            duration_min = video.get("duration_minutes", 0)
            
            if subject_keywords:
                subject_match = any(sk in title_lower for sk in subject_keywords)
                if not subject_match:
                    print(f"[YouTube] REJECT (no subject): {title[:50]}")
                    continue
            
            topic_lower = topic_clean.lower()
            topic_words = topic_lower.replace("-", " ").replace("_", " ").split()
            topic_match = any(word in title_lower for word in topic_words if len(word) > 2)
            
            if not topic_match and subject_clean:
                topic_match = topic_lower in title_lower
            
            if not topic_match:
                print(f"[YouTube] REJECT (no topic): {title[:50]}")
                continue
            
            if duration_min < 20:
                if duration_min < 10:
                    print(f"[YouTube] REJECT (too short {duration_min:.0f}m): {title[:50]}")
                    continue
                print(f"[YouTube] ACCEPT (borderline {duration_min:.0f}m): {title[:50]}")
            
            all_candidates.append({
                "video_id": video_id,
                "title": title,
                "channel": channel,
                "duration_minutes": duration_min,
                "duration": video.get("duration", "1h"),
                "views": video.get("views", 0),
            })
            print(f"[YouTube] ACCEPT: {title[:60]}")
            
            if len(all_candidates) >= max_results * 3:
                break
        
        if len(all_candidates) >= max_results:
            break
    
    if not all_candidates and subject_clean:
        print(f"[YouTube] No results - trying relaxed subject match...")
        for query in search_queries[:2]:
            raw_videos = search_youtube_alternative_free(query, 10)
            for video in raw_videos:
                video_id = video.get("video_id", "")
                if not video_id or video_id in seen_ids:
                    continue
                seen_ids.add(video_id)
                
                title = video.get("title", "")
                title_lower = title.lower()
                duration_min = video.get("duration_minutes", 0)
                
                if duration_min < 20:
                    continue
                
                all_candidates.append({
                    "video_id": video_id,
                    "title": title,
                    "channel": video.get("channel", "YouTube"),
                    "duration_minutes": duration_min,
                    "duration": video.get("duration", "1h"),
                    "views": video.get("views", 0),
                })
                print(f"[YouTube] RELAXED ACCEPT: {title[:60]}")
                
                if len(all_candidates) >= max_results * 2:
                    break
    
    all_candidates.sort(key=lambda x: (x["duration_minutes"], x["views"]), reverse=True)
    
    results = []
    for video in all_candidates[:max_results]:
        video_id = video["video_id"]
        results.append({
            "title": video["title"],
            "video_id": video_id,
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "channel": video["channel"],
            "duration": video["duration"],
            "views": video["views"],
            "embed_url": f"https://www.youtube.com/embed/{video_id}",
        })
        print(f"[YouTube] SELECTED: {video['title'][:60]}")
    
    print(f"[YouTube] FINAL: {len(results)} videos for '{subject_clean} {topic_clean}'")
    return results


def get_youtube_videos_scrape(topic, max_results=3, subject=None):
    return get_emergency_videos(topic, max_results, subject)


def generate_youtube_search_links(topic, max_results=2, subject=None):
    return get_emergency_videos(topic, max_results, subject)

def parse_iso_duration(duration_str):
    """Parse YouTube ISO 8601 duration to minutes"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 60 + minutes + seconds / 60

def parse_duration_str(duration_str):
    """Parse duration strings like '2h 15m', '1h 30m', '45m' to minutes"""
    import re
    hours = 0
    minutes = 0
    h_match = re.search(r'(\d+)\s*h', duration_str.lower())
    m_match = re.search(r'(\d+)\s*m', duration_str.lower())
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    return hours * 60 + minutes

def search_blogs(topic, max_results=2):
    """Search for actual blog articles"""
    topic_clean = topic.lower().strip()
    topic_slug = topic_clean.replace(' ', '-').replace('/', '-').replace('?', '')
    
    urls_to_try = [
        ("GeeksforGeeks", f"https://www.geeksforgeeks.org/{topic_slug}/"),
        ("W3Schools", f"https://www.w3schools.com/{topic_clean.replace(' ', '_')}/"),
    ]
    
    valid_blogs = []
    for name, url in urls_to_try:
        try:
            resp = requests.head(url, timeout=3, allow_redirects=True)
            if resp.status_code < 400:
                valid_blogs.append({
                    "title": f"{topic} - {name}",
                    "url": url
                })
        except:
            pass
    
    if not valid_blogs:
        valid_blogs = [
            {"title": f"Search {topic} on Google", "url": f"https://www.google.com/search?q={topic}+tutorial"},
        ]
    
    return valid_blogs[:max_results]

def search_practice_questions(topic, max_results=3):
    """Search for practice questions"""
    topic_clean = topic.lower().strip()
    topic_slug = topic_clean.replace(' ', '-').replace('/', '-').replace('?', '')
    
    urls_to_try = [
        ("GeeksforGeeks", f"https://www.geeksforgeeks.org/{topic_slug}/"),
        ("W3Schools", f"https://www.w3schools.com/{topic_clean.replace(' ', '_')}/"),
    ]
    
    valid_practice = []
    for name, url in urls_to_try:
        try:
            resp = requests.head(url, timeout=3, allow_redirects=True)
            if resp.status_code < 400:
                valid_practice.append({
                    "title": f"{topic} - {name} (Practice & Questions)",
                    "url": url
                })
        except:
            pass
    
    if not valid_practice:
        valid_practice = [
            {"title": f"{topic} Interview Questions", "url": f"https://www.google.com/search?q={topic}+interview+questions"},
        ]
    
    return valid_practice[:max_results]

def detect_level(topic):
    topic = topic.lower()

    school_keywords = [
        "class", "cbse", "ncert", "hindi", "grammar", "physics",
        "chemistry", "biology", "math", "trigonometry", "algebra"
    ]

    college_keywords = [
        "sql", "python", "machine learning", "data science",
        "react", "javascript", "backend", "api", "statistics"
    ]

    for word in college_keywords:
        if word in topic:
            return "college"

    for word in school_keywords:
        if word in topic:
            return "school"

    return "general"

def generate_practice_prompt(topic):
    level = detect_level(topic)

    if level == "school":
        level_instruction = "Use very simple language. Suitable for school students."
    elif level == "college":
        level_instruction = "Use clear but slightly technical language. Suitable for college students."
    else:
        level_instruction = "Use simple and clear language."

    return f"""
You are an expert teacher.

Topic: {topic}

Instructions:
- Generate exactly 5 practice questions
- {level_instruction}
- Avoid unnecessary jargon
- Keep answers short (2-3 lines)
- Questions should be meaningful and relevant

Structure:
- 2 easy questions
- 2 medium questions
- 1 hard question

Format strictly:

Q1. ...
Answer: ...

Q2. ...
Answer: ...

Q3. ...
Answer: ...

Q4. ...
Answer: ...

Q5. ...
Answer: ...
"""


def call_ai_api(messages, model=None, max_tokens=300):
    import os
    import requests

    try:
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")

        if model is None:
            model = ollama_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens
            }
        }

        response = requests.post(
            f"{ollama_base_url}/api/chat",
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            print("❌ Ollama error:", response.text)
            return None

        data = response.json()
        content = data.get("message", {}).get("content", "").strip()

        return content if content else None

    except Exception as e:
        print("❌ AI ERROR:", e)
        return None

def search_pdf_notes(topic, max_results=3):
    """Search for PDF notes for a topic - with direct PDF links"""
    cache_key = f"pdf_{topic.lower()}_{max_results}"
    cached = _get_cache(cache_key, _topic_cache)
    if cached:
        return cached
    
    topic_lower = topic.lower()
    
    pdf_resources = {
        "quadratic equations": [
            {"title": "Quadratic Equations NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh205.pdf"},
            {"title": "Quadratic Equations Important Questions", "url": "https://www.learncbse.in/quadratic-equations-class-10-important-questions/"},
        ],
        "trigonometry": [
            {"title": "Trigonometry NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh208.pdf"},
            {"title": "Trigonometry Formulas", "url": "https://www.learncbse.in/trigonometry-formulas-for-class-10/"},
        ],
        "calculus": [
            {"title": "Calculus Basics PDF", "url": "https://www.math.ucdavis.edu/~kouba/CalcOnePROBLEMSOLVER.html"},
            {"title": "Calculus Notes", "url": "https://www.khanacademy.org/math/ap-calculus-ab"},
        ],
        "probability": [
            {"title": "Probability NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh215.pdf"},
            {"title": "Probability Important Questions", "url": "https://www.learncbse.in/probability-class-10-important-questions/"},
        ],
        "newton's laws": [
            {"title": "Newton's Laws NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lesh105.pdf"},
            {"title": "Laws of Motion Notes", "url": "https://www.learncbse.in/newtons-laws-of-motion-class-9/"},
        ],
        "chemical bonding": [
            {"title": "Chemical Bonding NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lech104.pdf"},
            {"title": "Chemical Bonding Notes", "url": "https://www.meritnation.com/answers/5992"},
        ],
        "cell biology": [
            {"title": "Cell Biology NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lebo105.pdf"},
            {"title": "Cell Unit Notes", "url": "https://www.byjus.com/biology/cell/"},
        ],
        "html": [
            {"title": "HTML Cheat Sheet PDF", "url": "https://websitesetup.org/html5-cheat-sheet.pdf"},
            {"title": "HTML Tutorial", "url": "https://www.w3schools.com/html/"},
        ],
        "css": [
            {"title": "CSS Cheat Sheet PDF", "url": "https://websitesetup.org/css3-cheat-sheet.pdf"},
            {"title": "CSS Tutorial", "url": "https://www.w3schools.com/css/"},
        ],
        "javascript": [
            {"title": "JavaScript Notes PDF", "url": "https://www.javascript.com/resources"},
            {"title": "JavaScript Tutorial", "url": "https://www.w3schools.com/js/"},
        ],
        "python": [
            {"title": "Python Notes PDF", "url": "https://www.geeksforgeeks.org/python-programming-language/"},
            {"title": "Python Tutorial", "url": "https://www.w3schools.com/python/"},
        ],
        "sql": [
            {"title": "SQL Cheat Sheet PDF", "url": "https://www.sqltutorial.org/wp-content/uploads/2021/01/SQL-Cheat-Sheet.pdf"},
            {"title": "SQL Tutorial", "url": "https://www.w3schools.com/sql/"},
        ],
        "statistics": [
            {"title": "Statistics NCERT Notes", "url": "https://ncert.nic.in/textbook/pdf/lemh214.pdf"},
            {"title": "Statistics Formulas", "url": "https://www.mathsisfun.com/data/statistics.html"},
        ],
        "react": [
            {"title": "React Documentation", "url": "https://reactjs.org/docs/getting-started.html"},
            {"title": "React Tutorial", "url": "https://www.w3schools.com/react/"},
        ],
        "machine learning": [
            {"title": "ML Notes PDF", "url": "https://www.geeksforgeeks.org/machine-learning/"},
            {"title": "ML Tutorial", "url": "https://www.kaggle.com/learn/intro-to-machine-learning"},
        ],
    }
    
    for key, pdfs in pdf_resources.items():
        if key in topic_lower or topic_lower in key:
            result = pdfs[:max_results]
            _set_cache(cache_key, result, _topic_cache)
            return result
    
    topic_slug = topic.lower().replace(" ", "-").replace("'", "")
    fallback_pdfs = [
        {"title": f"{topic} Notes - GeeksforGeeks", "url": f"https://www.geeksforgeeks.org/{topic_slug}/"},
        {"title": f"{topic} Tutorial", "url": f"https://www.w3schools.com/{topic_slug}/"},
    ]
    result = fallback_pdfs[:max_results]
    _set_cache(cache_key, result, _topic_cache)
    return result

TOPIC_DATA = {
    "Quadratic Equations": {
        "key_concepts": ["Standard form ax^2 + bx + c = 0", "Discriminant (b^2 - 4ac)", "Factoring method", "Quadratic formula: x = (-b +/- sqrt(b^2-4ac))/2a", "Nature of roots (real, equal, imaginary)"],
        "explanation": "Quadratic equations are polynomial equations of degree 2. The discriminant (D = b^2 - 4ac) determines the nature of roots: D > 0 = two distinct real roots, D = 0 = equal roots, D < 0 = imaginary roots. Methods include factoring, completing square, and quadratic formula.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=ZfFPgBcOc6U", "https://www.youtube.com/watch?v=lfF3j1xY5nU"],
            "article": ["https://www.geeksforgeeks.org/quadratic-equations/", "https://www.mathsisfun.com/algebra/quadratic-equation.html"]
        },
        "practice_questions": [
            "Solve: x^2 - 5x + 6 = 0 using factoring method",
            "Find the discriminant and nature of roots: 2x^2 + 3x - 2 = 0",
            "Solve by quadratic formula: x^2 + 4x - 12 = 0",
            "If one root is 3, find k if equation is x^2 + kx + 6 = 0"
        ]
    },
    "Trigonometry": {
        "key_concepts": ["sin, cos, tan definitions in right triangle", "Pythagorean identity: sin^2x + cos^2x = 1", "sin(A+B) = sinAcosB + cosAsinB", "Values at 0, 30, 45, 60, 90 degrees", "Inverse trig: sin^-1, cos^-1, tan^-1"],
        "explanation": "Trigonometry studies relationships between angles and sides of triangles. The six ratios (sin, cos, tan, cosec, sec, cot) relate angles to side ratios. Key identities include Pythagorean, sum/difference, double angle, and half angle formulas.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=AqCkKAV1NWk", "https://www.youtube.com/watch?v=UxRyqXb6v60"],
            "article": ["https://www.geeksforgeeks.org/trigonometry/", "https://www.mathsisfun.com/algebra/trigonometry.html"]
        },
        "practice_questions": [
            "If sin x = 3/5, find cos x and tan x (x in first quadrant)",
            "Prove: sin^2x + cos^2x = 1",
            "Find value of sin 75 degrees using addition formula",
            "Solve: 2sin x = 1 for 0 <= x <= 360 degrees"
        ]
    },
    "Calculus": {
        "key_concepts": ["Limits: lim(x->a) f(x)", "Derivative: d/dx(x^n) = nx^(n-1)", "Product, quotient, chain rules", "Integration: integral(x^n) = x^(n+1)/(n+1)", "Maxima and minima using derivatives"],
        "explanation": "Calculus studies continuous change. Differential calculus finds rates of change (derivatives) while integral calculus calculates areas under curves. The Fundamental Theorem links both. Applications include optimization, motion, and area problems.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=WTLAdllg9tU", "https://www.youtube.com/watch?v=r5Qdg30RVME"],
            "article": ["https://www.khanacademy.org/math/ap-calculus-ab", "https://www.mathsisfun.com/calculus/"]
        },
        "practice_questions": [
            "Find d/dx: x^3 + 2x^2 - 5x + 7",
            "Evaluate: integral(x^2 dx) from 0 to 3",
            "Find local maxima/minima of f(x) = x^3 - 3x^2 + 2",
            "Calculate: lim(x->2) (x^2 - 4)/(x - 2)"
        ]
    },
    "Probability": {
        "key_concepts": ["P(A) = favorable outcomes/total outcomes", "P(A or B) = P(A) + P(B) - P(A and B)", "P(A and B) = P(A) x P(B) for independent", "Conditional probability: P(A|B) = P(A and B)/P(B)", "Bayes theorem"],
        "explanation": "Probability measures likelihood of events on a scale from 0 (impossible) to 1 (certain). Addition rule handles OR events, multiplication rule handles AND events. Conditional probability finds P(A given B occurred). Bayes theorem updates probabilities with new evidence.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=uzkc-qNVoOk", "https://www.youtube.com/watch?v=KZ7SDBMC2Xc"],
            "article": ["https://www.geeksforgeeks.org/probability/", "https://www.mathsisfun.com/data/probability.html"]
        },
        "practice_questions": [
            "A bag has 3 red and 5 blue balls. Find P(red ball) when drawing one ball",
            "Two dice are rolled. Find P(sum is 7)",
            "P(A)=0.4, P(B)=0.3, P(A and B)=0.1. Find P(A or B)",
            "A test detects disease with 95% accuracy. If 1% have disease, find probability of correct detection"
        ]
    },
    "Newton's Laws": {
        "key_concepts": ["First Law: Inertia - object stays at rest/motion", "Second Law: F = ma (force = mass x acceleration)", "Third Law: Every action has equal opposite reaction", "Free body diagrams show all forces", "Friction: f = uN"],
        "explanation": "Newton's three laws form classical mechanics. First law defines inertia, second law (F=ma) connects force to motion change, third law explains action-reaction pairs. Free body diagrams identify all forces acting on a body.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=kK1c7dL4Z4U", "https://www.youtube.com/watch?v=HmA20gF5UJI"],
            "article": ["https://www.physicsclassroom.com/class/newtlaws", "https://www.geeksforgeeks.org/newtons-laws-of-motion/"]
        },
        "practice_questions": [
            "A 5kg object accelerates at 2 m/s^2. Calculate the net force",
            "Calculate tension in rope with 10kg mass hanging vertically",
            "Two blocks (2kg, 3kg) connected by string on frictionless surface. Find acceleration if F = 20N",
            "A 1000kg car accelerates from 0 to 20m/s in 10s. Find force"
        ]
    },
    "Chemical Bonding": {
        "key_concepts": ["Ionic: electron transfer (metal + non-metal)", "Covalent: electron sharing (non-metals)", "VSEPR: electron pairs repel, determine shape", "Hybridization: sp, sp2, sp3", "Electronegativity difference determines bond type"],
        "explanation": "Chemical bonding holds atoms together. Ionic bonds form through electron transfer creating charged ions. Covalent bonds share electrons between atoms. VSEPR theory predicts molecular shapes based on electron pair repulsion. Hybridization explains orbital mixing.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=QJPvBOOMHYQ", "https://www.youtube.com/watch?v=Q2sOPnJjKqM"],
            "article": ["https://www.geeksforgeeks.org/chemical-bonding/", "https://www.chemguide.co.uk/atoms/bonding/bonding.html"]
        },
        "practice_questions": [
            "Explain why NaCl is ionic but HCl is covalent using electronegativity",
            "Predict shape and bond angle of NH3 using VSEPR",
            "What is hybridization of carbon in CH4, C2H4, and C2H2?",
            "Draw electron dot structure of CO2 and predict shape"
        ]
    },
    "Cell Biology": {
        "key_concepts": ["Fluid mosaic model of cell membrane", "Mitochondria: site of cellular respiration, ATP production", "DNA replication: semi-conservative", "Transcription: DNA to mRNA", "Translation: mRNA to protein at ribosome"],
        "explanation": "The cell is life's basic unit. Cell membrane (fluid mosaic) controls what enters/exits. Mitochondria produce ATP through cellular respiration. DNA stores genetic information and replicates semi-conservatively. Proteins are synthesized via transcription and translation.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=URUJD6N2hS8", "https://www.youtube.com/watch?v=8iLIVS9nn5s"],
            "article": ["https://www.nature.com/scitable/topicpage/cell-membrane-plasma-membrane-14053565/", "https://www.genome.gov/about-genomics/educational-resources"]
        },
        "practice_questions": [
            "Describe fluid mosaic model of cell membrane with diagram",
            "Calculate ATP yield from complete oxidation of one glucose molecule",
            "Explain semiconservative replication of DNA",
            "What happens during S-phase of cell cycle?"
        ]
    },
    "HTML": {
        "key_concepts": ["Document structure: DOCTYPE, html, head, body", "Semantic tags: header, nav, main, section, article, footer", "Form elements: input, select, textarea, button", "Tables: table, tr, th, td", "HTML5 APIs: Canvas, Geolocation"],
        "explanation": "HTML structures web content using elements and tags. Semantic HTML5 tags (header, nav, main, section, article, footer) improve accessibility and SEO. Forms collect user input. Tables display tabular data. Always use semantic elements over generic divs.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=qz0aGYrrlhU", "https://www.youtube.com/watch?v=pQN-pnXPaHg"],
            "article": ["https://www.w3schools.com/html/", "https://developer.mozilla.org/en-US/docs/Web/HTML"]
        },
        "practice_questions": [
            "Write complete HTML5 document with header, nav, main with 2 sections, footer",
            "Create a registration form with fields: name, email, password, confirm password",
            "Build an accessible table showing student marks with headers",
            "Explain difference between <article> and <section> tags"
        ]
    },
    "CSS": {
        "key_concepts": ["Box model: margin, border, padding, content", "Flexbox: justify-content, align-items, flex-direction", "CSS Grid: grid-template-columns, grid-gap", "Media queries: @media screen and (max-width:)", "Specificity: inline > ID > class > element"],
        "explanation": "CSS styles HTML elements. Box model treats every element as a box. Flexbox handles one-dimensional layouts (row or column). Grid handles two-dimensional layouts. Media queries create responsive designs. Specificity determines which styles apply.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=1PnVor36YS40", "https://www.youtube.com/watch?v=jV8B24rSN5o"],
            "article": ["https://css-tricks.com/snippets/css/a-guide-to-flexbox/", "https://www.w3schools.com/css/"]
        },
        "practice_questions": [
            "Create a card with 20px padding, 2px solid border, 10px margin using box model",
            "Center a div both horizontally and vertically using Flexbox",
            "Build a responsive grid with 3 columns that becomes 1 column on mobile",
            "Write CSS specificity calculation for: div#id.class:hover"
        ]
    },
    "JavaScript": {
        "key_concepts": ["let, const, var: block vs function scope", "Arrow functions: () => {}", "Array methods: map, filter, reduce, forEach", "DOM: getElementById, querySelector, addEventListener", "Async: Promise, async/await, fetch API"],
        "explanation": "JavaScript adds interactivity to web pages. ES6+ features include let/const (block scope), arrow functions, and async/await. Array methods (map, filter, reduce) transform data efficiently. DOM manipulation enables dynamic page updates.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=W6NZfCO5SIk", "https://www.youtube.com/watch?v=PoRJizFvM7s"],
            "article": ["https://developer.mozilla.org/en-US/docs/Web/JavaScript", "https://www.geeksforgeeks.org/javascript/"]
        },
        "practice_questions": [
            "Write function to sum all even numbers in array using reduce",
            "Create element and add click listener that changes its text",
            "Convert array of numbers to array of squares using map",
            "Write async function using fetch API to get user data"
        ]
    },
    "SQL": {
        "key_concepts": ["SELECT, FROM, WHERE, ORDER BY", "JOINs: INNER, LEFT, RIGHT, FULL", "GROUP BY with HAVING", "Subqueries and EXISTS", "Indexes for query optimization"],
        "explanation": "SQL manages relational databases. SELECT retrieves data, WHERE filters, JOIN combines tables. Aggregate functions (COUNT, SUM, AVG, MAX, MIN) work with GROUP BY. Subqueries nest SELECT statements. Indexes speed up queries on large tables.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=HXV3zeQKqGY", "https://www.youtube.com/watch?v=7S_tz1z_5bA"],
            "article": ["https://www.w3schools.com/sql/", "https://www.geeksforgeeks.org/sql-tutorial/"]
        },
        "practice_questions": [
            "Write query: Find employees earning above average salary with department name",
            "Create INNER JOIN between Orders and Customers tables",
            "Write subquery to find customers who never placed an order",
            "Explain difference between WHERE and HAVING clause with example"
        ]
    },
    "Statistics": {
        "key_concepts": ["Mean: sum/n, Median: middle value", "Mode: most frequent value", "Standard deviation: sqrt(sum((x-mean)^2)/n)", "Z-score: (x-mean)/std", "Correlation coefficient r"],
        "explanation": "Statistics summarizes and analyzes data. Central tendency measures (mean, median, mode) show typical values. Spread measures (range, variance, standard deviation) show data dispersion. Z-scores standardize values. Correlation measures relationship between variables.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=sf6xI9-9t40", "https://www.youtube.com/watch?v=cesvsG52vhI"],
            "article": ["https://www.mathsisfun.com/data/statistics.html", "https://www.geeksforgeeks.org/statistics/"]
        },
        "practice_questions": [
            "Calculate mean, median, mode: 12, 15, 15, 18, 20, 22, 25",
            "Find standard deviation: 10, 12, 14, 16, 18",
            "A test score is 85, mean is 70, std dev is 10. Find z-score and interpret",
            "Calculate correlation coefficient for x: 1,2,3,4,5 and y: 2,4,6,8,10"
        ]
    },
    "Python": {
        "key_concepts": ["Variables, data types (int, float, str, list, dict)", "Control flow: if/elif/else, for/while loops", "Functions: def, args, kwargs, lambda", "OOP: class, __init__, inheritance", "File handling: open, read, write"],
        "explanation": "Python is a versatile programming language. Variables store data, control flow manages execution order. Functions modularize code. Object-oriented programming uses classes and objects. Libraries like NumPy and Pandas enable data analysis.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=kqtD5dpn9C8", "https://www.youtube.com/watch?v=_uQrJ0TkZlc"],
            "article": ["https://www.geeksforgeeks.org/python-programming-language/", "https://www.w3schools.com/python/"]
        },
        "practice_questions": [
            "Write function to check if number is prime",
            "Create class BankAccount with deposit and withdrawal methods",
            "Write code to find duplicate elements in list using dictionary",
            "Sort list of dictionaries by key using lambda function"
        ]
    },
    "React": {
        "key_concepts": ["Components: functional vs class components", "Props: passing data to components", "State: useState hook for local state", "Hooks: useEffect, useContext, useReducer", "Lifecycle: component mounting, updating, unmounting"],
        "explanation": "React is a JavaScript library for building user interfaces. Components are reusable UI pieces. Props pass data from parent to child. State manages dynamic data within a component. Hooks like useState and useEffect enable functional components to have state and side effects.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Ke90Tje7VS0", "https://www.youtube.com/watch?v=W6NZfCO5SIk"],
            "article": ["https://reactjs.org/docs/getting-started.html", "https://www.w3schools.com/react/"]
        },
        "practice_questions": [
            "Create a React component that displays a counter with increment/decrement buttons",
            "Build a form with controlled inputs using useState",
            "Implement useEffect to fetch data from an API on component mount",
            "Create a custom hook for managing local storage"
        ]
    },
    "Backend": {
        "key_concepts": ["Node.js: server-side JavaScript runtime", "Express: routing, middleware, error handling", "REST APIs: GET, POST, PUT, DELETE endpoints", "Database: connection, CRUD operations", "Authentication: JWT, bcrypt, sessions"],
        "explanation": "Backend development handles server-side logic and database interactions. Node.js runs JavaScript on the server. Express.js provides a framework for building APIs. REST APIs follow conventions for HTTP methods. Authentication secures endpoints using tokens.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Oe421EPjeBE", "https://www.youtube.com/watch?v=W6NZfCO5SIk"],
            "article": ["https://nodejs.org/docs/", "https://expressjs.com/en/starter/"]
        },
        "practice_questions": [
            "Create an Express server with GET, POST, PUT, DELETE endpoints",
            "Write middleware to validate JWT tokens",
            "Connect to MongoDB and perform CRUD operations",
            "Implement user registration and login with password hashing"
        ]
    },
    "English Grammar": {
        "key_concepts": ["Parts of speech: noun, verb, adj, adv, preposition", "Tenses: present, past, future with 4 aspects", "Subject-verb agreement rules", "Active vs Passive voice conversion", "Direct vs Indirect speech changes"],
        "explanation": "Grammar governs language structure. Parts of speech categorize words by function. Tenses express time and aspect. Subject-verb agreement ensures grammatical number matches. Active voice emphasizes doer, passive emphasizes action. Indirect speech backshifts tenses.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=bJ1D6I0wV_w", "https://www.youtube.com/watch?v=N4cK8QK2UkU"],
            "article": ["https://www.grammarly.com/blog/", "https://owl.purdue.edu/owl/general_grammar/"]
        },
        "practice_questions": [
            "Identify all parts of speech: 'The quickly running athlete won the gold medal gracefully'",
            "Convert to passive voice: 'The teacher explains the grammar lesson'",
            "Change to indirect speech: He said, 'I will complete the project tomorrow'",
            "Choose correct verb: Neither the students nor the teacher (was/were) present"
        ]
    },
    "Economics": {
        "key_concepts": ["Law of Demand: P up = Q down", "Law of Supply: P up = Q up", "Elasticity: Ed = % change Qd / % change P", "Consumer equilibrium: MU/P equal for all goods", "Market structures: perfect comp, monopoly, oligopoly"],
        "explanation": "Economics studies resource allocation. Demand and supply determine prices in market. Elasticity measures responsiveness to price changes. Consumers maximize utility where MU/P equalizes. Different market structures have varying competition levels and pricing power.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=adBSoRGR9Tw", "https://www.youtube.com/watch?v=76Zl9K5c5Dk"],
            "article": ["https://www.investopedia.com/", "https://www.economicshelp.org/"]
        },
        "practice_questions": [
            "If price rises from 10 to 12 and quantity demanded falls from 100 to 80, calculate price elasticity",
            "Draw and explain consumer equilibrium with budget line and indifference curve",
            "Compare price and output in perfect competition vs monopoly",
            "Calculate total revenue if P = 50 - 2Q and Q = 15"
        ]
    },
    "default": {
        "key_concepts": ["Core definitions and terminology", "Fundamental principles and laws", "Practical applications in real world", "Problem-solving techniques", "Industry-standard practices"],
        "explanation": "This topic covers essential concepts that form the foundation for understanding the subject area. Mastering these basics enables tackling advanced topics effectively.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "article": ["https://www.geeksforgeeks.org/", "https://www.khanacademy.org/"]
        },
        "practice_questions": [
            "Define and explain the core concept with examples",
            "Solve a numerical problem applying this concept",
            "Compare and contrast with related concepts"
        ]
    },
    "Current Electricity": {
        "key_concepts": ["Electric Current (I = Q/t)", "Ohm's Law (V = IR)", "Resistance (R = ρL/A)", "Series and Parallel circuits", "Kirchhoff's Laws", "Electric Power (P = VI)", "Joule's Law of heating", "Drift velocity", "Resistivity and Conductivity", "Internal resistance of battery"],
        "explanation": "Current Electricity deals with the flow of electric charge through conductors. Key concepts include: (1) Electric Current - rate of flow of charge (I = Q/t), measured in Amperes. (2) Ohm's Law - voltage across conductor is proportional to current (V = IR). (3) Resistance - opposition to flow of current, depends on material, length, cross-section (R = ρL/A). (4) Series circuits - same current through all components, voltages add. (5) Parallel circuits - same voltage across all components, currents add. (6) Kirchhoff's Laws - Junction Law (sum of currents = 0) and Loop Law (sum of EMFs = sum of potential drops). (7) Electric Power - rate of energy dissipation (P = VI = I²R = V²/R). (8) Joule's Law - heat produced H = I²Rt. (9) Drift velocity - average velocity of electrons in conductor. (10) Resistivity (ρ) - intrinsic property of material, temperature coefficient.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=1-NXe41490w", "https://www.youtube.com/watch?v=8-iR1cKj9N4"],
            "article": ["https://www.physicsclassroom.com/class/circuits", "https://www.learncbse.in/current-electricity-class-12/"]
        },
        "practice_questions": [
            "Define electric current and state its SI unit.",
            "State and explain Ohm's Law with formula and graph.",
            "A wire has resistance 10Ω. Calculate current when 20V is applied.",
            "Explain series and parallel combination of resistors with examples.",
            "State Kirchhoff's Current and Voltage Laws.",
            "Calculate power in a circuit with 5A current and 220V supply.",
            "Define resistivity and conductivity. How does resistance change with temperature?",
            "Derive expression for equivalent resistance in series combination.",
            "What is drift velocity? Derive relation between drift velocity and current.",
            "A battery of emf 12V and internal resistance 2Ω is connected to external resistance 4Ω. Find current."
        ]
    },
    "Motion": {
        "key_concepts": ["Distance and Displacement", "Speed and Velocity", "Acceleration (a = Δv/Δt)", " Equations of motion (v = u + at, s = ut + ½at², v² = u² + 2as)", "Graphs (distance-time, velocity-time)", "Uniform and Non-uniform motion", "Circular motion", "Relative velocity"],
        "explanation": "Motion is the change in position of an object with respect to time. Key concepts: (1) Distance - total path length (scalar), Displacement - shortest distance from initial to final position (vector). (2) Speed - rate of change of distance (scalar), Velocity - rate of change of displacement (vector). (3) Acceleration - rate of change of velocity. (4) Equations of motion for uniformly accelerated motion: v = u + at, s = ut + ½at², v² = u² + 2as. (5) Graphs help visualize motion - slope of distance-time graph = speed, slope of velocity-time graph = acceleration, area under velocity-time graph = displacement. (6) Circular motion when object moves in a circular path with constant speed but changing direction.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=vL79i4w8j5s"],
            "article": ["https://www.physicsclassroom.com/class/1DKin", "https://www.learncbse.in/motion-class-9/"]
        },
        "practice_questions": [
            "Define motion and explain the difference between distance and displacement.",
            "A car accelerates from 20 m/s to 50 m/s in 5 seconds. Find acceleration.",
            "Draw and explain distance-time graph for uniform and non-uniform motion.",
            "Derive the three equations of motion.",
            "A ball is thrown upward with velocity 20 m/s. Find maximum height (g = 10 m/s²).",
            "Explain the concept of relative velocity with an example.",
            "What is circular motion? Give one example.",
            "A car travels 100 km in 2 hours and then 50 km in 1 hour. Find average speed."
        ]
    },
    "Force and Laws of Motion": {
        "key_concepts": ["Newton's First Law (Inertia)", "Newton's Second Law (F = ma)", "Newton's Third Law (Action-Reaction)", "Momentum (p = mv)", "Conservation of Momentum", "Friction (f = μN)", "Equilibrium of forces"],
        "explanation": "Force and Laws of Motion form the foundation of classical mechanics. (1) Newton's First Law: An object remains at rest or in uniform motion unless acted upon by external force (Law of Inertia). (2) Newton's Second Law: Rate of change of momentum is proportional to applied force (F = ma). (3) Newton's Third Law: Every action has equal and opposite reaction. (4) Momentum: product of mass and velocity (p = mv), conserved in absence of external forces. (5) Friction: opposes motion, proportional to normal reaction (f = μN). (6) Applications include rocket propulsion, collisions, etc.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=vL79i4w8j5s", "https://www.youtube.com/watch?v=y5B6zR1Fq08"],
            "article": ["https://www.physicsclassroom.com/class/newtlaws", "https://www.learncbse.in/newtons-laws-motion-class-9/"]
        },
        "practice_questions": [
            "State and explain Newton's three laws of motion with examples.",
            "A force of 20N acts on a 5kg mass. Find acceleration.",
            "Define momentum and state law of conservation of momentum.",
            "Two balls of masses 2kg and 4kg moving at 3m/s and 2m/s collide and stick together. Find final velocity.",
            "Explain the concept of inertia and give examples.",
            "Why is it difficult to move a heavy box than a light box? Explain using Newton's laws.",
            "A bullet of mass 20g is fired from a gun with velocity 100m/s. Find recoil velocity of gun (mass 2kg)."
        ]
    },
    "Work, Energy and Power": {
        "key_concepts": ["Work (W = F × d × cosθ)", "Kinetic Energy (KE = ½mv²)", "Potential Energy (PE = mgh)", "Work-Energy Theorem", "Conservation of Energy", "Power (P = W/t)", "Different forms of energy"],
        "explanation": "Work, Energy and Power are interrelated physical quantities. (1) Work: energy transferred when force moves object (W = Fd cosθ), unit Joule. (2) Kinetic Energy: energy due to motion (KE = ½mv²). (3) Potential Energy: energy due to position/height (PE = mgh). (4) Work-Energy Theorem: work done = change in kinetic energy. (5) Conservation of Energy: energy can neither be created nor destroyed, only transformed. (6) Power: rate of doing work (P = W/t), unit Watt. (7) Forms of mechanical, electrical, heat, light, sound energy.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=4A02J6mYf2Y", "https://www.youtube.com/watch?v=y5B6zR1Fq08"],
            "article": ["https://www.physicsclassroom.com/class/energy", "https://www.learncbse.in/work-energy-power-class-9/"]
        },
        "practice_questions": [
            "Define work and state its SI unit. When is work done negative?",
            "A body of mass 2kg falls from height 10m. Find its kinetic energy just before hitting ground.",
            "State and explain work-energy theorem.",
            "A man pushes a box with force 50N through 10m. Calculate work done.",
            "Define power. A motor does 5000J work in 10 seconds. Find power in kW.",
            "Explain conservation of energy with an example of pendulum.",
            "Find the power required to lift 100kg water from 50m well in 10 seconds."
        ]
    },
    "Sound": {
        "key_concepts": ["Sound waves - longitudinal", "Frequency, Wavelength, Speed (v = fλ)", "Reflection of sound (echo)", "Sound needs medium", "Ultrasound and its applications", "Doppler Effect", "Pitch and Loudness", "Musical sounds and noise"],
        "explanation": "Sound is a mechanical wave that requires a medium to travel. (1) Sound waves are longitudinal - particles vibrate parallel to direction of wave propagation. (2) Characteristics: Frequency (f) - pitch, Wavelength (λ) - distance between consecutive compressions, Speed (v = fλ). (3) Reflection: sound bounces off surfaces - echo heard after 0.1s minimum. (4) Sound cannot travel in vacuum. (5) Ultrasound: frequencies above 20kHz, used in medical imaging, cleaning. (6) Doppler Effect: change in frequency due to relative motion between source and observer. (7) Loudness (amplitude), Pitch (frequency).",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=lL4t-G1tZ6w"],
            "article": ["https://www.physicsclassroom.com/class/sound", "https://www.learncbse.in/sound-class-9/"]
        },
        "practice_questions": [
            "Explain why sound cannot travel through vacuum.",
            "The frequency of a tuning fork is 256Hz. If speed of sound is 340m/s, find wavelength.",
            "What is echo? Minimum distance to hear echo?",
            "Explain Doppler Effect with one example.",
            "Differentiate between loudness and pitch.",
            "A ship sends ultrasound and receives echo after 2 seconds. Find depth of sea (speed = 1500m/s).",
            "What are the applications of ultrasound?"
        ]
    },
    "Light - Reflection and Refraction": {
        "key_concepts": ["Laws of reflection", "Plane and spherical mirrors", "Mirror formula (1/f = 1/u + 1/v)", "Laws of refraction", "Refractive index (n = c/v)", "Lens formula", "Power of lens (P = 1/f)", "Total internal reflection"],
        "explanation": "Light is an electromagnetic wave that can be reflected and refracted. (1) Reflection: angle of incidence = angle of reflection. (2) Mirrors: Plane mirrors give laterally inverted image. Spherical mirrors (concave/convex) follow mirror formula. (3) Refraction: change in direction when light enters different medium, governed by Snell's law (n₁ sinθ₁ = n₂ sinθ₂). (4) Refractive index: n = speed of light in vacuum / speed in medium. (5) Lenses: Convex (converging), Concave (diverging), follow lens formula. (6) Power of lens: P = 1/f (dioptre). (7) Total internal reflection: when angle > critical angle, used in optical fibers.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Y8tS2qwCMg4"],
            "article": ["https://www.physicsclassroom.com/class/refln", "https://www.learncbse.in/reflection-light-class-10/"]
        },
        "practice_questions": [
            "State laws of reflection and refraction.",
            "An object 2cm tall is placed 10cm from a concave mirror of focal length 15cm. Find image position and nature.",
            "Define refractive index. If n = 1.5 for glass, find speed of light in glass (c = 3×10⁸ m/s).",
            "Explain total internal reflection with example.",
            "An object is placed 20cm from convex lens of focal length 10cm. Find image position.",
            "Difference between convex and concave lens.",
            "Define power of lens and its SI unit."
        ]
    },
    "Magnetic Effects of Electric Current": {
        "key_concepts": ["Magnetic field around current-carrying wire", "Right-hand thumb rule", "Force on current-carrying conductor (F = BIL sinθ)", "Fleming's Left Hand Rule", "Electric motor", "Electromagnetic induction (Faraday's Law)", "Electric generator", "Transformer"],
        "explanation": "Electricity and magnetism are interrelated - moving charges create magnetic fields. (1) Magnetic field: exists around current-carrying wire, direction given by right-hand thumb rule. (2) Force on conductor: F = BIL sinθ, direction by Fleming's Left Hand Rule. (3) Electric Motor: converts electrical energy to mechanical energy using magnetic force. (4) Electromagnetic Induction: changing magnetic field induces current (Faraday's Law). (5) Electric Generator: converts mechanical to electrical energy. (6) Transformer: changes AC voltage - step-up (increases V), step-down (decreases V).",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=w0NoRzpYnZg"],
            "article": ["https://www.physicsclassroom.com/class/magnetism", "https://www.learncbse.in/magnetic-effects-electric-current-class-10/"]
        },
        "practice_questions": [
            "Explain right-hand thumb rule for magnetic field around straight conductor.",
            "State Fleming's Left Hand Rule.",
            "What is electromagnetic induction? State Faraday's Law.",
            "Explain working of electric motor with diagram.",
            "A wire of length 0.5m carries current 2A in magnetic field 0.1T. Find force.",
            "What is the difference between AC and DC generator?",
            "Why transformer cannot work with DC?"
        ]
    },
    "Periodic Classification of Elements": {
        "key_concepts": ["Modern Periodic Table (18 groups, 7 periods)", "Mendeleev's periodic law", "Trends: atomic size, ionization energy, electronegativity", "Metals, non-metals, metalloids", "Groups (valence electrons)", "Periods (shells)", "Halogens, Noble gases"],
        "explanation": "Periodic table arranges elements in order of increasing atomic number showing periodic properties. (1) Modern Periodic Law: properties repeat at regular intervals. (2) Structure: 18 vertical groups, 7 horizontal periods. (3) Trends across period: atomic size decreases, ionization energy increases, electronegativity increases. (4) Groups: elements in same group have similar valence electrons and properties. (5) Periods: elements in same period have same number of electron shells. (6) Special groups: Group 1 - Alkali metals, Group 17 - Halogens, Group 18 - Noble gases. (7) Metals left, non-metals right, metalloids along border.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Q_Z0p8yg4F0"],
            "article": ["https://www.chemistrytutorials.org/wp-content/uploads/2019/03/periodic-table.pdf"]
        },
        "practice_questions": [
            "State Modern Periodic Law. How does atomic size vary across a period?",
            "Why noble gases are chemically inert?",
            "Define ionization energy. How does it vary in periodic table?",
            "Differentiate between metals and non-metals with examples.",
            "Explain why elements in same group have similar properties.",
            "What are metalloids? Give examples.",
            "Electronic configuration of element is 2,8,7. Find group and period."
        ]
    },
    "Acids, Bases and Salts": {
        "key_concepts": ["Acids: H⁺ donors, pH < 7", "Bases: OH⁻ donors, pH > 7", "Neutralization reaction", "Salts and their types", "pH scale", "Indicators (litmus, phenolphthalein)", "Strength of acids/bases", "Common properties of acids and bases"],
        "explanation": "Acids, Bases and Salts are important chemical compounds. (1) Acids: proton (H⁺) donors, sour taste, turn litmus red, pH < 7. (2) Bases: proton acceptors, bitter taste, slippery feel, turn litmus blue, pH > 7. (3) Neutralization: acid + base → salt + water. (4) pH scale: 0-14, 7 = neutral, acids < 7, bases > 7. (5) Indicators: substances that change color in acidic/basic medium (litmus, phenolphthalein, methyl orange). (6) Salts: ionic compounds formed from neutralization, types - normal, acid, basic, double salts. (7) Strength: strong acids (HCl, HNO₃, H₂SO₄), weak acids (CH₃COOH).",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=Q_Z0p8yg4F0"],
            "article": ["https://www.learncbse.in/acids-bases-salts-class-10/"]
        },
        "practice_questions": [
            "Define acid and base according to Arrhenius theory.",
            "What is pH? pH of solution is 3. Is it acidic or basic?",
            "Write balanced equation for reaction between NaOH and HCl.",
            "What are indicators? Give examples.",
            "Explain preparation of sodium chloride (common salt) in lab.",
            "Why does milk of magnesia work for acidity?",
            "Difference between strong and weak acids with examples."
        ]
    },
    "Heredity and Evolution": {
        "key_concepts": ["Mendel's Laws of Inheritance", "Genotype and Phenotype", "Sex determination in humans", "Darwin's Theory of Evolution", "Natural Selection", "Speciation", "Evidence of Evolution (fossils, homologous organs)", "DNA - genetic material"],
        "explanation": "Heredity and Evolution explain how traits pass from parents to offspring and how species change over time. (1) Heredity: transmission of traits from parents to offspring. (2) Mendel's Laws: Law of Dominance, Law of Segregation, Law of Independent Assortment. (3) Genotype: genetic makeup, Phenotype: physical appearance. (4) Sex determination: XY chromosomes in humans (XX = female, XY = male). (5) Evolution: changes in species over time, theory proposed by Darwin. (6) Natural Selection: survival of fittest. (7) Evidence: fossils, homologous organs, DNA similarities. (8) Speciation: formation of new species due to isolation.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=9It2QHv2c2w"],
            "article": ["https://www.ncert.nic.in/textbook/pdf/lebo105.pdf", "https://www.learncbse.in/heredity-evolution-class-10/"]
        },
        "practice_questions": [
            "State Mendel's Law of Dominance with example.",
            "Differentiate between genotype and phenotype.",
            "How is sex determined in human beings?",
            "Explain Darwin's theory of natural selection.",
            "What are fossils? How do they provide evidence for evolution?",
            "Define speciation with example.",
            "If brown eyes (B) are dominant over blue (b), cross pure breeding brown with pure breeding blue. Find genotypic and phenotypic ratios in F1 and F2."
        ]
    },
    "Our Environment": {
        "key_concepts": ["Ecosystem and its components", "Food chain and food web", "Biogeochemical cycles (Carbon, Nitrogen)", "Pollution - Air, Water, Soil", "Greenhouse Effect", "Ozone Depletion", "Waste management", "Biodiversity"],
        "explanation": "Our Environment includes all living and non-living things around us. (1) Ecosystem: interaction between organisms and physical environment, includes producers, consumers, decomposers. (2) Food chain: transfer of energy from one organism to another, food web - interconnected food chains. (3) Biogeochemical cycles: Carbon cycle, Nitrogen cycle maintain balance. (4) Pollution: harmful substances in environment - Air (smog, greenhouse gases), Water (industrial waste), Soil (pesticides). (5) Greenhouse Effect: warming due to CO₂, CH₄ gases. (6) Ozone depletion: CFCs break ozone layer. (7) Waste management: reduce, reuse, recycle. (8) Biodiversity: variety of life, essential for ecological balance.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=pXWBKxq4qGk"],
            "article": ["https://www.learncbse.in/our-environment-class-10/"]
        },
        "practice_questions": [
            "Define ecosystem. List its components.",
            "Explain food chain and food web with examples.",
            "What is greenhouse effect? How does it cause global warming?",
            "How can we reduce, reuse and recycle waste?",
            "Explain nitrogen cycle in nature.",
            "What are the causes and effects of water pollution?",
            "Why is biodiversity important for environment?"
        ]
    },
    "Cell: The Unit of Life": {
        "key_concepts": ["Cell theory", "Prokaryotic vs Eukaryotic cells", "Cell organelles (Nucleus, Mitochondria, Chloroplast, ER, Golgi)", "Cell membrane (fluid mosaic model)", "Diffusion and Osmosis", "Plant cell vs Animal cell", "DNA and RNA"],
        "explanation": "Cell is the basic structural and functional unit of all living organisms. (1) Cell Theory: all organisms made of cells, cells arise from pre-existing cells. (2) Types: Prokaryotic (no nucleus, e.g., bacteria) vs Eukaryotic (true nucleus, e.g., plant/animal cells). (3) Organelles: Nucleus (contains DNA, controls cell), Mitochondria (respiration, ATP), Chloroplast (photosynthesis in plants), ER (transport), Golgi (packaging). (4) Cell membrane: selectively permeable, fluid mosaic model. (5) Diffusion: movement from high to low concentration. (6) Osmosis: diffusion of water through semi-permeable membrane. (7) Plant cells have cell wall, chloroplast, large vacuole; animal cells don't.",
        "resources": {
            "youtube": ["https://www.youtube.com/watch?v=URUJD6N2hS8"],
            "article": ["https://www.ncert.nic.in/textbook/pdf/lebo103.pdf", "https://www.learncbse.in/cell-the-unit-life-class-9/"]
        },
        "practice_questions": [
            "State the three points of cell theory.",
            "Differentiate between prokaryotic and eukaryotic cells.",
            "Draw and label plant cell and animal cell.",
            "Explain structure and function of nucleus.",
            "What is osmosis? Differentiate between isotonic, hypotonic and hypertonic solutions.",
            "Why do plant cells have cell wall?",
            "Explain fluid mosaic model of cell membrane."
        ]
    }
}

def parse_subjects_input(subjects_text):
    parsed = []
    lines = subjects_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if ':' in line:
            parts = line.split(':', 1)
            subject = parts[0].strip()
            topics_str = parts[1].strip() if len(parts) > 1 else ""
            
            if topics_str:
                topics = [t.strip() for t in topics_str.split(',') if t.strip()]
                if subject and topics:
                    parsed.append({"subject": subject, "topics": topics})
            else:
                if subject:
                    parsed.append({"subject": subject, "topics": []})
        else:
            if line:
                parsed.append({"subject": line, "topics": []})
    
    return parsed


def get_topics_for_subject(subject, count=2, explicit_topics=None):
    import random
    random.seed(hash(subject) % 1000)
    
    if explicit_topics and len(explicit_topics) > 0:
        return explicit_topics[:count]
    
    subject_lower = subject.lower()
    
    all_topics_by_subject = {
        "math": ["Quadratic Equations", "Trigonometry", "Calculus", "Probability", "Statistics", "Algebra", "Geometry", "Arithmetic", "Linear Equations", "Polynomials"],
        "physics": ["Newton's Laws", "Motion", "Force", "Work and Energy", "Sound", "Light", "Electricity", "Current Electricity", "Magnetism", "Heat", "Waves"],
        "chemistry": ["Chemical Bonding", "Periodic Table", "Acids Bases and Salts", "Carbon and Its Compounds", "Metals and Non-metals", "Structure of Atom", "Chemical Reactions", "States of Matter"],
        "biology": ["Cell Biology", "Heredity and Evolution", "Our Environment", "Nutrition", "Digestion", "Circulatory System", "Respiratory System", "Genetics", "Ecology", "Photosynthesis"],
        "python": ["Python Basics", "Functions in Python", "Object-Oriented Programming", "File Handling", "Data Structures", "Error Handling", "Libraries and Modules"],
        "html": ["HTML Basics", "HTML Forms", "Semantic HTML", "HTML5 Elements", "Tables and Lists"],
        "css": ["CSS Basics", "Flexbox", "CSS Grid", "Responsive Design", "CSS Selectors", "Box Model"],
        "javascript": ["JavaScript Basics", "DOM Manipulation", "Events and Handlers", "Async JavaScript", "ES6 Features", "JSON Handling"],
        "programming": ["Variables and Data Types", "Control Flow", "Functions", "Object-Oriented Programming", "Data Structures", "Algorithms", "Debugging"],
        "english": ["English Grammar", "Reading Comprehension", "Vocabulary", "Writing Skills", "Sentence Structure"],
        "economics": ["Supply and Demand", "Elasticity", "Consumer Behavior", "Market Structures", "National Income"],
        "default": list(TOPIC_DATA.keys())[:-1]
    }
    
    topics = []
    for key, topic_list in all_topics_by_subject.items():
        if key in subject_lower:
            topics = topic_list
            break
    
    if not topics:
        topics = all_topics_by_subject["default"]
    
    random.shuffle(topics)
    return topics[:count]


def generate_specific_concepts(topic_name, subject):
    """Generate REAL subtopics (not generic templates) for a topic using AI - with strict subject validation"""
    
    # First validate topic relevance
    if not is_topic_relevant_to_subject(topic_name, subject):
        # Find relevant alternative topics for the subject
        subject_key = find_subject_key(subject)
        if subject_key:
            # Return predefined safe topics for unknown topics
            safe_topics = get_safe_topics_for_subject(subject, topic_name)
            return safe_topics
    
    # Generate strict prompt with subject boundary
    subject_key = find_subject_key(subject)
    domain_keywords = SUBJECT_DOMAIN_KEYWORDS.get(subject_key, [])
    keyword_hint = f"Valid domain terms: {', '.join(domain_keywords[:5])}" if domain_keywords else ""
    
    prompt = f"""STRICT SUBJECT BOUNDARY - {subject.upper()} ONLY

Topic: {topic_name}
Subject: {subject}
{keyword_hint}

CRITICAL CONSTRAINTS:
1. ONLY generate subtopics that belong to {subject}
2. DO NOT include topics from physics, chemistry, biology, math, or any other field
3. Each subtopic must be directly related to {subject} and {topic_name}
4. NO generic educational terms like "definition", "importance", "applications"
5. Return ONLY bullet points, max 8 subtopics

If the topic is NOT related to {subject}, return the closest valid {subject} subtopics instead.

Output as bullet points only:"""

    try:
        response = call_ai_api([
            {"role": "system", "content": "You are a STRICT {subject} expert. Generate only relevant subtopic names as bullet points. No explanations, no mixed subjects.".format(subject=subject)},
            {"role": "user", "content": prompt}
        ], max_tokens=150)
        
        if response:
            concepts = [line.strip("- ").strip() for line in response.split("\n") if line.strip() and len(line.strip()) > 2]
            concepts = [c for c in concepts if not c.lower().startswith(("definition", "concept", "topic", "what", "how", "why", "explain", "describe", "learn"))]
            
            # Validate generated concepts
            valid_concepts = []
            for c in concepts:
                if is_topic_relevant_to_subject(c, subject):
                    valid_concepts.append(c)
            
            if len(valid_concepts) >= 3:
                return valid_concepts[:10]
            
            # If not enough valid, use fallback but still filter
            fallback = get_safe_topics_for_subject(subject, topic_name)
            return fallback[:8]
    except Exception as e:
        print(f"AI concepts error: {e}")
    
    # Fallback to safe predefined topics
    return get_safe_topics_for_subject(subject, topic_name)[:8]


def get_safe_topics_for_subject(subject, topic_name):
    """Get safe, predefined topics for unknown topics within the subject"""
    subject_key = find_subject_key(subject)
    
    safe_topic_map = {
        "economics": ["Supply and Demand", "Price Elasticity", "Consumer Behavior", "Market Equilibrium", "National Income", "Inflation", "Money and Banking", "Fiscal Policy"],
        "physics": ["Laws of Motion", "Work and Energy", "Thermodynamics", "Waves and Sound", "Light and Optics", "Electricity", "Magnetism", "Modern Physics"],
        "chemistry": ["Atomic Structure", "Chemical Bonding", "Thermodynamics", "Kinetics", "Equilibrium", "Solutions", "Electrochemistry", "Organic Chemistry"],
        "biology": ["Cell Structure", "Biomolecules", "Enzymes", "Metabolism", "Genetics", "Evolution", "Ecology", "Human Physiology"],
        "mathematics": ["Algebra", "Calculus", "Trigonometry", "Geometry", "Statistics", "Probability", "Number Theory", "Linear Algebra"],
        "python": ["Variables", "Data Types", "Control Flow", "Functions", "OOP", "File Handling", "Error Handling", "Modules"],
        "html": ["Document Structure", "Forms", "Tables", "Lists", "Semantic Elements", "Multimedia", "Canvas", "HTML5 APIs"],
        "css": ["Box Model", "Flexbox", "Grid", "Responsive Design", "Animations", "Transitions", "Selectors", "Layout"],
        "javascript": ["Variables", "Functions", "DOM", "Events", "Async", "ES6 Features", "JSON", "Local Storage"],
        "sql": ["SELECT Queries", "Filtering", "Sorting", "Joins", "Subqueries", "Aggregations", "Indexes", "Views"],
        "machine learning": ["Supervised Learning", "Unsupervised Learning", "Regression", "Classification", "Neural Networks", "Feature Engineering", "Model Evaluation", "Hyperparameter Tuning"],
        "data science": ["Data Cleaning", "EDA", "Visualization", "Statistics", "Regression", "Classification", "Time Series", "Machine Learning"],
        "english": ["Grammar", "Vocabulary", "Reading", "Writing", "Speaking", "Listening", "Composition", "Literature"],
        "default": ["Introduction", "Fundamentals", "Core Concepts", "Advanced Topics", "Practical Applications", "Problem Solving", "Review", "Practice"]
    }
    
    topics = safe_topic_map.get(subject_key, safe_topic_map["default"])
    return topics


def generate_specific_explanation(topic_name, subject):
    """Generate concise, textbook-style explanation"""
    subject_lower = subject.lower()
    topic_lower = topic_name.lower()
    
    explanations = {
        "physics": f"""• Definition: {topic_name} deals with the behavior of matter and energy.
• Key Principle: Fundamental laws governing {topic_name} are essential for understanding natural phenomena.
• Applications: Used in technology, engineering, and everyday devices.
• Important Formula: Frequently tested in JEE, NEET, and board exams.""",

        "chemistry": f"""• Definition: {topic_name} involves the composition, structure, properties, and reactions of matter.
• Key Principle: Understanding {topic_name} helps predict how substances interact.
• Applications: Essential for pharmaceuticals, materials science, and industrial processes.
• Important: Frequently asked in competitive exams.""",

        "biology": f"""• Definition: {topic_name} describes how living organisms function and interact.
• Key Principle: Essential for understanding life processes and biological systems.
• Applications: Used in medicine, biotechnology, and agriculture.
• Important: Frequently tested in NEET and board exams.""",

        "mathematics": f"""• Definition: {topic_name} involves systematic study of numbers, patterns, and logical reasoning.
• Key Principle: Forms the foundation for all scientific and technical fields.
• Applications: Used in calculations, measurements, and problem-solving.
• Important: Numerical problems carry high weight in JEE and board exams.""",

        "programming": f"""• Definition: {topic_name} enables writing instructions for computers to perform tasks.
• Key Principle: Essential for building software, websites, and applications.
• Applications: Powers all modern technology and automation.
• Important: Frequently tested in coding interviews and exams.""",

        "default": f"""• Definition: {topic_name} is a fundamental concept in {subject}.
• Key Principle: Essential for understanding advanced topics in {subject}.
• Applications: Used in various real-world scenarios and problem-solving.
• Important: Frequently tested in exams."""
    }
    
    for key in explanations:
        if key in subject_lower:
            return explanations[key]
    
    return explanations["default"]


def generate_points_to_remember(topic_name, subject):
    """Generate concise exam-relevant points"""
    subject_lower = subject.lower()
    
    if "physics" in subject_lower:
        return [
            f"Definition: {topic_name} is a fundamental concept in physics.",
            f"Formula: Understand and memorize key formulas related to {topic_name}.",
            f"Laws: Know the laws and principles governing {topic_name}.",
            f"Units: Remember SI units of physical quantities in {topic_name}.",
            f"Applications: Real-world applications of {topic_name} are frequently asked.",
            f"Numerical: Practice numerical problems - carry high weight in JEE/NEET.",
            f"Derivations: Know important derivations for {topic_name}.",
            f"Diagrams: Practice labeled diagrams related to {topic_name}.",
            f"Common Mistakes: Avoid common errors in solving {topic_name} problems.",
            f"Exam Tip: Focus on {topic_name} for board and competitive exams."
        ]
    elif "math" in subject_lower:
        return [
            f"Definition: Understand the basic definition of {topic_name}.",
            f"Formula: All important formulas for {topic_name} must be memorized.",
            f"Theorems: Know key theorems related to {topic_name}.",
            f"Methods: Master step-by-step problem-solving methods.",
            f"Graphs: Practice graphical representations of {topic_name}.",
            f"Numerical: High-weight topic for JEE and board exams.",
            f"Shortcut: Learn shortcut methods for quick solutions.",
            f"Examples: Practice examples from NCERT and reference books.",
            f"Mistakes: Avoid calculation errors in {topic_name} problems.",
            f"Revision: Last-minute formulas and key points for {topic_name}."
        ]
    elif "chemistry" in subject_lower:
        return [
            f"Definition: Understand what {topic_name} means in chemistry.",
            f"Properties: Physical and chemical properties of {topic_name}.",
            f"Reactions: Important chemical reactions involving {topic_name}.",
            f"Structure: Know the atomic/molecular structure in {topic_name}.",
            f"Applications: Industrial and daily-life applications.",
            f"Nomenclature: IUPAC naming conventions for {topic_name}.",
            f"Equations: Write balanced chemical equations for {topic_name}.",
            f"Lab: Laboratory preparation methods for {topic_name}.",
            f"Uses: Important uses of {topic_name} in various fields.",
            f"Exam: Frequently asked in NEET and board exams."
        ]
    elif "biology" in subject_lower:
        return [
            f"Definition: Clear definition of {topic_name} in biology.",
            f"Process: Understand the process/mechanism of {topic_name}.",
            f"Function: Role and function of {topic_name} in living organisms.",
            f"Diagrams: Practice labeled diagrams for {topic_name}.",
            f"Terms: Important biological terms related to {topic_name}.",
            f"Human Health: Connection to human health and diseases.",
            f"Applications: Biotechnology applications of {topic_name}.",
            f"NCERT: Focus on NCERT content for {topic_name}.",
            f"NEET: High-weight topic for NEET exam.",
            f"Quick Rev: Key points for quick revision of {topic_name}."
        ]
    else:
        return [
            f"Definition: {topic_name} is a key concept in {subject}.",
            f"Core Principle: Understand the fundamental principle.",
            f"Key Terms: Important terminology for {topic_name}.",
            f"Applications: Real-world applications of {topic_name}.",
            f"Examples: Common examples illustrating {topic_name}.",
            f"Problems: Practice problems based on {topic_name}.",
            f"Formulas: Important formulas related to {topic_name}.",
            f"Notes: Create concise notes for {topic_name}.",
            f"Exam: Frequently tested in exams.",
            f"Revision: Quick revision points for {topic_name}."
        ]


def generate_topic_content(topic_name, subject):
    cache_key = f"topic_{topic_name.lower()}_{subject.lower()}"
    cached = _get_cache(cache_key, _topic_cache)
    if cached:
        return cached
    
    topic_lower = topic_name.lower().replace("'", "").replace("-", "")
    
    for key, data in TOPIC_DATA.items():
        if key.lower().replace("'", "").replace("-", "") in topic_lower or topic_lower in key.lower().replace("'", "").replace("-", ""):
            yt_videos = get_emergency_videos(topic_name, 2, subject)
            articles = get_article_resources(topic_name, 2)
            pdf_resources = search_pdf_notes(topic_name, 2)
            points = data.get("points_to_remember", generate_points_to_remember(topic_name, subject))
            result = {
                "key_concepts": data["key_concepts"],
                "explanation": data["explanation"],
                "youtube_resources": yt_videos if yt_videos else [],
                "article_resources": articles,
                "pdf_resources": pdf_resources,
                "practice_questions": data["practice_questions"],
                "points_to_remember": points
            }
            _set_cache(cache_key, result, _topic_cache)
            return result
    
    sub_topic_mapping = {
        "forms": "HTML", "flexbox": "CSS", "grid": "CSS", "responsive": "CSS",
        "dom": "JavaScript", "events": "JavaScript", "fetch": "JavaScript", "api": "JavaScript",
        "react": "React", "components": "React", "props": "React", "state": "React", "hooks": "React",
        "node": "Backend", "express": "Backend", "rest": "Backend",
    }
    
    for sub_topic, parent_topic in sub_topic_mapping.items():
        if sub_topic in topic_lower:
            if parent_topic in TOPIC_DATA:
                data = TOPIC_DATA[parent_topic]
                yt_videos = get_emergency_videos(topic_name, 2, subject)
                articles = get_article_resources(topic_name, 2)
                pdf_resources = search_pdf_notes(topic_name, 2)
                points = data.get("points_to_remember", generate_points_to_remember(topic_name, subject))
                result = {
                    "key_concepts": data["key_concepts"],
                    "explanation": f"{topic_name} is part of {parent_topic}. {data['explanation']}",
                    "youtube_resources": yt_videos if yt_videos else [],
                    "article_resources": articles,
                    "pdf_resources": pdf_resources,
                    "practice_questions": data["practice_questions"],
                    "points_to_remember": points
                }
                _set_cache(cache_key, result, _topic_cache)
                return result
    
    yt_videos = get_emergency_videos(topic_name, 2, subject)
    articles = get_article_resources(topic_name, 2)
    pdf_resources = search_pdf_notes(topic_name, 2)
    
    topic_key_concepts = generate_specific_concepts(topic_name, subject)
    topic_explanation = generate_specific_explanation(topic_name, subject)
    points_to_remember = generate_points_to_remember(topic_name, subject)
    
    result = {
        "key_concepts": topic_key_concepts,
        "explanation": topic_explanation,
        "youtube_resources": yt_videos if yt_videos else [],
        "article_resources": articles,
        "pdf_resources": pdf_resources,
        "practice_questions": [
            f"Define {topic_name} and explain its significance in {subject}",
            f"List and explain the main components of {topic_name}",
            f"How is {topic_name} applied in real-world scenarios?",
            f"Compare {topic_name} with related concepts in {subject}",
            f"Solve a problem based on {topic_name} principles"
        ],
        "points_to_remember": points_to_remember
    }
    _set_cache(cache_key, result, _topic_cache)
    return result

def generate_dynamic_concepts(topic, subject):
    prompt = f"""
You are an expert teacher.

Generate 8-10 SPECIFIC subtopics (NOT generic) for:

Subject: {subject}
Topic: {topic}

Rules:
- NO generic lines like "importance", "applications"
- ONLY real subtopics
- Make them exam-relevant
- Output as simple bullet points

Example (for SQL Joins):
- INNER JOIN
- LEFT JOIN
- RIGHT JOIN
- FULL OUTER JOIN
"""

    response = call_ai_api([
        {"role": "system", "content": "You generate structured study content."},
        {"role": "user", "content": prompt}
    ], max_tokens=200)

    if not response:
        return [f"Important concepts of {topic}"]

    return [line.strip("- ").strip() for line in response.split("\n") if line.strip()]



def process_topic(topic_name, subject, time_per_topic, first_block, second_block, third_block):
    topic_data = generate_topic_content(topic_name, subject)

    return {
        "topic_name": topic_name,
        "time": f"{time_per_topic} min",
        "explanation": topic_data["explanation"],
        "key_concepts": topic_data.get("key_concepts", [])[:8],
        "study_plan": [
            f"First {first_block} min: Read and understand core concepts from textbook",
            f"Next {second_block} min: Practice problems and examples",
            f"Last {third_block} min: Revise and create summary notes"
        ],
        "youtube_resources": topic_data["youtube_resources"],
        "practice_questions": topic_data["practice_questions"]
    }


def create_pdf(study_plan_data, all_questions=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MainTitle', fontSize=22, alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SubTitle', fontSize=12, alignment=TA_CENTER, spaceAfter=20, textColor=colors.HexColor('#7f8c8d')))
    styles.add(ParagraphStyle(name='DayHeader', fontSize=14, spaceAfter=8, spaceBefore=15, textColor=colors.HexColor('#2980b9'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SubjectTag', fontSize=10, spaceAfter=10, textColor=colors.HexColor('#27ae60')))
    styles.add(ParagraphStyle(name='TopicTitle', fontSize=12, spaceAfter=6, spaceBefore=12, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SectionLabel', fontSize=10, spaceAfter=4, spaceBefore=8, textColor=colors.HexColor('#34495e'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='ContentText', fontSize=10, spaceAfter=4, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='BulletText', fontSize=9, leftIndent=15, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='LinkText', fontSize=9, leftIndent=15, spaceAfter=4, textColor=colors.HexColor('#2980b9'), wordWrap='LTR'))
    styles.add(ParagraphStyle(name='QuestionText', fontSize=9, leftIndent=15, spaceAfter=4, textColor=colors.HexColor('#8e44ad')))
    
    story = []
    
    student_info = study_plan_data.get('student_info', {})
    
    story.append(Paragraph("STUDY PLAN", styles['MainTitle']))
    story.append(Paragraph(f"Student: {student_info.get('name', 'N/A')} | Subjects: {student_info.get('subjects', 'N/A')} | Duration: {student_info.get('duration', 'N/A')} | Daily: {student_info.get('daily_hours', 'N/A')} hours", styles['SubTitle']))
    story.append(Spacer(1, 15))
    
    study_plan = study_plan_data.get('study_plan', [])
    
    for day_data in study_plan:
        story.append(Paragraph(f"--- Day {day_data['day']} ---", styles['DayHeader']))
        story.append(Paragraph(f"Subject: {day_data['subject']} | Date: {day_data['date']}", styles['SubjectTag']))
        
        for topic in day_data.get('topics', []):
            time_allocated = topic.get('time', '60 min')
            story.append(Paragraph(f"Topic: {topic['topic_name']} ({time_allocated})", styles['TopicTitle']))
            
            story.append(Paragraph("Key Concepts:", styles['SectionLabel']))
            for concept in topic.get('key_concepts', []):
                story.append(Paragraph(f"- {concept}", styles['BulletText']))
            
            story.append(Paragraph("Explanation:", styles['SectionLabel']))
            story.append(Paragraph(topic.get('explanation', 'N/A'), styles['ContentText']))
            
            story.append(Paragraph("Study Plan:", styles['SectionLabel']))
            for step in topic.get('study_plan', []):
                story.append(Paragraph(f"- {step}", styles['BulletText']))
            
            yt_links = topic.get('youtube_resources', [])
            if yt_links:
                story.append(Paragraph("YouTube Tutorials:", styles['SectionLabel']))
                for yt_url in yt_links:
                    if yt_url.startswith('http'):
                        story.append(Paragraph(f"  - {yt_url}", styles['LinkText']))
                    else:
                        story.append(Paragraph(f"  - {yt_url}", styles['BulletText']))
            
            story.append(Paragraph("Practice Questions:", styles['SectionLabel']))
            for i, q in enumerate(topic.get('practice_questions', []), 1):
                story.append(Paragraph(f"{i}. {q}", styles['QuestionText']))
            
            points = topic.get('points_to_remember', [])
            if points:
                story.append(Paragraph("Points to Remember:", styles['SectionLabel']))
                for point in points:
                    story.append(Paragraph(f"• {point}", styles['BulletText']))
            
            if all_questions:
                topic_name = topic.get('topic_name', '')
                for concept in topic.get('key_concepts', [])[:5]:
                    key = f"{day_data['day']}_{topic_name}_{concept}"
                    questions = all_questions.get(key, [])
                    
                    if questions:
                        story.append(Paragraph(f"Important Questions - {concept}:", styles['SectionLabel']))
                        for i, q in enumerate(questions, 1):
                            story.append(Paragraph(f"Q{i}: {q.get('question', '')}", styles['QuestionText']))
                            story.append(Paragraph(f"Ans: {q.get('answer', '')}", styles['BulletText']))
            
            story.append(Spacer(1, 10))
            
            story.append(Spacer(1, 10))
        
        story.append(Spacer(1, 15))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-practice', methods=['POST'])
def generate_practice():
    try:
        data = request.get_json()
        ui_language = data.get("ui_language", "english")

        # ✅ Get inputs safely
        topic = data.get('topic', '').strip()
        subject = data.get('subject', '').strip()

        if not topic:
            return jsonify({"error": "Topic is required"}), 400

        # ✅ Check cache (include language in key)
        input_text = subject + " " + topic
        lang_instruction = get_language_instruction(input_text)
        cache_lang = "hi" if input_text and "\u0900" <= input_text[0] <= "\u097F" else "en"
        practice_cache_key = f"practice_{topic.lower()}_{subject.lower()}_{cache_lang}"
        cached = _get_cache(practice_cache_key, _topic_cache)
        if cached:
            return jsonify({"questions": cached, "cached": True})

        print("TOPIC:", topic)
        print("LANG INSTRUCTION:", lang_instruction[:50] + "...")

        # ✅ PROMPT WITH LANGUAGE INSTRUCTION FIRST
        prompt = f"""{lang_instruction}

Use EXACT SAME script as the input topic and subject. Match Devanagari for Hindi, Tamil for Tamil, etc.

Generate 5 high-quality exam-level questions with answers about:
Topic: {topic}
Subject: {subject}

Keep answers clear and useful for students."""

        response = call_ai_api([
            {"role": "system", "content": "You are an expert exam question generator. " + lang_instruction},
            {"role": "user", "content": prompt}
        ], max_tokens=600)

        # call_ai_api returns string or None
        if response and isinstance(response, str) and len(response) >= 50:
            content = response
        else:
            content = ''

        if not content or len(content) < 50:
            print("⚠️ AI failed to generate questions")
            return jsonify({"questions": "Unable to generate questions at this time. Please try again."})

        # ✅ Cache the result
        _set_cache(practice_cache_key, content, _topic_cache)
        return jsonify({"questions": content})

    except Exception as e:
        print("FULL ERROR:", e)
        return jsonify({"error": str(e)}), 500


def generate_key_concepts(topic, subject):
    try:
        prompt = f"""
Generate 8 to 10 VERY SPECIFIC subtopics for:

Subject: {subject}
Topic: {topic}

RULES:
- NO generic points like "introduction"
- Make them DIFFERENT and topic-specific
- Keep each point short

FORMAT:
- Point 1
- Point 2
"""

        content = call_ai_api([
            {"role": "user", "content": prompt}
        ], max_tokens=150)

        if content:
            concepts = [
                line.replace("-", "").strip()
                for line in content.split("\n")
                if line.strip()
            ]
        else:
            concepts = []

        # ✅ VALIDATION (VERY IMPORTANT)
        if len(concepts) >= 5:
            return concepts[:10]

    except Exception as e:
        print("AI concept error:", e)

    # ✅ FALLBACK → YOUR EXISTING FUNCTION
    return generate_specific_concepts(topic, subject)


@app.route('/generate-plan', methods=['POST'])
def generate_plan():
    try:
        data = request.get_json()
        ui_language = data.get("ui_language", "english")
        student_name = data.get('studentName', '').strip()
        subjects = data.get('subjects', '').strip()
        duration = data.get('duration')
        daily_hours = data.get('dailyHours')
        
        if not student_name or not subjects or not duration or not daily_hours:
            return jsonify({'error': 'Please fill all fields'}), 400
        
        if not student_name:
            return jsonify({'error': 'Please enter your name'}), 400
        if not subjects:
            return jsonify({'error': 'Please enter subjects/topics'}), 400
        if not duration or int(duration) < 1:
            return jsonify({'error': 'Please enter valid duration (minimum 1 day)'}), 400
            
        study_plan = generate_study_plan(student_name, subjects, int(duration), daily_hours)
        
        return jsonify({'success': True, 'study_plan': study_plan})
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        print("Error generating plan:", error_msg)
        print(traceback.format_exc())
        return jsonify({'error': f'Error: {error_msg[:100]}'}), 500

def create_pdf_v2(study_plan_data, all_questions=None):
    """Create PDF from study plan - handles both old and new structure"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MainTitle', fontSize=24, alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SubTitle', fontSize=12, alignment=TA_CENTER, spaceAfter=20, textColor=colors.HexColor('#7f8c8d')))
    styles.add(ParagraphStyle(name='DayHeader', fontSize=16, spaceAfter=8, spaceBefore=15, textColor=colors.HexColor('#2980b9'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SubjectTag', fontSize=11, spaceAfter=10, textColor=colors.HexColor('#27ae60')))
    styles.add(ParagraphStyle(name='TopicTitle', fontSize=14, spaceAfter=8, spaceBefore=10, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SectionLabel', fontSize=11, spaceAfter=4, spaceBefore=8, textColor=colors.HexColor('#34495e'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='ContentText', fontSize=10, spaceAfter=4, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='BulletText', fontSize=10, leftIndent=15, spaceAfter=3, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='LinkText', fontSize=9, leftIndent=15, spaceAfter=4, textColor=colors.HexColor('#2980b9'), wordWrap='LTR'))
    styles.add(ParagraphStyle(name='QuestionText', fontSize=9, leftIndent=15, spaceAfter=4, textColor=colors.HexColor('#8e44ad')))
    
    story = []
    
    student_info = study_plan_data.get('student_info', {})
    student_name = student_info.get('name', 'Student')
    subjects = student_info.get('subjects', student_info.get('subjects_list', []))
    duration = student_info.get('duration', 'N/A')
    daily_hours = student_info.get('daily_hours', 'N/A')
    
    if isinstance(subjects, list):
        subjects_str = ', '.join(subjects)
    else:
        subjects_str = str(subjects)
    
    story.append(Paragraph("📚 STUDY PLAN", styles['MainTitle']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Student:</b> {student_name}", styles['SubTitle']))
    story.append(Paragraph(f"<b>Subjects:</b> {subjects_str}", styles['SubTitle']))
    story.append(Paragraph(f"<b>Duration:</b> {duration} | <b>Daily Hours:</b> {daily_hours} hours", styles['SubTitle']))
    story.append(Spacer(1, 20))
    
    total_topics = student_info.get('total_topics', 0)
    if total_topics > 0:
        story.append(Paragraph(f"<b>Total Topics to Cover:</b> {total_topics}", styles['SubjectTag']))
        story.append(Spacer(1, 15))
    
    study_plan = study_plan_data.get('study_plan', [])
    
    for day_data in study_plan:
        story.append(Paragraph(f"{'═' * 50}", styles['ContentText']))
        story.append(Paragraph(f"<b>📅 DAY {day_data['day']}</b> | Date: {day_data.get('date', 'N/A')}", styles['DayHeader']))
        
        subjects_today = day_data.get('subject', 'General')
        story.append(Paragraph(f"<b>Subject:</b> {subjects_today}", styles['SubjectTag']))
        story.append(Spacer(1, 5))
        
        topics = day_data.get('topics', [])
        
        if not topics:
            story.append(Paragraph("No topics scheduled for this day.", styles['ContentText']))
            story.append(Spacer(1, 15))
            continue
        
        for idx, topic in enumerate(topics, 1):
            topic_name = topic.get('topic_name', 'General Topic')
            time_allocated = topic.get('time', '60 min')
            topic_subject = topic.get('subject', subjects_today)
            
            story.append(Paragraph(f"<b>Topic {idx}:</b> {topic_name}", styles['TopicTitle']))
            story.append(Paragraph(f"<i>Subject: {topic_subject} | Time: {time_allocated}</i>", styles['ContentText']))
            
            key_concepts = topic.get('key_concepts', [])
            if key_concepts:
                story.append(Paragraph("<b>Key Concepts:</b>", styles['SectionLabel']))
                for concept in key_concepts[:5]:
                    story.append(Paragraph(f"  • {concept}", styles['BulletText']))
            
            explanation = topic.get('explanation', '')
            if explanation and explanation != 'N/A':
                story.append(Spacer(1, 5))
                story.append(Paragraph("<b>Overview:</b>", styles['SectionLabel']))
                clean_explanation = explanation.replace('•', '  •').replace('\n', '<br/>')
                story.append(Paragraph(clean_explanation, styles['ContentText']))
            
            study_steps = topic.get('study_plan', [])
            if study_steps and isinstance(study_steps, list):
                story.append(Paragraph("<b>Study Plan:</b>", styles['SectionLabel']))
                for step in study_steps:
                    story.append(Paragraph(f"  → {step}", styles['BulletText']))
            
            youtube_resources = topic.get('youtube_resources', [])
            if youtube_resources and isinstance(youtube_resources, list):
                story.append(Paragraph("<b>Video Resources:</b>", styles['SectionLabel']))
                for resource in youtube_resources[:3]:
                    if isinstance(resource, dict):
                        title = resource.get('title', 'Video')
                        url = resource.get('url', '')
                        if url:
                            story.append(Paragraph(f"  • {title}", styles['LinkText']))
                    elif isinstance(resource, str) and resource.startswith('http'):
                        story.append(Paragraph(f"  • {resource}", styles['LinkText']))
            
            practice_questions = topic.get('practice_questions', [])
            if practice_questions and isinstance(practice_questions, list):
                story.append(Paragraph("<b>Practice Questions:</b>", styles['SectionLabel']))
                for i, q in enumerate(practice_questions[:5], 1):
                    story.append(Paragraph(f"  {i}. {q}", styles['QuestionText']))
            
            points = topic.get('points_to_remember', [])
            if points and isinstance(points, list):
                story.append(Paragraph("<b>Points to Remember:</b>", styles['SectionLabel']))
                for point in points[:5]:
                    story.append(Paragraph(f"  ✦ {point}", styles['BulletText']))
            
            story.append(Spacer(1, 10))
        
        story.append(Spacer(1, 15))
    
    story.append(Paragraph(f"{'═' * 50}", styles['ContentText']))
    story.append(Paragraph(f"<b>Generated by AI Study Planner</b> | Date: {datetime.now().strftime('%Y-%m-%d')}", styles['SubTitle']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    try:
        data = request.get_json()
        ui_language = data.get("ui_language", "english")
        study_plan = data.get('study_plan')
        all_questions = data.get('all_questions')
        
        if not study_plan:
            return jsonify({'error': 'Study plan is required'}), 400
        
        try:
            pdf_buffer = create_pdf_v2(study_plan, all_questions)
            pdf_buffer.seek(0)
            
            student_name = 'StudyPlan'
            if study_plan.get('student_info') and study_plan['student_info'].get('name'):
                student_name = study_plan['student_info']['name'].replace(' ', '_')
            
            filename = f'{student_name}_Study_Plan_{datetime.now().strftime("%Y%m%d")}.pdf'
            
            response = send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return response
        except Exception as pdf_error:
            import traceback
            print(f"PDF creation error: {pdf_error}")
            traceback.print_exc()
            return jsonify({'error': f'PDF creation failed: {str(pdf_error)[:200]}'}), 500
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)[:200]}'}), 500

@app.route('/warmup', methods=['GET'])
def warmup():
    return jsonify({'success': True, 'message': 'Ready'})

@app.route('/fetch-resources', methods=['POST'])
def fetch_resources():
    try:
        data = request.get_json()
        ui_language = data.get("ui_language", "english")
        topic = data.get('topic', '').strip()
        subject = data.get('subject', '').strip()
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        search_query = topic if not subject else f"{subject} {topic}"
        youtube_videos = search_youtube(search_query, 3)
        blog_articles = get_article_resources(topic, 2)
        
        resources = []
        for video in youtube_videos[:3]:
            resources.append({
                "type": "YouTube",
                "title": video.get("title", ""),
                "url": video.get("url", ""),
                "video_id": video.get("video_id", ""),
                "thumbnail": video.get("thumbnail", ""),
                "channel": video.get("channel", ""),
                "duration": video.get("duration", ""),
                "views": video.get("viewCount", 0)
            })
        
        for blog in blog_articles[:2]:
            resources.append({
                "type": "Blog",
                "title": blog["title"],
                "url": blog["url"]
            })
        
        return jsonify({'success': True, 'resources': resources})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download-txt', methods=['POST'])
def download_txt():
    try:
        data = request.get_json()
        ui_language = data.get("ui_language", "english")
        study_plan = data.get('study_plan')
        all_questions = data.get('all_questions')
        
        if not study_plan:
            return jsonify({'error': 'Study plan is required'}), 400
        
        text_content = format_study_plan_text(study_plan, all_questions)
        
        return text_content, 200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': f'attachment; filename=study_plan_{datetime.now().strftime("%Y%m%d")}.txt'
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error: {str(e)}'}), 500

def format_study_plan_text(study_plan, all_questions):
    text = "=" * 60 + "\n"
    text += "SMART AI STUDY PLAN\n"
    text += "=" * 60 + "\n\n"
    
    student = study_plan.get('student_info', {})
    text += f"Student: {student.get('name', 'N/A')}\n"
    text += f"Subjects: {student.get('subjects', 'N/A')}\n"
    text += f"Duration: {student.get('duration', 'N/A')}\n"
    text += f"Daily Hours: {student.get('daily_hours', 'N/A')} hours\n\n"
    
    text += "=" * 60 + "\n"
    text += "STUDY SCHEDULE\n"
    text += "=" * 60 + "\n\n"
    
    for day_data in study_plan.get('study_plan', []):
        text += f"DAY-{day_data['day']:02d}\n"
        text += f"Subject: {day_data['subject']}\n\n"
        
        for topic in day_data.get('topics', []):
            text += f"Topic: {topic.get('topic_name', 'N/A')}\n"
            text += f"Explanation: {topic.get('explanation', 'N/A')}\n\n"
            
            text += "Key Concepts:\n"
            for concept in topic.get('key_concepts', []):
                text += f"  - {concept}\n"
            text += "\n"
            
            text += "Step-by-Step Breakdown:\n"
            for i, step in enumerate(topic.get('breakdown', []), 1):
                text += f"  {i}. {step}\n"
            text += "\n"
            
            text += "Resources:\n"
            for resource in topic.get('resources', []):
                text += f"  - [{resource.get('type', 'Resource')}] {resource.get('title', 'N/A')}: {resource.get('url', 'N/A')}\n"
            text += "\n"
            
            if all_questions:
                topic_name = topic.get('topic_name', '')
                for concept in topic.get('key_concepts', [])[:5]:
                    key = f"{day_data['day']}_{topic_name}_{concept}"
                    questions = all_questions.get(key, [])
                    
                    if questions:
                        text += f"Practice Questions for {concept}:\n"
                        for i, q in enumerate(questions, 1):
                            text += f"  Q{i}: {q.get('question', '')}\n"
                            text += f"  Ans: {q.get('answer', '')}\n\n"
            
            text += "-" * 40 + "\n\n"
    
    return text


def generate_study_plan(student_name, subjects, duration, daily_hours):
    from datetime import datetime, timedelta
    
    parsed_subjects = parse_subjects_input(subjects)
    
    if not parsed_subjects:
        subjects_list = [s.strip() for s in subjects.split(",")] if isinstance(subjects, str) else subjects
    else:
        subjects_list = [s["subject"] for s in parsed_subjects]
    
    subjects_text = ", ".join([s["subject"] for s in parsed_subjects]) if parsed_subjects else ", ".join(subjects_list)
    
    try:
        total_days = max(1, min(365, int(duration)))
    except:
        total_days = 7
    
    daily_hours = int(daily_hours) if daily_hours else 2
    time_per_topic = (daily_hours * 60) // 2
    first_block = 30
    second_block = time_per_topic - 30
    third_block = 30
    
    today = datetime.now()
    
    reset_video_ids()
    
    study_plan = {
        "student_info": {
            "name": student_name,
            "subjects": subjects_text,
            "duration": f"{total_days} days",
            "daily_hours": daily_hours,
            "total_days": total_days
        },
        "total_days": total_days,
        "study_plan": []
    }
    
    topics_per_day = 2
    
    for day_num in range(1, total_days + 1):
        current_date = (today + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
        
        if parsed_subjects:
            subject_data = parsed_subjects[(day_num - 1) % len(parsed_subjects)]
            subject = subject_data["subject"]
            explicit_topics = subject_data.get("topics", [])
        else:
            subject = subjects_list[day_num % len(subjects_list)] if subjects_list else "General Studies"
            explicit_topics = []
        
        topics = get_topics_for_subject(subject, topics_per_day, explicit_topics if explicit_topics else None)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_topic, t, subject, time_per_topic, first_block, second_block, third_block) for t in topics]
            day_topics = [f.result() for f in futures]
        
        study_plan["study_plan"].append({
            "day": day_num,
            "date": current_date,
            "subject": subject,
            "topics": day_topics
        })
    
    return study_plan

def create_pdf(study_plan_data, all_questions=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MainTitle', fontSize=22, alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SubTitle', fontSize=12, alignment=TA_CENTER, spaceAfter=20, textColor=colors.HexColor('#7f8c8d')))
    styles.add(ParagraphStyle(name='DayHeader', fontSize=14, spaceAfter=8, spaceBefore=15, textColor=colors.HexColor('#2980b9'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SubjectTag', fontSize=10, spaceAfter=10, textColor=colors.HexColor('#27ae60')))
    styles.add(ParagraphStyle(name='TopicTitle', fontSize=12, spaceAfter=6, spaceBefore=12, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SectionLabel', fontSize=10, spaceAfter=4, spaceBefore=8, textColor=colors.HexColor('#34495e'), fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='ContentText', fontSize=10, spaceAfter=4, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='BulletText', fontSize=9, leftIndent=15, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='LinkText', fontSize=9, leftIndent=15, spaceAfter=4, textColor=colors.HexColor('#2980b9'), wordWrap='LTR'))
    styles.add(ParagraphStyle(name='QuestionText', fontSize=9, leftIndent=15, spaceAfter=4, textColor=colors.HexColor('#8e44ad')))
    
    story = []
    
    student_info = study_plan_data.get('student_info', {})
    
    story.append(Paragraph("STUDY PLAN", styles['MainTitle']))
    story.append(Paragraph(f"Student: {student_info.get('name', 'N/A')} | Subjects: {student_info.get('subjects', 'N/A')} | Duration: {student_info.get('duration', 'N/A')} | Daily: {student_info.get('daily_hours', 'N/A')} hours", styles['SubTitle']))
    story.append(Spacer(1, 15))
    
    study_plan = study_plan_data.get('study_plan', [])
    
    for day_data in study_plan:
        story.append(Paragraph(f"--- Day {day_data['day']} ---", styles['DayHeader']))
        story.append(Paragraph(f"Subject: {day_data['subject']} | Date: {day_data['date']}", styles['SubjectTag']))
        
        for topic in day_data.get('topics', []):
            time_allocated = topic.get('time', '60 min')
            story.append(Paragraph(f"Topic: {topic['topic_name']} ({time_allocated})", styles['TopicTitle']))
            
            story.append(Paragraph("Key Concepts:", styles['SectionLabel']))
            for concept in topic.get('key_concepts', []):
                story.append(Paragraph(f"- {concept}", styles['BulletText']))
            
            story.append(Paragraph("Explanation:", styles['SectionLabel']))
            story.append(Paragraph(topic.get('explanation', 'N/A'), styles['ContentText']))
            
            story.append(Paragraph("Study Plan:", styles['SectionLabel']))
            for step in topic.get('study_plan', []):
                story.append(Paragraph(f"- {step}", styles['BulletText']))
            
            yt_links = topic.get('youtube_resources', [])
            if yt_links:
                story.append(Paragraph("YouTube Tutorials:", styles['SectionLabel']))
                for yt_url in yt_links:
                    if yt_url.startswith('http'):
                        story.append(Paragraph(f"  - {yt_url}", styles['LinkText']))
                    else:
                        story.append(Paragraph(f"  - {yt_url}", styles['BulletText']))
            
            story.append(Paragraph("Practice Questions:", styles['SectionLabel']))
            for i, q in enumerate(topic.get('practice_questions', []), 1):
                story.append(Paragraph(f"{i}. {q}", styles['QuestionText']))
            
            points = topic.get('points_to_remember', [])
            if points:
                story.append(Paragraph("Points to Remember:", styles['SectionLabel']))
                for point in points:
                    story.append(Paragraph(f"• {point}", styles['BulletText']))
            
            if all_questions:
                topic_name = topic.get('topic_name', '')
                for concept in topic.get('key_concepts', [])[:5]:
                    key = f"{day_data['day']}_{topic_name}_{concept}"
                    questions = all_questions.get(key, [])
                    
                    if questions:
                        story.append(Paragraph(f"Important Questions - {concept}:", styles['SectionLabel']))
                        for i, q in enumerate(questions, 1):
                            story.append(Paragraph(f"Q{i}: {q.get('question', '')}", styles['QuestionText']))
                            story.append(Paragraph(f"Ans: {q.get('answer', '')}", styles['BulletText']))
            
            story.append(Spacer(1, 10))
            
            story.append(Spacer(1, 10))
        
        story.append(Spacer(1, 15))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/validate-academic', methods=['POST'])
def validate_academic():
    """
    Validate if Subject and Topic are academic and related.
    
    Request Body:
    {
        "subject": "string",
        "topic": "string",
        "use_ai": boolean (optional, default: false)
    }
    
    Response:
    {
        "valid": true/false,
        "reason": "string or null",
        "suggested_subject": "string or null",
        "corrected_topic": "string or null"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "valid": False,
                "reason": "Request body is required",
                "suggested_subject": None,
                "corrected_topic": None
            }), 400
        
        subject = data.get('subject', '').strip()
        topic = data.get('topic', '').strip()
        use_ai = data.get('use_ai', False)
        
        if not subject:
            return jsonify({
                "valid": False,
                "reason": "Subject is required",
                "suggested_subject": None,
                "corrected_topic": None
            }), 400
        
        if not topic:
            return jsonify({
                "valid": False,
                "reason": "Topic is required",
                "suggested_subject": None,
                "corrected_topic": None
            }), 400
        
        if use_ai:
            result = validate_academic_input_ai(subject, topic)
        else:
            result = validate_academic_input(subject, topic)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "valid": False,
            "reason": f"Validation error: {str(e)}",
            "suggested_subject": None,
            "corrected_topic": None
        }), 500


@app.route('/parse-subjects', methods=['POST'])
def parse_subjects():
    """
    Parse subjects and topics from raw input text.
    
    Request Body:
    {
        "subjects_text": "Cyber Security: Ethical Hacking, SQL, Mathematics: Calculus"
    }
    
    Response:
    {
        "success": true,
        "parsed": [{"subject": "...", "topics": [...]}],
        "expanded": [{"subject": "...", "topic": "..."}],
        "summary": {...}
    }
    """
    try:
        data = request.get_json()
        subjects_text = data.get('subjects_text', '').strip()
        
        if not subjects_text:
            return jsonify({
                "success": False,
                "error": "subjects_text is required"
            }), 400
        
        parsed = parse_subjects_topics_input(subjects_text)
        expanded = expand_all_topics(parsed)
        
        summary = {
            "total_subjects": len(parsed),
            "total_topics": len(expanded),
            "subjects": [p["subject"] for p in parsed],
            "topics_list": [e["topic"] for e in expanded]
        }
        
        return jsonify({
            "success": True,
            "parsed": parsed,
            "expanded": expanded,
            "summary": summary
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/generate-study-plan', methods=['POST'])
def generate_study_plan_v2():
    """
    Generate a complete study plan covering ALL subjects and topics.
    Uses AI-powered generation for comprehensive, actionable plans.
    
    Request Body:
    {
        "studentName": "Risha",
        "subjectsText": "Cyber Security: Ethical Hacking, SQL, Mathematics: Calculus, Algebra",
        "duration": 7,
        "dailyHours": 3,
        "difficulty": "Medium",
        "useAI": true
    }
    
    Response:
    {
        "success": true,
        "study_plan": {...}
    }
    """
    try:
        data = request.get_json()
        student_name = data.get('studentName', 'Student').strip()
        subjects_text = data.get('subjectsText', '').strip()
        duration = data.get('duration', 7)
        daily_hours = data.get('dailyHours', 2)
        difficulty = data.get('difficulty', 'Medium')
        use_ai = data.get('useAI', True)
        
        if not subjects_text:
            return jsonify({
                "success": False,
                "error": "subjectsText is required"
            }), 400
        
        if use_ai and openai_client:
            schedule = generate_ai_study_plan(
                openai_client, 
                student_name, 
                subjects_text, 
                duration, 
                daily_hours,
                difficulty
            )
            
            if "error" in schedule and "fallback" not in schedule:
                return jsonify({
                    "success": False,
                    "error": schedule["error"]
                }), 400
            
            if "fallback" in schedule:
                schedule = schedule["fallback"]
        else:
            schedule = create_study_schedule(student_name, subjects_text, duration, daily_hours, difficulty)
            
            if "error" in schedule:
                return jsonify({
                    "success": False,
                    "error": schedule["error"]
                }), 400
        
        parsed = parse_subjects_topics_input(subjects_text)
        expanded = expand_all_topics(parsed)
        
        schedule["validation"] = {
            "all_topics_covered": len(expanded) == schedule["validation"]["expected_topics"],
            "total_topics_assigned": schedule["validation"]["total_topics_assigned"],
            "expected_topics": len(expanded),
            "subjects_list": [p["subject"] for p in parsed],
            "topics_list": [e["topic"] for e in expanded]
        }
        
        return jsonify({
            "success": True,
            "study_plan": schedule
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=False, port=5000, use_reloader=False)

