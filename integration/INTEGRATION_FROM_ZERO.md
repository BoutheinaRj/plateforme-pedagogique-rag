# Integration From Zero (API /api/answer)

This folder gives you ready clients to connect another project to this API.

## 1) Start the API server

From project root:

```powershell
c:/Users/LENOVO/OneDrive/Desktop/astro_kb_pipeline/.venv/Scripts/python.exe -m uvicorn fastapi_app:app --host 127.0.0.1 --port 8000
```

Check health:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/health"
```

## 2) Python client (no external package)

Run:

```powershell
c:/Users/LENOVO/OneDrive/Desktop/astro_kb_pipeline/.venv/Scripts/python.exe integration/python_api_client.py --question "Comment conjuguer avoir au present ?" --grade 3 --language fr --subject francais --age 8
```

Use from another Python project:

```python
from integration.python_api_client import ask_api, build_payload

payload = build_payload(
    question="Comment conjuguer avoir au present ?",
    grade=3,
    language="fr",
    subject="francais",
    age=8,
)

result = ask_api("http://127.0.0.1:8000", payload)
print(result["answer"])
```

## 3) Node client (uses native fetch)

Run:

```powershell
node integration/node_api_client.mjs --question "Comment conjuguer avoir au present ?" --grade 3 --language fr --subject francais --age 8
```

Use from another Node project:

```js
const payload = {
  question: "Comment conjuguer avoir au present ?",
  grade: 3,
  language: "fr",
  subject: "francais",
  age: 8,
  conversation: [],
};

const response = await fetch("http://127.0.0.1:8000/api/answer", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload),
});

const data = await response.json();
console.log(data.answer);
```

## 4) Response fields to consume in your main project

- `answer`: final generated response.
- `sources`: retrieved chunks used by RAG.
- `mode`: generator mode (example: `gemini_rag`).
- `retrieval_mode`: retrieval strategy used.
- `grade_alignment`: grade-level guard output.

## 5) Recommended production hardening

- Add API auth (API key or JWT).
- Add route versioning (`/api/v1/answer`).
- Add retries/timeouts in the caller.
- Log a request id for traceability.
