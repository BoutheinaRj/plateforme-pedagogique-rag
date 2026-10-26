"""
Answer Generator - Generate answers using matching KB chunks + GPT.
Combines semantic search results with LLM for context-aware responses.
"""

import json
import os
from datetime import datetime

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class AnswerGenerator:
    """Generate answers using KB matching + GPT."""
    
    def __init__(self, api_key=None, model_name="gpt-3.5-turbo"):
        """Initialize answer generator.
        
        Args:
            api_key: OpenAI API key (or use OPENAI_API_KEY env var)
            model_name: LLM model (gpt-3.5-turbo, gpt-4, etc.)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai not installed. Run: pip install openai")
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers not installed")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("No OpenAI API key provided or OPENAI_API_KEY env var not set")
        
        openai.api_key = self.api_key
        self.model = model_name
        self.semantic_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self.chunks = {}
    
    def load_kb(self, json_dir):
        """Load KB chunks.
        
        Args:
            json_dir: Directory with JSON chunks
        """
        print(f"Chargement KB: {json_dir}...", end=" ")
        
        all_chunks = []
        for root, dirs, files in os.walk(json_dir):
            for file in files:
                if file.endswith('_chunks.json'):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            chunks = json.load(f)
                        all_chunks.extend(chunks)
                    except:
                        pass
        
        # Add embeddings
        texts = [c['text'] for c in all_chunks]
        embeddings = self.semantic_model.encode(texts, show_progress_bar=False)
        for chunk, emb in zip(all_chunks, embeddings):
            chunk['embedding'] = emb
        
        self.chunks = all_chunks
        print(f"✅ {len(all_chunks)} chunks")
    
    def find_relevant_chunks(self, query, top_k=3, filters=None):
        """Find relevant KB chunks for query.
        
        Args:
            query: User question
            top_k: Number of chunks to return
            filters: Metadata filters (grade, language, subject, etc.)
        
        Returns:
            List of relevant chunks
        """
        import numpy as np
        
        # Encode query
        query_emb = self.semantic_model.encode(query)
        
        # Filter chunks
        candidates = self.chunks
        if filters:
            for key, value in filters.items():
                candidates = [c for c in candidates if c.get(key) == value]
        
        # Compute similarities
        similarities = []
        for chunk in candidates:
            sim = np.dot(query_emb, chunk['embedding']) / (
                np.linalg.norm(query_emb) * np.linalg.norm(chunk['embedding'])
            )
            similarities.append((chunk, sim))
        
        # Return top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in similarities[:top_k]]
    
    def generate_answer(self, question, student_grade=None, language="auto", subject=None):
        """Generate answer to a question.
        
        Args:
            question: Student question
            student_grade: Grade level (1-6)
            language: "ar" (Arabic), "fr" (French), or "auto"
            subject: Subject if known
        
        Returns:
            (answer, metadata) tuple
        """
        # Detect language if needed
        if language == "auto":
            language = self._detect_language(question)
        
        # Prepare filters
        filters = {}
        if student_grade:
            filters["grade"] = student_grade
        if language:
            filters["language"] = language
        if subject:
            filters["subject"] = subject
        
        # Find relevant chunks
        relevant_chunks = self.find_relevant_chunks(question, top_k=3, filters=filters)
        
        if not relevant_chunks:
            return "Je n'ai pas trouvé d'informations pertinentes." if language == "fr" else "لم أجد معلومات ذات صلة.", {
                "success": False,
                "chunks_found": 0
            }
        
        # Build context
        context = "\n\n".join([
            f"[Source: {c.get('subject', 'Unknown')} - Grade {c.get('grade', '?')}]\n{c['text']}"
            for c in relevant_chunks
        ])
        
        # Generate answer with GPT
        system_prompt = self._get_system_prompt(language, student_grade)
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Question de l'élève: {question}\n\nContexte du cours:\n{context}"
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            
            return answer, {
                "success": True,
                "chunks_used": len(relevant_chunks),
                "language": language,
                "grade": student_grade,
                "model": self.model,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            return f"Erreur: {str(e)}", {"success": False, "error": str(e)}
    
    def _detect_language(self, text):
        """Detect if text is Arabic or French."""
        arabic_count = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        return "ar" if arabic_count > len(text) * 0.3 else "fr"
    
    def _get_system_prompt(self, language, grade):
        """Get appropriate system prompt."""
        if language == "ar":
            return f"""أنت معلم ذكي يساعد تلميذ في الصف {grade}.
إجابتك يجب أن تكون:
- مناسبة لمستوى الصف {grade}
- واضحة وسهلة الفهم
- مدعومة بأمثلة من المواد الدراسية
استخدم المعلومات من السياق المعطاة."""
        else:
            return f"""Tu es un professeur intelligent qui aide un élève de {grade}ème année.
Tes réponses doivent être:
- Appropriées au niveau de {grade}ème
- Claires et faciles à comprendre
- Soutenues par des exemples du cours
Utilise les informations du contexte fourni."""
    
    def interactive_qa(self):
        """Interactive Q&A interface."""
        print("\n" + "=" * 80)
        print("💬 ASSISTANT PÉDAGOGIQUE - Q&A")
        print("=" * 80)
        print("\nCommandes:")
        print("  'grade X' - Définir le niveau (ex: grade 1)")
        print("  'sujet X' - Définir la matière (ex: sujet Maths)")
        print("  'langue ar/fr' - Définir la langue")
        print("  'quit' - Quitter")
        print("=" * 80 + "\n")
        
        student_grade = None
        language = "auto"
        subject = None
        
        while True:
            try:
                question = input("❓ Question: ").strip()
                
                if not question:
                    continue
                if question.lower() == "quit":
                    print("Au revoir! 👋")
                    break
                
                # Parse commands
                if question.lower().startswith("grade "):
                    student_grade = int(question.split()[1])
                    print(f"✅ Niveau défini: {student_grade}")
                    continue
                elif question.lower().startswith("sujet "):
                    subject = " ".join(question.split()[1:])
                    print(f"✅ Matière définie: {subject}")
                    continue
                elif question.lower().startswith("langue "):
                    language = question.split()[1]
                    print(f"✅ Langue définie: {language}")
                    continue
                
                # Generate answer
                print("\n⏳ Génération de la réponse...")
                answer, metadata = self.generate_answer(
                    question,
                    student_grade=student_grade,
                    language=language,
                    subject=subject
                )
                
                print(f"\n✅ Réponse:\n")
                print(answer)
                print(f"\n📊 Métadonnées: {metadata}\n")
                print("-" * 80 + "\n")
            
            except KeyboardInterrupt:
                print("\n\nAu revoir! 👋")
                break
            except Exception as e:
                print(f"❌ Erreur: {str(e)}\n")


def main():
    import sys
    
    # Setup
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    json_dir = os.path.join(project_root, "data", "json_out")
    
    print("=" * 80)
    print("GÉNÉRATEUR DE RÉPONSES")
    print("=" * 80)
    print()
    
    # Check dependencies
    if not OPENAI_AVAILABLE:
        print("❌ openai not installed")
        print("   pip install openai")
        sys.exit(1)
    
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("❌ sentence-transformers not installed")
        print("   pip install sentence-transformers")
        sys.exit(1)
    
    # Initialize
    try:
        generator = AnswerGenerator()
    except ValueError as e:
        print(f"❌ {e}")
        print("\nConfiguration:")
        print("  1. Créer compte: https://platform.openai.com")
        print("  2. Générer clé API")
        print("  3. Définir variable d'environnement OPENAI_API_KEY")
        print("  ou passer directement: AnswerGenerator(api_key='sk-...')")
        sys.exit(1)
    
    # Load KB
    generator.load_kb(json_dir)
    
    # Interactive mode
    generator.interactive_qa()


if __name__ == "__main__":
    main()
