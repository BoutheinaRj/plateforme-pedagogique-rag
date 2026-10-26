"""
Test script: RAG + Gemini pour réponses pédagogiques structurées
Teste les questions d'enfants avec réponses basées sur le curriculum tunisien
"""

import sys
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Import le module app qui charge la KB
sys.path.insert(0, str(Path(__file__).parent))
import app

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY pas trouvée dans .env")
    sys.exit(1)

print(f"✅ Clé Gemini chargée: {GEMINI_API_KEY[:15]}...")
print(f"✅ KB chargée: {len(app.RETRIEVAL_KB)} chunks\n")

# Questions de test par grade/sujet
TEST_QUESTIONS = [
    {
        "question": "Comment on conjugue le verbe avoir au présent?",
        "grade": 3,
        "subject": "francais",
        "language": "fr",
        "age": 8
    },
    {
        "question": "Explique-moi les fractions simples?",
        "grade": 4,
        "subject": "mathematiques",
        "language": "fr",
        "age": 9
    },
    {
        "question": "C'est quoi un adjectif?",
        "grade": 2,
        "subject": "francais",
        "language": "fr",
        "age": 7
    },
]

print("=" * 80)
print("🧪 TEST: Questions d'enfants avec réponses RAG + Gemini")
print("=" * 80)

for i, test in enumerate(TEST_QUESTIONS, 1):
    print(f"\n{'='*80}")
    print(f"📋 Test {i}/{len(TEST_QUESTIONS)}")
    print(f"{'='*80}")
    print(f"👧 Grade: {test['grade']}")
    print(f"📚 Sujet: {test['subject']}")
    print(f"🌍 Langue: {test['language']}")
    print(f"👤 Âge: {test['age']} ans")
    print(f"\n❓ Question: {test['question']}")
    print("-" * 80)
    
    # Récupérer les chunks pertinents du curriculum
    filters = app.build_filters(
        grade=test['grade'],
        language=test['language'],
        subject=test['subject'],
        age=test['age']
    )
    
    results, retrieval_mode = app.retrieve_relevant_chunks(
        test['question'],
        filters=filters,
        limit=3
    )
    
    print(f"\n📖 Chunks trouvés: {len(results)} (mode: {retrieval_mode})")
    
    if results:
        for j, (chunk, score) in enumerate(results[:2], 1):
            source = chunk.get('source_file', 'unknown')
            source_type = chunk.get('source_type', 'unknown')
            text = chunk.get('text', '')[:150]
            print(f"\n  [{j}] Source: {source_type} | Score: {score:.2f}")
            print(f"      {text}...")
    
    # Générer réponse avec Gemini basée sur les chunks
    print(f"\n⏳ Génération de réponse Gemini...")
    generated = app.generate_grounded_answer(
        test['question'],
        [chunk for chunk, _ in results] if results else [],
        test['language'],
        grade=test['grade']
    )
    
    print(f"\n✨ Réponse générée (mode: {generated['mode']}):")
    print(f"{generated['answer']}")
    
    print(f"\n📝 Sources:")
    if results:
        for chunk, score in results:
            print(f"  - {chunk.get('source_file')} (score: {score:.2f})")

print("\n" + "="*80)
print("✅ Test terminé!")
print("="*80)
