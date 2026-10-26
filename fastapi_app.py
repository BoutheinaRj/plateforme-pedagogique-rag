"""FastAPI layer for Astro KB RAG service.

This module reuses the existing retrieval/generation core from app.py
and exposes production-style JSON endpoints with OpenAPI docs.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import app as rag


app = FastAPI(
    title="Pedagogical Knowledge Base API",
    version="1.0.0",
    description="FastAPI facade for retrieval and grounded answer generation.",
)

PROJECT_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    grade: Optional[int] = None
    language: Optional[str] = None
    subject: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=50)
    mode: str = Field(default="hybrid")


class ChatTurn(BaseModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    grade: Optional[int] = None
    language: str = Field(default="auto")
    subject: Optional[str] = None
    age: Optional[int] = None
    conversation: List[ChatTurn] = Field(default_factory=list)


@app.get("/", response_class=HTMLResponse)
def root(request: Request) -> HTMLResponse:
    active_kb = rag.RETRIEVAL_KB
    stats = {
        "total_chunks": len(active_kb),
        "grades": sorted(set(c.get("grade") for c in active_kb if c.get("grade"))),
        "subjects": sorted(set(c.get("subject") for c in active_kb if c.get("subject"))),
        "languages": sorted(set(c.get("language") for c in active_kb if c.get("language"))),
        "sources": sorted(set(c.get("source_type") for c in active_kb if c.get("source_type"))),
    }
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats})


@app.get("/api")
def api_root() -> Dict[str, Any]:
    return {
        "service": "fastapi-rag",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "kb_loaded": len(rag.RETRIEVAL_KB) > 0,
        "chunks_count": len(rag.RETRIEVAL_KB),
        "chunks_clean": len(rag.KB_CLEAN),
        "chunks_all": len(rag.KB_ALL),
        "retrieval_quality": rag.DEFAULT_RETRIEVAL_QUALITY,
    }


@app.get("/api/stats")
def stats(quality: str = Query(default=rag.DEFAULT_RETRIEVAL_QUALITY)) -> Dict[str, Any]:
    selected_kb, selected_quality = rag.resolve_kb_scope(quality)
    if not selected_kb:
        raise HTTPException(status_code=404, detail="No KB loaded")

    selected_stats = rag.summarize_kb(selected_kb)
    clean_stats = rag.summarize_kb(rag.KB_CLEAN)
    all_stats = rag.summarize_kb(rag.KB_ALL)

    return {
        "quality": selected_quality,
        "total_chunks": selected_stats["total_chunks"],
        "by_grade": selected_stats["by_grade"],
        "by_subject": selected_stats["by_subject"],
        "by_language": selected_stats["by_language"],
        "totals": {
            "clean": clean_stats["total_chunks"],
            "all": all_stats["total_chunks"],
            "retrieval": len(rag.RETRIEVAL_KB),
        },
    }


@app.post("/api/search")
def search(payload: SearchRequest) -> Dict[str, Any]:
    query = payload.query.strip().lower()
    if not query:
        raise HTTPException(status_code=400, detail="Query required")

    filters = rag.build_filters(
        grade=payload.grade,
        language=payload.language,
        subject=payload.subject,
    )

    results: List[Dict[str, Any]] = []

    if payload.mode in ["semantic", "hybrid"]:
        semantic_results = rag.SEARCH_ENGINE.search_semantic(
            query,
            top_k=max(payload.limit * 5, 20),
            filters=filters,
        )
        for chunk, score in semantic_results:
            results.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "grade": chunk.get("grade"),
                    "subject": chunk.get("subject"),
                    "language": chunk.get("language"),
                    "source_type": chunk.get("source_type"),
                    "source_file": chunk.get("source_file"),
                    "text": chunk.get("text", "")[:200] + "...",
                    "full_text": chunk.get("text"),
                    "score": float(score),
                    "mode": "hybrid" if payload.mode == "hybrid" else "semantic",
                }
            )

    if payload.mode in ["keyword", "hybrid"] and (not results or payload.mode == "keyword"):
        for chunk, score in rag.keyword_search(query, filters=filters, limit=payload.limit * 2):
            results.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "grade": chunk.get("grade"),
                    "subject": chunk.get("subject"),
                    "language": chunk.get("language"),
                    "source_type": chunk.get("source_type"),
                    "source_file": chunk.get("source_file"),
                    "text": chunk.get("text", "")[:200] + "...",
                    "full_text": chunk.get("text"),
                    "score": float(score),
                    "mode": "keyword",
                }
            )

    seen = set()
    unique_results = []
    for item in results:
        chunk_id = item.get("chunk_id")
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        unique_results.append(item)

    unique_results = unique_results[: payload.limit]

    return {
        "query": query,
        "results_count": len(unique_results),
        "results": unique_results,
        "search_mode": payload.mode if results else "keyword (semantic unavailable)",
    }


@app.get("/api/chunks")
def chunks(
    quality: str = Query(default=rag.DEFAULT_RETRIEVAL_QUALITY),
    grade: Optional[int] = None,
    subject: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=200),
) -> Dict[str, Any]:
    selected_kb, selected_quality = rag.resolve_kb_scope(quality)
    filtered = []

    for chunk in selected_kb:
        if grade and chunk.get("grade") != grade:
            continue
        if subject and chunk.get("subject") != subject:
            continue
        if language and chunk.get("language") != language:
            continue

        filtered.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "grade": chunk.get("grade"),
                "subject": chunk.get("subject"),
                "language": chunk.get("language"),
                "text": chunk.get("text", "")[:300] + "...",
            }
        )

    return {
        "quality": selected_quality,
        "total": len(filtered),
        "chunks": filtered[:limit],
    }


@app.get("/api/chunk/{chunk_id}")
def chunk_detail(chunk_id: str) -> Dict[str, Any]:
    for chunk in rag.KB_ALL:
        if chunk.get("chunk_id") == chunk_id:
            return chunk
    raise HTTPException(status_code=404, detail="Chunk not found")


@app.get("/api/program")
def program(quality: str = Query(default=rag.DEFAULT_RETRIEVAL_QUALITY)) -> Dict[str, Any]:
    selected_kb, _ = rag.resolve_kb_scope(quality)
    program_data: Dict[str, Dict[str, Any]] = {}

    for chunk in selected_kb:
        grade = chunk.get("grade")
        if grade is None:
            continue

        subject = chunk.get("subject", "Unknown")
        language = chunk.get("language", "Unknown")
        grade_key = str(grade)
        if grade_key not in program_data:
            program_data[grade_key] = {
                "subjects": set(),
                "languages": set(),
                "chunk_count": 0,
            }

        program_data[grade_key]["subjects"].add(subject)
        program_data[grade_key]["languages"].add(language)
        program_data[grade_key]["chunk_count"] += 1

    result = {}
    for grade in sorted(program_data.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        result[grade] = {
            "subjects": sorted(list(program_data[grade]["subjects"])),
            "languages": sorted(list(program_data[grade]["languages"])),
            "chunk_count": program_data[grade]["chunk_count"],
        }

    return result


@app.get("/api/progression/{grade}")
def progression(
    grade: int,
    quality: str = Query(default=rag.DEFAULT_RETRIEVAL_QUALITY),
) -> Dict[str, Any]:
    selected_kb, _ = rag.resolve_kb_scope(quality)
    grade_chunks = [c for c in selected_kb if c.get("grade") == grade]

    by_subject: Dict[str, List[Dict[str, Any]]] = {}
    for chunk in grade_chunks:
        subject = chunk.get("subject", "Unknown")
        by_subject.setdefault(subject, [])
        by_subject[subject].append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "subject": subject,
                "language": chunk.get("language"),
                "text": chunk.get("text", "")[:200] + "..."
                if len(chunk.get("text", "")) > 200
                else chunk.get("text", ""),
                "source_file": chunk.get("source_file"),
            }
        )

    return {
        "grade": grade,
        "total_chunks": len(grade_chunks),
        "by_subject": by_subject,
    }


@app.get("/api/subject-program/{grade}/{subject}")
def subject_program(
    grade: int,
    subject: str,
    quality: str = Query(default=rag.DEFAULT_RETRIEVAL_QUALITY),
) -> Dict[str, Any]:
    selected_kb, _ = rag.resolve_kb_scope(quality)
    filtered = [c for c in selected_kb if c.get("grade") == grade and c.get("subject") == subject]
    filtered.sort(key=lambda x: (x.get("source_file", ""), x.get("chunk_index", 0)))

    result = []
    for chunk in filtered:
        result.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "file": chunk.get("source_file"),
                "index": f"{chunk.get('chunk_index', 0)}/{chunk.get('total_chunks', 1)}",
                "language": chunk.get("language"),
                "text": chunk.get("text", ""),
            }
        )

    return {
        "grade": grade,
        "subject": subject,
        "total": len(result),
        "chunks": result,
    }


@app.post("/api/answer")
def answer(payload: AnswerRequest) -> Dict[str, Any]:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question required")

    conversation_history = [
        {"role": turn.role, "content": turn.content}
        for turn in (payload.conversation or [])
        if turn.role and turn.content
    ]

    resolved_language = rag.detect_language(question) if payload.language == "auto" else payload.language
    pedagogical_mode = rag.detect_pedagogical_mode(question)
    is_edu_question = rag.is_education_question(
        question,
        subject=payload.subject,
        grade=payload.grade,
        age=payload.age,
    )

    if not is_edu_question:
        general = rag.generate_general_answer(
            question,
            resolved_language,
            grade=payload.grade,
            conversation_history=conversation_history,
        )
        return {
            "question": question,
            "answer": general["answer"],
            "sources": [],
            "mode": general["mode"],
            "role": "general_child",
            "retrieval_mode": "general_llm",
            "pedagogical_mode": pedagogical_mode,
            "grade": payload.grade,
            "language": resolved_language,
            "subject": payload.subject,
            "prompt_preview": general["prompt_preview"],
            "openai_configured": bool(rag.OPENAI_AVAILABLE and rag.OPENAI_API_KEY),
            "gemini_configured": bool(rag.GEMINI_AVAILABLE and rag.GEMINI_API_KEY),
        }

    filters = rag.build_filters(
        grade=payload.grade,
        language=resolved_language,
        subject=payload.subject,
        age=payload.age,
    )

    if pedagogical_mode == "course_extract":
        extracted = rag.build_pdf_course_extract_answer(
            question,
            resolved_language,
            filters=filters,
            subject=payload.subject,
        )
        if extracted["success"]:
            return {
                "question": question,
                "answer": extracted["answer"],
                "sources": extracted["sources"],
                "mode": extracted["mode"],
                "role": "educational_program",
                "retrieval_mode": extracted["retrieval_mode"],
                "pedagogical_mode": pedagogical_mode,
                "grade": filters.get("grade"),
                "language": resolved_language,
                "subject": payload.subject,
                "prompt_preview": None,
                "llm_error": None,
                "openai_configured": bool(rag.OPENAI_AVAILABLE and rag.OPENAI_API_KEY),
                "gemini_configured": bool(rag.GEMINI_AVAILABLE and rag.GEMINI_API_KEY),
                "grade_alignment": {
                    "is_advanced": False,
                    "required_grade": None,
                    "topic": None,
                    "message": None,
                },
            }

        no_result = rag.generate_educational_fallback_answer(
            question,
            resolved_language,
            grade=filters.get("grade"),
            subject=payload.subject,
            conversation_history=conversation_history,
        )
        return {
            "question": question,
            "answer": no_result["answer"],
            "sources": [],
            "mode": no_result["mode"],
            "role": "educational_program",
            "retrieval_mode": extracted.get("retrieval_mode", "keyword_mmr"),
            "pedagogical_mode": pedagogical_mode,
            "grade": filters.get("grade"),
            "language": resolved_language,
            "subject": payload.subject,
            "prompt_preview": no_result.get("prompt_preview"),
            "llm_error": no_result.get("llm_error"),
            "grade_alignment": {
                "is_advanced": False,
                "required_grade": None,
                "topic": None,
                "message": None,
            },
        }

    alignment = rag.assess_grade_alignment(question, payload.grade)
    if alignment["is_advanced"]:
        no_result = rag.generate_educational_fallback_answer(
            question,
            resolved_language,
            grade=payload.grade,
            subject=payload.subject,
            level_note=alignment["message"],
            conversation_history=conversation_history,
        )
        return {
            "question": question,
            "answer": no_result["answer"],
            "sources": [],
            "mode": "grade_scope_fallback",
            "role": "educational_program",
            "retrieval_mode": "grade_guard",
            "pedagogical_mode": pedagogical_mode,
            "grade": payload.grade,
            "language": resolved_language,
            "subject": payload.subject,
            "prompt_preview": no_result.get("prompt_preview"),
            "llm_error": no_result.get("llm_error"),
            "grade_alignment": alignment,
        }

    results, retrieval_mode = rag.retrieve_relevant_chunks(question, filters=filters, limit=3)

    if not results:
        no_result = rag.generate_educational_fallback_answer(
            question,
            resolved_language,
            grade=filters.get("grade"),
            subject=payload.subject,
            conversation_history=conversation_history,
        )
        return {
            "question": question,
            "answer": no_result["answer"],
            "sources": [],
            "mode": no_result["mode"],
            "role": "educational_program",
            "retrieval_mode": retrieval_mode,
            "pedagogical_mode": pedagogical_mode,
            "grade": filters.get("grade"),
            "language": resolved_language,
            "subject": payload.subject,
            "prompt_preview": no_result.get("prompt_preview"),
            "llm_error": no_result.get("llm_error"),
            "grade_alignment": alignment,
        }

    source_chunks = []
    for chunk, score in results:
        source_chunks.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "source_file": chunk.get("source_file"),
                "source_type": chunk.get("source_type"),
                "grade": chunk.get("grade"),
                "subject": chunk.get("subject"),
                "language": chunk.get("language"),
                "score": float(score),
                "text": chunk.get("text", "")[:400],
            }
        )

    generated = rag.generate_grounded_answer(
        question,
        [chunk for chunk, _ in results],
        resolved_language,
        grade=filters.get("grade"),
        conversation_history=conversation_history,
    )

    return {
        "question": question,
        "answer": generated["answer"],
        "sources": source_chunks,
        "mode": generated["mode"],
        "role": "educational_program",
        "retrieval_mode": retrieval_mode,
        "pedagogical_mode": pedagogical_mode,
        "grade": filters.get("grade"),
        "language": resolved_language,
        "subject": payload.subject,
        "prompt_preview": generated["prompt_preview"],
        "openai_configured": bool(rag.OPENAI_AVAILABLE and rag.OPENAI_API_KEY),
        "gemini_configured": bool(rag.GEMINI_AVAILABLE and rag.GEMINI_API_KEY),
        "grade_alignment": alignment,
    }
