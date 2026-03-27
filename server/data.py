"""
Sample clinical trial dataset with deliberate errors across 3 difficulty levels.

EASY task errors (missing / invalid required fields):
  - P001: Age is missing
  - P003: Gender is missing
  - P007: Visit Date is missing

MEDIUM task violations (protocol rules):
  Protocol rules:
    1. Patients must receive the drug on Day 14 ±2 (window: Day 12–16)
    2. Dose amount must be between 40mg and 60mg (inclusive)
    3. Patient age must be >= 18 to enroll
    4. Visit must occur within 30 days of enrollment
  Violations:
  - P034: Dose_Day = 19 (outside Day 12–16 window)
  - P041: Dose_Amount = 75mg (exceeds 60mg limit)
  - P055: Dose_Amount = 30mg (below 40mg minimum)
  - P062: Visit_Days_Since_Enrollment = 35 (exceeds 30-day window)

HARD task anomalies (cross-field inconsistency + temporal + audit):
  - P016: Age = 16, enrolled → age eligibility violation
  - P022: First_Dose_Date before Enrollment_Date → temporal error
  - Audit log: record modified after dataset lock → audit anomaly
"""

from typing import List, Dict, Any

# ─────────────────────────────────────────────────────────
#  EASY: Basic field validation dataset
# ─────────────────────────────────────────────────────────

EASY_PATIENT_RECORDS: List[Dict[str, Any]] = [
    {"Patient_ID": "P001", "Age": None,     "Gender": "Female", "Visit_Date": "2024-04-01", "Dose_Amount": "50mg"},
    {"Patient_ID": "P002", "Age": 34,       "Gender": "Male",   "Visit_Date": "2024-04-02", "Dose_Amount": "45mg"},
    {"Patient_ID": "P003", "Age": 28,       "Gender": None,     "Visit_Date": "2024-04-03", "Dose_Amount": "50mg"},
    {"Patient_ID": "P004", "Age": 45,       "Gender": "Female", "Visit_Date": "2024-04-04", "Dose_Amount": "55mg"},
    {"Patient_ID": "P005", "Age": 52,       "Gender": "Male",   "Visit_Date": "2024-04-05", "Dose_Amount": "50mg"},
    {"Patient_ID": "P006", "Age": 31,       "Gender": "Female", "Visit_Date": "2024-04-06", "Dose_Amount": "50mg"},
    {"Patient_ID": "P007", "Age": 39,       "Gender": "Male",   "Visit_Date": None,         "Dose_Amount": "50mg"},
    {"Patient_ID": "P008", "Age": 27,       "Gender": "Female", "Visit_Date": "2024-04-08", "Dose_Amount": "50mg"},
]

EASY_REQUIRED_FIELDS = ["Patient_ID", "Age", "Gender", "Visit_Date", "Dose_Amount"]

# Ground-truth errors — agent must find these (or equivalents)
EASY_GROUND_TRUTH = [
    "Missing Age for P001",
    "Missing Gender for P003",
    "Missing Visit_Date for P007",
]

# ─────────────────────────────────────────────────────────
#  MEDIUM: Protocol rule reasoning dataset
# ─────────────────────────────────────────────────────────

PROTOCOL_RULES: List[str] = [
    "Patients must receive the drug on Day 14 ±2 (allowed window: Day 12 to Day 16).",
    "Dose amount must be between 40mg and 60mg inclusive.",
    "Patient age must be 18 or older at time of enrollment.",
    "Patient visit must occur within 30 days of enrollment date.",
]

MEDIUM_PATIENT_RECORDS: List[Dict[str, Any]] = [
    {"Patient_ID": "P030", "Age": 40, "Dose_Day": 14, "Dose_Amount": "50mg", "Visit_Days_Since_Enrollment": 10},
    {"Patient_ID": "P031", "Age": 55, "Dose_Day": 13, "Dose_Amount": "45mg", "Visit_Days_Since_Enrollment": 20},
    {"Patient_ID": "P032", "Age": 29, "Dose_Day": 15, "Dose_Amount": "60mg", "Visit_Days_Since_Enrollment": 28},
    {"Patient_ID": "P033", "Age": 38, "Dose_Day": 12, "Dose_Amount": "40mg", "Visit_Days_Since_Enrollment": 5},
    {"Patient_ID": "P034", "Age": 33, "Dose_Day": 19, "Dose_Amount": "55mg", "Visit_Days_Since_Enrollment": 14},  # VIOLATION: Dose_Day
    {"Patient_ID": "P041", "Age": 47, "Dose_Day": 14, "Dose_Amount": "75mg", "Visit_Days_Since_Enrollment": 7},   # VIOLATION: Dose_Amount high
    {"Patient_ID": "P055", "Age": 36, "Dose_Day": 14, "Dose_Amount": "30mg", "Visit_Days_Since_Enrollment": 12},  # VIOLATION: Dose_Amount low
    {"Patient_ID": "P062", "Age": 42, "Dose_Day": 14, "Dose_Amount": "50mg", "Visit_Days_Since_Enrollment": 35},  # VIOLATION: Visit window
]

MEDIUM_GROUND_TRUTH = [
    "Protocol violation: P034 received dose on Day 19 (allowed window Day 12-16)",
    "Protocol violation: P041 dose amount 75mg exceeds maximum of 60mg",
    "Protocol violation: P055 dose amount 30mg is below minimum of 40mg",
    "Protocol violation: P062 visit occurred 35 days after enrollment (maximum 30 days)",
]

# ─────────────────────────────────────────────────────────
#  HARD: Advanced data integrity + audit analysis
# ─────────────────────────────────────────────────────────

HARD_PATIENT_RECORDS: List[Dict[str, Any]] = [
    {
        "Patient_ID": "P010",
        "Age": 34,
        "Enrollment_Status": "Approved",
        "Enrollment_Date": "2024-03-10",
        "First_Dose_Date": "2024-03-25",
        "Dose_Amount": "50mg",
    },
    {
        "Patient_ID": "P016",
        "Age": 16,                          # INCONSISTENCY: age < 18 but enrolled
        "Enrollment_Status": "Approved",
        "Enrollment_Date": "2024-03-12",
        "First_Dose_Date": "2024-03-26",
        "Dose_Amount": "50mg",
    },
    {
        "Patient_ID": "P022",
        "Age": 45,
        "Enrollment_Status": "Approved",
        "Enrollment_Date": "2024-03-15",    # TEMPORAL: dose before enrollment
        "First_Dose_Date": "2024-03-10",
        "Dose_Amount": "50mg",
    },
    {
        "Patient_ID": "P030",
        "Age": 52,
        "Enrollment_Status": "Approved",
        "Enrollment_Date": "2024-03-18",
        "First_Dose_Date": "2024-04-01",
        "Dose_Amount": "50mg",
    },
]

HARD_AUDIT_LOGS: List[str] = [
    "2024-05-01 10:23 Dose for P010 changed from 50mg to 80mg by user123",
    "2024-05-02 09:10 Trial dataset locked by admin",
    "2024-05-03 08:00 Dose for P010 changed again to 60mg by user123",  # AUDIT: modified after lock
    "2024-05-04 11:00 Report generated by admin",
    "2024-05-05 14:30 Enrollment status for P030 reviewed by auditor",
]

HARD_GROUND_TRUTH = [
    "Cross-field inconsistency: P016 is age 16 (under 18) but has Enrollment_Status Approved",
    "Temporal error: P022 First_Dose_Date 2024-03-10 is before Enrollment_Date 2024-03-15",
    "Audit anomaly: Dose for P010 was modified after dataset lock on 2024-05-02",
]

# ─────────────────────────────────────────────────────────
#  Task metadata
# ─────────────────────────────────────────────────────────

TASKS = [
    {
        "id": "easy",
        "name": "Basic Field Validation",
        "difficulty": "easy",
        "description": (
            "Validate patient records and detect missing or invalid required fields. "
            "Required fields: Patient_ID, Age, Gender, Visit_Date, Dose_Amount."
        ),
        "action_schema": {
            "task_id": "string (must be 'easy')",
            "findings": "list of strings describing each error found",
            "explanation": "string, optional human-readable explanation",
        },
    },
    {
        "id": "medium",
        "name": "Protocol Rule Reasoning",
        "difficulty": "medium",
        "description": (
            "Interpret clinical trial protocol rules and detect violations in patient records. "
            "Rules: Dose Day 14±2, Dose 40–60mg, Age ≥18, Visit within 30 days of enrollment."
        ),
        "action_schema": {
            "task_id": "string (must be 'medium')",
            "findings": "list of strings describing each protocol violation found",
            "explanation": "string, optional human-readable explanation",
        },
    },
    {
        "id": "hard",
        "name": "Advanced Data Integrity and Audit Analysis",
        "difficulty": "hard",
        "description": (
            "Detect cross-field inconsistencies (e.g. underage patient enrolled), "
            "temporal data errors (dose before enrollment), and audit trail anomalies "
            "(record modified after dataset lock)."
        ),
        "action_schema": {
            "task_id": "string (must be 'hard')",
            "findings": "list of strings describing each anomaly found",
            "explanation": "string, optional human-readable explanation",
        },
    },
]
