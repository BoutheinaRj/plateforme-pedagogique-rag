# Plateforme pédagogique RAG

Plateforme pédagogique pour l'enseignement de base (1ère à 6ème année) : les élèves posent une question et obtiennent une réponse adaptée à leur niveau, construite à partir des manuels scolaires, cahiers d'activités et programmes officiels.

Le projet regroupe :

- un **pipeline de traitement** des PDF scolaires (détection, extraction native ou OCR, nettoyage, découpage en chunks JSON) ;
- un **moteur de recherche hybride** (sémantique + mots-clés) filtrable par niveau, matière et langue ;
- un **générateur de réponses pédagogiques** (Gemini ou OpenAI) appuyé sur les sources retrouvées ;
- une **API REST FastAPI** documentée et une **interface web** au thème enfants.

## Fonctionnalités

- Niveaux 1 à 6, matières : Arabe, Français, Anglais, Math, Sciences, Éducation islamique, Histoire, Géographie, Éducation civique…
- Contenus multilingues : français, arabe, anglais
- Réponses adaptées au niveau et à l'âge de l'élève, avec les sources citées
- Programme officiel et progression par niveau et par matière
- Documentation interactive OpenAPI sur `/docs`

## Stack technique

| Domaine | Outils |
|---|---|
| API | FastAPI, Uvicorn, Jinja2 |
| Recherche | Sentence-Transformers, PyTorch, NumPy |
| Extraction PDF | PyMuPDF, Tesseract OCR, pdf2image / Poppler, OpenCV |
| Génération | Google Gemini (par défaut), OpenAI (optionnel) |
| Stockage | Fichiers JSON, MongoDB (optionnel) |

## Installation

Prérequis : Python 3.11+, et pour l'OCR [Tesseract](https://github.com/tesseract-ocr/tesseract) et [Poppler](https://poppler.freedesktop.org/) (voir [SETUP.md](SETUP.md)).

```bash
git clone https://github.com/BoutheinaRj/plateforme-pedagogique-rag.git
cd plateforme-pedagogique-rag

python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

Créer un fichier `.env` à la racine (il n'est jamais versionné) :

```env
# Gemini (fournisseur par défaut)
GEMINI_API_KEY=votre_cle_gemini
GEMINI_API_KEYS=cle1,cle2
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_FALLBACK_MODELS=gemini-2.5-flash-lite
GEMINI_REQUEST_DELAY=4.5
GEMINI_MAX_RETRIES=1

# OpenAI (optionnel)
OPENAI_API_KEY=votre_cle_openai
OPENAI_MODEL=gpt-4o-mini
```

## Construire la base de connaissances

Le dossier `data/` n'est pas inclus dans le dépôt (documents volumineux). Placer les PDF dans `data/raw_pdfs/` puis lancer le pipeline :

```bash
python scripts/run_all.py              # toutes les étapes
python scripts/run_all.py --dpi 200    # OCR en 200 DPI
python scripts/run_all.py --limit 10   # seulement les 10 premiers PDF
python scripts/run_all.py --mongodb    # import MongoDB en plus
```

| Étape | Script | Résultat |
|---|---|---|
| 1. Détection du type de PDF | `01_detect_pdf_type.py` | natif ou scanné |
| 2. Extraction du texte | `02_extract_pipeline.py` | `data/extracted_text/` |
| 3. Nettoyage | `03_clean_text.py` | `data/cleaned_text/` |
| 4. Découpage en chunks | `04_chunk_and_json.py` | `data/json_out/*_chunks.json` |
| 5. Import MongoDB (optionnel) | `05_import_mongodb.py` | collection MongoDB |

## Lancer l'application

```bash
uvicorn fastapi_app:app --reload --host 0.0.0.0 --port 8000
```

- Interface web : http://localhost:8000
- Swagger : http://localhost:8000/docs
- ReDoc : http://localhost:8000/redoc

> Sous Windows, si le démarrage échoue avec `UnicodeEncodeError`, définir `PYTHONUTF8=1` avant de lancer la commande.

## Endpoints principaux

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | État du service et taille de la base |
| GET | `/api/stats` | Répartition des chunks par niveau, matière, langue |
| POST | `/api/search` | Recherche sémantique, mots-clés ou hybride |
| POST | `/api/answer` | Réponse pédagogique avec sources |
| GET | `/api/chunks` | Liste paginée des chunks |
| GET | `/api/chunk/{chunk_id}` | Détail d'un chunk |
| GET | `/api/program` | Programme officiel |
| GET | `/api/progression/{grade}` | Progression d'un niveau |
| GET | `/api/subject-program/{grade}/{subject}` | Programme d'une matière pour un niveau |

### Exemple : recherche

```http
POST /api/search
Content-Type: application/json

{
  "query": "les fractions",
  "grade": 5,
  "language": "fr",
  "subject": "Math",
  "limit": 5,
  "mode": "hybrid"
}
```

### Exemple : réponse pédagogique

```http
POST /api/answer
Content-Type: application/json

{
  "question": "Explique les fractions simplement",
  "grade": 5,
  "age": 10,
  "language": "fr",
  "subject": "Math",
  "conversation": []
}
```

```json
{
  "question": "Explique les fractions simplement",
  "answer": "Une fraction représente une partie d'un tout...",
  "sources": [],
  "mode": "grounded",
  "grade": 5,
  "language": "fr"
}
```

Des clients prêts à l'emploi sont fournis en Python et Node.js dans [integration/](integration/).

## Structure du projet

```text
plateforme-pedagogique-rag/
├── fastapi_app.py      # API REST
├── app.py              # Cœur RAG : chargement, recherche, génération
├── scripts/            # Pipeline de traitement des PDF (01 → 07, run_all.py)
├── integration/        # Clients API Python / Node.js
├── templates/          # Interface web (Jinja2)
├── static/             # CSS / JS de l'interface
├── data/               # Données locales (non versionnées)
└── requirements.txt
```

## Tests

```bash
python test_search.py
python test_semantic_search.py
python test_rag_simple.py
python test_rag_gemini.py   # nécessite une clé Gemini
```

## Documentation complémentaire

- [ARCHITECTURE.md](ARCHITECTURE.md) : architecture détaillée
- [SETUP.md](SETUP.md) : installation de Tesseract et Poppler
- [GEMINI_OPTIMISATION.md](GEMINI_OPTIMISATION.md) : gestion des quotas Gemini
- [NEXT_STEPS.md](NEXT_STEPS.md) : pistes d'évolution

## Licence

MIT
