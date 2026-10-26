import fitz  # PyMuPDF
import os
import sys

# Import dynamique du script 01
spec = __import__('importlib.util').util.spec_from_file_location(
    "detect_pdf_module",
    os.path.join(os.path.dirname(__file__), "01_detect_pdf_type.py")
)
detect_pdf_module = __import__('importlib.util').util.module_from_spec(spec)
spec.loader.exec_module(detect_pdf_module)
detect_pdf_type = detect_pdf_module.detect_pdf_type

def test_multiple_pdfs():
    """Test detection sur plusieurs PDF."""
    root_pdf_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw_pdfs")
    
    results = []
    pdf_count = 0
    
    print("=" * 80)
    print("TEST DE CLASSIFICATION DE PDFs")
    print("=" * 80)
    print()
    
    for dirpath, dirnames, filenames in os.walk(root_pdf_dir):
        for filename in filenames:
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(dirpath, filename)
                pdf_count += 1
                
                # Limiter à 10 PDFs pour le test
                if pdf_count > 10:
                    break
                
                try:
                    pdf_type, extracted_text = detect_pdf_type(pdf_path)
                    text_len = len(extracted_text.strip())
                    category = "📄 TEXTE NATIF" if pdf_type == "text" else "📸 SCANNÉ"
                    
                    # Chemin relatif plus court
                    rel_path = os.path.relpath(pdf_path, root_pdf_dir)
                    
                    result = {
                        "file": rel_path,
                        "type": pdf_type,
                        "text_length": text_len,
                        "category": category
                    }
                    results.append(result)
                    
                    print(f"{category} | {text_len:>6} chars | {rel_path}")
                    
                except Exception as e:
                    print(f"❌ ERREUR | {filename} | {str(e)}")
        
        if pdf_count > 10:
            break
    
    print()
    print("=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    
    text_count = sum(1 for r in results if r["type"] == "text")
    scan_count = sum(1 for r in results if r["type"] == "scan")
    
    print(f"Total PDFs testés: {len(results)}")
    print(f"  ✓ PDFs Texte Natif: {text_count}")
    print(f"  ✓ PDFs Scannés: {scan_count}")
    print()

if __name__ == "__main__":
    test_multiple_pdfs()
