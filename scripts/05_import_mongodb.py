import json
import os
from pathlib import Path

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


def connect_to_mongodb(uri="mongodb://localhost:27017/"):
    """Connect to MongoDB.
    
    Args:
        uri: MongoDB connection URI
            - Local: mongodb://localhost:27017/
            - Atlas: mongodb+srv://user:pass@cluster.mongodb.net/
    
    Returns:
        (db, error_message) tuple
    """
    if not PYMONGO_AVAILABLE:
        return None, "❌ pymongo not installed. Run: pip install pymongo"
    
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Verify connection
        client.admin.command('ping')
        db = client['astro_ai_kb']
        return db, None
    except ServerSelectionTimeoutError:
        return None, f"❌ MongoDB not accessible at {uri}"
    except ConnectionFailure as e:
        return None, f"❌ Connection failed: {str(e)}"
    except Exception as e:
        return None, f"❌ Error: {str(e)}"


def import_json_to_mongodb(json_path, db, collection_name="chunks"):
    """Import JSON chunks into MongoDB.
    
    Args:
        json_path: Path to JSON file
        db: MongoDB database
        collection_name: Collection name (default: "chunks")
    
    Returns:
        Success count, error message
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        if not chunks:
            return 0, "No chunks found in JSON"
        
        collection = db[collection_name]
        
        # Add source_file and import_timestamp if not present
        for chunk in chunks:
            chunk['imported_at'] = __import__('datetime').datetime.utcnow()
        
        result = collection.insert_many(chunks)
        return len(result.inserted_ids), None
    
    except json.JSONDecodeError as e:
        return 0, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return 0, f"Error: {str(e)}"


def create_indexes(db):
    """Create MongoDB indexes for efficient querying."""
    collection = db['chunks']
    
    # Text index for full-text search
    collection.create_index([('text', 'text'), ('subject', 'text')])
    
    # Index for metadata filtering
    collection.create_index([('grade', 1)])
    collection.create_index([('subject', 1)])
    collection.create_index([('language', 1)])
    collection.create_index([('source_type', 1)])
    
    # Compound index for common queries
    collection.create_index([('grade', 1), ('subject', 1), ('language', 1)])
    
    print("✅ Indexes créés")


def show_mongodb_stats(db):
    """Display MongoDB collection statistics."""
    collection = db['chunks']
    
    count = collection.count_documents({})
    
    # Group by metadata
    grades = collection.distinct('grade')
    subjects = collection.distinct('subject')
    languages = collection.distinct('language')
    source_types = collection.distinct('source_type')
    
    print("\n📊 Statistiques MongoDB:")
    print(f"  • Total chunks: {count}")
    print(f"  • Grades: {sorted(grades)}")
    print(f"  • Matières: {sorted(subjects)}")
    print(f"  • Langues: {sorted(languages)}")
    print(f"  • Types source: {sorted(source_types)}")
    
    # Sample query: Count by grade
    print("\n  Chunks par grade:")
    for grade in sorted(grades):
        grade_count = collection.count_documents({'grade': grade})
        print(f"    Grade {grade}: {grade_count} chunks")


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("IMPORT MONGODB")
    print("=" * 80)
    print()
    
    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    json_dir = os.path.join(project_root, "data", "json_out")
    
    # Configuration (customize as needed)
    MONGODB_URI = "mongodb://localhost:27017/"  # Local MongoDB
    # MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/"  # Atlas
    
    print(f"MongoDB URI: {MONGODB_URI}")
    print(f"JSON source: {json_dir}")
    print()
    
    # Connect to MongoDB
    print("Connexion à MongoDB...", end=" ")
    db, error = connect_to_mongodb(MONGODB_URI)
    
    if error:
        print(error)
        print("\n📝 Installation:")
        print("  Local: installer MongoDB Community Edition")
        print("  Cloud: créer cluster sur MongoDB Atlas (free tier disponible)")
        print("  Docker: docker run -d -p 27017:27017 mongo")
        sys.exit(1)
    
    print("✅ Connecté")
    print()
    
    # Find and import all JSON files
    print("Recherche des fichiers JSON...")
    json_count = 0
    total_chunks = 0
    error_count = 0
    
    for root, dirs, files in os.walk(json_dir):
        for file in files:
            if file.endswith('_chunks.json'):
                json_count += 1
                json_path = os.path.join(root, file)
                
                print(f"\n  📄 {file}")
                chunks_inserted, error = import_json_to_mongodb(json_path, db)
                
                if error:
                    print(f"     ❌ {error}")
                    error_count += 1
                else:
                    print(f"     ✅ {chunks_inserted} chunks importés")
                    total_chunks += chunks_inserted
    
    print()
    print("=" * 80)
    
    if json_count == 0:
        print("❌ Aucun fichier JSON trouvé")
        print(f"   Vérifiez: {json_dir}")
        sys.exit(1)
    
    print(f"Import terminé:")
    print(f"  • Fichiers JSON: {json_count}")
    print(f"  • Total chunks importés: {total_chunks}")
    print(f"  • Erreurs: {error_count}")
    
    # Create indexes for efficient querying
    print("\nCréation des indexes...")
    try:
        create_indexes(db)
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
    
    # Show statistics
    try:
        show_mongodb_stats(db)
    except Exception as e:
        print(f"Impossible de récupérer les stats: {str(e)}")
    
    print()
    print("=" * 80)
    print("✨ Import terminé!")
    print()
    print("🔍 Requêtes MongoDB utiles:")
    print()
    print("  # Tous les chunks arabe")
    print("  db.chunks.find({language: 'ar'})")
    print()
    print("  # Maths Grade 1")
    print("  db.chunks.find({grade: 1, subject: 'Maths'})")
    print()
    print("  # Recherche full-text")
    print('  db.chunks.find({$text: {$search: "fraction"}})')
    print()
    print("  # Compter par grade")
    print("  db.chunks.aggregate([{$group: {_id: '$grade', count: {$sum: 1}}}])")
    print()
    print("=" * 80)
