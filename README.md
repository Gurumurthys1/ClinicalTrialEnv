# 🧬 ClinicalTrialEnv

**LLM-Powered Clinical Trial Data Validator — OpenEnv Environment**

[![OpenEnv](https://img.shields.io/badge/OpenEnv-v1.0.0-blue)](https://openenv.dev)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

An OpenEnv environment where an AI agent validates clinical trial patient data, detects protocol violations, and analyzes audit trail anomalies across 3 difficulty levels.

---

## 🎯 Environment Description

Clinical trials collect large amounts of patient data (demographics, treatment schedules, lab results). Before submission to regulators like the FDA, the dataset must strictly follow protocol rules. This environment tasks an agent with finding all errors.

**Real-world utility**: Automates the tedious manual process of clinical data review, which typically requires specialized data managers reviewing hundreds of records.

---

## 🧩 Tasks

| Task | Difficulty | Errors to Find | Description |
|--- |--- |--- |--- |
| `easy` | 🟢 Easy | 3 | Detect missing/null required fields (Patient_ID, Age, Gender, Visit_Date, Dose_Amount) |
| `medium` | 🟡 Medium | 4 | Detect clinical protocol violations (wrong dose day, invalid dose amount, late visits) |
| `hard` | 🔴 Hard | 3 | Detect cross-field inconsistencies, temporal errors, and audit trail anomalies |

### Easy Task Details
Find all records with missing required fields:
- **P001**: Age is null
- **P003**: Gender is null  
- **P007**: Visit_Date is null

### Medium Task Details
Protocol rules violation detection:
- **P034**: Received dose on Day 19 (allowed window: Day 12–16)
- **P041**: Dose amount 75mg exceeds maximum 60mg
- **P055**: Dose amount 30mg is below minimum 40mg
- **P062**: Visit occurred 35 days after enrollment (max 30 days)

### Hard Task Details
Advanced anomaly detection:
- **P016**: Age 16, enrolled (cross-field inconsistency — eligibility rule: age ≥ 18)
- **P022**: First_Dose_Date before Enrollment_Date (temporal error)
- **P010**: Dose modified after dataset lock on 2024-05-02 (audit anomaly)

---

## 🔌 Action & Observation Spaces

### Action
```python
class ClinicalTrialAction(Action):
    task_id: str          # "easy" | "medium" | "hard"
    findings: List[str]   # list of error descriptions
    explanation: str      # overall summary (optional)
```

### Observation
```python
class ClinicalTrialObservation(Observation):
    task_id: str
    task_description: str
    patient_records: List[Dict]   # patient data
    protocol_rules: List[str]     # rules to check against
    audit_logs: List[str]         # audit trail (hard task)
    expected_finding_count: int   # how many errors exist
    findings_submitted: List[str] # what agent submitted
    message: str                  # feedback
    done: bool
    reward: Optional[float]       # 0.0–1.0
```

### State
```python
class ClinicalTrialState(State):
    current_task: str           # active task id
    total_errors_in_dataset: int
    episode_id: str
    step_count: int
```

---

## 🏆 Reward Function

Rewards are computed by deterministic graders using keyword-matching on findings:

| Score | Meaning |
|--- |--- |
| 1.0 | All errors correctly identified |
| 0.67–0.99 | Most errors found (partial credit) |
| 0.33–0.66 | Some errors found |
| 0.0–0.32 | Few or no errors found |

Each task uses a different grader with task-specific keyword sets. Partial credit is awarded per error found (e.g., 2/3 errors = 0.67).

---

## 🚀 Setup & Usage

### Local Development

```bash
# Clone / navigate to project
cd clinical_trial_env

# Install dependencies
pip install -r requirements.txt

# Start the server (from parent directory)
cd ..
uvicorn clinical_trial_env.server.app:app --host 0.0.0.0 --port 7860 --reload

# Open dashboard
open http://localhost:7860
```

### Docker

```bash
cd clinical_trial_env
docker build -t clinical-trial-env .
docker run -p 7860:7860 -e OPENAI_API_KEY=sk-... clinical-trial-env
```

---

## 📡 API Endpoints

The environment exposes the standard OpenEnv API plus 3 extra endpoints:

### Standard OpenEnv API
| Method | Endpoint | Description |
|--- |--- |--- |
| `POST` | `/api/reset` | Start a new episode (`{"task_id": "easy"}`) |
| `POST` | `/api/step` | Submit findings (`{"session_id": "...", "task_id": "easy", "findings": [...]}`) |
| `GET` | `/api/state` | Get current episode state |

### Required Hackathon Endpoints
| Method | Endpoint | Description |
|--- |--- |--- |
| `GET` | `/tasks` | List all tasks with action schemas |
| `POST` | `/grader` | Run grader on findings (`{"task_id": "easy", "findings": [...]}`) |
| `POST` | `/baseline` | Trigger baseline inference script |

### 🛠️ Interactive Dashboard Endpoints
| Method | Endpoint | Description |
|--- |--- |--- |
| `POST` | `/api/upload` | Upload custom patient records via CSV |
| `GET` | `/api/uploaded-data`| Retrieve currently uploaded CSV data |
| `GET` | `/api/protocols` | Get protocol rules for active task |
| `POST` | `/api/protocols` | Add a new protocol rule |
| `PUT` | `/api/protocols` | Update an existing protocol rule |
| `DELETE` | `/api/protocols` | Remove a protocol rule |

---

## 🤖 Baseline Inference Script

Runs GPT against all 3 tasks and reports scores:

```bash
export OPENAI_API_KEY=sk-...
export BASE_URL=http://localhost:7860  # or your HF Space URL

python clinical_trial_env/baseline_inference.py
```

### Expected Baseline Scores (gpt-4o-mini)

| Task | Score |
|--- |--- |
| Easy | ~0.67–1.00 |
| Medium | ~0.50–0.75 |
| Hard | ~0.33–0.67 |
| **Average** | **~0.50–0.81** |

*Scores vary based on LLM version and temperature settings.*

---

## 📁 Project Structure

```
clinical_trial_env/
├── __init__.py
├── models.py              # Pydantic Action, Observation, State
├── openenv.yaml           # OpenEnv metadata
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── baseline_inference.py  # OpenAI baseline agent
├── client.py              # EnvClient subclass
└── server/
    ├── __init__.py
    ├── app.py             # FastAPI app + extra endpoints
    ├── environment.py     # Environment logic (reset/step/state)
    ├── data.py            # Sample datasets with deliberate errors
    ├── graders.py         # Deterministic graders (0.0–1.0)
    └── static/
        ├── index.html     # Premium dark-mode dashboard UI
        ├── styles.css
        └── script.js
```

---

## 🏗️ OpenEnv Spec Compliance

- ✅ Typed `Action`, `Observation`, `State` Pydantic models
- ✅ `step(action)` → returns observation, reward, done, info
- ✅ `reset()` → returns initial observation
- ✅ `state` → returns current state
- ✅ `openenv.yaml` with metadata and task definitions
- ✅ Minimum 3 tasks with difficulty progression
- ✅ Graders return deterministic scores in [0.0, 1.0]
- ✅ Partial reward signal (not just binary)
- ✅ Baseline inference script using OpenAI API
- ✅ Dockerfile for containerized deployment
- ✅ `/tasks`, `/grader`, `/baseline` endpoints

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
