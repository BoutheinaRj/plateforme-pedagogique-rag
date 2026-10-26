# 🚀 Guide d'Optimisation - API Gemini

## Problème Rencontré

**Erreur 429: TooManyRequests** - Le quota minute était épuisé après seulement quelques requêtes.

### Racine du problème

Tu avais:
- ❌ **4 clés Gemini** dans le même projet → elles se concurrencent
- ❌ **Modèles fallback multiples** (1.5-pro, 1.5-flash, etc) → certains n'existent pas/plus
- ❌ **Pas de délai** entre requêtes → dépassement du quota minute

---

## Solutions Appliquées ✅

### 1. **Une Seule Clé Gemini**
- ❌ AVANT: 4 clés → quota partagé
- ✅ APRÈS: 1 clé → quota concentré

**Dans `.env`:**
```env
GEMINI_API_KEY=votre_cle_gemini
```

**Supprime les autres clés dans Google Cloud Console**

---

### 2. **Utiliser UNIQUEMENT gemini-2.0-flash**

**Avant:**
```python
GEMINI_FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",  # ❌ N'existe plus
    "gemini-pro",              # ❌ N'existe plus
]
```

**Après:**
```python
GEMINI_FALLBACK_MODELS = ["gemini-2.0-flash"]  # ✅ Seul modèle fiable
```

**Pourquoi gemini-2.0-flash?**
- ✅ Quota le plus haut en gratuit (10 req/min)
- ✅ Gratuit: 1500 req/jour
- ✅ Vitesse: Plus rapide que les autres
- ✅ Coût: $0.075 pour 1M tokens (entrée)

---

### 3. **Ajouter des Délais Entre Requêtes**

**Nouveau code:**
```python
GEMINI_REQUEST_DELAY = 6  # secondes

def generate_with_gemini(system_prompt, user_prompt, ...):
    import time
    time.sleep(GEMINI_REQUEST_DELAY)  # ✅ Respecter quota minute
    genai.configure(api_key=GEMINI_API_KEY)
```

**Calcul:**
- Quota gratuit: **10 requêtes par minute**
- Délai: 6 secondes = 10 requêtes max/minute ✅

---

### 4. **⭐ SOLUTION DÉFINITIVE: Activer la Facturation (Sans Payer)**

**C'est la clé!** Vas sur [Google Cloud Console](https://console.cloud.google.com):

1. **Clique sur ton projet** → "Billing" (Facturation)
2. **Lie une carte bancaire**
3. **Active le paiement à l'usage** (pay-as-you-go)

**Résultat:**
- ✅ Quota minute: **50-100 req/min** (vs 10)
- ✅ Quota jour: **1.5 million jetons** gratuits
- ✅ **Tu ne paies que si tu dépasses** 1.5M jetons/mois
- ✅ Usage normal école = **gratuit toujours**

---

## Quotas Comparés

| Métrique | Gratuit (Sans Billing) | Gratuit (Avec Billing) |
|----------|-----|-----|
| **Requêtes/minute** | 10 | 50-100 |
| **Requêtes/jour** | 1500 | Illimité |
| **Jetons/mois gratuits** | 0 | 1.5M |
| **Coût (usage normal)** | Limité | Gratuit |
| **Cas d'usage** | Tests | Production école |

---

## Checklist Avant Production

- [ ] Une seule clé GEMINI_API_KEY dans `.env`
- [ ] Modèles fallback = UNIQUEMENT `["gemini-2.0-flash"]`
- [ ] Délai de 6 secondes activé entre requêtes
- [ ] Carte bancaire liée (même si utilisation gratuite)
- [ ] Tester avec `python test_rapport_prof.py`

---

## Test Rapide

```bash
$env:PYTHONIOENCODING = "utf-8"
python app.py

# Puis va sur http://localhost:5000
# Envoie 2-3 questions rapidement (le délai gérera les espacements)
```

**Résultat attendu:**
- ✅ Pas d'erreur 429
- ✅ Réponses Gemini OK
- ✅ Latence ~1-2 secondes/requête (délai inclus)

---

## 💡 Astuce Future

Si tu veux **davantage de capacité** pour une utilisation intensive:
- Gemini Premium: $20/mois → quota illimité
- Ou reste gratuit avec billing (1.5M jetons = ~15k questions)

---

**Document créé:** 7 juillet 2026
**Version:** 1.0
