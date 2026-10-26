#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pdf2image import convert_from_path
from pathlib import Path

POPPLER_PATH = r"C:\Users\LENOVO\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"

# Find a PDF that needs OCR
pdf_path = Path("data/raw_pdfs/Cahiers_Activites/4eme_Primere/Arabe").glob("*.pdf")
pdf = next(pdf_path)
print(f"Testing with: {pdf.name}")

imgs = convert_from_path(str(pdf), dpi=100, poppler_path=POPPLER_PATH)
print(f"Poppler OK: {len(imgs)} pages converted")
