import fitz
import os
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import io

# Poppler path for pdf2image on Windows
POPPLER_PATH = r"C:\Users\LENOVO\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"

def extract_text_pymupdf(pdf_path):
    """Extract text directly from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def extract_text_ocr(pdf_path, lang="ara+fra", dpi=300):
    """Extract text from PDF using OCR (for scanned PDFs).
    
    Args:
        pdf_path: Path to PDF file
        lang: Language codes (e.g., "ara+fra" for Arabic+French)
        dpi: DPI for PDF to image conversion (300 for quality, 200 for speed)
    """
    # Convert PDF to images
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=POPPLER_PATH)
    total_pages = len(images)
    full_text = ""
    
    print(f"  OCR: {total_pages} pages à traiter (DPI={dpi})...")
    
    for i, img in enumerate(images):
        # Show progress for large PDFs
        if total_pages > 5:
            progress = f"  [{i+1}/{total_pages}]"
            print(progress, end="\r", flush=True)
        
        # OCR with specified languages
        page_text = pytesseract.image_to_string(img, lang=lang)
        full_text += page_text + "\n"
    
    if total_pages > 5:
        print(f"  OCR terminé: {total_pages} pages ✓        ")
    
    return full_text

def extract_pdf(pdf_path, output_txt_path, threshold=500, dpi=300, lang="ara+fra"):
    """Extract text from PDF (automatic text/OCR detection).
    
    Args:
        pdf_path: Path to PDF
        output_txt_path: Output text file path
        threshold: Minimum characters to consider as "text" PDF
        dpi: DPI for OCR (300 recommended, 200 for speed)
        lang: Languages for OCR (ara+fra for Arabic+French)
    """
    print(f"\n📄 Traitement: {os.path.basename(pdf_path)}")
    
    # Try direct extraction first
    print("  Tentative extraction directe...", end=" ")
    text = extract_text_pymupdf(pdf_path)
    
    if len(text.strip()) > threshold:
        print("✓ OK (texte natif)")
        extraction_method = "directe"
    else:
        print("✗ Insuffisant - passage en OCR")
        try:
            text = extract_text_ocr(pdf_path, lang=lang, dpi=dpi)
            extraction_method = "OCR"
        except Exception as e:
            print(f"  ⚠️  OCR failed ({str(e)[:50]}...) - using empty text")
            text = ""
            extraction_method = "OCR_ERROR"
    
    # Save output
    os.makedirs(os.path.dirname(output_txt_path), exist_ok=True)
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    # Summary
    text_length = len(text.strip())
    print(f"  Extraction: {extraction_method}")
    print(f"  Résultat: {text_length} caractères")
    print(f"  Sauvegardé: {output_txt_path}")
    
    return text

if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("PIPELINE D'EXTRACTION DE TEXTE - TEST")
    print("=" * 80)
    
    # Configuration avec chemins absolus basés sur le script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    root_pdf_dir = os.path.join(project_root, "data", "raw_pdfs")
    output_text_dir = os.path.join(project_root, "data", "extracted_text")
    
    test_limit = 999999  # Process ALL PDFs
    dpi_ocr = 200  # Use 200 DPI for faster OCR (set to 300 for better quality)
    
    if len(sys.argv) > 1:
        dpi_ocr = int(sys.argv[1])
    
    print(f"Configuration: DPI OCR = {dpi_ocr}")
    print(f"Racine PDF: {root_pdf_dir}")
    print("=" * 80)
    
    # Test sur plusieurs PDFs
    pdf_count = 0
    success_count = 0
    error_count = 0
    
    for dirpath, dirnames, filenames in os.walk(root_pdf_dir):
        for filename in filenames:
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(dirpath, filename)
                pdf_count += 1
                
                if pdf_count > test_limit:
                    break
                
                try:
                    # Créer chemin de sortie
                    rel_path = os.path.relpath(dirpath, root_pdf_dir)
                    base_name = os.path.splitext(filename)[0]
                    output_txt_path = os.path.join(output_text_dir, rel_path, base_name + ".txt")
                    
                    # Extraction
                    extract_pdf(pdf_path, output_txt_path, dpi=dpi_ocr)
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ ERREUR: {str(e)}")
                    error_count += 1
        
        if pdf_count > test_limit:
            break
    
    print()
    print("=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    print(f"PDFs traités: {success_count}")
    print(f"Erreurs: {error_count}")
    print("=" * 80)