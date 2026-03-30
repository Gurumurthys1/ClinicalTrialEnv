"""
FastAPI application for ClinicalTrialEnvironment.

Custom routes (not using create_fastapi_app) because the local openenv module
has hardcoded WordGameAction. This app creates its own /api/reset, /api/step,
/api/state endpoints plus the required hackathon endpoints:
  GET  /tasks     → list of tasks and action schemas
  POST /grader    → return grader score for a completed episode
  POST /baseline  → trigger the baseline inference script and return scores
"""

import os
import io
import csv
import sys
import uuid
import subprocess
from typing import List, Optional

from fastapi import FastAPI, Body, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

from .environment import ClinicalTrialEnvironment
from ..models import ClinicalTrialAction
from .data import TASKS, PROTOCOL_RULES, EASY_REQUIRED_FIELDS
from .graders import GRADER_MAP

# ── Custom protocol storage (in-memory, overlays defaults) ────────────────────
custom_protocols = {
    "easy": list(EASY_REQUIRED_FIELDS),
    "medium": list(PROTOCOL_RULES),
    "hard": [
        "Patient age must be 18 or older at enrollment.",
        "First dose date must be on or after enrollment date.",
        "No records may be modified after dataset lock.",
    ],
}

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="ClinicalTrialEnv",
    description="LLM-Powered Clinical Trial Data Validator — OpenEnv Environment",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session storage ───────────────────────────────────────────────────────────
sessions = {}

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "healthy"}


# ── OpenEnv core API ──────────────────────────────────────────────────────────

@app.post("/api/reset")
def reset(
    session_id: Optional[str] = Body(None),
    task_id: str = Body("easy"),
):
    """Start a new episode. Optionally specify task_id: easy | medium | hard."""
    if not session_id:
        session_id = str(uuid.uuid4())
    env = ClinicalTrialEnvironment()
    obs = env.reset(episode_id=session_id, task_id=task_id)
    sessions[session_id] = env
    return {
        "session_id": session_id,
        "observation": obs.dict(),
        "done": obs.done,
        "reward": obs.reward,
    }


@app.post("/api/step")
def step(
    session_id: str = Body(...),
    task_id: str = Body("easy"),
    findings: List[str] = Body([]),
    explanation: str = Body(""),
):
    """Submit agent findings for grading."""
    env = sessions.get(session_id)
    if not env:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid session_id: {session_id}. Call /api/reset first."},
        )
    action = ClinicalTrialAction(
        task_id=task_id,
        findings=findings,
        explanation=explanation,
    )
    obs = env.step(action)
    return {
        "session_id": session_id,
        "observation": obs.dict(),
        "done": obs.done,
        "reward": obs.reward,
    }


@app.get("/api/state")
def get_state(session_id: str):
    """Get current state of an episode."""
    env = sessions.get(session_id)
    if not env:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid session_id: {session_id}"},
        )
    return env.state.dict()


# ── Static UI ─────────────────────────────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return RedirectResponse(url="/static/index.html")


# ── /tasks ────────────────────────────────────────────────────────────────────
@app.get("/tasks")
def list_tasks():
    """Return all tasks with their action schemas."""
    return JSONResponse(content={"tasks": TASKS})


# ── /grader ───────────────────────────────────────────────────────────────────
class GraderRequest(BaseModel):
    task_id: str
    findings: List[str]


@app.post("/grader")
def run_grader(req: GraderRequest):
    """Run the grader for a specific task given a list of findings."""
    if req.task_id not in GRADER_MAP:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown task_id '{req.task_id}'. Valid: easy, medium, hard"},
        )
    score = GRADER_MAP[req.task_id](req.findings)
    return JSONResponse(content={
        "task_id": req.task_id,
        "score": score,
        "findings_submitted": req.findings,
        "note": "Score range: 0.0 (no errors found) to 1.0 (all errors found)",
    })


# ── /baseline ─────────────────────────────────────────────────────────────────
@app.post("/baseline")
def run_baseline():
    """Trigger the baseline inference script and return its scores."""
    script = os.path.join(os.path.dirname(__file__), "..", "baseline_inference.py")
    script = os.path.abspath(script)

    if not os.path.exists(script):
        return JSONResponse(
            status_code=404,
            content={"error": "baseline_inference.py not found"},
        )

    api_key = os.environ.get("OPENAI_API_KEY", "")
    env = {**os.environ, "OPENAI_API_KEY": api_key}

    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        output = result.stdout + result.stderr
        return JSONResponse(content={
            "status": "completed" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "output": output,
        })
    except subprocess.TimeoutExpired:
        return JSONResponse(
            status_code=504,
            content={"error": "Baseline script timed out after 120 seconds"},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


# ── /api/protocols — Protocol Rule CRUD ───────────────────────────────────────

class AddProtocolRequest(BaseModel):
    task_id: str
    rule: str


class UpdateProtocolRequest(BaseModel):
    task_id: str
    index: int
    rule: str


class DeleteProtocolRequest(BaseModel):
    task_id: str
    index: int


@app.get("/api/protocols")
def get_protocols(task_id: str = "easy"):
    """Get all protocol rules for a task."""
    if task_id not in custom_protocols:
        return JSONResponse(status_code=400, content={"error": f"Unknown task_id: {task_id}"})
    return JSONResponse(content={
        "task_id": task_id,
        "protocols": custom_protocols[task_id],
    })


@app.post("/api/protocols")
def add_protocol(req: AddProtocolRequest):
    """Add a new protocol rule to a task."""
    if req.task_id not in custom_protocols:
        return JSONResponse(status_code=400, content={"error": f"Unknown task_id: {req.task_id}"})
    if not req.rule.strip():
        return JSONResponse(status_code=400, content={"error": "Rule cannot be empty"})
    custom_protocols[req.task_id].append(req.rule.strip())
    return JSONResponse(content={
        "message": "Protocol rule added successfully",
        "task_id": req.task_id,
        "protocols": custom_protocols[req.task_id],
    })


@app.put("/api/protocols")
def update_protocol(req: UpdateProtocolRequest):
    """Update an existing protocol rule by index."""
    if req.task_id not in custom_protocols:
        return JSONResponse(status_code=400, content={"error": f"Unknown task_id: {req.task_id}"})
    rules = custom_protocols[req.task_id]
    if req.index < 0 or req.index >= len(rules):
        return JSONResponse(status_code=400, content={"error": f"Index {req.index} out of range (0–{len(rules)-1})"})
    if not req.rule.strip():
        return JSONResponse(status_code=400, content={"error": "Rule cannot be empty"})
    old_rule = rules[req.index]
    rules[req.index] = req.rule.strip()
    return JSONResponse(content={
        "message": f"Rule #{req.index} updated",
        "old_rule": old_rule,
        "new_rule": req.rule.strip(),
        "protocols": rules,
    })


@app.delete("/api/protocols")
def delete_protocol(req: DeleteProtocolRequest):
    """Delete a protocol rule by index."""
    if req.task_id not in custom_protocols:
        return JSONResponse(status_code=400, content={"error": f"Unknown task_id: {req.task_id}"})
    rules = custom_protocols[req.task_id]
    if req.index < 0 or req.index >= len(rules):
        return JSONResponse(status_code=400, content={"error": f"Index {req.index} out of range (0–{len(rules)-1})"})
    removed = rules.pop(req.index)
    return JSONResponse(content={
        "message": f"Rule deleted: {removed}",
        "protocols": rules,
    })


# ── /api/extract-rules — LLM Protocol Extraction ──────────────────────────────
import json
import io
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
try:
    import docx
except ImportError:
    docx = None

from huggingface_hub import InferenceClient
from fastapi import File, UploadFile, Form, HTTPException

@app.post("/api/extract-rules")
async def extract_rules_from_text(
    task_id: str = Form(...),
    text: str = Form(""),
    file: UploadFile = File(None)
):
    """Use HuggingFace LLM to extract validation rules from unstructured text or an uploaded file."""
    if task_id not in custom_protocols:
        return JSONResponse(status_code=400, content={"error": f"Unknown task_id: {task_id}"})
    
    extracted_text = text.strip()

    # If a file is provided, read its text
    if file and file.filename:
        content = await file.read()
        filename = file.filename.lower()
        
        try:
            if filename.endswith(".txt"):
                extracted_text = content.decode('utf-8')
            elif filename.endswith(".pdf"):
                if not PyPDF2:
                    return JSONResponse(status_code=400, content={"error": "PyPDF2 is not installed."})
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text() or "")
                extracted_text = "\n".join(text_parts)
            elif filename.endswith((".doc", ".docx")):
                if not docx:
                    return JSONResponse(status_code=400, content={"error": "python-docx is not installed."})
                doc = docx.Document(io.BytesIO(content))
                extracted_text = "\n".join([para.text for para in doc.paragraphs])
            else:
                return JSONResponse(status_code=400, content={"error": "Unsupported file format. Please upload .txt, .pdf, or .docx"})
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"Failed to parse file: {str(e)}"})

    if not extracted_text.strip():
        return JSONResponse(status_code=400, content={"error": "No text provided (either paste text or upload a document)."})
    
    # Send the combined/extracted text to the LLM
    text_to_process = extracted_text.strip()
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        # Fallback for demo purposes if no token is provided
        return JSONResponse(content={
            "message": "Successfully extracted 3 rules (Mock Demo Mode)",
            "extracted_rules": [
                "Patients must be between 18 and 65 years old",
                "The required drug dose is 50mg (40mg acceptable if under 60kg)",
                "All visits must occur within 30 days of the baseline"
            ]
        })

    client = InferenceClient(
        provider="novita",
        api_key=hf_token
    )

    system_prompt = (
        "You are an expert clinical trial protocol analyzer. "
        "Extract a list of actionable validation rules from the provided text. "
        "Output ONLY a valid JSON array of strings, where each string is a single clear rule. "
        "Do not include any explanation or markdown formatting outside the JSON array."
    )

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract rules from this protocol text:\n\n{text_to_process}"}
            ],
            max_tokens=500,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        
        # Clean up common LLM formatting issues
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            extracted_rules = json.loads(content)
            if not isinstance(extracted_rules, list):
                raise ValueError("Expected a JSON array")
        except Exception:
            # Fallback if parsing fails
            extracted_rules = [r.strip("-* ") for r in content.split('\n') if r.strip("-* ")]

        return JSONResponse(content={
            "message": f"Successfully extracted {len(extracted_rules)} rules",
            "extracted_rules": extracted_rules
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Extraction failed: {str(e)}"}
        )

class AutoValidateRequest(BaseModel):
    task_id: str
    records: list
    protocol_rules: list

@app.post("/api/auto-validate")
def auto_validate(req: AutoValidateRequest):
    """Use HuggingFace LLM to automatically find errors in the given records based on the given rules."""
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        # Fallback for demo mode
        return JSONResponse(content={
            "findings": [
                "Mock finding: Missing Age for Patient (Demo Mode)",
                "Mock finding: Protocol violation: wrong dose (Demo Mode)"
            ],
            "explanation": "No HF_TOKEN was set. Returning mock findings for UI demonstration."
        })

    client = InferenceClient(
        provider="novita",
        api_key=hf_token
    )

    records_str = json.dumps(req.records, indent=2)
    rules_str = "\n".join(f"- {r}" for r in req.protocol_rules)

    prompt = f"""You are a clinical trial data validator. Your task: {req.task_id.upper()}

Protocol Rules:
{rules_str}

Patient Records:
{records_str}

Instructions:
Analyze the data carefully and identify ALL errors, violations, or anomalies.
Return your response as a JSON object with two fields:
  "findings": a list of strings, each describing one specific error found
  "explanation": a brief overall summary of your analysis

Important: Include the Patient ID in each finding if applicable.
Respond ONLY with valid JSON. No markdown."""

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct",
            messages=[
                {"role": "system", "content": "You are an expert clinical trial data auditor. Always respond with valid JSON only. No markdown."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        
        # Clean up common LLM formatting issues
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            parsed = json.loads(content)
            findings = parsed.get("findings", [])
            explanation = parsed.get("explanation", "")
        except Exception:
            # Fallback
            findings = [r.strip("-* ") for r in content.split('\n') if r.strip("-* ")]
            explanation = "Extracted from malformed JSON output"

        return JSONResponse(content={
            "findings": findings,
            "explanation": explanation
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Validation failed: {str(e)}"}
        )

# ── /api/upload — CSV Data Upload ─────────────────────────────────────────────

uploaded_data = {
    "records": [],
    "filename": "",
    "row_count": 0,
    "columns": [],
}


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file with patient data."""
    if not file.filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only CSV files are allowed. Please upload a .csv file."},
        )

    try:
        contents = await file.read()
        text = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        records = []
        for row in reader:
            # Convert numeric fields
            clean_row = {}
            for key, value in row.items():
                key = key.strip()
                if value is None or value.strip() == "":
                    clean_row[key] = None
                else:
                    value = value.strip()
                    # Try to convert to number
                    try:
                        if "." in value:
                            clean_row[key] = float(value)
                        else:
                            clean_row[key] = int(value)
                    except ValueError:
                        clean_row[key] = value
            records.append(clean_row)

        uploaded_data["records"] = records
        uploaded_data["filename"] = file.filename
        uploaded_data["row_count"] = len(records)
        uploaded_data["columns"] = list(records[0].keys()) if records else []

        return JSONResponse(content={
            "message": f"Successfully uploaded {file.filename}",
            "row_count": len(records),
            "columns": uploaded_data["columns"],
            "preview": records[:5],  # First 5 rows as preview
            "records": records,
        })
    except UnicodeDecodeError:
        return JSONResponse(
            status_code=400,
            content={"error": "File encoding error. Please upload a UTF-8 encoded CSV."},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to parse CSV: {str(e)}"},
        )


@app.get("/api/uploaded-data")
def get_uploaded_data():
    """Get the currently uploaded dataset."""
    if not uploaded_data["records"]:
        return JSONResponse(content={
            "has_data": False,
            "message": "No data uploaded yet. Upload a CSV file to get started.",
        })
    return JSONResponse(content={
        "has_data": True,
        "filename": uploaded_data["filename"],
        "row_count": uploaded_data["row_count"],
        "columns": uploaded_data["columns"],
        "records": uploaded_data["records"],
    })
