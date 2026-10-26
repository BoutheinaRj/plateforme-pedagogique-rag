import json

with open('data/json_out/Cahiers_Activites/1er_Primaire/Arabe/madrassatii.com-tamarine-nouveau-1er_chunks.json', encoding='utf-8') as f:
    chunks = json.load(f)

chunk = chunks[0]
print("=" * 80)
print("EXEMPLE: PREMIER CHUNK JSON")
print("=" * 80)
print(f"ID: {chunk['chunk_id']}")
print(f"Grade: {chunk['grade']}")
print(f"Matière: {chunk['subject']}")
print(f"Langue: {chunk['language']}")
print(f"Type: {chunk['source_type']}")
print(f"Fichier source: {chunk['source_file']}")
print(f"Position: Chunk {chunk['chunk_index']}/{chunk['total_chunks']}")
print(f"\nTEXTE ({len(chunk['text'])} chars):")
print("-" * 80)
print(chunk['text'][:300] + "...")
print("-" * 80)
print(f"\nTOTAL CHUNKS: {len(chunks)}")
print("=" * 80)
