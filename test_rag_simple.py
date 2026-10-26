"""
Test simple RAG + Gemini - Réponses pédagogiques structurées
Sans chargement des lourds modèles ML, juste JSON + recherche simple
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
import re

load_dotenv()

# Configuration Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY pas trouvée")
    exit(1)

print(f"✅ Clé Gemini chargée")

# Import Gemini
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)

# Charger les JSON chunks
def load_kb_chunks():
    """Charge tous les chunks JSON rapidement"""
    chunks = []
    json_dir = Path("data/json_out")
    
    if not json_dir.exists():
        print("❌ data/json_out n'existe pas")
        return chunks
    
    for json_file in json_dir.glob("**/*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    chunks.extend(data)
                else:
                    chunks.append(data)
        except Exception as e:
            pass  # Skip errors
    
    return chunks

print("⏳ Chargement de la KB...")
KB = load_kb_chunks()
print(f"✅ KB chargée: {len(KB)} chunks\n")

def simple_search(query, grade=None, language="fr", limit=3):
    """Recherche simple par keywords (sans embeddings ML)"""
    results = []
    
    # Keywords de recherche
    keywords = query.lower().split()
    
    for chunk in KB:
        # Filtrer par grade/langue
        if grade and chunk.get('grade') != grade:
            continue
        if chunk.get('language') != language:
            continue
        
        # Score basé sur correspondance de mots
        text = chunk.get('text', '').lower()
        score = sum(1 for kw in keywords if kw in text) / len(keywords) if keywords else 0
        
        if score > 0:
            results.append((chunk, score))
    
    # Trier par score
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]

def generate_answer(question, context_chunks, grade, language="fr"):
    """Génère une réponse avec Gemini basée sur les chunks éducatifs"""
    
    # Construire le contexte
    context_text = ""
    for i, chunk in enumerate(context_chunks, 1):
        text = chunk.get('text', '')[:300]  # Limiter la longueur
        source = chunk.get('source_file', 'Source inconnue')
        context_text += f"\n[Source {i}] ({source}):\n{text}\n"
    
    if not context_text:
        context_text = "[Pas de sources éducatives trouvées]"
    
    # Prompt pour répondre comme un professeur
    age_map = {
        1: "6 ans", 2: "7 ans", 3: "8 ans", 4: "9 ans", 
        5: "10 ans", 6: "11 ans"
    }
    age = age_map.get(grade, f"environ {5+grade} ans")
    
    prompt = f"""Tu es un professeur pédagogue bienveillant qui répond à des questions d'enfants.

Grade de l'enfant: {grade} (environ {age})
Langue: Français
Question de l'enfant: {question}

Sources du curriculum tunisien:
{context_text}

Réponds de manière:
1. SIMPLE et adaptée à l'âge ({age})
2. STRUCTURÉE avec des exemples concrets
3. BIENVEILLANTE et encourageante
4. Basée SUR LES SOURCES du curriculum ci-dessus

Réponds directement, sans "Bonjour" ni préambule.
Maximum 5-6 phrases.
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
        return response.text
    except Exception as e:
        return f"[Erreur Gemini: {str(e)[:50]}]"

# Tests
print("="*80)
print("🧪 TEST: Questions d'enfants avec RAG + Gemini")
print("="*80)

tests = [
    ("Conjugue le verbe avoir au présent", 3, "fr"),
    ("Qu'est-ce qu'une fraction?", 4, "fr"),
    ("Comment on reconnaît un adjectif?", 2, "fr"),
]

for i, (question, grade, lang) in enumerate(tests, 1):
    print(f"\n{'─'*80}")
    print(f"📝 Test {i}/{len(tests)}")
    print(f"{'─'*80}")
    print(f"👧 Grade: {grade}")
    print(f"❓ Question: {question}")
    
    # Recherche
    results = simple_search(question, grade=grade, language=lang, limit=2)
    print(f"\n📖 Chunks trouvés: {len(results)}")
    
    if results:
        for j, (chunk, score) in enumerate(results, 1):
            source = chunk.get('source_file', 'unknown')
            print(f"   [{j}] {source}")
    
    # Génération
    print(f"\n⏳ Génération avec Gemini...")
    answer = generate_answer(question, [c for c, _ in results], grade, lang)
    print(f"\n✨ Réponse du professeur:")
    print(f"   {answer}")

print("\n" + "="*80)
print("✅ Test terminé!")
print("="*80)
