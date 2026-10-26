"""
Flask Web Interface for Astro KB Pipeline Testing
"""

import os
import json
import re
import time
import threading
import unicodedata
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import sys
import numpy as np
from scipy.spatial.distance import cosine
from dotenv import load_dotenv

# Load environment variables from .env - explicitly load from project root
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)
print(f"🔧 Loading .env from: {_env_path}")
print(f"✅ GEMINI_API_KEY set: {'Yes' if os.getenv('GEMINI_API_KEY') else 'No'}")
print(f"✅ GEMINI_MODEL: {os.getenv('GEMINI_MODEL', 'NOT SET')}")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Try to load semantic transformer
try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False
    print("⚠️  sentence-transformers not available. Semantic search disabled.")

try:
    from huggingface_hub import snapshot_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

app = Flask(__name__, template_folder='templates', static_folder='static')

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEYS = [key.strip() for key in os.getenv("GEMINI_API_KEYS", "").split(",") if key.strip()]
if GEMINI_API_KEY and GEMINI_API_KEY not in GEMINI_API_KEYS:
    GEMINI_API_KEYS.insert(0, GEMINI_API_KEY)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
# Optimisation quotas: Utiliser UNIQUEMENT gemini-2.5-flash-lite
# - Gratuit: 10 req/min, 1500 req/jour
# - Avec billing: 50+ req/min (500K+ req/jour)
GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite").split(",")
    if model.strip()
]
if GEMINI_MODEL and GEMINI_MODEL not in GEMINI_FALLBACK_MODELS:
    GEMINI_FALLBACK_MODELS.insert(0, GEMINI_MODEL)
GEMINI_REQUEST_DELAY = float(os.getenv("GEMINI_REQUEST_DELAY", "4.5"))  # délai min par clé
GEMINI_MAX_RETRIES = max(0, int(os.getenv("GEMINI_MAX_RETRIES", "1")))
GEMINI_LAST_ERROR = None
GEMINI_KEY_LAST_CALL = {}
MIN_CHUNK_CHARS = 50
MIN_LEGIBLE_CHAR_RATIO = 0.60
DEFAULT_RETRIEVAL_QUALITY = "clean"
SUBJECT_ALIASES = {
    "anglais": "anglais",
    "englais": "anglais",
    "english": "anglais",
}
SOURCE_TYPE_BONUS = {
    "manuel": 0.30,
    "cahier_activites": 0.25,
    "programme_officiel": 0.20,
    "exercices": 0.0,
}
SOURCE_FILE_PENALTY_TERMS = (
    "إمتحان",
    "امتحان",
    "devoir",
    "test",
    "evaluation",
    "évaluation",
    "controle",
    "contrôle",
)
QUERY_TERM_EXPANSIONS = {
    "pronom": ["pronoms", "personnel", "personnels"],
    "pronoms": ["pronom", "personnel", "personnels"],
    "determinant": ["determinants", "article", "articles"],
    "déterminant": ["determinants", "article", "articles"],
    "fraction": ["fractions", "numerateur", "denominateur"],
    "fractions": ["fraction", "numerateur", "denominateur"],
    "verbe": ["verbes", "conjugaison", "conjuguer"],
    "verbes": ["verbe", "conjugaison", "conjuguer"],
    "addition": ["additionner", "somme"],
    "soustraction": ["soustraire", "difference"],
}
TOPIC_MIN_GRADE_RULES = [
    (1, ["present", "verbe", "verbes", "phrase", "paragraphe", "addition", "soustraction", "lecture"]),
    (2, ["pluriel", "singulier", "conjugaison", "multiplication", "division"]),
    (3, ["imparfait", "fraction", "determinant", "determinants", "pronom", "pronoms"]),
    (4, ["proportion", "decimale", "decimales", "geometrie", "equation simple"]),
    (5, ["subjonctif", "pourcentage", "proportionnalite", "equation", "analyse de texte"]),
    (6, ["complement circonstanciel", "voix passive", "algebre", "fonction", "argumentation"]),
]
EDUCATION_KEYWORDS = {
    "fr": {
        "ecole", "education", "eleve", "prof", "professeur", "classe", "niveau", "primaire",
        "cours", "lecon", "exercice", "devoir", "matiere", "programme", "pedagogique", "grammaire",
        "conjugaison", "orthographe", "lecture", "arabe", "francais", "anglais", "math", "mathematique",
        "science", "histoire", "geographie", "fraction", "addition", "soustraction", "multiplication",
    },
    "en": {
        "education", "school", "student", "teacher", "class", "grade", "primary", "lesson", "exercise",
        "homework", "subject", "curriculum", "pedagogy", "grammar", "reading", "math", "mathematics",
        "science", "history", "geography", "fraction", "addition", "subtraction", "multiplication",
    },
    "ar": {
        "تعليم", "مدرسة", "تلميذ", "أستاذ", "استاذ", "قسم", "مستوى", "ابتدائي", "درس", "تمرين",
        "واجب", "مادة", "برنامج", "بيداغوجي", "قواعد", "قراءة", "رياضيات", "علوم", "تاريخ", "جغرافيا",
    },
}

# Configure JSON encoding
app.json.ensure_ascii = False

# Force UTF-8 encoding for all responses
@app.after_request
def set_utf8_header(response):
    if 'Content-Type' in response.headers:
        if 'application/json' in response.headers['Content-Type']:
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
        elif 'text/html' in response.headers['Content-Type']:
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

# Load KB chunks
def load_kb(strict=True):
    """Load KB chunks from JSON files.

    strict=True keeps only cleaner chunks for retrieval quality.
    strict=False keeps all chunks for full-data inspection.
    """
    kb_path = Path(__file__).parent / "data" / "json_out"
    chunks = []
    
    for json_file in kb_path.rglob("*_chunks.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                file_chunks = json.load(f)
                for chunk in file_chunks:
                    prepared_chunk = prepare_chunk(chunk, source_path=str(json_file), strict=strict)
                    if prepared_chunk:
                        chunks.append(prepared_chunk)
        except:
            pass
    
    return chunks


def detect_language(text):
    """Detect if text is Arabic or default to French for Latin-script text."""
    if not text:
        return "fr"

    arabic_count = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
    return "ar" if arabic_count > len(text) * 0.2 else "fr"


def strip_source_lines(text):
    """Remove explicit source markers from model answers for cleaner UX."""
    if not text:
        return text

    cleaned_lines = []
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        lowered = line.casefold()
        if lowered.startswith("source:"):
            continue
        if lowered.startswith("sources:"):
            continue
        if line.startswith("المصدر:"):
            continue
        cleaned_lines.append(raw_line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def enforce_answer_language(answer, target_language, question):
    """Ensure answer language follows requested language, with one corrective pass."""
    cleaned_answer = strip_source_lines(answer or "")
    if not cleaned_answer:
        return cleaned_answer

    if target_language == "ar":
        return cleaned_answer

    detected = detect_language(cleaned_answer)
    if target_language == "fr" and detected != "ar":
        return cleaned_answer
    if target_language == "en" and detected != "ar":
        return cleaned_answer

    if target_language == "en":
        rewrite_system = (
            "Rewrite the answer in clear English for a primary-school student. "
            "Do not include any source line or citation label."
        )
        rewrite_user = f"Question: {question}\n\nAnswer to rewrite:\n{cleaned_answer}"
    else:
        rewrite_system = (
            "Réécris cette réponse en français clair et simple pour un élève du primaire. "
            "N'ajoute aucune ligne Source ni citation."
        )
        rewrite_user = f"Question: {question}\n\nRéponse à réécrire:\n{cleaned_answer}"

    rewritten = generate_with_gemini(rewrite_system, rewrite_user, temperature=0.1, max_tokens=420)
    if not rewritten:
        rewritten = generate_with_openai(rewrite_system, rewrite_user, temperature=0.1, max_tokens=420)

    if rewritten:
        return strip_source_lines(rewritten)

    return cleaned_answer


def is_likely_mojibake(text):
    """Detect heavily corrupted extraction output that should be excluded."""
    if not text:
        return True

    visible_chars = [char for char in text if not char.isspace()]
    if not visible_chars:
        return True

    arabic_chars = sum(1 for char in visible_chars if '\u0600' <= char <= '\u06FF')
    latin_chars = sum(1 for char in visible_chars if ('a' <= char.lower() <= 'z') or char in "àâäçéèêëîïôöùûüÿœæ")
    digit_chars = sum(1 for char in visible_chars if char.isdigit())
    punctuation_chars = sum(1 for char in visible_chars if char in ".,;:!?()[]{}'\"-_/+*=#%@& ")

    mojibake_markers = set("°±²³´µ¶·¸¹»¼½¾ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïñòóôõöøùúûüýþÿ¢£¤¥¦¨©ª«¬®¯×÷ƒˆ˜€™‹›⁄−∂∆∏∑√∞∫≈≤≥◊`")
    suspicious_chars = sum(1 for char in visible_chars if char in mojibake_markers)

    legible_ratio = (arabic_chars + latin_chars + digit_chars + punctuation_chars) / len(visible_chars)
    suspicious_ratio = suspicious_chars / len(visible_chars)

    return legible_ratio < MIN_LEGIBLE_CHAR_RATIO or (arabic_chars == 0 and suspicious_ratio > 0.20)


def normalize_subject(subject):
    """Normalize subject names and merge common spelling variants."""
    normalized = (subject or "").strip().casefold()
    return SUBJECT_ALIASES.get(normalized, normalized)


def canonical_subject(subject):
    """Return a display-friendly canonical subject label."""
    normalized = normalize_subject(subject)
    if normalized == "anglais":
        return "Anglais"
    return (subject or "").strip() or "Inconnu"


def infer_chunk_language(chunk, text):
    """Infer chunk language, including explicit support for English sources."""
    subject = normalize_subject(chunk.get("subject"))
    source_file = (chunk.get("source_file") or "").casefold()

    if subject == "anglais" or "english" in source_file:
        return "en"

    return detect_language(text)


def tokenize(text):
    """Tokenize French/Arabic text with a simple unicode-aware regex."""
    return re.findall(r"\w+", (text or "").casefold(), flags=re.UNICODE)


def expand_query_terms(query):
    """Expand query with lightweight pedagogical synonyms/variants."""
    terms = set(tokenize(query))
    expanded = set(terms)
    for term in list(terms):
        expanded.update(QUERY_TERM_EXPANSIONS.get(term, []))
    return expanded


def jaccard_similarity(text_a, text_b):
    """Compute token-level Jaccard similarity for diversity control."""
    terms_a = set(tokenize(text_a))
    terms_b = set(tokenize(text_b))
    if not terms_a or not terms_b:
        return 0.0
    intersection = len(terms_a.intersection(terms_b))
    union = len(terms_a.union(terms_b))
    return intersection / union if union else 0.0


def keyword_score(query, chunk_text):
    """Score lexical overlap with query expansion and phrase bonus."""
    query_terms = expand_query_terms(query)
    chunk_terms = set(tokenize(chunk_text))
    if not query_terms:
        return 0.0

    overlap = len(query_terms.intersection(chunk_terms)) / len(query_terms)

    query_tokens = tokenize(query)
    chunk_lower = (chunk_text or "").casefold()
    phrase_bonus = 0.0
    if len(query_tokens) >= 2:
        phrase = " ".join(query_tokens[:4])
        if phrase and phrase in chunk_lower:
            phrase_bonus = 0.15

    return min(1.0, overlap + phrase_bonus)


def source_bonus(chunk):
    """Reward pedagogical sources and penalize exam-like files."""
    source_type = (chunk.get("source_type") or "").strip().lower()
    bonus = SOURCE_TYPE_BONUS.get(source_type, 0.0)

    source_file = (chunk.get("source_file") or "").casefold()
    if any(term.casefold() in source_file for term in SOURCE_FILE_PENALTY_TERMS):
        bonus -= 0.10

    return bonus


def prepare_chunk(chunk, source_path=None, strict=True):
    """Normalize and validate a chunk at load time."""
    text = (chunk.get("text") or "").strip()
    if strict and len(text) < MIN_CHUNK_CHARS:
        return None

    detected_language = infer_chunk_language(chunk, text)
    stored_language = (chunk.get("language") or "").strip().lower()
    if strict and is_likely_mojibake(text):
        return None

    prepared = dict(chunk)
    prepared["text"] = text
    prepared["subject"] = canonical_subject(prepared.get("subject"))
    prepared["chunk_uid"] = "::".join([
        str(source_path or prepared.get("source_file") or "unknown"),
        str(prepared.get("chunk_id") or "unknown"),
        str(prepared.get("chunk_index") or 0),
    ])
    prepared["subject_normalized"] = normalize_subject(prepared.get("subject"))
    prepared["detected_language"] = detected_language

    prepared["metadata_language"] = stored_language if stored_language in {"ar", "fr", "en"} else None
    prepared["language_mismatch"] = bool(prepared["metadata_language"] and prepared["metadata_language"] != detected_language)
    prepared["language"] = prepared["detected_language"]

    return prepared


def chunk_matches_filters(chunk, filters=None):
    """Apply hard filters before scoring."""
    filters = filters or {}

    if filters.get("grade") and chunk.get("grade") != filters["grade"]:
        return False

    if filters.get("language"):
        if chunk.get("language") != filters["language"]:
            return False

    if filters.get("subject"):
        requested_subject = normalize_subject(filters["subject"])
        chunk_subject = chunk.get("subject_normalized") or normalize_subject(chunk.get("subject"))
        if requested_subject and requested_subject not in chunk_subject:
            return False

    return True


def age_to_grade(age):
    """Map age ranges to Tunisian primary grades."""
    mapping = {
        6: 1,
        7: 2,
        8: 3,
        9: 4,
        10: 5,
        11: 6,
        12: 6,
    }
    return mapping.get(age)


def build_filters(grade=None, language=None, subject=None, age=None):
    """Normalize retrieval filters from request parameters."""
    resolved_grade = grade
    if resolved_grade is None and age is not None:
        resolved_grade = age_to_grade(age)

    filters = {}
    if resolved_grade:
        filters["grade"] = int(resolved_grade)
    if language and language != "auto":
        filters["language"] = language
    if subject:
        filters["subject"] = subject
    return filters


def keyword_search(query, filters=None, limit=5):
    """Fallback lexical retrieval when semantic search is unavailable."""
    filters = filters or {}
    results = []

    for chunk in RETRIEVAL_KB:
        if not chunk_matches_filters(chunk, filters):
            continue

        text = chunk.get("text", "")
        score = keyword_score(query, text)

        if score > 0:
            results.append((chunk, float(score)))

    results.sort(key=lambda item: item[1], reverse=True)
    return results[:limit]


def reciprocal_rank_fusion(result_lists, k=60):
    """Merge ranked result lists with reciprocal rank fusion (RRF)."""
    fused = {}
    chunk_lookup = {}

    for ranked_results in result_lists:
        for rank, (chunk, score) in enumerate(ranked_results, start=1):
            chunk_key = chunk.get("chunk_uid") or chunk.get("chunk_id")
            if not chunk_key:
                continue
            chunk_lookup[chunk_key] = chunk
            fused.setdefault(chunk_key, 0.0)
            fused[chunk_key] += 1.0 / (k + rank)
            fused[chunk_key] += 0.10 * max(0.0, float(score))

    merged = []
    for chunk_key, fused_score in fused.items():
        chunk = chunk_lookup[chunk_key]
        merged.append((chunk, fused_score + source_bonus(chunk)))

    merged.sort(key=lambda item: item[1], reverse=True)
    return merged


def mmr_select(results, limit, lambda_mult=0.72):
    """Apply Maximal Marginal Relevance to keep relevant but diverse chunks."""
    if not results:
        return []

    selected = [results[0]]
    remaining = list(results[1:])

    while remaining and len(selected) < limit:
        best_item = None
        best_mmr = -1e9

        for candidate in remaining:
            cand_chunk, cand_score = candidate
            max_similarity = max(
                jaccard_similarity(cand_chunk.get("text", ""), picked_chunk.get("text", ""))
                for picked_chunk, _ in selected
            )
            mmr_score = (lambda_mult * float(cand_score)) - ((1 - lambda_mult) * max_similarity)
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_item = candidate

        if best_item is None:
            break

        selected.append(best_item)
        remaining.remove(best_item)

    return selected


def retrieve_relevant_chunks(query, filters=None, limit=3):
    """Retrieve relevant chunks with hybrid fusion and MMR diversification."""
    filters = filters or {}
    top_k = max(limit * 12, 30)
    keyword_results = keyword_search(query, filters=filters, limit=top_k)

    semantic_results = SEARCH_ENGINE.search_semantic(query, top_k=top_k, filters=filters)
    if semantic_results:
        fused = reciprocal_rank_fusion([semantic_results, keyword_results])
        selected = mmr_select(fused, limit=limit)
        return selected, "hybrid_rrf_mmr"

    # Fallback still uses diversification so retrieval is not plain lexical only.
    keyword_ranked = [(chunk, float(score) + source_bonus(chunk)) for chunk, score in keyword_results]
    selected = mmr_select(keyword_ranked, limit=limit)
    return selected, "keyword_mmr"


def build_rag_prompt(question, chunks, language, grade=None, conversation_history=None):
    """Build a constrained prompt using retrieved course excerpts."""
    language_label = {
        "ar": "العربية",
        "fr": "français",
        "en": "English",
    }.get(language, "français")
    grade_label = f"niveau {grade}" if grade else "niveau primaire"
    context_blocks = []

    for idx, chunk in enumerate(chunks, 1):
        context_blocks.append(
            f"[Source {idx}] chunk_id={chunk.get('chunk_id')} | fichier={chunk.get('source_file')} | matière={chunk.get('subject')} | niveau={chunk.get('grade')}\n{chunk.get('text', '')}"
        )

    context = "\n\n".join(context_blocks)
    pedagogical_mode = detect_pedagogical_mode(question)
    discussion_style = get_discussion_style_instruction(language)
    conversation_context = build_conversation_context(conversation_history, language)

    if language == "ar":
        system_prompt = (
            "أنت معلّم تونسي لمرحلة الابتدائي. أجب فقط باستعمال المعلومات الموجودة في المصادر. "
            "إذا كانت المعلومة غير موجودة، قل ذلك بوضوح. اجعل الجواب مناسبًا لعمر الطفل، واضحًا وقصيرًا. "
            "كيّف الشرح دائمًا مع المستوى الدراسي المحدد. إذا كان السؤال أعلى من المستوى، "
            "اذكر ذلك بلطف ثم قدم صياغة أبسط تناسب المستوى الحالي. "
            "اكتب الإجابة بالعربية فقط. لا تكتب سطر مصدر ولا أي تنسيق استشهاد."
        )
        system_prompt += " " + discussion_style
        mode_instruction = pedagogical_mode_instruction("ar", pedagogical_mode)
        if mode_instruction:
            system_prompt += " " + mode_instruction
        user_prompt = (
            f"لغة الإجابة: {language_label}\n"
            f"المستوى: {grade_label}\n"
            f"وضع التوليد: {pedagogical_mode}\n"
            f"سؤال التلميذ: {question}\n\n"
            f"المصادر الرسمية:\n{context}"
        )
        if conversation_context:
            user_prompt += "\n\n" + conversation_context
    elif language == "en":
        system_prompt = (
            "You are a Tunisian primary school teacher. Answer only with information found in the provided sources. "
            "If the information is missing, say so clearly. Keep the answer short, simple, and appropriate for a child. "
            "Always adapt to the student's grade. If the question is above level, say it kindly and provide a simpler version. "
            "Write the answer in English only. Do not add source lines or citation labels."
        )
        system_prompt += " " + discussion_style
        mode_instruction = pedagogical_mode_instruction("en", pedagogical_mode)
        if mode_instruction:
            system_prompt += " " + mode_instruction
        user_prompt = (
            f"Answer language: {language_label}\n"
            f"Level: {grade_label}\n"
            f"Generation mode: {pedagogical_mode}\n"
            f"Student question: {question}\n\n"
            f"Official sources:\n{context}"
        )
        if conversation_context:
            user_prompt += "\n\n" + conversation_context
    else:
        system_prompt = (
            "Tu es un professeur tunisien du primaire. Réponds uniquement avec les informations présentes dans les sources. "
            "Si l'information manque, dis-le clairement. La réponse doit être courte, claire et adaptée à l'enfant. "
            "Adapte toujours la réponse au niveau scolaire donné. Si la question est au-dessus du niveau, "
            "dis-le avec bienveillance puis propose une version simplifiée adaptée à la classe. "
            "Réponds en français uniquement. N'ajoute aucune ligne Source ni balise de citation."
        )
        system_prompt += " " + discussion_style
        mode_instruction = pedagogical_mode_instruction("fr", pedagogical_mode)
        if mode_instruction:
            system_prompt += " " + mode_instruction
        user_prompt = (
            f"Langue de réponse: {language_label}\n"
            f"Niveau: {grade_label}\n"
            f"Mode de generation: {pedagogical_mode}\n"
            f"Question de l'élève: {question}\n\n"
            f"Sources officielles:\n{context}"
        )
        if conversation_context:
            user_prompt += "\n\n" + conversation_context

    return system_prompt, user_prompt


def is_education_question(question, subject=None, grade=None, age=None):
    """Decide if the question should use educational RAG or general LLM mode."""
    if subject or grade or age:
        return True

    normalized_question = normalize_text_for_match(question)
    if not normalized_question:
        return False

    tokens = set(tokenize(normalized_question))
    keyword_hits = 0

    for lang_keywords in EDUCATION_KEYWORDS.values():
        for keyword in lang_keywords:
            normalized_keyword = normalize_text_for_match(keyword)
            if not normalized_keyword:
                continue
            if normalized_keyword in normalized_question or normalized_keyword in tokens:
                keyword_hits += 1
                if keyword_hits >= 1:
                    return True

    return False


def assess_grade_alignment(question, grade):
    """Estimate whether a question is above the learner's grade."""
    if not question or not grade:
        return {
            "is_advanced": False,
            "required_grade": None,
            "topic": None,
            "message": None,
        }

    normalized_question = normalize_text_for_match(question)
    if not normalized_question:
        return {
            "is_advanced": False,
            "required_grade": None,
            "topic": None,
            "message": None,
        }

    best_required_grade = 0
    best_topic = None
    for min_grade, keywords in TOPIC_MIN_GRADE_RULES:
        for keyword in keywords:
            normalized_keyword = normalize_text_for_match(keyword)
            if normalized_keyword and normalized_keyword in normalized_question and min_grade > best_required_grade:
                best_required_grade = min_grade
                best_topic = keyword

    if best_required_grade <= grade:
        return {
            "is_advanced": False,
            "required_grade": best_required_grade if best_required_grade else None,
            "topic": best_topic,
            "message": None,
        }

    message = (
        f"Ce sujet ({best_topic or 'cette notion'}) semble plutot de niveau {best_required_grade}eme primaire, "
        f"alors que l'eleve est en {grade}eme primaire."
    )
    return {
        "is_advanced": True,
        "required_grade": best_required_grade,
        "topic": best_topic,
        "message": message,
    }


def looks_like_no_info_answer(answer, language):
    """Detect refusal-like answers that only say no info was found."""
    if not answer:
        return True

    normalized = normalize_text_for_match(str(answer))
    if not normalized:
        return True

    patterns = {
        "fr": [
            "je ne trouve pas",
            "je n ai pas trouve",
            "pas d information",
            "aucune information",
            "sources fournies",
            "base locale",
            "pas trouve d extrait",
            "introuvable",
        ],
        "en": [
            "i could not find",
            "i cannot find",
            "no information",
            "not found in the sources",
            "local kb",
        ],
        "ar": [
            "لم اجد",
            "لا اجد",
            "لا توجد معلومات",
            "غير موجود",
            "في المصادر",
            "قاعدة المعرفة",
        ],
    }

    checks = patterns.get(language, patterns["fr"])
    return any(token in normalized for token in checks)


def generate_with_gemini(system_prompt, user_prompt, temperature=0.2, max_tokens=500):
    """Generate text with Gemini API if configured."""
    global GEMINI_LAST_ERROR
    GEMINI_LAST_ERROR = None

    if not GEMINI_AVAILABLE or not GEMINI_API_KEYS:
        GEMINI_LAST_ERROR = "Gemini SDK missing or GEMINI_API_KEY not configured."
        return None

    def _extract_retry_delay_seconds(error_text):
        if not error_text:
            return None
        retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", error_text, flags=re.IGNORECASE)
        if retry_match:
            try:
                return float(retry_match.group(1))
            except ValueError:
                return None
        return None

    try:
        for api_key in GEMINI_API_KEYS:
            attempted_models = set()
            # Respecter le quota minute par clé
            last_call_ts = GEMINI_KEY_LAST_CALL.get(api_key, 0.0)
            wait_seconds = GEMINI_REQUEST_DELAY - (time.time() - last_call_ts)
            if wait_seconds > 0:
                time.sleep(wait_seconds)

            genai.configure(api_key=api_key)

            for model_name in GEMINI_FALLBACK_MODELS:
                if not model_name or model_name in attempted_models:
                    continue
                attempted_models.add(model_name)

                attempt = 0
                while attempt <= GEMINI_MAX_RETRIES:
                    try:
                        model = genai.GenerativeModel(model_name=model_name)
                        response = model.generate_content(
                            [
                                {"role": "user", "parts": [system_prompt]},
                                {"role": "user", "parts": [user_prompt]},
                            ],
                            generation_config={
                                "temperature": temperature,
                                "max_output_tokens": max_tokens,
                            },
                        )
                        GEMINI_KEY_LAST_CALL[api_key] = time.time()

                        if not response:
                            break
                        text = getattr(response, "text", None)
                        if text:
                            return text.strip()

                        candidates = getattr(response, "candidates", None) or []
                        for candidate in candidates:
                            content = getattr(candidate, "content", None)
                            parts = getattr(content, "parts", None) or []
                            combined = "\n".join(getattr(part, "text", "") for part in parts if getattr(part, "text", ""))
                            if combined.strip():
                                return combined.strip()
                        break
                    except Exception as model_error:
                        err_text = str(model_error)
                        err_text_lower = err_text.lower()
                        GEMINI_LAST_ERROR = f"{model_name}: {err_text}"
                        print(f"Gemini model '{model_name}' failed: {model_error}")

                        is_429 = "429" in err_text or "toomanyrequests" in err_text_lower or "quota" in err_text_lower
                        is_503 = "503" in err_text or "serviceunavailable" in err_text_lower
                        is_daily_quota = "perday" in err_text_lower

                        if attempt >= GEMINI_MAX_RETRIES or is_daily_quota or not (is_429 or is_503):
                            break

                        retry_after = _extract_retry_delay_seconds(err_text)
                        if retry_after is None:
                            retry_after = min(8.0, 1.5 + (attempt * 2.0))
                        else:
                            retry_after = min(retry_after, 8.0)

                        time.sleep(max(0.5, retry_after))
                        attempt += 1
                        continue
    except Exception as e:
        GEMINI_LAST_ERROR = str(e)
        print(f"Gemini generation error: {e}")

    if not GEMINI_LAST_ERROR:
        GEMINI_LAST_ERROR = "Gemini returned an empty response."

    return None


def generate_with_openai(system_prompt, user_prompt, temperature=0.2, max_tokens=500):
    """Generate text with OpenAI if configured."""
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        return None

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except Exception as e:
        print(f"OpenAI generation error: {e}")
        return None


def generate_general_answer(question, language, grade=None, conversation_history=None):
    """Generate a non-RAG answer for general questions outside education domain.

    This role is intentionally child-friendly.
    """
    grade_label = f"niveau {grade}" if grade else "niveau primaire"
    discussion_context = build_conversation_context(conversation_history, language)
    if language == "ar":
        system_prompt = (
            "أنت مساعد لطيف للأطفال. "
            "أجب بلغة بسيطة وواضحة تناسب طفلًا في المرحلة الابتدائية. "
            "استعمل جمل قصيرة ومثالًا صغيرًا عندما يفيد ذلك. "
            "إذا كان السؤال خطيرًا أو غير مناسب، ارفض بلطف وقدّم بديلًا آمنًا. "
            + get_discussion_style_instruction("ar")
        )
        user_prompt = f"المستوى: {grade_label}\nالسؤال: {question}"
        fallback = "وضع تجريبي: فعّل Gemini عبر GEMINI_API_KEY للحصول على إجابة ذكية كاملة."
    elif language == "en":
        system_prompt = (
            "You are a kind assistant for children. "
            "Answer in simple words for primary-school level, with short clear sentences. "
            "When useful, include one tiny example. "
            "If a request is unsafe or inappropriate, refuse politely and suggest a safe alternative. "
            + get_discussion_style_instruction("en")
        )
        user_prompt = f"Level: {grade_label}\nQuestion: {question}"
        fallback = "Demo mode: set GEMINI_API_KEY to enable full intelligent responses."
    else:
        system_prompt = (
            "Tu es un assistant bienveillant pour les enfants. "
            "Réponds avec des mots simples, des phrases courtes, et un ton pédagogique adapté au primaire. "
            "Quand c'est utile, ajoute un mini exemple concret. "
            "Si la demande est dangereuse ou inadaptée, refuse poliment et propose une alternative sûre. "
            + get_discussion_style_instruction("fr")
        )
        user_prompt = f"Niveau: {grade_label}\nQuestion: {question}"
        fallback = "Mode demo: configure GEMINI_API_KEY pour activer des reponses intelligentes completes."

    if discussion_context:
        user_prompt += "\n\n" + discussion_context

    gemini_answer = generate_with_gemini(system_prompt, user_prompt, temperature=0.4, max_tokens=600)
    if gemini_answer:
        final_answer = enforce_answer_language(gemini_answer, language, question)
        return {
            "answer": final_answer,
            "mode": "gemini_general",
            "prompt_preview": None,
        }

    openai_answer = generate_with_openai(system_prompt, user_prompt, temperature=0.4, max_tokens=600)
    if openai_answer:
        final_answer = enforce_answer_language(openai_answer, language, question)
        return {
            "answer": final_answer,
            "mode": "openai_general",
            "prompt_preview": None,
            "llm_error": None,
        }

    gemini_configured = bool(GEMINI_AVAILABLE and GEMINI_API_KEYS)
    gemini_reason = None
    if gemini_configured and GEMINI_LAST_ERROR:
        gemini_reason = str(GEMINI_LAST_ERROR).splitlines()[0].strip()[:220]
        if language == "ar":
            fallback = f"تعذر الاتصال بـ Gemini حاليا: {gemini_reason}"
        elif language == "en":
            fallback = f"Gemini is temporarily unavailable: {gemini_reason}"
        else:
            fallback = f"Gemini est temporairement indisponible: {gemini_reason}"

    return {
        "answer": fallback,
        "mode": "general_fallback",
        "prompt_preview": {
            "system": system_prompt,
            "user": user_prompt,
        },
        "llm_error": gemini_reason,
    }


def generate_educational_fallback_answer(
    question,
    language,
    grade=None,
    subject=None,
    level_note=None,
    conversation_history=None,
):
    """Fallback for educational intent when KB retrieval has no direct match.

    The answer stays pedagogical and level-aware, while clearly stating that
    no exact source snippet was found in the local curriculum KB.
    """
    grade_label = f"niveau {grade}" if grade else "niveau primaire"
    subject_label = subject if subject else "matière non précisée"
    level_note = (level_note or "").strip()
    pedagogical_mode = detect_pedagogical_mode(question)
    discussion_context = build_conversation_context(conversation_history, language)

    if language == "ar":
        system_prompt = (
            "أنت معلّم تونسي للمرحلة الابتدائية. "
            "المطلوب: قدّم شرحًا تعليميًا بسيطًا وذكيًا مناسبًا للمستوى. "
            "إذا كان السؤال متقدمًا على المستوى، قل ذلك بلطف (مثل: هذا المستوى متقدم قليلًا الآن) "
            "ثم اقترح نسخة أسهل مناسبة للمستوى الحالي. "
            "لا تختلق مراجع أو مصادر. اختم بخطوة تدريب قصيرة. "
            + get_discussion_style_instruction("ar")
        )
        mode_instruction = pedagogical_mode_instruction("ar", pedagogical_mode)
        if mode_instruction:
            system_prompt += " " + mode_instruction
        user_prompt = (
            f"المستوى: {grade_label}\n"
            f"المادة: {subject_label}\n"
            f"وضع التوليد: {pedagogical_mode}\n"
            f"سؤال التلميذ: {question}\n"
            f"ملاحظة المستوى: {level_note or 'لا توجد ملاحظة إضافية'}\n"
            "ملاحظة: لا توجد نتيجة مباشرة في قاعدة المعرفة."
        )
        if discussion_context:
            user_prompt += "\n\n" + discussion_context
        fallback = (
            "سؤالك ممتاز. هذا الموضوع قد يكون متقدمًا قليلًا على مستواك الحالي في الابتدائي، "
            "لكن نقدر نبسطه خطوة خطوة بطريقة مناسبة لعمرك، ثم نتدرّب بتمرين صغير."
            if level_note
            else "سؤالك ممتاز. سنشرح الفكرة بطريقة مبسطة ومناسبة لمستواك، ثم نتدرّب بخطوة قصيرة."
        )
    elif language == "en":
        system_prompt = (
            "You are a Tunisian primary teacher. "
            "Provide a smart, child-friendly educational explanation for the level. "
            "If the question is above level, say it kindly and propose a simpler version for the current grade. "
            "Do not invent sources. End with one short practice step. "
            + get_discussion_style_instruction("en")
        )
        mode_instruction = pedagogical_mode_instruction("en", pedagogical_mode)
        if mode_instruction:
            system_prompt += " " + mode_instruction
        user_prompt = (
            f"Level: {grade_label}\n"
            f"Subject: {subject_label}\n"
            f"Generation mode: {pedagogical_mode}\n"
            f"Student question: {question}\n"
            f"Level note: {level_note or 'no extra level note'}\n"
            "Note: no direct match was found in the local knowledge base."
        )
        if discussion_context:
            user_prompt += "\n\n" + discussion_context
        fallback = (
            "Great question. This may be a bit advanced for your current primary level, "
            "but I can teach it in a simpler way for your grade and give you a short practice step."
            if level_note
            else "Great question. I will explain it in a simple way for your grade and add a short practice step."
        )
    else:
        system_prompt = (
            "Tu es un enseignant tunisien du primaire. "
            "Donne une explication pédagogique, claire et intelligente, adaptée au niveau. "
            "Si la question est au-dessus du niveau, dis-le avec bienveillance (ex: c'est un peu avancé pour ton niveau actuel), "
            "puis propose une version simplifiée adaptée à la classe. "
            "N'invente pas de sources et termine par un mini exercice. "
            + get_discussion_style_instruction("fr")
        )
        mode_instruction = pedagogical_mode_instruction("fr", pedagogical_mode)
        if mode_instruction:
            system_prompt += " " + mode_instruction
        user_prompt = (
            f"Niveau: {grade_label}\n"
            f"Matière: {subject_label}\n"
            f"Mode de generation: {pedagogical_mode}\n"
            f"Question de l'élève: {question}\n"
            f"Note de niveau: {level_note or 'aucune note supplementaire'}\n"
            "Note: aucune correspondance directe dans la base de connaissances."
        )
        if discussion_context:
            user_prompt += "\n\n" + discussion_context
        fallback = (
            "Très bonne question. Ce point est peut-être un peu avancé pour ton niveau actuel du primaire. "
            "Je peux te l'expliquer en version plus simple, adaptée à ta classe, puis te proposer un petit exercice."
            if level_note
            else "Très bonne question. Je vais te l'expliquer simplement selon ta classe, puis te proposer un petit exercice."
        )

    gemini_answer = generate_with_gemini(system_prompt, user_prompt, temperature=0.3, max_tokens=420)
    if gemini_answer:
        final_answer = enforce_answer_language(gemini_answer, language, question)
        return {
            "answer": final_answer,
            "mode": "gemini_edu_fallback",
            "prompt_preview": None,
        }

    openai_answer = generate_with_openai(system_prompt, user_prompt, temperature=0.3, max_tokens=420)
    if openai_answer:
        final_answer = enforce_answer_language(openai_answer, language, question)
        return {
            "answer": final_answer,
            "mode": "openai_edu_fallback",
            "prompt_preview": None,
            "llm_error": None,
        }

    return {
        "answer": fallback,
        "mode": "edu_fallback_no_llm",
        "prompt_preview": {
            "system": system_prompt,
            "user": user_prompt,
        },
        "llm_error": str(GEMINI_LAST_ERROR).splitlines()[0].strip()[:220] if GEMINI_LAST_ERROR else None,
    }


def extract_question_keywords(question, max_terms=8):
    """Extract lightweight keywords from a learner question."""
    stopwords = {
        "le", "la", "les", "de", "des", "du", "un", "une", "et", "ou", "pour", "dans", "sur", "avec",
        "que", "quoi", "qui", "est", "sont", "a", "au", "aux", "en", "d", "l", "il", "elle", "on",
        "the", "a", "an", "is", "are", "what", "how", "why", "to", "of", "for", "in", "on", "with",
        "ما", "ماذا", "كيف", "لماذا", "في", "من", "على", "الى", "إلى", "عن", "هو", "هي", "هذا", "هذه",
    }
    terms = []
    for token in tokenize(question):
        normalized = normalize_text_for_match(token)
        if len(normalized) < 3:
            continue
        if normalized in stopwords:
            continue
        terms.append(normalized)
        if len(terms) >= max_terms:
            break
    return terms


def normalize_text_for_match(text):
    """Normalize text for loose lexical matching (accents/plurals/case)."""
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized.endswith("s") and len(normalized) > 4:
        normalized = normalized[:-1]
    return normalized


def build_conversation_context(conversation_history, language, max_turns=6):
    """Format recent turns to keep continuity in child-facing discussions."""
    if not conversation_history:
        return ""

    sanitized = []
    for turn in conversation_history:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", "")).strip().lower()
        content = str(turn.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        sanitized.append({"role": role, "content": content[:700]})

    if not sanitized:
        return ""

    recent_turns = sanitized[-max_turns:]
    if language == "ar":
        header = "سياق الحوار السابق:"
        user_label = "الطفل"
        assistant_label = "المعلم"
    elif language == "en":
        header = "Previous conversation context:"
        user_label = "Child"
        assistant_label = "Teacher"
    else:
        header = "Contexte de discussion precedente :"
        user_label = "Enfant"
        assistant_label = "Enseignant"

    lines = []
    for turn in recent_turns:
        label = user_label if turn["role"] == "user" else assistant_label
        lines.append(f"- {label}: {turn['content']}")

    return header + "\n" + "\n".join(lines)


def get_discussion_style_instruction(language):
    """Force a friendly conversational style suitable for children."""
    if language == "ar":
        return (
            "اجعل الرد بصيغة حوار ودية مع الطفل: جمل قصيرة، نبرة مشجعة، "
            "وفي النهاية اسأل سؤال متابعة قصيرًا لتشجيع التفاعل."
        )
    if language == "en":
        return (
            "Keep a friendly discussion style for a child: short sentences, encouraging tone, "
            "and end with one short follow-up question."
        )
    return (
        "Garde un style de discussion bienveillant pour l'enfant: phrases courtes, ton encourageant, "
        "et termine par une courte question de relance."
    )


def request_mentions_questions(question):
    """Detect whether learner explicitly asks for follow-up questions/quiz."""
    normalized = normalize_text_for_match(question)
    if not normalized:
        return False

    markers = [
        "question",
        "questions",
        "quiz",
        "qcm",
        "pose moi",
        "اسئلة",
        "أسئلة",
        "اختبار",
        "كويز",
    ]
    return any(marker in normalized for marker in markers)


def _fallback_comprehension_questions(language, count=3):
    """Provide deterministic child-friendly questions when LLM is unavailable."""
    if language == "ar":
        base = [
            "1. ما الفكرة الأساسية في هذا النص؟",
            "2. ما أهم معلومة تعلّمتها من هذا المقطع؟",
            "3. هل يمكنك إعطاء مثال بسيط من حياتك مرتبط بالدرس؟",
        ]
    elif language == "en":
        base = [
            "1. What is the main idea of this text?",
            "2. What is one important thing you learned from this excerpt?",
            "3. Can you give one simple real-life example related to this lesson?",
        ]
    else:
        base = [
            "1. Quelle est l'idee principale de ce texte ?",
            "2. Quelle information importante as-tu retenue de cet extrait ?",
            "3. Donne un exemple simple de la vie courante lie a cette lecon.",
        ]
    return "\n".join(base[:count])


def generate_extract_questions(excerpt_text, language):
    """Generate short comprehension questions from extracted PDF lesson text."""
    if not excerpt_text:
        return _fallback_comprehension_questions(language)

    if language == "ar":
        system_prompt = (
            "أنت معلّم ابتدائي. أنشئ فقط 3 أسئلة فهم قصيرة جدًا حول النص. "
            "اكتبها مرقمة من 1 إلى 3، بدون أجوبة."
        )
        user_prompt = f"نص الدرس:\n{excerpt_text[:2200]}"
    elif language == "en":
        system_prompt = (
            "You are a primary teacher. Create exactly 3 short comprehension questions based on the text. "
            "Return numbered lines 1 to 3, no answers."
        )
        user_prompt = f"Lesson excerpt:\n{excerpt_text[:2200]}"
    else:
        system_prompt = (
            "Tu es enseignant au primaire. Cree exactement 3 questions de comprehension tres courtes a partir du texte. "
            "Retourne uniquement des lignes numerotees de 1 a 3, sans reponses."
        )
        user_prompt = f"Extrait du cours:\n{excerpt_text[:2200]}"

    generated = generate_with_gemini(system_prompt, user_prompt, temperature=0.2, max_tokens=220)
    if not generated:
        generated = generate_with_openai(system_prompt, user_prompt, temperature=0.2, max_tokens=220)
    if not generated:
        return _fallback_comprehension_questions(language)

    lines = [line.strip() for line in str(generated).splitlines() if line.strip()]
    numbered = []
    for idx, line in enumerate(lines, start=1):
        cleaned = re.sub(r"^\d+[\).\-\s]*", "", line).strip()
        if cleaned:
            numbered.append(f"{idx}. {cleaned}")
        if len(numbered) >= 3:
            break

    if len(numbered) < 3:
        return _fallback_comprehension_questions(language)
    return "\n".join(numbered)


def build_pdf_course_extract_answer(question, language, filters=None, subject=None):
    """Extract a grounded lesson excerpt directly from PDF chunks and format it clearly."""
    filters = filters or {}
    results, retrieval_mode = retrieve_relevant_chunks(question, filters=filters, limit=6)
    if not results:
        return {
            "success": False,
            "answer": None,
            "sources": [],
            "mode": "pdf_extract_no_match",
            "retrieval_mode": retrieval_mode,
        }

    def _chunk_quality_rank(chunk, base_score):
        text = (chunk.get("text") or "").strip()
        if not text:
            return -9999.0

        detected = chunk.get("detected_language") or chunk.get("language")
        language_bonus = 0.40 if detected == language else 0.0
        readability_penalty = -0.80 if is_likely_mojibake(text) else 0.0
        length_bonus = 0.10 if len(text) >= 120 else 0.0
        return float(base_score) + language_bonus + readability_penalty + length_bonus

    ranked_candidates = sorted(
        results,
        key=lambda item: _chunk_quality_rank(item[0], item[1]),
        reverse=True,
    )

    anchor_chunk, anchor_score = ranked_candidates[0]
    source_file = anchor_chunk.get("source_file")
    source_type = anchor_chunk.get("source_type")
    anchor_detected_language = anchor_chunk.get("detected_language") or anchor_chunk.get("language")

    same_file_chunks = [
        chunk
        for chunk in RETRIEVAL_KB
        if chunk.get("source_file") == source_file
    ]
    same_file_chunks.sort(key=lambda item: item.get("chunk_index", 0))

    readable_same_file_chunks = [
        chunk for chunk in same_file_chunks
        if not is_likely_mojibake((chunk.get("text") or "").strip())
    ]
    if readable_same_file_chunks:
        same_file_chunks = readable_same_file_chunks

    same_language_chunks = [
        chunk for chunk in same_file_chunks
        if (chunk.get("detected_language") or chunk.get("language")) == anchor_detected_language
    ]
    if same_language_chunks:
        same_file_chunks = same_language_chunks

    anchor_uid = anchor_chunk.get("chunk_uid")
    anchor_pos = 0
    for idx, chunk in enumerate(same_file_chunks):
        if chunk.get("chunk_uid") == anchor_uid:
            anchor_pos = idx
            break

    start = max(0, anchor_pos - 1)
    end = min(len(same_file_chunks), anchor_pos + 2)
    selected_chunks = same_file_chunks[start:end] if same_file_chunks else [anchor_chunk]

    excerpt_blocks = []
    sources = []
    for chunk in selected_chunks:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        excerpt_blocks.append(text)
        sources.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "source_file": chunk.get("source_file"),
                "source_type": chunk.get("source_type"),
                "grade": chunk.get("grade"),
                "subject": chunk.get("subject"),
                "language": chunk.get("language"),
                "score": float(anchor_score),
                "text": text[:400],
            }
        )

    excerpt_text = "\n\n".join(excerpt_blocks).strip()
    if len(excerpt_text) > 2600:
        excerpt_text = excerpt_text[:2600].rstrip() + "..."

    include_questions = request_mentions_questions(question)
    questions_block = ""
    if include_questions:
        generated_questions = generate_extract_questions(excerpt_text, language)
        if language == "ar":
            questions_block = f"\n\nاسئلة فهم سريعة:\n{generated_questions}"
        elif language == "en":
            questions_block = f"\n\nQuick comprehension questions:\n{generated_questions}"
        else:
            questions_block = f"\n\nQuestions de comprehension:\n{generated_questions}"

    grade_label = anchor_chunk.get("grade")
    subject_label = subject or anchor_chunk.get("subject") or "Inconnu"

    if language == "ar":
        answer = (
            "📄 استخراج مباشر من ملف PDF\n"
            f"المصدر: {source_file or 'غير معروف'} ({source_type or 'وثيقة'})\n"
            f"المستوى: {grade_label or 'ابتدائي'} | المادة: {subject_label}\n\n"
            "نص الدرس المستخرج:\n"
            "--------------------------------\n"
            f"{excerpt_text or 'لم يتم العثور على نص كافٍ في هذا المقطع.'}\n"
            "--------------------------------"
            f"{questions_block}"
        )
    elif language == "en":
        answer = (
            "📄 Direct extraction from PDF\n"
            f"Source: {source_file or 'unknown'} ({source_type or 'document'})\n"
            f"Grade: {grade_label or 'primary'} | Subject: {subject_label}\n\n"
            "Extracted lesson text:\n"
            "--------------------------------\n"
            f"{excerpt_text or 'No sufficient text found in this segment.'}\n"
            "--------------------------------"
            f"{questions_block}"
        )
    else:
        answer = (
            "📄 Extrait direct depuis le PDF\n"
            f"Source: {source_file or 'inconnue'} ({source_type or 'document'})\n"
            f"Niveau: {grade_label or 'primaire'} | Matiere: {subject_label}\n\n"
            "Texte du cours extrait:\n"
            "--------------------------------\n"
            f"{excerpt_text or 'Aucun texte suffisant trouve dans ce segment.'}\n"
            "--------------------------------"
            f"{questions_block}"
        )

    return {
        "success": True,
        "answer": answer,
        "sources": sources,
        "mode": "pdf_course_extract",
        "retrieval_mode": retrieval_mode,
    }


def detect_pedagogical_mode(question):
    """Detect explicit generation mode requested by the learner."""
    normalized_question = normalize_text_for_match(question)
    if not normalized_question:
        return "answer"

    quiz_markers = [
        "quiz",
        "qcm",
        "pose moi des questions",
        "exercice de revision",
        "اختبار",
        "كويز",
        "اسئلة",
        "أسئلة",
    ]
    revision_markers = [
        "revision",
        "reviser",
        "réviser",
        "question reponse",
        "questions reponses",
        "مراجعة",
        "راجع",
    ]
    lesson_markers = [
        "donne moi une lecon",
        "donner une lecon",
        "fais moi une lecon",
        "explique moi la lecon",
        "lesson",
        "give me a lesson",
        "teach me",
        "درس",
        "اعطني درس",
        "اعطيني درس",
        "اريد درس",
        "أريد درس",
        "شرح الدرس",
    ]
    extract_markers = [
        "extract",
        "extrait",
        "extraire",
        "texte du manuel",
        "texte de manuel",
        "depuis pdf",
        "from pdf",
        "raw text",
        "النص من pdf",
        "استخرج",
        "استخراج",
        "من pdf",
        "من الكتاب",
    ]

    if any(marker in normalized_question for marker in extract_markers):
        return "course_extract"

    if any(marker in normalized_question for marker in quiz_markers):
        return "quiz"
    if any(marker in normalized_question for marker in revision_markers):
        return "revision_qa"
    if any(marker in normalized_question for marker in lesson_markers):
        return "lesson"
    return "answer"


def is_lesson_request(question):
    """Backward-compatible helper kept for existing call sites."""
    return detect_pedagogical_mode(question) == "lesson"


def pedagogical_mode_instruction(language, mode):
    """Return strict output formatting instructions for requested pedagogical mode."""
    if mode == "lesson":
        if language == "ar":
            return (
                "نمط الإخراج إلزامي: اكتب الجواب بصيغة دفتر المعلمة وبعناوين واضحة بهذا الترتيب: "
                "1) عنوان الدرس، 2) الهدف من الدرس، 3) تمهيد قصير، 4) الشرح خطوة بخطوة بنقاط قصيرة، "
                "5) كلمات مفتاحية، 6) مثال محلول، 7) تمرين للتلميذ، 8) خلاصة قصيرة. "
                "استخدم لغة بسيطة مناسبة للابتدائي، وجمل قصيرة وواضحة."
            )
        if language == "en":
            return (
                "Output format is mandatory: write the response like a teacher notebook with these sections in order: "
                "1) Lesson Title, 2) Learning Objective, 3) Short Warm-up, 4) Step-by-step Explanation (bullet points), "
                "5) Key Vocabulary, 6) Solved Example, 7) Practice Task, 8) Short Summary. "
                "Use simple primary-school language and short clear sentences."
            )
        return (
            "Format obligatoire: reponds en style cahier de maitresse avec des sections dans cet ordre: "
            "1) Titre de la lecon, 2) Objectif, 3) Mise en route courte, 4) Explication pas a pas (puces), "
            "5) Mots cles, 6) Exemple resolu, 7) Exercice pour l'eleve, 8) Resume tres court. "
            "Utilise un vocabulaire simple de primaire et des phrases courtes."
        )

    if mode == "quiz":
        if language == "ar":
            return (
                "نمط الإخراج إلزامي: أنشئ كويز مراجعة قصير من 5 أسئلة متدرجة حول الدرس. "
                "التنسيق: عنوان قصير، ثم الأسئلة مرقمة 1 إلى 5، ثم قسم (التصحيح المختصر) مع إجابات قصيرة جدا. "
                "اجعل الأسئلة مناسبة لمستوى الابتدائي ومرتبطة مباشرة بالمصادر."
            )
        if language == "en":
            return (
                "Output format is mandatory: generate a short 5-question quiz based on the lesson. "
                "Format: short title, numbered questions (1 to 5), then a brief Answer Key section with very short answers. "
                "Keep questions primary-school level and source-grounded."
            )
        return (
            "Format obligatoire: genere un quiz court de 5 questions progressives sur la lecon. "
            "Format: titre court, questions numerotees 1 a 5, puis section Corrige bref avec des reponses tres courtes. "
            "Questions adaptees au primaire et ancrees dans les sources."
        )

    if mode == "revision_qa":
        if language == "ar":
            return (
                "نمط الإخراج إلزامي: أنشئ بطاقة مراجعة سؤال/جواب. "
                "قدّم 6 أسئلة قصيرة للمراجعة، وتحت كل سؤال جواب نموذجي قصير جدا في سطر مستقل. "
                "استخدم لغة بسيطة مناسبة للابتدائي."
            )
        if language == "en":
            return (
                "Output format is mandatory: create a revision Q&A sheet. "
                "Provide 6 short revision questions, and under each question add one very short model answer. "
                "Use simple primary-school language."
            )
        return (
            "Format obligatoire: cree une fiche de revision en mode question/reponse. "
            "Donne 6 questions courtes de revision, puis sous chaque question une reponse modele tres courte. "
            "Langage simple niveau primaire."
        )

    return ""


def extract_short_answer(chunk_text, question, max_chars=220):
    """Return a concise, readable sentence from retrieved chunk text."""
    clean_text = " ".join((chunk_text or "").split())
    if not clean_text:
        return ""

    sentences = re.split(r"(?<=[.!?؟])\s+", clean_text)
    normalized_keywords = extract_question_keywords(question)
    fallback_keywords = ["pronom", "personnel", "remplace", "nom", "determinant", "grammaire", "conjugaison"]
    if not normalized_keywords:
        normalized_keywords = fallback_keywords
    raw_keywords = [kw.casefold() for kw in tokenize(question) if len(kw) >= 4]

    scored_sentences = []
    for sentence in sentences:
        sentence_clean = " ".join(sentence.split())
        if len(sentence_clean) < 35:
            continue

        sentence_norm = normalize_text_for_match(sentence_clean)
        if not sentence_norm:
            continue

        # Avoid cover-page like lines with almost no pedagogical signal.
        alpha_chars = sum(1 for ch in sentence_clean if ch.isalpha())
        upper_chars = sum(1 for ch in sentence_clean if ch.isupper())
        if alpha_chars > 0 and upper_chars / alpha_chars > 0.60:
            continue

        sentence_tokens = sentence_norm.split()
        overlap = 0
        for kw in normalized_keywords:
            for tok in sentence_tokens:
                if tok == kw or tok.startswith(kw) or kw.startswith(tok):
                    overlap += 1
                    break

        length_bonus = 0.25 if 60 <= len(sentence_clean) <= 200 else 0.0
        scored_sentences.append((overlap + length_bonus, sentence_clean))

    if scored_sentences:
        scored_sentences.sort(key=lambda item: item[0], reverse=True)
        best_sentence = scored_sentences[0][1]
        if len(best_sentence) > max_chars and raw_keywords:
            lowered = best_sentence.casefold()
            for keyword in raw_keywords:
                idx = lowered.find(keyword)
                if idx < 0 and not keyword.endswith("s"):
                    idx = lowered.find(keyword + "s")
                if idx >= 0:
                    start = max(0, idx - 80)
                    end = min(len(best_sentence), idx + 140)
                    snippet = best_sentence[start:end].strip(" ,;:-")
                    return snippet[:max_chars] + ("..." if len(snippet) > max_chars else "")
        return best_sentence[:max_chars] + ("..." if len(best_sentence) > max_chars else "")

    for sentence in sentences:
        if len(sentence) >= 30:
            return sentence[:max_chars] + ("..." if len(sentence) > max_chars else "")

    return clean_text[:max_chars] + ("..." if len(clean_text) > max_chars else "")


def generate_grounded_answer(question, chunks, language, grade=None, conversation_history=None):
    """Generate grounded answer with Gemini/OpenAI, else return a prompt preview."""
    system_prompt, user_prompt = build_rag_prompt(
        question,
        chunks,
        language,
        grade=grade,
        conversation_history=conversation_history,
    )

    gemini_answer = generate_with_gemini(system_prompt, user_prompt, temperature=0.2, max_tokens=500)
    if gemini_answer:
        final_answer = enforce_answer_language(gemini_answer, language, question)
        if looks_like_no_info_answer(final_answer, language):
            fallback = generate_educational_fallback_answer(
                question,
                language,
                grade=grade,
                conversation_history=conversation_history,
            )
            return {
                "answer": fallback["answer"],
                "mode": "gemini_rag_level_fallback",
                "prompt_preview": None,
                "llm_error": fallback.get("llm_error"),
            }
        return {
            "answer": final_answer,
            "mode": "gemini_rag",
            "prompt_preview": None,
        }

    openai_answer = generate_with_openai(system_prompt, user_prompt, temperature=0.2, max_tokens=400)
    if openai_answer:
        final_answer = enforce_answer_language(openai_answer, language, question)
        if looks_like_no_info_answer(final_answer, language):
            fallback = generate_educational_fallback_answer(
                question,
                language,
                grade=grade,
                conversation_history=conversation_history,
            )
            return {
                "answer": fallback["answer"],
                "mode": "openai_rag_level_fallback",
                "prompt_preview": None,
                "llm_error": fallback.get("llm_error"),
            }
        return {
            "answer": final_answer,
            "mode": "openai",
            "prompt_preview": None,
        }

    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        first_chunk = chunks[0] if chunks else {}
        short_answer = extract_short_answer(first_chunk.get("text", ""), question)
        source_line = f"{first_chunk.get('chunk_id', 'unknown')} | {first_chunk.get('source_file', 'unknown')}"
        gemini_error_prefix = ""
        gemini_reason = None
        if GEMINI_AVAILABLE and GEMINI_API_KEYS and GEMINI_LAST_ERROR:
            gemini_reason = str(GEMINI_LAST_ERROR).splitlines()[0].strip()[:220]
            if language == "ar":
                gemini_error_prefix = f"تعذر الاتصال بـ Gemini حاليا: {gemini_reason}\n"
            elif language == "en":
                gemini_error_prefix = f"Gemini is temporarily unavailable: {gemini_reason}\n"
            else:
                gemini_error_prefix = f"Gemini est temporairement indisponible: {gemini_reason}\n"

        if language == "ar":
            fallback_answer = (
                f"{gemini_error_prefix}"
                "وضع تجريبي (بدون OpenAI): حسب المصادر الرسمية، هذه الخلاصة:\n"
                f"{short_answer or 'تم العثور على معلومات مرتبطة بالسؤال في المصادر أدناه.'}\n"
                f"المصدر: {source_line}"
            )
        elif language == "en":
            fallback_answer = (
                f"{gemini_error_prefix}"
                "Demo mode (without OpenAI): based on official sources, this is the key point:\n"
                f"{short_answer or 'Relevant information was found in the sources below.'}\n"
                f"Source: {source_line}"
            )
        else:
            fallback_answer = (
                f"{gemini_error_prefix}"
                "Mode demo (sans OpenAI): d'apres les sources officielles, voici l'essentiel :\n"
                f"{short_answer or 'Information trouvee dans les sources ci-dessous.'}\n"
                f"Source: {source_line}"
            )
        return {
            "answer": strip_source_lines(fallback_answer.strip()),
            "mode": "prompt_preview",
            "prompt_preview": {
                "system": system_prompt,
                "user": user_prompt,
            },
            "llm_error": gemini_reason,
        }

    # Should not be reached in normal flow because OpenAI path is attempted above.
    return {
        "answer": "Mode demo: aucun fournisseur LLM disponible.",
        "mode": "prompt_preview",
        "prompt_preview": {
            "system": system_prompt,
            "user": user_prompt,
        },
        "llm_error": str(GEMINI_LAST_ERROR).splitlines()[0].strip()[:220] if GEMINI_LAST_ERROR else None,
    }

# Semantic Search Class
class SemanticSearchEngine:
    """Semantic search using embeddings."""
    
    def __init__(self, chunks):
        self.chunks = chunks
        self.embeddings_cache = {}
        self.query_embedding_cache = {}
        self.model = None
        self.initialized = False
        self._init_lock = threading.Lock()
    
    def _init_model(self):
        """Initialize embedding model on first use."""
        if self.initialized or not SEMANTIC_SEARCH_AVAILABLE:
            return

        with self._init_lock:
            if self.initialized or not SEMANTIC_SEARCH_AVAILABLE:
                return

            try:
                print("🔄 Chargement du modèle d'embeddings...")
                model_ref = self._prepare_model_path("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
                self.model = SentenceTransformer(model_ref)
                self._encode_chunks()
                self.initialized = True
                print("✅ Modèle chargé et chunks encodés")
            except Exception as e:
                print(f"❌ Erreur lors du chargement: {e}")
                self.model = None

    def _prepare_model_path(self, model_id):
        """Download only required model assets to avoid huge optional runtime artifacts."""
        if not HF_HUB_AVAILABLE:
            return model_id

        cache_dir = Path.home() / ".cache" / "astro_kb_pipeline" / "hf_models"
        cache_dir.mkdir(parents=True, exist_ok=True)

        required_patterns = [
            "*.json",
            "*.txt",
            "*.md",
            "*tokenizer*",
            "*vocab*",
            "*sentencepiece*",
            "*special_tokens_map*",
            "*config*",
            "*pytorch_model.bin",
            "*model.safetensors",
            "modules.json",
            "README.md",
        ]

        try:
            local_path = snapshot_download(
                repo_id=model_id,
                cache_dir=str(cache_dir),
                allow_patterns=required_patterns,
                local_files_only=False,
            )
            return local_path
        except Exception:
            # Fallback to default model resolution if selective download is not available.
            return model_id
    
    def _encode_chunks(self):
        """Pre-compute embeddings for all chunks."""
        texts = [c.get('text', '')[:500] for c in self.chunks]  # Limit to 500 chars
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        
        for chunk, embedding in zip(self.chunks, embeddings):
            chunk_id = chunk.get('chunk_id')
            self.embeddings_cache[chunk_id] = embedding
    
    def search_semantic(self, query, top_k=5, filters=None):
        """Hybrid retrieval with hard filters and semantic + keyword ranking."""
        if not self.initialized and SEMANTIC_SEARCH_AVAILABLE:
            self._init_model()

        if not self.initialized or not self.model:
            return []
        
        try:
            # Encode query
            if query not in self.query_embedding_cache:
                self.query_embedding_cache[query] = self.model.encode(query, convert_to_numpy=True)
            query_embedding = self.query_embedding_cache[query]
            
            # Score all chunks
            scores = []
            for chunk in self.chunks:
                if not chunk_matches_filters(chunk, filters):
                    continue
                
                chunk_id = chunk.get('chunk_id')
                if chunk_id in self.embeddings_cache:
                    chunk_embedding = self.embeddings_cache[chunk_id]
                    semantic_score = 1 - cosine(query_embedding, chunk_embedding)
                    lexical_score = keyword_score(query, chunk.get('text', ''))
                    final_score = (0.5 * semantic_score) + (0.3 * lexical_score) + source_bonus(chunk)
                    scores.append((chunk, final_score))
            
            # Sort by similarity and return top_k
            scores.sort(key=lambda x: x[1], reverse=True)
            return [(chunk, score) for chunk, score in scores[:top_k]]
        
        except Exception as e:
            print(f"Erreur recherche sémantique: {e}")
            return []

# Global KB and Search Engine
KB_ALL = load_kb(strict=False)
KB_CLEAN = load_kb(strict=True)
RETRIEVAL_KB = KB_CLEAN if DEFAULT_RETRIEVAL_QUALITY == "clean" else KB_ALL
SEARCH_ENGINE = SemanticSearchEngine(RETRIEVAL_KB)


def summarize_kb(chunks):
    """Build aggregate stats for a KB collection."""
    stats_by_grade = {}
    stats_by_subject = {}
    stats_by_language = {}

    for chunk in chunks:
        grade = chunk.get('grade')
        subject = chunk.get('subject')
        language = chunk.get('language')

        if grade:
            stats_by_grade[grade] = stats_by_grade.get(grade, 0) + 1
        if subject:
            stats_by_subject[subject] = stats_by_subject.get(subject, 0) + 1
        if language:
            stats_by_language[language] = stats_by_language.get(language, 0) + 1

    return {
        "total_chunks": len(chunks),
        "by_grade": stats_by_grade,
        "by_subject": stats_by_subject,
        "by_language": stats_by_language,
    }


def resolve_kb_scope(quality):
    """Resolve which KB dataset to use based on quality mode."""
    normalized = (quality or "").strip().lower()
    if normalized == "all":
        return KB_ALL, "all"
    return KB_CLEAN, "clean"


@app.route('/')
def index():
    """Main page."""
    active_kb = RETRIEVAL_KB
    stats = {
        "total_chunks": len(active_kb),
        "grades": sorted(set(c.get('grade') for c in active_kb if c.get('grade'))),
        "subjects": sorted(set(c.get('subject') for c in active_kb if c.get('subject'))),
        "languages": sorted(set(c.get('language') for c in active_kb if c.get('language'))),
        "sources": sorted(set(c.get('source_type') for c in active_kb if c.get('source_type')))
    }
    return render_template('index.html', stats=stats)

@app.route('/api/stats')
def get_stats():
    """Get KB statistics."""
    quality = request.args.get('quality', DEFAULT_RETRIEVAL_QUALITY)
    selected_kb, selected_quality = resolve_kb_scope(quality)

    if not selected_kb:
        return jsonify({"error": "No KB loaded"}), 404

    selected_stats = summarize_kb(selected_kb)
    clean_stats = summarize_kb(KB_CLEAN)
    all_stats = summarize_kb(KB_ALL)

    return jsonify({
        "quality": selected_quality,
        "total_chunks": selected_stats["total_chunks"],
        "by_grade": selected_stats["by_grade"],
        "by_subject": selected_stats["by_subject"],
        "by_language": selected_stats["by_language"],
        "totals": {
            "clean": clean_stats["total_chunks"],
            "all": all_stats["total_chunks"],
            "retrieval": len(RETRIEVAL_KB),
        },
    })

@app.route('/api/search', methods=['POST'])
def search():
    """Search in KB using keyword matching and semantic search."""
    data = request.json
    query = data.get('query', '').lower()
    grade = data.get('grade')
    language = data.get('language')
    subject = data.get('subject')
    limit = int(data.get('limit', 5))
    search_mode = data.get('mode', 'hybrid')  # 'keyword', 'semantic', 'hybrid'
    
    if not query:
        return jsonify({"error": "Query required"}), 400
    
    results = []
    filters = build_filters(
        grade=int(grade) if grade else None,
        language=language,
        subject=subject,
    )
    
    # Semantic search (if available)
    if search_mode in ['semantic', 'hybrid']:
        semantic_results = SEARCH_ENGINE.search_semantic(query, top_k=max(limit * 5, 20), filters=filters)
        for chunk, score in semantic_results:
            results.append({
                "chunk_id": chunk.get('chunk_id'),
                "grade": chunk.get('grade'),
                "subject": chunk.get('subject'),
                "language": chunk.get('language'),
                "source_type": chunk.get('source_type'),
                "source_file": chunk.get('source_file'),
                "text": chunk.get('text')[:200] + "...",
                "full_text": chunk.get('text'),
                "score": float(score),
                "mode": "hybrid" if search_mode == 'hybrid' else "semantic"
            })
    
    # Keyword search (if not semantic-only or no semantic results)
    if search_mode in ['keyword', 'hybrid'] and (not results or search_mode == 'keyword'):
        for chunk, score in keyword_search(query, filters=filters, limit=limit*2):
            results.append({
                "chunk_id": chunk.get('chunk_id'),
                "grade": chunk.get('grade'),
                "subject": chunk.get('subject'),
                "language": chunk.get('language'),
                "source_type": chunk.get('source_type'),
                "source_file": chunk.get('source_file'),
                "text": chunk.get('text')[:200] + "...",
                "full_text": chunk.get('text'),
                "score": float(score),
                "mode": "keyword"
            })
    
    # Deduplicate and limit
    seen = set()
    unique_results = []
    for r in results:
        if r['chunk_id'] not in seen:
            unique_results.append(r)
            seen.add(r['chunk_id'])
    
    unique_results = unique_results[:limit]
    
    return jsonify({
        "query": query,
        "results_count": len(unique_results),
        "results": unique_results,
        "search_mode": search_mode if results else "keyword (semantic unavailable)"
    })


@app.route('/api/chunks')
def get_chunks():
    """Get chunks by filters."""
    quality = request.args.get('quality', DEFAULT_RETRIEVAL_QUALITY)
    selected_kb, selected_quality = resolve_kb_scope(quality)
    grade = request.args.get('grade', type=int)
    subject = request.args.get('subject')
    language = request.args.get('language')
    limit = request.args.get('limit', default=10, type=int)
    
    results = []
    for chunk in selected_kb:
        if grade and chunk.get('grade') != grade:
            continue
        if subject and chunk.get('subject') != subject:
            continue
        if language and chunk.get('language') != language:
            continue
        
        results.append({
            "chunk_id": chunk.get('chunk_id'),
            "grade": chunk.get('grade'),
            "subject": chunk.get('subject'),
            "language": chunk.get('language'),
            "text": chunk.get('text')[:300] + "..."
        })
    
    return jsonify({
        "quality": selected_quality,
        "total": len(results),
        "chunks": results[:limit]
    })

@app.route('/api/chunk/<chunk_id>')
def get_chunk_detail(chunk_id):
    """Get full chunk details."""
    for chunk in KB_ALL:
        if chunk.get('chunk_id') == chunk_id:
            return jsonify(chunk)
    
    return jsonify({"error": "Chunk not found"}), 404

@app.route('/api/answer', methods=['POST'])
def generate_answer():
    """Generate a grounded answer from KB chunks with optional OpenAI generation."""
    data = request.json or {}
    question = (data.get('question') or '').strip()
    grade = data.get('grade')
    language = data.get('language', 'auto')
    subject = data.get('subject')
    age = data.get('age')
    conversation_history = data.get('conversation')
    if not isinstance(conversation_history, list):
        conversation_history = []

    if not question:
        return jsonify({"error": "Question required"}), 400

    if grade not in [None, "", 0, "0"]:
        try:
            grade = int(grade)
        except (TypeError, ValueError):
            return jsonify({"error": "grade must be an integer"}), 400
    else:
        grade = None

    if age not in [None, "", 0, "0"]:
        try:
            age = int(age)
        except (TypeError, ValueError):
            return jsonify({"error": "age must be an integer"}), 400
    else:
        age = None

    resolved_language = detect_language(question) if language == 'auto' else language
    pedagogical_mode = detect_pedagogical_mode(question)
    is_edu_question = is_education_question(question, subject=subject, grade=grade, age=age)

    if not is_edu_question:
        general = generate_general_answer(
            question,
            resolved_language,
            grade=grade,
            conversation_history=conversation_history,
        )
        return jsonify({
            "question": question,
            "answer": general["answer"],
            "sources": [],
            "mode": general["mode"],
            "role": "general_child",
            "retrieval_mode": "general_llm",
            "pedagogical_mode": pedagogical_mode,
            "grade": grade,
            "language": resolved_language,
            "subject": subject,
            "prompt_preview": general["prompt_preview"],
            "llm_error": general.get("llm_error"),
            "openai_configured": bool(OPENAI_AVAILABLE and OPENAI_API_KEY),
            "gemini_configured": bool(GEMINI_AVAILABLE and GEMINI_API_KEYS),
        })

    filters = build_filters(grade=grade, language=resolved_language, subject=subject, age=age)

    if pedagogical_mode == "course_extract":
        extracted = build_pdf_course_extract_answer(
            question,
            resolved_language,
            filters=filters,
            subject=subject,
        )
        if extracted["success"]:
            return jsonify({
                "question": question,
                "answer": extracted["answer"],
                "sources": extracted["sources"],
                "mode": extracted["mode"],
                "role": "educational_program",
                "retrieval_mode": extracted["retrieval_mode"],
                "pedagogical_mode": pedagogical_mode,
                "grade": filters.get("grade"),
                "language": resolved_language,
                "subject": subject,
                "prompt_preview": None,
                "llm_error": None,
                "openai_configured": bool(OPENAI_AVAILABLE and OPENAI_API_KEY),
                "gemini_configured": bool(GEMINI_AVAILABLE and GEMINI_API_KEYS),
                "grade_alignment": {
                    "is_advanced": False,
                    "required_grade": None,
                    "topic": None,
                    "message": None,
                },
            })

        no_result = generate_educational_fallback_answer(
            question,
            resolved_language,
            grade=filters.get("grade"),
            subject=subject,
            conversation_history=conversation_history,
        )
        return jsonify({
            "question": question,
            "answer": no_result["answer"],
            "sources": [],
            "mode": no_result["mode"],
            "role": "educational_program",
            "retrieval_mode": extracted.get("retrieval_mode", "keyword_mmr"),
            "pedagogical_mode": pedagogical_mode,
            "grade": filters.get("grade"),
            "language": resolved_language,
            "subject": subject,
            "prompt_preview": no_result.get("prompt_preview"),
            "llm_error": no_result.get("llm_error"),
            "grade_alignment": {
                "is_advanced": False,
                "required_grade": None,
                "topic": None,
                "message": None,
            },
        })

    alignment = assess_grade_alignment(question, grade)
    if alignment["is_advanced"]:
        no_result = generate_educational_fallback_answer(
            question,
            resolved_language,
            grade=grade,
            subject=subject,
            level_note=alignment["message"],
            conversation_history=conversation_history,
        )
        return jsonify({
            "question": question,
            "answer": no_result["answer"],
            "sources": [],
            "mode": "grade_scope_fallback",
            "role": "educational_program",
            "retrieval_mode": "grade_guard",
            "pedagogical_mode": pedagogical_mode,
            "grade": grade,
            "language": resolved_language,
            "subject": subject,
            "prompt_preview": no_result.get("prompt_preview"),
            "llm_error": no_result.get("llm_error"),
            "grade_alignment": alignment,
        })

    results, retrieval_mode = retrieve_relevant_chunks(question, filters=filters, limit=3)

    if not results:
        no_result = generate_educational_fallback_answer(
            question,
            resolved_language,
            grade=filters.get("grade"),
            subject=subject,
            conversation_history=conversation_history,
        )
        return jsonify({
            "question": question,
            "answer": no_result["answer"],
            "sources": [],
            "mode": no_result["mode"],
            "role": "educational_program",
            "retrieval_mode": retrieval_mode,
            "pedagogical_mode": pedagogical_mode,
            "grade": filters.get("grade"),
            "language": resolved_language,
            "subject": subject,
            "prompt_preview": no_result.get("prompt_preview"),
            "llm_error": no_result.get("llm_error"),
            "grade_alignment": alignment,
        })

    source_chunks = []
    for chunk, score in results:
        source_chunks.append({
            "chunk_id": chunk.get('chunk_id'),
            "source_file": chunk.get('source_file'),
            "source_type": chunk.get('source_type'),
            "grade": chunk.get('grade'),
            "subject": chunk.get('subject'),
            "language": chunk.get('language'),
            "score": float(score),
            "text": chunk.get('text', '')[:400],
        })

    generated = generate_grounded_answer(
        question,
        [chunk for chunk, _ in results],
        resolved_language,
        grade=filters.get("grade"),
        conversation_history=conversation_history,
    )

    return jsonify({
        "question": question,
        "answer": generated["answer"],
        "sources": source_chunks,
        "mode": generated["mode"],
        "role": "educational_program",
        "retrieval_mode": retrieval_mode,
        "pedagogical_mode": pedagogical_mode,
        "grade": filters.get("grade"),
        "language": resolved_language,
        "subject": subject,
        "prompt_preview": generated["prompt_preview"],
        "llm_error": generated.get("llm_error"),
        "openai_configured": bool(OPENAI_AVAILABLE and OPENAI_API_KEY),
        "gemini_configured": bool(GEMINI_AVAILABLE and GEMINI_API_KEYS),
        "grade_alignment": alignment,
    })

@app.route('/api/program')
def get_program():
    """Get curriculum structure: grades and subjects per grade."""
    try:
        quality = request.args.get('quality', DEFAULT_RETRIEVAL_QUALITY)
        selected_kb, _ = resolve_kb_scope(quality)
        program = {}
        
        for chunk in selected_kb:
            grade = chunk.get('grade')
            subject = chunk.get('subject', 'Unknown')
            language = chunk.get('language', 'Unknown')
            
            # Skip if grade is None
            if grade is None:
                continue
                
            grade_key = str(grade)
            if grade_key not in program:
                program[grade_key] = {
                    "subjects": set(),
                    "languages": set(),
                    "chunk_count": 0
                }
            
            program[grade_key]["subjects"].add(subject)
            program[grade_key]["languages"].add(language)
            program[grade_key]["chunk_count"] += 1
        
        # Convert sets to lists for JSON
        result = {}
        for grade in sorted(program.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            result[grade] = {
                "subjects": sorted(list(program[grade]["subjects"])),
                "languages": sorted(list(program[grade]["languages"])),
                "chunk_count": program[grade]["chunk_count"]
            }
        
        return jsonify(result)
    except Exception as e:
        print(f"ERROR in /api/program: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/progression/<int:grade>')
def get_grade_progression(grade):
    """Get all chunks for a specific grade level."""
    quality = request.args.get('quality', DEFAULT_RETRIEVAL_QUALITY)
    selected_kb, _ = resolve_kb_scope(quality)
    grade_chunks = [c for c in selected_kb if c.get('grade') == grade]
    
    # Group by subject
    by_subject = {}
    for chunk in grade_chunks:
        subject = chunk.get('subject', 'Unknown')
        if subject not in by_subject:
            by_subject[subject] = []
        by_subject[subject].append({
            "chunk_id": chunk.get('chunk_id'),
            "subject": subject,
            "language": chunk.get('language'),
            "text": chunk.get('text', '')[:200] + "..." if len(chunk.get('text', '')) > 200 else chunk.get('text', ''),
            "source_file": chunk.get('source_file')
        })
    
    return jsonify({
        "grade": grade,
        "total_chunks": len(grade_chunks),
        "by_subject": by_subject
    })

@app.route('/api/subject-program/<int:grade>/<subject>')
def get_subject_program(grade, subject):
    """Get all chunks for a specific grade and subject."""
    quality = request.args.get('quality', DEFAULT_RETRIEVAL_QUALITY)
    selected_kb, _ = resolve_kb_scope(quality)
    filtered = [c for c in selected_kb if c.get('grade') == grade and c.get('subject') == subject]
    
    # Sort by chunk index
    filtered.sort(key=lambda x: (x.get('source_file', ''), x.get('chunk_index', 0)))
    
    result = []
    for chunk in filtered:
        result.append({
            "chunk_id": chunk.get('chunk_id'),
            "file": chunk.get('source_file'),
            "index": f"{chunk.get('chunk_index', 0)}/{chunk.get('total_chunks', 1)}",
            "language": chunk.get('language'),
            "text": chunk.get('text', '')
        })
    
    return jsonify({
        "grade": grade,
        "subject": subject,
        "total": len(result),
        "chunks": result
    })

@app.route('/api/health')
def health():
    """Health check."""
    return jsonify({
        "status": "ok",
        "kb_loaded": len(RETRIEVAL_KB) > 0,
        "chunks_count": len(RETRIEVAL_KB),
        "chunks_clean": len(KB_CLEAN),
        "chunks_all": len(KB_ALL),
        "retrieval_quality": DEFAULT_RETRIEVAL_QUALITY,
    })

if __name__ == '__main__':
    if len(RETRIEVAL_KB) == 0:
        print("⚠️  Warning: KB not loaded. Run pipeline first:")
        print("   python scripts/run_all.py")

    print(f"\n✅ KB clean: {len(KB_CLEAN)} chunks")
    print(f"✅ KB all: {len(KB_ALL)} chunks")
    print(f"✅ KB retrieval ({DEFAULT_RETRIEVAL_QUALITY}): {len(RETRIEVAL_KB)} chunks")
    print("🚀 Starting Flask server on http://localhost:5000\n")
    
    app.run(debug=False, port=5000, host='127.0.0.1', use_reloader=False)
