#!/usr/bin/env python3
"""
riddle_solver.py

A single-turn LLM client for solving riddles, using a local Ollama server
as the model backend (per PRD: "RiddleSolver — A Single-Turn LLM Assistant
for Riddles").

Usage:
    python riddle_solver.py "The more you take, the more you leave behind. What am I?"
    python riddle_solver.py "I speak without a mouth..." --mode guided_hint
    python riddle_solver.py "..." --model llama3.2 --json

Requires:
    - Ollama running locally (default http://localhost:11434)
    - A model pulled, e.g.: `ollama pull llama3.2`
    - pip install requests
"""

import argparse
import json
import sys
import requests


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
MAX_RETRIES = 2  # retries if the model returns malformed JSON


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = """\
Example 1
Riddle: "The more you take, the more you leave behind. What am I?"
Response:
{
  "answer": "Footsteps",
  "confidence": "High",
  "category": "wordplay",
  "is_well_known": true,
  "reasoning": [
    "The riddle plays on the double meaning of 'take' as in taking steps.",
    "Each step taken leaves a footprint behind.",
    "So the more steps you take, the more footsteps you leave."
  ],
  "alternate_answers": [],
  "notes": "Classic riddle; 'footsteps' is the widely accepted answer."
}

Example 2
Riddle: "What has a wick and gives light, but grows shorter as it grows older?"
Response:
{
  "answer": "A candle",
  "confidence": "High",
  "category": "classic_riddle",
  "is_well_known": true,
  "reasoning": [
    "The object 'grows shorter as it grows older', suggesting it diminishes with use.",
    "It has a wick and gives light, which specifically points to a candle.",
    "Combining both clues, the answer is a candle."
  ],
  "alternate_answers": [],
  "notes": "Well-known riddle; canonical answer is 'a candle'."
}

Example 3 (ambiguous case)
Riddle: "What can you catch but not throw?"
Response:
{
  "answer": "A cold",
  "confidence": "Medium",
  "category": "wordplay",
  "is_well_known": true,
  "reasoning": [
    "'Catch' has multiple meanings: physically catching an object, or 'catching' an illness.",
    "Since you cannot literally throw an illness, 'a cold' fits the wordplay.",
    "This is the most common accepted answer for this riddle."
  ],
  "alternate_answers": [
    {"answer": "A cough", "justification": "Similar wordplay logic to 'a cold', also something you 'catch'."},
    {"answer": "Someone's attention", "justification": "You can 'catch' someone's attention but not literally throw it."}
  ],
  "notes": "Multiple valid interpretations exist depending on riddle source."
}
"""

SYSTEM_PROMPT_ANSWER = f"""You are RiddleSolver, an assistant specialized in solving riddles \
presented in quizzes, games, and educational settings. You operate in a SINGLE TURN: \
you will not get a chance to ask the user a follow-up question, so you must handle \
ambiguity yourself within this one response.

Rules:
1. Reason step-by-step internally before answering, but only output the final structured result.
2. Never state a guess as certain fact if you are not confident. Use the "confidence" field honestly \
(High, Medium, or Low).
3. If the riddle is incomplete, ambiguous, or has multiple accepted answers, state your best \
interpretation and answer, then list credible alternates in "alternate_answers".
4. For well-known/classic riddles, prefer the widely-accepted canonical answer, even if a cleverer \
alternate technically fits, but note the alternate if relevant.
5. Keep "reasoning" concise: 2-5 short numbered steps, not long paragraphs.
6. Output ONLY valid JSON matching the schema below. No markdown fences, no extra commentary, \
no text before or after the JSON object.

JSON schema:
{{
  "answer": string,
  "confidence": "High" | "Medium" | "Low",
  "category": string,               // e.g. "wordplay", "math_logic", "lateral_thinking", "classic_riddle", "trick_question"
  "is_well_known": boolean,
  "reasoning": [string, ...],
  "alternate_answers": [{{"answer": string, "justification": string}}, ...],
  "notes": string
}}

Here are examples of correct responses:

{FEW_SHOT_EXAMPLES}

Now solve the user's riddle and respond with ONLY the JSON object, nothing else.
"""

SYSTEM_PROMPT_GUIDED_HINT = """You are RiddleSolver, operating in GUIDED HINT mode. You operate in a \
SINGLE TURN, so you must produce all hints now rather than waiting for the user to ask for more.

Rules:
1. Do NOT reveal the final answer.
2. Produce 2-3 hints of increasing specificity: the first should be vague/thematic, \
the last should strongly imply the answer without stating it outright.
3. Output ONLY valid JSON matching this schema, no markdown fences, no extra commentary:

{
  "category": string,
  "hints": [string, string, ...],
  "note": string   // e.g. "Final answer withheld in guided_hint mode."
}
"""


def build_messages(riddle_text: str, mode: str, difficulty_context: str | None):
    system_prompt = SYSTEM_PROMPT_GUIDED_HINT if mode == "guided_hint" else SYSTEM_PROMPT_ANSWER

    user_content = f'Riddle: "{riddle_text}"'
    if difficulty_context:
        user_content += f"\nContext for calibrating explanation depth/tone: {difficulty_context}"
    if mode == "answer_only":
        user_content += "\n(Respond with the same JSON schema, but you may leave 'reasoning' as a single short step.)"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

def call_ollama(messages, model: str, host: str, timeout: int = 60) -> str:
    """Single-turn call to a local Ollama server's chat endpoint."""
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",   # ask Ollama to constrain output to valid JSON
        "options": {
            "temperature": 0.2  # low temperature: favor consistent, well-calibrated answers
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise SystemExit(
            f"Could not connect to Ollama at {host}. "
            f"Is Ollama running? Try `ollama serve` or check the host with --host."
        )
    except requests.exceptions.HTTPError as e:
        raise SystemExit(f"Ollama returned an error: {e}\nResponse body: {resp.text}")

    data = resp.json()
    # Ollama /api/chat non-streaming response shape: {"message": {"role": ..., "content": ...}, ...}
    return data.get("message", {}).get("content", "")


def solve_riddle(riddle_text: str, mode: str, model: str, host: str,
                  difficulty_context: str | None = None):
    messages = build_messages(riddle_text, mode, difficulty_context)

    last_raw = None
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        raw = call_ollama(messages, model=model, host=host)
        last_raw = raw
        try:
            parsed = json.loads(raw)
            return parsed, raw
        except json.JSONDecodeError as e:
            last_error = e
            # Ask the model to fix its own output on retry
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "That was not valid JSON. Respond again with ONLY a valid JSON object "
                    "matching the schema, no other text."
                )},
            ]
            continue

    raise SystemExit(
        f"Model failed to return valid JSON after {MAX_RETRIES + 1} attempts.\n"
        f"Last error: {last_error}\nLast raw output:\n{last_raw}"
    )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_human_readable(parsed: dict, mode: str):
    if mode == "guided_hint":
        print(f"Category: {parsed.get('category', 'unknown')}")
        print("Hints:")
        for i, hint in enumerate(parsed.get("hints", []), start=1):
            print(f"  {i}. {hint}")
        if parsed.get("note"):
            print(f"\nNote: {parsed['note']}")
        return

    print(f"Answer:     {parsed.get('answer', '(none)')}")
    print(f"Confidence: {parsed.get('confidence', 'unknown')}")
    print(f"Category:   {parsed.get('category', 'unknown')}"
          + (" (well-known riddle)" if parsed.get("is_well_known") else ""))

    reasoning = parsed.get("reasoning", [])
    if reasoning:
        print("\nReasoning:")
        for i, step in enumerate(reasoning, start=1):
            print(f"  {i}. {step}")

    alternates = parsed.get("alternate_answers", [])
    if alternates:
        print("\nAlternate answers:")
        for alt in alternates:
            print(f"  - {alt.get('answer')}: {alt.get('justification')}")

    if parsed.get("notes"):
        print(f"\nNotes: {parsed['notes']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Solve a riddle using a local Ollama model (single-turn RiddleSolver client)."
    )
    parser.add_argument("riddle", nargs="?", help="The riddle text. If omitted, you'll be prompted.")
    parser.add_argument("--mode", choices=["answer_only", "answer_with_explanation", "guided_hint"],
                         default="answer_with_explanation", help="Response mode (default: answer_with_explanation)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Ollama server host (default: {DEFAULT_HOST})")
    parser.add_argument("--context", default=None, help="Optional difficulty/audience context, e.g. 'for a 10-year-old'")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of human-readable format")

    args = parser.parse_args()

    riddle_text = args.riddle or input("Enter a riddle: ").strip()
    if not riddle_text:
        raise SystemExit("No riddle provided.")

    parsed, raw = solve_riddle(
        riddle_text=riddle_text,
        mode=args.mode,
        model=args.model,
        host=args.host,
        difficulty_context=args.context,
    )

    if args.json:
        print(json.dumps(parsed, indent=2))
    else:
        print_human_readable(parsed, args.mode)


if __name__ == "__main__":
    main()
