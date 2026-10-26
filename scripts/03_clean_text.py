import re
import os

def clean_text(raw_text):
    """Clean extracted text from PDFs.
    
    Steps:
    1. Remove page numbers (ex: "Page 12" or "12" on its own line)
    2. Replace single line breaks with spaces (fix broken sentences)
    3. Replace multiple spaces with single space
    4. Remove excessive blank lines
    """
    # 1. Remove page numbers (lines containing only digits/spaces)
    text = re.sub(r'(?m)^\s*\d+\s*$', '', raw_text)
    
    # 2. Replace single line breaks with spaces (but keep paragraph breaks)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    
    # 3. Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    
    # 4. Remove excessive blank lines (keep max 2 consecutive newlines = 1 blank line)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    
    return text.strip()


def clean_file(input_txt, output_txt):
    """Clean extracted text file.
    
    Args:
        input_txt: Path to extracted text file
        output_txt: Path to cleaned text file
    """
    with open(input_txt, 'r', encoding='utf-8') as f:
        raw = f.read()
    
    cleaned = clean_text(raw)
    
    os.makedirs(os.path.dirname(output_txt), exist_ok=True)
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    
    # Stats
    original_size = len(raw)
    cleaned_size = len(cleaned)
    reduction = ((original_size - cleaned_size) / original_size * 100) if original_size > 0 else 0
    
    print(f"✓ Nettoyé: {os.path.basename(output_txt)}")
    print(f"  Original: {original_size:,} chars → Nettoyé: {cleaned_size:,} chars ({reduction:.1f}% réduit)")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    print("=" * 80)
    print("NETTOYAGE DE TEXTE EXTRAIT")
    print("=" * 80)
    
    # Find all extracted text files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    extracted_dir = os.path.join(project_root, "data", "extracted_text")
    cleaned_dir = os.path.join(project_root, "data", "cleaned_text")
    
    print(f"Source: {extracted_dir}")
    print(f"Destination: {cleaned_dir}")
    print()
    
    # Process all .txt files recursively
    txt_count = 0
    for root, dirs, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith('.txt'):
                txt_count += 1
                input_path = os.path.join(root, file)
                
                # Preserve directory structure in cleaned_dir
                rel_path = os.path.relpath(root, extracted_dir)
                output_root = os.path.join(cleaned_dir, rel_path) if rel_path != '.' else cleaned_dir
                output_path = os.path.join(output_root, file.replace('.txt', '_clean.txt'))
                
                try:
                    clean_file(input_path, output_path)
                except Exception as e:
                    print(f"❌ Erreur: {file} - {str(e)}")
    
    print()
    print("=" * 80)
    print(f"Nettoyage terminé: {txt_count} fichiers traités")
    print("=" * 80)
