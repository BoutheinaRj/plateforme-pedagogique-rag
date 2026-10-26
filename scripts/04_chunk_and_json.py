import os
import json
import re
from pathlib import Path


def split_into_chunks(text, chunk_size_words=500, overlap_words=50):
    """Split text into overlapping chunks.
    
    Args:
        text: Text to split
        chunk_size_words: Words per chunk (default 500)
        overlap_words: Overlapping words between chunks (default 50)
    
    Returns:
        List of text chunks
    """
    words = text.split()
    chunks = []
    step = chunk_size_words - overlap_words
    
    if step <= 0:
        step = chunk_size_words
    
    for i in range(0, len(words), step):
        chunk_words = words[i:i+chunk_size_words]
        if not chunk_words:
            break
        chunk_text = " ".join(chunk_words)
        chunks.append(chunk_text)
    
    return chunks


def extract_metadata_from_path(file_path, project_root):
    """Extract metadata (grade, subject, language) from file path.
    
    Example:
    Cahiers_Activites/1er_Primaire/Arabe/file.txt
    -> grade=1, subject="Arabe", language="ar"
    """
    rel_path = os.path.relpath(file_path, project_root)
    parts = rel_path.split(os.sep)
    
    # Default values
    grade = None
    subject = None
    language = "ar"  # Default to Arabic
    source_type = "unknown"
    
    # Detect source type from first directory
    if parts and parts[0]:
        if "Cahiers" in parts[0]:
            source_type = "cahier_activites"
        elif "Exercices" in parts[0]:
            source_type = "exercices"
        elif "Manuels" in parts[0]:
            source_type = "manuel"
        elif "Programmes" in parts[0]:
            source_type = "programme_officiel"
    
    # Extract grade from path (1er, 2eme, 3eme, 4eme, 5eme, 6eme)
    for part in parts:
        if "1er" in part:
            grade = 1
        elif "2eme" in part or "2éme" in part:
            grade = 2
        elif "3eme" in part or "3éme" in part:
            grade = 3
        elif "4eme" in part or "4éme" in part:
            grade = 4
        elif "5eme" in part or "5éme" in part:
            grade = 5
        elif "6eme" in part or "6éme" in part:
            grade = 6
    
    # Extract subject
    for part in parts:
        if part in ["Arabe", "Francais", "Math", "Science", "Islamique", 
                   "Geographie", "Historique", "Madania", "Anglais", "Technologie",
                   "Geometrique", "Hist_Geo_Madania", "Englais", "Sciance"]:
            subject = part
            # Detect language from subject or part name
            if part in ["Francais", "Englais"]:
                language = "fr"
            elif "Math" in part or "Science" in part or "Anglais" in part:
                language = "fr"
            elif part in ["Arabe", "Islamique"]:
                language = "ar"
            break
    
    # Detect from filename
    filename = os.path.basename(file_path)
    if "_FR" in filename or "Francais" in filename or "francais" in filename:
        language = "fr"
    elif "_AR" in filename:
        language = "ar"
    
    return {
        "grade": grade,
        "subject": subject,
        "language": language,
        "source_type": source_type
    }


def create_json_from_cleaned(cleaned_txt_path, output_json_path, project_root):
    """Convert cleaned text to JSON with chunks.
    
    Args:
        cleaned_txt_path: Path to cleaned text file
        output_json_path: Path to output JSON file
        project_root: Project root for metadata extraction
    """
    # Extract metadata
    metadata = extract_metadata_from_path(cleaned_txt_path, project_root)
    
    # Read cleaned text
    with open(cleaned_txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Split into chunks
    chunks = split_into_chunks(text)
    
    # Create JSON objects
    json_data = []
    for idx, chunk in enumerate(chunks):
        obj = {
            "chunk_id": f"{metadata['grade']}_{metadata['subject']}_{metadata['language']}_{idx+1}",
            "grade": metadata["grade"],
            "subject": metadata["subject"],
            "language": metadata["language"],
            "source_type": metadata["source_type"],
            "source_file": os.path.basename(cleaned_txt_path),
            "chunk_index": idx + 1,
            "total_chunks": len(chunks),
            "text": chunk
        }
        json_data.append(obj)
    
    # Save JSON
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ JSON créé: {os.path.basename(output_json_path)}")
    print(f"  Chunks: {len(chunks)} | Grade: {metadata['grade']} | Matière: {metadata['subject']} | Langue: {metadata['language']}")


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("CHUNKING ET CRÉATION JSON")
    print("=" * 80)
    
    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    cleaned_dir = os.path.join(project_root, "data", "cleaned_text")
    json_dir = os.path.join(project_root, "data", "json_out")
    
    print(f"Source: {cleaned_dir}")
    print(f"Destination: {json_dir}")
    print()
    
    # Process all cleaned text files
    txt_count = 0
    for root, dirs, files in os.walk(cleaned_dir):
        for file in files:
            if file.endswith('_clean.txt'):
                txt_count += 1
                input_path = os.path.join(root, file)
                
                # Create output path preserving structure
                rel_path = os.path.relpath(root, cleaned_dir)
                output_root = os.path.join(json_dir, rel_path) if rel_path != '.' else json_dir
                base_name = file.replace('_clean.txt', '')
                output_path = os.path.join(output_root, base_name + '_chunks.json')
                
                try:
                    create_json_from_cleaned(input_path, output_path, cleaned_dir)
                except Exception as e:
                    print(f"❌ Erreur: {file} - {str(e)}")
    
    print()
    print("=" * 80)
    print(f"Chunking terminé: {txt_count} fichiers traités")
    print("=" * 80)
