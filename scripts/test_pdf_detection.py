#!/usr/bin/env python3
import sys
import os
import fitz

# Import the detect_pdf_type function directly
def detect_pdf_type(pdf_path, threshold=500):
    """
    Retourne 'text' si l'extraction directe donne plus de 'threshold' caractères,
    sinon 'scan'.
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    if len(full_text.strip()) > threshold:
        return "text", full_text
    else:
        return "scan", full_text

# Test PDFs
test_pdfs = [
    r"C:\Users\LENOVO\OneDrive\Desktop\astro_kb_pipeline\data\raw_pdfs\Cahiers_Activites\1er_Primaire\Arabe\madrassatii.com-tamarine-nouveau-1er.pdf",
    r"C:\Users\LENOVO\OneDrive\Desktop\astro_kb_pipeline\data\raw_pdfs\Cahiers_Activites\2eme_Primere\Arabe\madrassatii.comtamarine-nouveau-2.pdf",
    r"C:\Users\LENOVO\OneDrive\Desktop\astro_kb_pipeline\data\raw_pdfs\Cahiers_Activites\3eme_Primaire\Arabe\101316P01.pdf",
    r"C:\Users\LENOVO\OneDrive\Desktop\astro_kb_pipeline\data\raw_pdfs\Cahiers_Activites\4eme_Primere\Arabe\أدوات التواصل - كتاب التمارين - السنة الرابعة من التعليم الأساسي.pdf",
    r"C:\Users\LENOVO\OneDrive\Desktop\astro_kb_pipeline\data\raw_pdfs\Cahiers_Activites\4eme_Primere\Francais\Au rythme des projets - Cahier d'activités - 4éme enseignement de base.pdf",
]

print("=" * 80)
print("PDF TYPE CLASSIFICATION TEST")
print("=" * 80)

results = []
for pdf_path in test_pdfs:
    if os.path.exists(pdf_path):
        try:
            pdf_type, extracted_text = detect_pdf_type(pdf_path)
            text_length = len(extracted_text.strip())
            results.append({
                'path': os.path.basename(pdf_path),
                'type': pdf_type,
                'text_length': text_length,
                'status': '✓'
            })
            print(f"\n✓ {os.path.basename(pdf_path)}")
            print(f"  Type: {pdf_type.upper()}")
            print(f"  Extracted text length: {text_length} chars")
            print(f"  Preview: {extracted_text[:100]}...")
        except Exception as e:
            results.append({
                'path': os.path.basename(pdf_path),
                'type': 'ERROR',
                'text_length': 0,
                'status': f'✗ {str(e)}'
            })
            print(f"\n✗ {os.path.basename(pdf_path)}")
            print(f"  Error: {str(e)}")
    else:
        print(f"\n✗ File not found: {pdf_path}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
text_count = sum(1 for r in results if r['type'] == 'text')
scan_count = sum(1 for r in results if r['type'] == 'scan')
error_count = sum(1 for r in results if r['type'] == 'ERROR')

print(f"Total tested: {len(results)}")
print(f"  - Text PDFs: {text_count}")
print(f"  - Scan PDFs: {scan_count}")
print(f"  - Errors: {error_count}")
print("=" * 80)
