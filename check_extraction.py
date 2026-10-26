import json
from pathlib import Path

# Extraction check
extracted = list(Path('data/extracted_text').rglob('*.txt'))
non_empty = [f for f in extracted if f.stat().st_size > 0]
total_chars = sum(f.stat().st_size for f in non_empty)

print("EXTRACTION")
print(f"  Total fichiers: {len(extracted)} / 393")
print(f"  Avec texte: {len(non_empty)}")
print(f"  Vides (OCR echoue): {len(extracted) - len(non_empty)}")
print(f"  Total caracteres: {total_chars/1024/1024:.1f}MB")
print()

# Nettoyage check
cleaned = list(Path('data/cleaned_text').rglob('*.txt'))
print("NETTOYAGE")
print(f"  Fichiers nettoyes: {len(cleaned)}")
status = "OUI" if len(cleaned) == len(non_empty) else "NON - INCOMPLET"
print(f"  Complet: {status}")
print()

# Chunks check
json_files = list(Path('data/json_out').rglob('*.json'))
print("CHUNKS JSON")
print(f"  Fichiers JSON: {len(json_files)}")

# Sample structure
if json_files:
    with open(json_files[0], encoding='utf-8') as f:
        sample = json.load(f)
    if sample:
        print(f"  Exemple de chunk:")
        chunk = sample[0]
        for key in chunk.keys():
            val = chunk[key]
            if isinstance(val, str) and len(str(val)) > 50:
                print(f"    - {key}: {str(val)[:50]}...")
            else:
                print(f"    - {key}: {val}")
