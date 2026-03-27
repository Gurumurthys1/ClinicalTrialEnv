"""
ClinicalTrialEnvClient — OpenEnv client wrapper for the clinical_trial_env server.
"""

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult
from .models import ClinicalTrialAction, ClinicalTrialObservation, ClinicalTrialState


class ClinicalTrialEnvClient(EnvClient[ClinicalTrialAction, ClinicalTrialObservation, ClinicalTrialState]):

    def _step_payload(self, action: ClinicalTrialAction) -> dict:
        return {
            "task_id": action.task_id,
            "findings": action.findings,
            "explanation": action.explanation,
        }

    def _parse_result(self, payload: dict) -> StepResult:
        obs_data = payload.get("observation", {})
        return StepResult(
            observation=ClinicalTrialObservation(
                done=payload.get("done", False),
                reward=payload.get("reward"),
                task_id=obs_data.get("task_id", "easy"),
                task_description=obs_data.get("task_description", ""),
                patient_records=obs_data.get("patient_records", []),
                protocol_rules=obs_data.get("protocol_rules", []),
                audit_logs=obs_data.get("audit_logs", []),
                expected_finding_count=obs_data.get("expected_finding_count", 0),
                findings_submitted=obs_data.get("findings_submitted", []),
                message=obs_data.get("message", ""),
            ),
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: dict) -> ClinicalTrialState:
        return ClinicalTrialState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            current_task=payload.get("current_task", "easy"),
            total_errors_in_dataset=payload.get("total_errors_in_dataset", 0),
        )
