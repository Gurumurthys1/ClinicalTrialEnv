"""
Baseline Inference Script — ClinicalTrialEnv

Runs an LLM against all 3 tasks of the clinical_trial_env environment.

Supports TWO backends (auto-detected):
  1. HuggingFace Inference API (FREE, default) — uses HF_TOKEN env var
  2. OpenAI API — uses OPENAI_API_KEY env var

Recommended HuggingFace models (free tier):
  - mistralai/Mistral-7B-Instruct-v0.3   (best for structured reasoning)
  - meta-llama/Meta-Llama-3.1-8B-Instruct
  - HuggingFaceH4/zephyr-7b-beta

Usage:
    # HuggingFace (FREE — recommended):
    export HF_TOKEN=hf_...
    python baseline_inference.py

    # OpenAI:
    export OPENAI_API_KEY=sk-...
    python baseline_inference.py
"""

import os
import re
import json
import requests

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("BASE_URL", "http://localhost:7860")
TASK_IDS = ["easy", "medium", "hard"]

# Auto-detect backend
HF_TOKEN = os.environ.get("HF_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# HuggingFace config
HF_MODEL = os.environ.get("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
HF_PROVIDER = os.environ.get("HF_PROVIDER", "novita")

# OpenAI config
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def get_backend():
    """Auto-detect which LLM backend to use."""
    if HF_TOKEN:
        return "HuggingFace", HF_MODEL
    elif OPENAI_API_KEY:
        return "OpenAI", OPENAI_MODEL
    else:
        return None, None


def call_llm(system_prompt: str, user_prompt: str, backend: str, model: str) -> str:
    """Call the LLM and return the raw text response."""
    if backend == "HuggingFace":
        from huggingface_hub import InferenceClient
        client = InferenceClient(provider=HF_PROVIDER, api_key=HF_TOKEN)
        response = client.chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1024,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    else:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1024,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()


# ── Environment API helpers ───────────────────────────────────────────────────

def reset_episode(task_id: str) -> dict:
    resp = requests.post(f"{BASE_URL}/api/reset", json={"task_id": task_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def step_episode(session_id: str, task_id: str, findings: list, explanation: str = "") -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/step",
        json={"session_id": session_id, "task_id": task_id, "findings": findings, "explanation": explanation},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(obs: dict) -> str:
    task_id = obs.get("task_id", "unknown")
    description = obs.get("task_description", "")
    records = json.dumps(obs.get("patient_records", []), indent=2)
    rules = "\n".join(f"- {r}" for r in obs.get("protocol_rules", []))
    audit = "\n".join(f"- {l}" for l in obs.get("audit_logs", []))

    prompt = f"""You are a clinical trial data validator. Your task: {task_id.upper()}

Task Description:
{description}

Protocol Rules:
{rules}

Patient Records:
{records}
"""
    if audit:
        prompt += f"\nAudit Trail Logs:\n{audit}\n"

    prompt += """
Instructions:
Analyze the data carefully and identify ALL errors, violations, or anomalies.
Return your response as a JSON object with two fields:
  "findings": a list of strings, each describing one specific error found
  "explanation": a brief overall summary of your analysis

Important: Include the Patient ID (e.g. P001, P034) in each finding.
For missing fields, mention which field is missing.
For protocol violations, mention the specific violation.
For audit anomalies, mention what was modified and when.

Example format:
{
  "findings": [
    "Missing Age for P001",
    "Protocol violation: P034 received dose on Day 19 (allowed window Day 12-16)"
  ],
  "explanation": "Found 2 errors in the clinical trial data."
}

Respond ONLY with valid JSON. No markdown, no code blocks, no extra text.
"""
    return prompt


# ── Run one task ──────────────────────────────────────────────────────────────

def run_task(backend: str, model: str, task_id: str) -> float:
    print(f"\n{'='*60}")
    print(f"  Running task: {task_id.upper()}")
    print(f"{'='*60}")

    # Reset
    reset_data = reset_episode(task_id)
    session_id = reset_data.get("session_id", "")
    obs = reset_data.get("observation", reset_data)
    print(f"  Session ID: {session_id}")
    print(f"  Expected errors to find: {obs.get('expected_finding_count', '?')}")

    # Build prompt and call LLM
    prompt = build_prompt(obs)
    print(f"  Calling {model}...")

    system_prompt = (
        "You are an expert clinical trial data auditor. "
        "You must analyze patient records and find all errors. "
        "Always respond with valid JSON only. No markdown."
    )

    try:
        raw = call_llm(system_prompt, prompt, backend, model)
    except Exception as e:
        print(f"  ERROR calling LLM: {e}")
        raw = '{"findings": [], "explanation": "LLM call failed"}'

    # Parse JSON response — robust multi-stage parser
    cleaned = raw
    # Stage 1: Strip markdown code blocks
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    findings = []
    explanation = ""

    # Stage 2: Try direct JSON parse
    try:
        parsed = json.loads(cleaned)
        findings = parsed.get("findings", [])
        explanation = parsed.get("explanation", "")
    except json.JSONDecodeError:
        # Stage 3: Try to extract JSON block between first { and last }
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            json_block = cleaned[brace_start:brace_end + 1]
            try:
                parsed = json.loads(json_block)
                findings = parsed.get("findings", [])
                explanation = parsed.get("explanation", "")
            except json.JSONDecodeError:
                pass

        # Stage 4: If still no findings, extract quoted strings as findings
        if not findings:
            print(f"  WARNING: LLM returned non-JSON. Extracting findings from text...")
            # Find all quoted strings that look like findings
            quoted = re.findall(r'"([^"]{10,})"', raw)
            findings = [q for q in quoted if any(kw in q.lower() for kw in
                        ["missing", "violation", "error", "invalid", "p0", "p03", "p04",
                         "p05", "p06", "p01", "p02", "p016", "p022", "dose", "age",
                         "enroll", "audit", "lock", "inconsist", "temporal"])]
            if not findings:
                # Last resort: use non-empty lines
                lines = [l.strip() for l in raw.split("\n")
                         if l.strip() and not l.strip().startswith(("{", "}", "[", "]", "\"findings", "\"explanation"))]
                findings = lines[:10] if lines else []
            explanation = "Extracted from malformed LLM output"

    print(f"  Agent findings ({len(findings)}):")
    for f in findings:
        print(f"    - {f}")

    # Step — submit findings for grading
    step_data = step_episode(session_id, task_id, findings, explanation)
    reward = step_data.get("reward", 0.0)
    message = step_data.get("observation", {}).get("message", step_data.get("message", ""))

    print(f"  Score: {reward:.4f}")
    print(f"  Feedback: {message}")

    return reward


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║   ClinicalTrialEnv — Baseline Inference Script       ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Server: {BASE_URL}")

    backend, model = get_backend()

    if backend is None:
        print("\n  ⚠ ERROR: No API key found. Set one of these environment variables:")
        print("    export HF_TOKEN=hf_...       (HuggingFace — FREE, recommended)")
        print("    export OPENAI_API_KEY=sk-...  (OpenAI)")
        print()
        print("  To get a free HuggingFace token:")
        print("    1. Go to https://huggingface.co/settings/tokens")
        print("    2. Create a Fine-grained token with Inference permissions")
        print("    3. Set it: export HF_TOKEN=hf_your_token_here")
        return

    print(f"  Backend: {backend}")
    print(f"  Model:   {model}")

    scores = {}
    for task_id in TASK_IDS:
        try:
            score = run_task(backend, model, task_id)
            scores[task_id] = score
        except Exception as e:
            print(f"  ERROR running task '{task_id}': {e}")
            scores[task_id] = 0.0

    # Summary
    print(f"\n{'='*60}")
    print("  BASELINE RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Model: {model} ({backend})")
    print()
    for task_id, score in scores.items():
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        print(f"  {task_id.upper():8s}  [{bar}] {score:.4f}")
    avg = sum(scores.values()) / len(scores) if scores else 0.0
    print(f"\n  Average score: {avg:.4f}")
    print(f"{'='*60}\n")

    # Machine-readable output
    print(json.dumps({
        "model": model,
        "backend": backend,
        "baseline_scores": scores,
        "average": avg,
    }, indent=2))


if __name__ == "__main__":
    main()
