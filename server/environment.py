"""
ClinicalTrialEnvironment — full OpenEnv Environment implementation.

Supports 3 tasks (easy / medium / hard) with concurrent sessions.
API:
  reset(task_id="easy"|"medium"|"hard") → ClinicalTrialObservation
  step(action: ClinicalTrialAction)     → ClinicalTrialObservation
  state                                 → ClinicalTrialState (property)
"""

import uuid
from openenv.core.env_server import Environment
from ..models import ClinicalTrialAction, ClinicalTrialObservation, ClinicalTrialState
from .data import (
    EASY_PATIENT_RECORDS, EASY_REQUIRED_FIELDS, EASY_GROUND_TRUTH,
    PROTOCOL_RULES, MEDIUM_PATIENT_RECORDS, MEDIUM_GROUND_TRUTH,
    HARD_PATIENT_RECORDS, HARD_AUDIT_LOGS, HARD_GROUND_TRUTH,
    TASKS,
)
from .graders import GRADER_MAP


# ── Task-specific data bundles ───────────────────────────────────────────────

TASK_DATA = {
    "easy": {
        "patient_records": EASY_PATIENT_RECORDS,
        "protocol_rules": [
            f"Required fields: {', '.join(EASY_REQUIRED_FIELDS)}. "
            "Each field must be present and non-null for every patient record."
        ],
        "audit_logs": [],
        "ground_truth_count": len(EASY_GROUND_TRUTH),
        "task_description": (
            "Examine the patient records below and identify all missing or null "
            "required fields. Required fields are: Patient_ID, Age, Gender, "
            "Visit_Date, Dose_Amount. Report each missing field as a finding."
        ),
    },
    "medium": {
        "patient_records": MEDIUM_PATIENT_RECORDS,
        "protocol_rules": PROTOCOL_RULES,
        "audit_logs": [],
        "ground_truth_count": len(MEDIUM_GROUND_TRUTH),
        "task_description": (
            "Review the patient records against the protocol rules provided. "
            "Identify all protocol violations (wrong dose day, invalid dose amount, "
            "underage patients, late visits). Report each violation as a finding."
        ),
    },
    "hard": {
        "patient_records": HARD_PATIENT_RECORDS,
        "protocol_rules": [
            "Patient age must be 18 or older at time of enrollment.",
            "First_Dose_Date must be on or after Enrollment_Date.",
            "No record modifications are permitted after the trial dataset is locked.",
        ],
        "audit_logs": HARD_AUDIT_LOGS,
        "ground_truth_count": len(HARD_GROUND_TRUTH),
        "task_description": (
            "Perform an advanced data integrity audit. Detect: (1) cross-field "
            "inconsistencies (e.g. underage patient enrolled), (2) temporal data "
            "errors (dose administered before enrollment), and (3) audit trail "
            "anomalies (record modified after dataset lock). Report each anomaly "
            "as a specific finding."
        ),
    },
}

TASK_IDS = list(TASK_DATA.keys())


class ClinicalTrialEnvironment(Environment):
    """OpenEnv environment for clinical trial data validation."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = ClinicalTrialState()
        self._task_id = "easy"
        self._findings_submitted: list = []
        self._done = False
        self._last_reward: float | None = None

    # ── reset ────────────────────────────────────────────────────────────────

    def reset(self, seed=None, episode_id=None, task_id: str = "easy", **kwargs) -> ClinicalTrialObservation:
        if task_id not in TASK_DATA:
            task_id = "easy"

        data = TASK_DATA[task_id]
        self._task_id = task_id
        self._findings_submitted = []
        self._done = False
        self._last_reward = None

        self._state = ClinicalTrialState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            current_task=task_id,
            total_errors_in_dataset=data["ground_truth_count"],
        )

        return ClinicalTrialObservation(
            done=False,
            reward=None,
            task_id=task_id,
            task_description=data["task_description"],
            patient_records=data["patient_records"],
            protocol_rules=data["protocol_rules"],
            audit_logs=data["audit_logs"],
            expected_finding_count=data["ground_truth_count"],
            findings_submitted=[],
            message=(
                f"Episode started. Task: {task_id.upper()}. "
                f"Analyze the data and submit your findings via step()."
            ),
        )

    # ── step ─────────────────────────────────────────────────────────────────

    def step(self, action: ClinicalTrialAction, timeout_s=None, **kwargs) -> ClinicalTrialObservation:
        self._state.step_count += 1

        # Validate task_id matches current episode
        if action.task_id not in TASK_DATA:
            return self._error_obs(f"Unknown task_id '{action.task_id}'. Must be one of: {TASK_IDS}")

        # Run grader
        grader = GRADER_MAP[self._task_id]
        reward = grader(action.findings)

        self._findings_submitted = action.findings
        self._last_reward = reward
        self._done = True  # one-shot: agent submits once, episode ends

        # Build feedback message
        data = TASK_DATA[self._task_id]
        n_expected = data["ground_truth_count"]
        n_found_approx = round(reward * n_expected)

        if reward == 1.0:
            msg = f"✅ Perfect score! All {n_expected} errors detected correctly."
        elif reward >= 0.67:
            msg = f"🟡 Good job! Detected approximately {n_found_approx}/{n_expected} errors. Score: {reward:.2f}"
        elif reward >= 0.33:
            msg = f"🟠 Partial. Detected approximately {n_found_approx}/{n_expected} errors. Score: {reward:.2f}"
        else:
            msg = f"🔴 Missed most errors. Detected approximately {n_found_approx}/{n_expected}. Score: {reward:.2f}"

        return ClinicalTrialObservation(
            done=True,
            reward=reward,
            task_id=self._task_id,
            task_description=data["task_description"],
            patient_records=data["patient_records"],
            protocol_rules=data["protocol_rules"],
            audit_logs=data["audit_logs"],
            expected_finding_count=n_expected,
            findings_submitted=self._findings_submitted,
            message=msg,
        )

    # ── state property ───────────────────────────────────────────────────────

    @property
    def state(self) -> ClinicalTrialState:
        return self._state

    # ── helpers ──────────────────────────────────────────────────────────────

    def _error_obs(self, msg: str) -> ClinicalTrialObservation:
        data = TASK_DATA.get(self._task_id, TASK_DATA["easy"])
        return ClinicalTrialObservation(
            done=False,
            reward=0.0,
            task_id=self._task_id,
            task_description=data["task_description"],
            patient_records=data["patient_records"],
            protocol_rules=data["protocol_rules"],
            audit_logs=data["audit_logs"],
            expected_finding_count=data["ground_truth_count"],
            findings_submitted=[],
            message=f"Error: {msg}",
        )
