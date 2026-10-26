#!/usr/bin/env python
"""Quick test of semantic search functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from importlib.util import spec_from_file_location, module_from_spec

spec = spec_from_file_location("semantic_search", os.path.join(os.path.dirname(__file__), 'scripts', '06_semantic_search.py'))
module = module_from_spec(spec)
spec.loader.exec_module(module)
SemanticSearcher = module.SemanticSearcher

import time

print("🔍 Test Recherche Sémantique")
print("=" * 50)

try:
    # Initialize
    searcher = SemanticSearcher()
    
    # Load chunks
    searcher.load_chunks_from_json("data/json_out")
    
    # Test queries
    test_queries = [
        "addition",
        "fraction",
        "lecture",
        "حروف",  # Arabic letters
    ]
    
    for query in test_queries:
        print(f"\n📝 Requête: '{query}'")
        print("-" * 50)
        
        start = time.time()
        results = searcher.search(query, top_k=3)
        elapsed = time.time() - start
        
        print(f"⏱️  Temps: {elapsed:.2f}s")
        print(f"📊 Résultats: {len(results)}")
        
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. Score: {result['score']:.3f}")
            print(f"     Grade: {result['grade']} | Sujet: {result['subject']}")
            print(f"     Texte: {result['text'][:100]}...")
    
    print("\n✅ Test réussi!")

except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
