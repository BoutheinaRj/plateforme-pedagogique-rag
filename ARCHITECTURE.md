# 🏗️ Architecture du Projet Astro KB

Aperçu technique complet du pipeline de base de connaissances pédagogique.

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Composants](#composants)
3. [Flux de Données](#flux-de-données)
4. [Technologies](#technologies)
5. [Performance](#performance)

---

## 🎯 Vue d'Ensemble

Le projet Astro KB transforme des PDFs pédagogiques (manuels, cahiers, exercices) en base de connaissances indexée, permettant:

1. **Extraction intelligente** - Texte natif ou OCR selon le type
2. **Nettoyage automatique** - Suppression du bruit, normalisation
3. **Indexation sémantique** - Embeddings multilingues
4. **Matching contextuel** - Recherche par similarité
5. **Génération de réponses** - Réponses adaptées au niveau via GPT

---

## 🔧 Composants

### 1. **Détection de Type** (`01_detect_pdf_type.py`)

**Entrée:** PDF  
**Sortie:** Classification (text/scan)

```python
detect_pdf_type(pdf_path) → "text" | "scan"
```

**Logique:**
- Extrait texte avec PyMuPDF
- Si > 500 caractères → texte natif
- Sinon → scanné (OCR nécessaire)

**Technologie:** PyMuPDF (fitz)

---

### 2. **Extraction de Texte** (`02_extract_pipeline.py`)

**Entrée:** PDF  
**Sortie:** Fichier `.txt` avec texte brut

```
PDF → [Détection] → [PyMuPDF ou OCR] → Texte Brut
```

**Deux chemins:**

**Chemin 1: Texte Natif (Rapide)**
```python
doc = fitz.open(pdf)
text = page.get_text()  # ~100ms/page
```

**Chemin 2: OCR (Lent)**
```python
images = convert_from_path(pdf, dpi=200)  # PDF → PNG
text = pytesseract.image_to_string(img, lang='ara+fra')  # ~5-10s/page
```

**Métadonnées extraites:**
- Taille du texte
- Méthode d'extraction
- Nombre de pages

**Technologies:**
- PyMuPDF (texte direct)
- pdf2image + Poppler (PDF→images)
- Tesseract OCR (images→texte)

---

### 3. **Nettoyage de Texte** (`03_clean_text.py`)

**Entrée:** Texte brut  
**Sortie:** Texte nettoyé

```
Texte Brut → [Regex] → [Normalisation] → Texte Propre
```

**Opérations:**

| Opération | Pattern | Exemple |
|-----------|---------|---------|
| Supprimer numéros de page | `^\s*\d+\s*$` | "12" → "" |
| Réparer sauts de ligne | `(?<!\n)\n(?!\n)` | "mot\ncontinue" → "mot continue" |
| Espaces multiples | ` +` | "mot  mot" → "mot mot" |
| Lignes blanches | `\n{2,}` | "\n\n\n" → "\n\n" |

**Amélioration:**
- 23.9% réduction taille (test: 61K → 46K chars)
- Conserve structure paragraphes
- Préserve UTF-8 (Arabe/Français)

---

### 4. **Chunking & JSON** (`04_chunk_and_json.py`)

**Entrée:** Texte nettoyé  
**Sortie:** JSON avec chunks métadonnés

```
Texte → [Split par mots] → [Chunks de 500 mots] → [JSON]
```

**Stratégie de chunking:**

```
words = [1, 2, 3, 4, 5, ..., 550]
                ↓
chunks avec overlap:
[1-500] → [451-950] → [901-1400] → ...
          ↑overlap 50 mots (2-51)
```

**Avantages:**
- Pas de coupure conceptuelle
- Contexte préservé aux limites
- Chunks de ~3000 caractères

**Métadonnées auto-détectées:**

```python
# Exemple: raw_pdfs/Manuels_Scolaires/5eme_Primaire/Francais/file.pdf

{
  "chunk_id": "5_Francais_fr_1",           # Grade_Subject_Lang_Index
  "grade": 5,                               # Auto-détecté de "5eme"
  "subject": "Francais",                    # Du nom du dossier
  "language": "fr",                         # Détecté de "Francais"
  "source_type": "manuel",                  # Détecté de "Manuels_Scolaires"
  "source_file": "filename_clean.txt",
  "chunk_index": 1,
  "total_chunks": 42,
  "text": "...",
  "embedding": [0.1, 0.2, ...]             # Ajouté lors de recherche
}
```

**Format JSON de sortie:**
```
data/json_out/
├── Cahiers_Activites/1er_Primaire/Arabe/
│   └── file_chunks.json
├── Manuels_Scolaires/5eme_Primaire/Francais/
│   └── file_chunks.json
```

---

### 5. **Import MongoDB** (`05_import_mongodb.py`)

**Optionnel - Indexation avancée**

**Entrée:** JSON chunks  
**Sortie:** Collections MongoDB indexées

```
JSON → [Parsing] → [Indexing] → MongoDB
```

**Structure:**
```
Database: astro_ai_kb
├── Collection: chunks
│   ├── Index: text (full-text)
│   ├── Index: grade
│   ├── Index: subject
│   ├── Index: language
│   └── Index: (grade, subject, language) compound
```

**Requêtes utiles:**
```javascript
// Arabe grade 1
db.chunks.find({grade: 1, language: "ar"})

// Recherche full-text
db.chunks.find({$text: {$search: "fraction"}})

// Stats
db.chunks.aggregate([{$group: {_id: "$grade", count: {$sum: 1}}}])
```

---

### 6. **Recherche Sémantique** (`06_semantic_search.py`)

**Entrée:** Requête utilisateur  
**Sortie:** Top-K chunks similaires

```
Query → [Embedding] → [Similarity] → [Top-K] → Chunks
```

**Processus:**

1. **Encoder requête:**
```python
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
query_embedding = model.encode(query)  # 384-dim vector
```

2. **Calculer similarité (Cosine):**
```
similarity = dot(query_emb, chunk_emb) / (||query_emb|| * ||chunk_emb||)
```

3. **Filtrer par métadonnées:**
```python
filters = {"grade": 1, "language": "ar", "subject": "Maths"}
candidates = [c for c in chunks if all(c.get(k) == v for k, v in filters.items())]
```

4. **Retourner top-3:**
```python
return sorted_by_similarity[:3]
```

**Modèles disponibles:**
- `paraphrase-multilingual-MiniLM-L12-v2` (rapide, recommandé)
- `paraphrase-multilingual-mpnet-base-v2` (meilleur, plus lent)
- `intfloat/multilingual-e5-small` (nouveau)

**Temps:**
- Embedding query: ~50ms
- Similarité 1000 chunks: ~100ms
- Total: ~150ms

---

### 7. **Génération de Réponses** (`07_answer_generator.py`)

**Entrée:** Question + Grade + Langue  
**Sortie:** Réponse contextuelle

```
Question → [Search] → [Chunks] → [Prompt] → [GPT] → Réponse
```

**Pipeline:**

1. **Détection de langue:**
   - Arabe: `\u0600-\u06FF` > 30%
   - Sinon: Français

2. **Recherche de chunks:**
   - Filtrer par grade, langue, sujet
   - Chercher les 3 plus similaires

3. **Construction du prompt:**
```python
system_msg = f"""Tu es prof de niveau {grade} parlant {langue}"""
user_msg = f"""Question: {question}

Contexte du cours:
[Source: Maths - Grade 1]
{chunk1_text}

[Source: Francais - Grade 2]
{chunk2_text}
...
"""
```

4. **Appel GPT:**
```python
response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[system, user],
    temperature=0.7,
    max_tokens=500
)
```

**Temps de réponse:**
- Recherche: ~150ms
- GPT: ~2-5s
- Total: ~2-5s

---

## 🔄 Flux de Données

```
┌────────────────────────────────────────────────┐
│            PIPELINE COMPLÈTE                   │
└────────────────────────────────────────────────┘

Phase 1: PREPARATION
─────────────────────
raw_pdfs/
└── PDF files
    ↓ (01_detect_pdf_type.py)
    │ Classification: text/scan

Phase 2: EXTRACTION
───────────────────
    ↓ (02_extract_pipeline.py)
    │ PyMuPDF (texte natif) → ~100ms/page
    │ ou
    │ pdf2image + Tesseract → ~5-10s/page
    ↓
extracted_text/
└── *.txt files

Phase 3: CLEANING
─────────────────
    ↓ (03_clean_text.py)
    │ Regex normalisation
    │ 2-24% réduction
    ↓
cleaned_text/
└── *_clean.txt files

Phase 4: INDEXATION
──────────────────
    ↓ (04_chunk_and_json.py)
    │ Split en chunks (500 mots)
    │ Auto-détection métadonnées
    ↓
json_out/
└── *_chunks.json files
    └── {chunk_id, grade, subject, language, text, ...}

Phase 5: DATABASE (optionnel)
──────────────────────────────
    ↓ (05_import_mongodb.py)
    │ Index full-text, métadonnées
    ↓
MongoDB
└── astro_ai_kb.chunks

Phase 6: RECHERCHE
──────────────────
[User Query] → (06_semantic_search.py)
             ↓
             Embedding + Similarité
             ↓
        Top-K Chunks

Phase 7: GÉNÉRATION
───────────────────
Chunks + Question → (07_answer_generator.py)
                  ↓
                  System Prompt
                  ↓
                  OpenAI GPT
                  ↓
                Answer Contextuelle
```

---

## 💻 Technologies

### Core Libraries

| Lib | Version | Rôle |
|-----|---------|------|
| **PyMuPDF** | 1.23.8 | Extraction texte direct |
| **pdf2image** | 1.16.3 | PDF → Images |
| **pytesseract** | 0.3.10 | Wrapper Tesseract |
| **pillow** | 10.1.0 | Traitement images |
| **opencv** | 4.8.1 | Vision (optionnel) |

### Machine Learning

| Lib | Version | Rôle |
|-----|---------|------|
| **sentence-transformers** | 2.2.2 | Embeddings |
| **torch** | 2.1.1 | Backend ML |
| **numpy** | 1.24.3 | Calculs |

### External Services

| Service | Rôle | Gratuit |
|---------|------|---------|
| **Tesseract** | OCR | ✓ |
| **Poppler** | PDF→Images | ✓ |
| **MongoDB** | Database | ✓ (local/atlas) |
| **OpenAI** | LLM | $0.002/1K tokens |

### Langues Supportées

- **Arabe** (Tesseract + Sentence-Transformers)
- **Français** (Tesseract + Sentence-Transformers)

---

## ⚡ Performance

### Benchmarks (testé sur i7-12700K, 32GB RAM)

| Étape | Type PDF | Temps | Dépend |
|-------|----------|-------|--------|
| Détection | - | 100ms | Taille PDF |
| Extraction | Texte | 50ms | Pages |
| Extraction | Scan (DPI=200) | 5-10s/page | OCR |
| Extraction | Scan (DPI=300) | 10-15s/page | OCR |
| Nettoyage | - | 100ms | Taille texte |
| Chunking | 162K chars | 50ms | Texte |
| Embedding (1 chunk) | 3K chars | 10ms | Modèle |
| Similarité (1000 chunks) | - | 100ms | Nombre |
| GPT Response | - | 2-5s | Réseau |

### Optimisations

1. **OCR Rapide:** Utiliser DPI=200 au lieu de 300
2. **Batch Embeddings:** Encoder plusieurs chunks en parallèle
3. **Cache:** Pré-computer tous les embeddings
4. **Filters:** Réduire chunks avant similarité (grade, langue)

### Scalabilité

- **Chunks:** 66 (test) → 10,000+ (scalable)
- **Modèle embedding:** 384-dim → ~50MB GPU RAM
- **MongoDB:** Index → O(log n) queries

---

## 📈 Exemple Complet

### Entrée
```
Question: "Comment additionner deux fractions?"
Grade: 5
Language: "fr"
Subject: "Maths"
```

### Processus

1. **Embedding query:**
   - Dimensions: 384
   - Temps: 50ms

2. **Recherche chunks:**
   - Filtres: grade=5, language=fr, subject=Maths
   - Similarité: [0.92, 0.87, 0.81]
   - Temps: 150ms

3. **Chunks matchés:**
   ```
   [1] 0.92: "Pour additionner deux fractions avec le même dénominateur..."
   [2] 0.87: "L'addition de fractions est une opération..."
   [3] 0.81: "Quand les dénominateurs sont différents..."
   ```

4. **Prompt GPT:**
   ```
   System: Tu es prof de math niveau 5
   User: Question + chunks
   ```

5. **Réponse:**
   ```
   "Pour additionner deux fractions:
   1. Vérifier que les dénominateurs sont identiques
   2. Additionner les numérateurs
   3. Garder le même dénominateur
   
   Exemple: 1/4 + 2/4 = 3/4"
   ```

### Temps Total: ~2.5 secondes

---

## 🚀 Prochaines Étapes

1. **API REST** - Endpoint pour Q&A
2. **Web UI** - Interface chat
3. **Mobile App** - Accès élèves
4. **Analytics** - Usage tracking
5. **Modèles Custom** - Fine-tuning

---

**Version:** 1.0  
**Date:** 2026-07-03
