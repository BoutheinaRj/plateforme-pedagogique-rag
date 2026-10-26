#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-extract empty files (OCR_ERROR) using Poppler now that it's configured.
"""
import os
import sys
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

POPPLER_PATH = r"C:\Users\LENOVO\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

project_root = Path(__file__).parent.parent  # Go up from scripts/ to project root
pdf_root = project_root / "data" / "raw_pdfs"
txt_root = project_root / "data" / "extracted_text"

# Find all empty txt files
empty_txts = [f for f in txt_root.rglob("*.txt") if f.stat().st_size == 0]
print(f"Files to re-process: {len(empty_txts)}")
print("-" * 80)

success = 0
errors = 0

for txt_path in empty_txts:
    # Get corresponding PDF path
    rel = txt_path.relative_to(txt_root)
    pdf_name = rel.stem + ".pdf"
    pdf_path = pdf_root / rel.parent / pdf_name
    
    if not pdf_path.exists():
        print(f"[SKIP] PDF not found: {pdf_name}")
        continue
    
    print(f"\n[OCR] {pdf_name}")
    try:
        images = convert_from_path(str(pdf_path), dpi=200, poppler_path=POPPLER_PATH)
        print(f"  Pages: {len(images)}", end=" -> OCR...", flush=True)
        
        full_text = ""
        for i, img in enumerate(images):
            if len(images) > 5:
                print(f"\r  Page {i+1}/{len(images)}...", end="", flush=True)
            page_text = pytesseract.image_to_string(img, lang="ara+fra")
            full_text += page_text + "\n"
        
        # Save
        txt_path.write_text(full_text, encoding="utf-8")
        print(f"\r  Done: {len(full_text)} chars saved to {txt_path.name}")
        success += 1
        
    except Exception as e:
        print(f"\n  ERROR: {e}")
        errors += 1

print()
print("=" * 80)
print(f"Re-extracted: {success}, Errors: {errors}")
print("=" * 80)
print("\nNext: Run scripts/03_clean_text.py and scripts/04_chunk_and_json.py")
