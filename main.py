#!/usr/bin/env python3
"""
main.py

FastAPI wrapper around riddle_solver.py, turning the single-turn RiddleSolver
client into a proper HTTP client-server app.

Local dev:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Then test with:
    curl http://localhost:8000/health
    curl -X POST http://localhost:8000/solve \
         -H "Content-Type: application/json" \
         -d '{"riddle": "What gets wetter as it dries?"}'

Environment variables:
    OLLAMA_HOST   - where Ollama is reachable (default: http://localhost:11434)
    OLLAMA_MODEL  - default model name (default: llama3.2)
    ALLOWED_ORIGINS - comma-separated list of allowed CORS origins
                      (default: "*", tighten this before deploying publicly)
"""

import os
from typing import Optional, List, Literal

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from riddle_solver import solve_riddle

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app = FastAPI(
    title="RiddleSolver API",
    description="Single-turn riddle-solving API backed by a local/remote Ollama model.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # e.g. ["https://your-app.vercel.app"] in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class SolveRequest(BaseModel):
    riddle: str = Field(..., min_length=1, description="The riddle text to solve.")
    mode: Literal["answer_only", "answer_with_explanation", "guided_hint"] = "answer_with_explanation"
    context: Optional[str] = Field(None, description="Audience/difficulty context, e.g. 'for a 10-year-old'.")
    model: Optional[str] = Field(None, description="Override the default Ollama model for this request.")


class AlternateAnswer(BaseModel):
    answer: str
    justification: str


class SolveResponse(BaseModel):
    answer: Optional[str] = None
    confidence: Optional[str] = None
    category: Optional[str] = None
    is_well_known: Optional[bool] = None
    reasoning: Optional[List[str]] = None
    alternate_answers: Optional[List[AlternateAnswer]] = None
    notes: Optional[str] = None
    # guided_hint mode fields
    hints: Optional[List[str]] = None
    note: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    ollama_host: str
    model: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    """Checks the API itself is up, and separately whether Ollama is reachable."""
    ollama_ok = False
    try:
        r = requests.get(OLLAMA_HOST, timeout=3)
        ollama_ok = r.status_code == 200
    except requests.exceptions.RequestException:
        ollama_ok = False

    return HealthResponse(
        status="ok",
        ollama_reachable=ollama_ok,
        ollama_host=OLLAMA_HOST,
        model=OLLAMA_MODEL,
    )


@app.post("/solve", response_model=SolveResponse)
def solve(req: SolveRequest):
    """Solve a riddle in a single turn. See PRD for schema/behavior details."""
    try:
        parsed, _raw = solve_riddle(
            riddle_text=req.riddle,
            mode=req.mode,
            model=req.model or OLLAMA_MODEL,
            host=OLLAMA_HOST,
            difficulty_context=req.context,
        )
    except SystemExit as e:
        # solve_riddle raises SystemExit on connection failure or JSON-parse failure
        # in the CLI version; convert that to a proper HTTP error here.
        raise HTTPException(status_code=502, detail=str(e))

    return SolveResponse(**parsed)


@app.get("/")
def root():
    return {
        "name": "RiddleSolver API",
        "endpoints": {
            "GET /health": "Check API and Ollama connectivity",
            "POST /solve": "Solve a riddle (body: {riddle, mode, context, model})",
        },
    }
