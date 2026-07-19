#!/usr/bin/env python3
"""
eval_benchmark.py

Minimal accuracy benchmark for riddle_solver.py, per PRD Section 8
("Success Metrics") and Section 10 (calibration risk).

Runs a small curated set of riddles through the local model and checks
whether the returned answer matches (loosely, via substring match) any
of the accepted answers. This is a starting point, not a rigorous grader —
for real evaluation, review mismatches by hand, since riddle answers can
be phrased many valid ways.

Usage:
    python eval_benchmark.py --model llama3.2
"""

import argparse
from riddle_solver import solve_riddle

# A small starter benchmark. Expand this to 150-300 items per the PRD
# milestone plan before drawing real conclusions about accuracy.
BENCHMARK = [
    {
        "riddle": "The more you take, the more you leave behind. What am I?",
        "accepted": ["footsteps", "footprints"],
    },
    {
        "riddle": "What has a wick and gives light, but grows shorter as it grows older?",
        "accepted": ["candle"],
    },
    {
        "riddle": "What can you catch but not throw?",
        "accepted": ["cold", "cough", "attention", "eye"],
    },
    {
        "riddle": "I speak without a mouth and hear without ears. I have no body, "
                   "but I come alive with wind. What am I?",
        "accepted": ["echo"],
    },
    {
        "riddle": "What has keys but no locks, space but no room, and you can enter but not go in?",
        "accepted": ["keyboard"],
    },
    {
        "riddle": "The person who makes it, sells it. The person who buys it never uses it. "
                   "The person who uses it never knows they're using it. What is it?",
        "accepted": ["coffin"],
    },
    {
        "riddle": "What gets wetter as it dries?",
        "accepted": ["towel"],
    },
    {
        "riddle": "I am not alive, but I grow; I don't have lungs, but I need air; "
                   "I don't have a mouth, but water kills me. What am I?",
        "accepted": ["fire"],
    },
]


def run_benchmark(model: str, host: str):
    total = len(BENCHMARK)
    correct = 0
    results = []

    for item in BENCHMARK:
        parsed, _raw = solve_riddle(
            riddle_text=item["riddle"],
            mode="answer_with_explanation",
            model=model,
            host=host,
        )
        model_answer = (parsed.get("answer") or "").strip().lower()
        is_correct = any(acc in model_answer for acc in item["accepted"])
        correct += int(is_correct)
        results.append({
            "riddle": item["riddle"],
            "expected_any_of": item["accepted"],
            "model_answer": parsed.get("answer"),
            "confidence": parsed.get("confidence"),
            "correct": is_correct,
        })

    print(f"\nAccuracy: {correct}/{total} ({100 * correct / total:.1f}%)\n")
    for r in results:
        mark = "PASS" if r["correct"] else "FAIL"
        print(f"[{mark}] {r['riddle']}")
        print(f"       expected one of: {r['expected_any_of']}")
        print(f"       model answered:  {r['model_answer']}  (confidence: {r['confidence']})\n")

    return correct, total


def main():
    parser = argparse.ArgumentParser(description="Run the RiddleSolver benchmark against a local Ollama model.")
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--host", default="http://localhost:11434")
    args = parser.parse_args()

    run_benchmark(model=args.model, host=args.host)


if __name__ == "__main__":
    main()
