"""Grok (xAI) integration.

Two capabilities are exposed:

1. ``generate_deliverables_from_plan`` — turn a free-text master plan into a
   structured set of *plan points* and *deliverables*. Used when a project is
   configured.
2. ``analyze_deliverable`` — score a single deliverable against the master plan
   and return strengths / gaps / recommendations. Powers the AI-analysis
   subpanel.

The xAI API is OpenAI-compatible (base ``https://api.x.ai/v1``,
``POST /chat/completions``, Bearer auth). If no ``GROK_API_KEY`` is configured
the module degrades gracefully to a deterministic mock so the whole platform
remains runnable end-to-end without a key.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger("grok")

_SYSTEM_GENERATOR = (
    "You are a senior delivery manager. Given a project's master plan, break it "
    "into a structured JSON object. Extract the high-level objectives as "
    "'plan_points' and, for each, propose concrete client-facing 'deliverables'. "
    "Respond with STRICT JSON only, no prose, matching this shape: "
    '{"plan_points":[{"title":str,"description":str,'
    '"deliverables":[{"title":str,"description":str,"acceptance_criteria":str}]}]}'
)

_SYSTEM_ANALYZER = (
    "You are a meticulous project quality analyst. You are given a project master "
    "plan and a single deliverable. Judge how well the deliverable aligns with, "
    "and advances, the master plan. Respond with STRICT JSON only matching: "
    '{"score":number(0-100),"summary":str,"strengths":[str],"gaps":[str],'
    '"recommendations":[str]}'
)


class GrokClient:
    def __init__(self) -> None:
        self.api_key = settings.grok_api_key
        self.base_url = settings.grok_base_url.rstrip("/")
        self.model = settings.grok_model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # --------------------------------------------------------------------- #
    # Low-level call
    # --------------------------------------------------------------------- #
    def _chat(self, system: str, user: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=90.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Best-effort JSON extraction, tolerant of code fences / stray prose."""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    # --------------------------------------------------------------------- #
    # High-level operations
    # --------------------------------------------------------------------- #
    def generate_deliverables_from_plan(self, master_plan: str) -> dict:
        if not self.enabled:
            return _mock_generate(master_plan)
        try:
            raw = self._chat(_SYSTEM_GENERATOR, f"Master plan:\n\n{master_plan}")
            parsed = self._extract_json(raw)
            parsed["_mock"] = False
            return parsed
        except Exception as exc:  # network / parse / auth — never break the flow
            logger.warning("Grok generation failed, falling back to mock: %s", exc)
            return _mock_generate(master_plan)

    def analyze_deliverable(
        self, master_plan: str, title: str, description: str, acceptance: str
    ) -> dict:
        if not self.enabled:
            return _mock_analyze(title, description, acceptance)
        try:
            user = (
                f"MASTER PLAN:\n{master_plan}\n\n"
                f"DELIVERABLE TITLE: {title}\n"
                f"DELIVERABLE DESCRIPTION: {description}\n"
                f"ACCEPTANCE CRITERIA: {acceptance}"
            )
            raw = self._chat(_SYSTEM_ANALYZER, user)
            parsed = self._extract_json(raw)
            parsed["_mock"] = False
            parsed["_model"] = self.model
            return parsed
        except Exception as exc:
            logger.warning("Grok analysis failed, falling back to mock: %s", exc)
            return _mock_analyze(title, description, acceptance)


# --------------------------------------------------------------------------- #
# Deterministic mock — keeps the platform fully functional without a key.
# Heuristic, not random, so results are stable and demoable.
# --------------------------------------------------------------------------- #
def _split_points(master_plan: str) -> list[str]:
    """Split a plan into candidate objective lines."""
    lines: list[str] = []
    for raw in master_plan.splitlines():
        line = raw.strip()
        if not line:
            continue
        # strip common bullet / numbering prefixes
        line = re.sub(r"^([-*•]|\d+[.)])\s*", "", line)
        if len(line) > 3:
            lines.append(line)
    # If it was one long paragraph, fall back to sentence splitting.
    if len(lines) <= 1 and master_plan.strip():
        lines = [s.strip() for s in re.split(r"(?<=[.!?])\s+", master_plan) if s.strip()]
    return lines[:12] or ["Project objective"]


def _mock_generate(master_plan: str) -> dict:
    points = _split_points(master_plan)
    plan_points = []
    for p in points:
        title = p[:120]
        plan_points.append(
            {
                "title": title,
                "description": p,
                "deliverables": [
                    {
                        "title": f"Design & spec: {title[:80]}",
                        "description": f"Produce the design and specification covering: {p}",
                        "acceptance_criteria": "Specification reviewed and approved by the client.",
                    },
                    {
                        "title": f"Implement: {title[:80]}",
                        "description": f"Build the functionality for: {p}",
                        "acceptance_criteria": "Feature implemented, tested and demoable.",
                    },
                ],
            }
        )
    return {"plan_points": plan_points, "_mock": True}


def _mock_analyze(title: str, description: str, acceptance: str) -> dict:
    text = f"{title} {description} {acceptance}"
    words = len(text.split())
    has_criteria = bool(acceptance.strip())
    # Heuristic score: richer descriptions + explicit criteria score higher.
    score = min(100, 45 + min(words, 60) // 2 + (20 if has_criteria else 0))
    strengths = ["Deliverable is clearly titled and scoped."]
    if has_criteria:
        strengths.append("Explicit acceptance criteria make completion verifiable.")
    if words > 30:
        strengths.append("Description provides good detail for execution.")
    gaps = []
    if not has_criteria:
        gaps.append("No acceptance criteria — completion is hard to verify.")
    if words < 15:
        gaps.append("Description is thin; add measurable outcomes.")
    if not gaps:
        gaps.append("Consider linking explicitly to a master-plan milestone.")
    recommendations = [
        "Tie the deliverable to a specific master-plan objective.",
        "Define measurable acceptance criteria before starting.",
    ]
    return {
        "score": float(score),
        "summary": (
            f"Heuristic (mock) alignment assessment: this deliverable scores "
            f"{score}/100 against the plan. Configure GROK_API_KEY for a full "
            f"AI-driven analysis."
        ),
        "strengths": strengths,
        "gaps": gaps,
        "recommendations": recommendations,
        "_mock": True,
        "_model": "mock",
    }


grok = GrokClient()
