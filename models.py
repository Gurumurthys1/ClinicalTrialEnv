from typing import List, Optional, Dict, Any
from openenv.core.env_server import Action, Observation, State


class ClinicalTrialAction(Action):
    """Action submitted by the agent to validate clinical trial data."""
    task_id: str                        # "easy" | "medium" | "hard"
    findings: List[str]                 # List of errors/violations detected by the agent
    explanation: str = ""               # Human-readable explanation of findings


class ClinicalTrialObservation(Observation):
    """Observation returned after reset() or step()."""
    task_id: str
    task_description: str
    patient_records: List[Dict[str, Any]]   # Patient data to validate
    protocol_rules: List[str]               # Natural language protocol rules
    audit_logs: List[str]                   # Audit trail entries (hard task)
    expected_finding_count: int             # How many errors exist in total
    findings_submitted: List[str]           # What the agent submitted (empty on reset)
    message: str


class ClinicalTrialState(State):
    """Internal state of the environment episode."""
    current_task: str = "easy"
    total_errors_in_dataset: int = 0
