# 🛠️ Guide Complet d'Installation

Guide étape par étape pour mettre en place le pipeline Astro KB.

---

## ✅ Checklist Pré-Installation

- [ ] Python 3.11+ installé
- [ ] Windows 10+ 
- [ ] 5GB d'espace disque (pour modèles ML)
- [ ] Connexion internet (téléchargement des dépendances)

---

## 1️⃣ Cloner le Repository

```bash
git clone <your-repo-url>
cd astro_kb_pipeline
```

---

## 2️⃣ Créer Environnement Virtuel Python

### Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Windows CMD:
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### Vérifier activation:
```
(.venv) C:\...\astro_kb_pipeline>
```

---

## 3️⃣ Installer Dépendances Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Résumé des paquets:**
- `pymupdf` - Extraction texte direct des PDFs
- `pdf2image` - Conversion PDF → Images (pour OCR)
- `pytesseract` - Wrapper Python pour Tesseract
- `sentence-transformers` - Embeddings multilingues
- `openai` - Intégration ChatGPT (optionnel)
- `pymongo` - MongoDB (optionnel)

---

## 4️⃣ Installer Tesseract (OCR)

### Via WinGet (Recommandé):
```powershell
winget install Tesseract
```

### Configuration pendant l'installation:
- ✓ Cocher: **Add Tesseract to PATH**
- ✓ Cocher: **Arabic**
- ✓ Cocher: **French**
- Accepter le chemin par défaut: `C:\Program Files\Tesseract-OCR`

### Vérification:
```bash
tesseract --version
tesseract --list-langs
```

Vous devez voir:
- `tesseract v5.5.0` (ou plus récent)
- `ara` et `fra` dans la liste des langues

---

## 5️⃣ Installer Poppler (PDF→Images)

### Via WinGet:
```powershell
winget install Poppler
```

### Redémarrer PowerShell après l'installation:
```powershell
exit
powershell
.\.venv\Scripts\Activate.ps1
```

### Vérification:
```bash
pdftoppm --version
```

---

## 6️⃣ Configuration Optionnelle

### A) MongoDB (pour indexation avancée)

**Option 1 - Local (recommandé pour test):**
```powershell
# via WinGet
winget install MongoDB

# ou Docker
docker run -d -p 27017:27017 mongo
```

**Option 2 - Cloud (MongoDB Atlas - Gratuit):**
1. Créer compte: https://www.mongodb.com/cloud/atlas
2. Créer cluster gratuit
3. Récupérer connection string
4. Éditer `scripts/05_import_mongodb.py`:
```python
MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/"
```

### B) OpenAI (pour génération de réponses)

1. Créer compte: https://platform.openai.com
2. Générer clé API (https://platform.openai.com/api-keys)
3. Définir variable d'environnement:

**PowerShell:**
```powershell
$env:OPENAI_API_KEY = "sk-..."
```

**Permanent (redémarrage requis):**
```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")
```

**Vérification:**
```bash
python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
```

---

## 🚀 Première Exécution

### Étape 1: Vérifier l'installation
```bash
python -c "import fitz, pdf2image, pytesseract; print('✅ Tous les modules OK')"
```

### Étape 2: Lancer le pipeline test
```bash
python scripts\run_all.py
```

Vous verrez:
```
================================================================================
 🚀 ASTRO KB PIPELINE - EXECUTION COMPLETE
================================================================================

Configuration:
  • Projet: C:\...\astro_kb_pipeline
  • OCR DPI: 300
  • Limite PDFs: Illimité
  • MongoDB: Non
  • Étape cible: Toutes

▶️  ÉTAPE 1: Détection des types PDF
...
```

---

## 📊 Résultats Attendus

Après l'exécution:

```
data/
├── extracted_text/         # Texte extrait
├── cleaned_text/           # Texte nettoyé
└── json_out/              # JSON avec métadonnées
```

**Exemple JSON chunk:**
```json
{
  "chunk_id": "1_Arabe_ar_1",
  "grade": 1,
  "subject": "Arabe",
  "language": "ar",
  "text": "...",
  "chunk_index": 1,
  "total_chunks": 15
}
```

---

## ⚡ Utilisation Rapide

### Pipeline Complète:
```bash
# Tous les PDFs (mode qualité)
python scripts\run_all.py

# Rapide
python scripts\run_all.py --dpi 200

# Test (5 PDFs)
python scripts\run_all.py --limit 5
```

### Étapes Individuelles:
```bash
# Détection
python scripts\01_detect_pdf_type.py

# Extraction (DPI=200)
python scripts\02_extract_pipeline.py 200

# Nettoyage
python scripts\03_clean_text.py

# Chunking + JSON
python scripts\04_chunk_and_json.py
```

### Recherche Sémantique:
```bash
python scripts\06_semantic_search.py
```

### Génération de Réponses:
```bash
python scripts\07_answer_generator.py
```

---

## 🔧 Troubleshooting

### Problème: "Tesseract not found"

**Solution 1 - Ajouter au PATH:**
```powershell
[Environment]::SetEnvironmentVariable(
  "PATH",
  "$($env:PATH);C:\Program Files\Tesseract-OCR",
  "User"
)
```

**Solution 2 - Vérifier installation:**
```bash
Get-ChildItem "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### Problème: "Poppler not found"

**Solution:**
```powershell
# Réinstaller
winget uninstall Poppler
winget install Poppler

# Redémarrer PowerShell
exit
powershell
```

### Problème: "ModuleNotFoundError"

```bash
# Vérifier l'environnement
pip list

# Réinstaller dépendances
pip install -r requirements.txt --force-reinstall
```

### Problème: Pas assez de RAM pour embeddings

```bash
# Utiliser modèle plus petit
# Éditer scripts/06_semantic_search.py
model = SentenceTransformer("all-MiniLM-L6-v2")  # Plus petit
```

---

## 📚 Architecture

```
Pipeline:
┌─────────────┐
│ PDF Brut    │
└──────┬──────┘
       │ detect_pdf_type.py
       ▼
┌─────────────────┐
│ Classification  │
│ (Text/Scanned)  │
└──────┬──────────┘
       │ extract_pipeline.py
       ▼
┌─────────────────┐
│ Texte Brut      │
│ (extracted_text)│
└──────┬──────────┘
       │ clean_text.py
       ▼
┌─────────────────┐
│ Texte Nettoyé   │
│ (cleaned_text)  │
└──────┬──────────┘
       │ chunk_and_json.py
       ▼
┌─────────────────┐
│ JSON Chunké     │
│ (json_out)      │
└──────┬──────────┘
       │ import_mongodb.py (optionnel)
       ▼
┌─────────────────┐
│ MongoDB         │
│ (base indexée)  │
└─────────────────┘
       │
       │ semantic_search.py
       ▼
┌─────────────────┐
│ Chunks Matchés  │
└──────┬──────────┘
       │ answer_generator.py
       ▼
┌─────────────────┐
│ Réponse GPT     │
└─────────────────┘
```

---

## ✨ Prochaines Étapes

1. **Traiter tous les PDFs:**
   ```bash
   python scripts\run_all.py
   ```

2. **Tester la recherche:**
   ```bash
   python scripts\06_semantic_search.py
   ```

3. **Générer les réponses:**
   ```bash
   python scripts\07_answer_generator.py
   ```

4. **Deployer une API** (en développement)

---

## 📞 Support

Pour les problèmes:
1. Vérifier la section Troubleshooting
2. Consulter les logs dans le terminal
3. Vérifier que tous les prérequis sont installés
4. Redémarrer PowerShell/CMD

---

**Version:** 1.0  
**Date:** 2026-07-03  
**Auteur:** Équipe Astro AI
