"""
Semantic Search - Match user queries to relevant chunks.
Uses Sentence-Transformers for multilingual embeddings (Arabic, French).
"""

import json
import os
from pathlib import Path
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class SemanticSearcher:
    """Semantic search on KB chunks."""
    
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        """Initialize semantic searcher with embeddings model.
        
        Models:
        - "paraphrase-multilingual-MiniLM-L12-v2" (small, fast)
        - "paraphrase-multilingual-mpnet-base-v2" (better, larger)
        - "intfloat/multilingual-e5-small" (newer)
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
        
        print(f"Chargement du modèle: {model_name}...", end=" ")
        self.model = SentenceTransformer(model_name)
        print("✅")
        self.chunks_cache = {}
        self.embeddings_cache = {}
    
    def load_chunks_from_json(self, json_dir):
        """Load all JSON chunks into memory.
        
        Args:
            json_dir: Directory containing JSON chunk files
        
        Returns:
            List of chunks with embeddings
        """
        print(f"\nChargement des chunks de {json_dir}...")
        
        all_chunks = []
        chunk_count = 0
        
        for root, dirs, files in os.walk(json_dir):
            for file in files:
                if file.endswith('_chunks.json'):
                    json_path = os.path.join(root, file)
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            chunks = json.load(f)
                        all_chunks.extend(chunks)
                        chunk_count += len(chunks)
                    except Exception as e:
                        print(f"  ⚠️  Erreur {file}: {str(e)}")
        
        print(f"  ✅ {chunk_count} chunks chargés")
        
        # Generate embeddings for all chunks
        print("Génération des embeddings...", end=" ")
        chunk_texts = [chunk['text'] for chunk in all_chunks]
        embeddings = self.model.encode(chunk_texts, show_progress_bar=True)
        print("✅")
        
        # Store with embeddings
        for chunk, embedding in zip(all_chunks, embeddings):
            chunk['embedding'] = embedding
        
        self.chunks_cache = all_chunks
        return all_chunks
    
    def search(self, query, top_k=5, filters=None):
        """Search for similar chunks.
        
        Args:
            query: Search query (text)
            top_k: Number of results to return
            filters: Dict of metadata filters
                Ex: {"grade": 1, "language": "ar", "subject": "Maths"}
        
        Returns:
            List of (chunk, score) tuples
        """
        if not self.chunks_cache:
            return [], "No chunks loaded"
        
        # Encode query
        query_embedding = self.model.encode(query)
        
        # Filter chunks if needed
        candidates = self.chunks_cache
        if filters:
            candidates = self._filter_chunks(candidates, filters)
        
        if not candidates:
            return [], "No chunks match the filters"
        
        # Compute similarity scores
        similarities = []
        for chunk in candidates:
            # Cosine similarity
            score = self._cosine_similarity(query_embedding, chunk['embedding'])
            similarities.append((chunk, score))
        
        # Sort by score
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k], None
    
    def _filter_chunks(self, chunks, filters):
        """Filter chunks by metadata.
        
        Args:
            chunks: List of chunks
            filters: Dict of metadata
        
        Returns:
            Filtered list
        """
        result = chunks
        for key, value in filters.items():
            result = [c for c in result if c.get(key) == value]
        return result
    
    def _cosine_similarity(self, a, b):
        """Compute cosine similarity between vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def interactive_search():
    """Interactive search interface."""
    import sys
    
    print("\n" + "=" * 80)
    print("RECHERCHE SÉMANTIQUE INTERACTIVE")
    print("=" * 80)
    
    # Setup
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    json_dir = os.path.join(project_root, "data", "json_out")
    
    # Initialize searcher
    try:
        searcher = SemanticSearcher()
    except ImportError as e:
        print(f"\n❌ {e}")
        print("\nInstallation:")
        print("  pip install sentence-transformers")
        sys.exit(1)
    
    # Load chunks
    searcher.load_chunks_from_json(json_dir)
    
    print("\n" + "=" * 80)
    print("💡 Exemples de requêtes:")
    print("  • 'Comment additionner deux fractions?'")
    print("  • 'الجمع والطرح في الرياضيات'")
    print("  • 'Filtre: grade=1 language=ar' (métadonnées)")
    print("\nTapez 'quit' pour quitter")
    print("=" * 80 + "\n")
    
    while True:
        try:
            query = input("🔍 Votre requête: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Au revoir! 👋")
                break
            
            if not query:
                continue
            
            # Parse filters if specified
            filters = None
            if query.startswith("Filtre:"):
                query_parts = query.split("|")
                filter_str = query_parts[0].replace("Filtre:", "").strip()
                query = query_parts[1].strip() if len(query_parts) > 1 else ""
                
                # Parse filters: "grade=1 language=ar"
                filters = {}
                for part in filter_str.split():
                    if "=" in part:
                        k, v = part.split("=")
                        v = int(v) if v.isdigit() else v
                        filters[k] = v
            
            # Search
            results, error = searcher.search(query, top_k=3, filters=filters)
            
            if error:
                print(f"⚠️  {error}\n")
                continue
            
            print(f"\n✅ Résultats ({len(results)} trouvés):\n")
            
            for i, (chunk, score) in enumerate(results, 1):
                print(f"[{i}] Score: {score:.3f} | Grade: {chunk.get('grade')} | Matière: {chunk.get('subject')} | Langue: {chunk.get('language')}")
                print(f"    {chunk['text'][:150]}...")
                print()
        
        except KeyboardInterrupt:
            print("\n\nAu revoir! 👋")
            break
        except Exception as e:
            print(f"❌ Erreur: {str(e)}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Command-line search
        query = " ".join(sys.argv[1:])
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        json_dir = os.path.join(project_root, "data", "json_out")
        
        try:
            searcher = SemanticSearcher()
            searcher.load_chunks_from_json(json_dir)
            
            results, error = searcher.search(query, top_k=3)
            if error:
                print(f"Erreur: {error}")
            else:
                print(f"\n✅ Résultats pour: '{query}'\n")
                for i, (chunk, score) in enumerate(results, 1):
                    print(f"[{i}] {score:.3f}: {chunk['text'][:100]}...")
        except ImportError as e:
            print(f"❌ {e}")
            sys.exit(1)
    else:
        # Interactive mode
        interactive_search()
