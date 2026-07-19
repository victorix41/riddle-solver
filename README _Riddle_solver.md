# RiddleSolver — Local Ollama Client

A single-turn riddle-solving client implementing the RiddleSolver PRD, using
a local Ollama server as the model backend.

## Setup

1. Make sure Ollama is installed and running:
   ```bash
   ollama serve
   ```
   (On WSL2, this is typically already running as a background service after install —
   check with `curl http://localhost:11434` to confirm it responds.)

2. Pull a model if you haven't already:
   ```bash
   ollama pull llama3.2
   ```

3. Install the Python dependency:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Basic:
```bash
python riddle_solver.py "The more you take, the more you leave behind. What am I?"
```

Guided hints instead of a direct answer (useful for live quiz settings):
```bash
python riddle_solver.py "What has keys but no locks?" --mode guided_hint
```

Raw JSON output (for piping into another app/UI):
```bash
python riddle_solver.py "What gets wetter as it dries?" --json
```

Add audience/difficulty context to calibrate explanation tone:
```bash
python riddle_solver.py "What has a wick and gives light?" --context "for a 10-year-old"
```

Point at a different model or host:
```bash
python riddle_solver.py "..." --model llama3.2:1b --host http://localhost:11434
```

## Evaluating Accuracy

The PRD sets a target of ~90% accuracy on classic riddles. Small local models
(especially llama3.2:1b/3b) will likely fall short of that — run the benchmark
to see where you land, then expand `BENCHMARK` in `eval_benchmark.py` toward
the PRD's 150-300 item target:

```bash
python eval_benchmark.py --model llama3.2
```

This prints pass/fail per riddle and an overall accuracy percentage. Note the
matcher is a simple substring check — review FAILs by hand, since riddles
often have valid answers phrased differently than expected.

## FastAPI Wrapper (HTTP API)

The CLI logic is also exposed as an HTTP API in `main.py`, so it can be called
from a browser, Postman, or a Vercel-hosted frontend.

### Run locally (same laptop as Ollama)

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then test:
```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/solve \
     -H "Content-Type: application/json" \
     -d '{"riddle": "What gets wetter as it dries?"}'
```

Interactive API docs (Swagger UI) are auto-generated at:
```
http://localhost:8000/docs
```

### `/solve` request body

```json
{
  "riddle": "What gets wetter as it dries?",
  "mode": "answer_with_explanation",
  "context": "for a 10-year-old",
  "model": "llama3.2"
}
```
Only `riddle` is required. `mode` is one of `answer_only`, `answer_with_explanation`
(default), `guided_hint`.

### Environment variables

Copy `.env.example` to `.env` (or set these in Render's dashboard):

| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_HOST` | Where Ollama is reachable | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default model name | `llama3.2` |
| `ALLOWED_ORIGINS` | CORS-allowed frontend origins (comma-separated) | `*` |

### Deployment approach: local backend + Vercel frontend

This project runs the FastAPI backend **locally** (on the same laptop as
Ollama) — no Render or other backend hosting needed. Only the frontend
(a static HTML/JS page in `../riddle_solver_frontend/index.html`) is deployed
to Vercel.

**Why this works:** when a browser loads the Vercel-hosted frontend, its
`fetch()` calls run *in that browser*, not on Vercel's servers. So if you
(the person running Ollama + FastAPI locally) are the one viewing the page,
`fetch("http://localhost:8000/solve")` reaches your own laptop correctly.

**The catch:** this only works for the person whose laptop is running the
backend. If someone else opens your Vercel link on their own machine, their
`localhost:8000` has nothing running, so the request will fail. That's fine
for a live demo you're driving yourself; if you eventually need it to work
for other viewers, you'd need to tunnel your local backend out (e.g. ngrok)
and set the frontend's "API host" field to that tunnel URL instead of
`localhost:8000`.

### CORS setup

Since the frontend is served from a `vercel.app` URL (not `localhost`), set
`ALLOWED_ORIGINS` to include that origin before relying on this outside of
local testing:

```bash
# in your local .env, or wherever you run uvicorn from
ALLOWED_ORIGINS=https://your-app.vercel.app
```

`*` (the default) works fine while testing locally, since the browser and
API are both on `localhost` during local dev — but tighten it once you have
your real Vercel URL.

### Running the full local + Vercel setup

1. Start the backend locally as usual:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
2. Deploy `../riddle_solver_frontend/index.html` to Vercel (see that folder's
   own instructions).
3. Open your Vercel URL in your browser. In the "API host" field at the top
   of the page, confirm it says `http://localhost:8000` (this is prefilled by
   default). Type a riddle and click "Solve Riddle."

## Notes / Known Limitations

- Ollama's `format: "json"` setting constrains output to valid JSON syntax,
  but doesn't guarantee it matches your exact schema — `riddle_solver.py`
  retries (up to 2x) if parsing fails or asks the model to self-correct.
- Small local models are noticeably weaker than large hosted models at
  wordplay/lateral-thinking riddles. Expect more `Medium`/`Low` confidence
  answers and more benchmark FAILs than you'd see with a frontier model.
- `guided_hint` mode is best-effort: nothing stops the model from leaking
  the answer in a hint. If this matters for your use case (e.g. a live game
  where hints are shown before a reveal), spot-check outputs before trusting
  the withholding behavior fully.
