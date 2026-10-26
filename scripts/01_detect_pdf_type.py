import fitz  # PyMuPDF
import os

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

# Test sur un PDF (à adapter)
if __name__ == "__main__":
    pdf_test = "../data/raw_pdfs/Manuels_Scolaires/1ere/Maths_1ere_FR.pdf"
    if os.path.exists(pdf_test):
        typ, txt = detect_pdf_type(pdf_test)
        print(f"Type détecté : {typ}")
        print(f"Premiers 300 caractères : {txt[:300]}")
    else:
        print("Fichier non trouvé. Ajuste le chemin.")