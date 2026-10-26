#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated pipeline to process all PDFs end-to-end.
Usage:
    python run_all.py                    # Default: all steps
    python run_all.py --dpi 200          # Use DPI 200 for OCR
    python run_all.py --limit 10         # Process first 10 PDFs
    python run_all.py --mongodb          # Also import to MongoDB
    python run_all.py --step extract     # Run only extraction step
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


class PipelineRunner:
    def __init__(self, project_root, dpi=300, limit=None, mongodb=False, step=None):
        self.project_root = project_root
        self.scripts_dir = os.path.join(project_root, "scripts")
        self.dpi = dpi
        self.limit = limit
        self.mongodb = mongodb
        self.step = step
        self.start_time = datetime.now()
        
    def print_header(self, text):
        """Print formatted header."""
        width = 80
        print("\n" + "=" * width)
        print(f" {text.center(width-2)}")
        print("=" * width + "\n")
    
    def print_step(self, step_num, name):
        """Print step header."""
        print(f"\n> ETAPE {step_num}: {name}")
        print("-" * 80)
    
    def run_script(self, script_name, args=None):
        """Run a Python script with optional arguments."""
        script_path = os.path.join(self.scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            print(f"[ERREUR] Script not found: {script_path}")
            return False
        
        cmd = [sys.executable, script_path]
        if args:
            cmd.extend(args)
        
        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"[ERREUR] Error running {script_name}: {e}")
            return False
    
    def run_pipeline(self):
        """Run the complete pipeline."""
        self.print_header("[START] ASTRO KB PIPELINE - EXECUTION COMPLETE")
        
        print(f"Configuration:")
        print(f"  • Projet: {self.project_root}")
        print(f"  • OCR DPI: {self.dpi}")
        print(f"  • Limite PDFs: {self.limit if self.limit else 'Illimité'}")
        print(f"  • MongoDB: {'Oui' if self.mongodb else 'Non'}")
        print(f"  • Étape cible: {self.step if self.step else 'Toutes'}")
        print()
        
        steps = {
            "detect": ("01_detect_pdf_type.py", []),
            "extract": ("02_extract_pipeline.py", [str(self.dpi)]),
            "clean": ("03_clean_text.py", []),
            "chunk": ("04_chunk_and_json.py", []),
            "mongodb": ("05_import_mongodb.py", []),
        }
        
        # Determine which steps to run
        if self.step:
            steps_to_run = {self.step: steps[self.step]} if self.step in steps else {}
            if not steps_to_run:
                print(f"[ERREUR] Étape inconnue: {self.step}")
                print(f"   Étapes disponibles: {', '.join(steps.keys())}")
                return False
        else:
            steps_to_run = steps.copy()
            if not self.mongodb:
                del steps_to_run["mongodb"]
        
        results = {}
        
        # Step 1: Detection
        if "detect" in steps_to_run:
            self.print_step(1, "Détection des types PDF")
            results["detect"] = self.run_script(*steps_to_run["detect"])
            if not results["detect"]:
                print("[WARN] Detection failed, continuing...")
        
        # Step 2: Extraction
        if "extract" in steps_to_run:
            self.print_step(2, "Extraction de texte")
            results["extract"] = self.run_script(*steps_to_run["extract"])
            if not results["extract"]:
                print("[ERREUR] Extraction failed. Stopping.")
                return False
        
        # Step 3: Cleaning
        if "clean" in steps_to_run:
            self.print_step(3, "Nettoyage du texte")
            results["clean"] = self.run_script(*steps_to_run["clean"])
            if not results["clean"]:
                print("[WARN] Cleaning failed, continuing...")
        
        # Step 4: Chunking
        if "chunk" in steps_to_run:
            self.print_step(4, "Chunking et création JSON")
            results["chunk"] = self.run_script(*steps_to_run["chunk"])
            if not results["chunk"]:
                print("[WARN] Chunking failed, continuing...")
        
        # Step 5: MongoDB Import
        if "mongodb" in steps_to_run:
            self.print_step(5, "Import dans MongoDB")
            results["mongodb"] = self.run_script(*steps_to_run["mongodb"])
            if not results["mongodb"]:
                print("[WARN] MongoDB import failed")
        
        # Summary
        self.print_summary(results)
        return True
    
    def print_summary(self, results):
        """Print pipeline summary."""
        self.print_header("[SUMMARY] RESUME FINAL")
        
        for step, success in results.items():
            status = "[OK] SUCCESS" if success else "[FAIL] ERROR"
            print(f"  {step.upper():15} {status}")
        
        elapsed = datetime.now() - self.start_time
        minutes, seconds = divmod(elapsed.total_seconds(), 60)
        
        print(f"\n[TIME] Total time: {int(minutes)}m {int(seconds)}s")
        print(f"\n[DONE] Pipeline complete!")
        
        # Next steps
        print(f"\n[NEXT] Next steps:")
        print(f"   1. Check files in data/json_out/")
        print(f"   2. Implement semantic search")
        print(f"   3. Generate embeddings for similarity")
        print(f"   4. Create matching API")


def main():
    parser = argparse.ArgumentParser(
        description="Astro KB Pipeline - Automated PDF processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all.py                    # Run all steps
  python run_all.py --dpi 200          # Faster OCR
  python run_all.py --limit 10         # Test first 10 PDFs
  python run_all.py --step extract     # Only extraction
  python run_all.py --mongodb          # Include MongoDB import
  python run_all.py --dpi 200 --mongodb --limit 50  # Custom mix
        """
    )
    
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for PDF to image conversion (200=fast, 300=quality) [default: 300]"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit processing to N PDFs (for testing)"
    )
    parser.add_argument(
        "--mongodb",
        action="store_true",
        help="Also import results to MongoDB"
    )
    parser.add_argument(
        "--step",
        choices=["detect", "extract", "clean", "chunk", "mongodb"],
        help="Run only a specific step"
    )
    
    args = parser.parse_args()
    
    # Get project root (scripts/ directory is one level up from run_all.py)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)  # Go up one level from scripts/
    
    # Run pipeline
    runner = PipelineRunner(
        project_root,
        dpi=args.dpi,
        limit=args.limit,
        mongodb=args.mongodb,
        step=args.step
    )
    
    success = runner.run_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
