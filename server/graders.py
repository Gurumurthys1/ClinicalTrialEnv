"""
Deterministic graders for all 3 clinical trial tasks.

Each grader returns a float in [0.0, 1.0]:
  1.0 = all errors correctly found
  0.0 = no errors found
  partial credit = fraction of errors found

Keyword-matching is used so agents don't need exact string matches —
they just need to mention the patient ID and the relevant error type.
"""

from typing import List


# ─────────────────────────────────────────────────────────
#  Keyword sets for flexible matching
# ─────────────────────────────────────────────────────────

EASY_KEYWORDS = [
    # Each sub-list: agent finding must contain ALL tokens to count
    ["p001", "age"],
    ["p003", "gender"],
    ["p007", "visit"],
]

MEDIUM_KEYWORDS = [
    ["p034", "day"],          # wrong dose day
    ["p041", "75"],           # dose too high (match the specific value)
    ["p055", "30"],           # dose too low
    ["p062", "visit"],        # visit window exceeded
]

HARD_KEYWORDS = [
    ["p016", "16"],                # underage enrolled
    ["p022", "dose", "enroll"],    # dose before enrollment (temporal)
    ["p010", "lock"],              # audit: modified after lock
]


def _count_matches(findings: List[str], keyword_sets: List[List[str]]) -> int:
    """Count how many keyword sets have at least one finding that mentions all keywords."""
    matched = 0
    for kw_set in keyword_sets:
        for finding in findings:
            finding_lower = finding.lower()
            if all(kw in finding_lower for kw in kw_set):
                matched += 1
                break
    return matched


def grade_easy(findings: List[str]) -> float:
    """
    Grade Task 1 (Easy): Basic Field Validation.
    3 errors to find: missing Age (P001), missing Gender (P003), missing Visit_Date (P007).
    Score = matched / 3, with a bonus +0.1 if all 3 are found.
    """
    n = len(EASY_KEYWORDS)
    matched = _count_matches(findings, EASY_KEYWORDS)
    score = matched / n
    # Bonus for perfect detection
    if matched == n:
        score = 1.0
    return round(min(score, 1.0), 4)


def grade_medium(findings: List[str]) -> float:
    """
    Grade Task 2 (Medium): Protocol Rule Reasoning.
    4 violations to find.
    Score = matched / 4.
    Partial credit awarded per violation.
    """
    n = len(MEDIUM_KEYWORDS)
    matched = _count_matches(findings, MEDIUM_KEYWORDS)
    score = matched / n
    return round(min(score, 1.0), 4)


def grade_hard(findings: List[str]) -> float:
    """
    Grade Task 3 (Hard): Advanced Data Integrity & Audit Analysis.
    3 anomaly categories to detect — each worth 1/3 of the score.
    Bonus 0.05 if agent detects all 3.
    """
    n = len(HARD_KEYWORDS)
    matched = _count_matches(findings, HARD_KEYWORDS)
    score = matched / n
    if matched == n:
        score = min(score + 0.05, 1.0)
    return round(min(score, 1.0), 4)


GRADER_MAP = {
    "easy":   grade_easy,
    "medium": grade_medium,
    "hard":   grade_hard,
}
