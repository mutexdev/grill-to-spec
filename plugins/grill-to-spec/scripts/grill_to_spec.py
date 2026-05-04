#!/usr/bin/env python3
"""Generate and evaluate PRD.json and task artifacts.

The plugin skills are conversational, but this script keeps the artifact format
deterministic so tests and evals can verify the workflow with local assets.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPECS_OUTPUT = object()
REQUIRED_PRD_KEYS = [
    "schema_version",
    "project",
    "source",
    "problem_statement",
    "goals",
    "non_goals",
    "actors",
    "user_stories",
    "requirements",
    "acceptance_criteria",
    "implementation_decisions",
    "testing_decisions",
    "traceability",
    "quality_gates",
]

CANONICAL_GRILL_TO_SPEC_GOALS = [
    "Run a phase-gated Codex workflow that starts with Grill-Me discovery before implementation.",
    "Ask one question at a time during grilling and include the recommended answer.",
    "Create PRD.json with user stories, requirements, acceptance criteria, implementation decisions, testing decisions, and traceability.",
    "Create task artifacts that decompose PRD requirements into vertical-slice tasks with blockers, HITL/AFK classification, and PRD references.",
    "Use vendored Spec Kit scripts and templates for specify, clarify, plan, tasks, analyze, and checklist workflows.",
    "Require explicit user approval before any implementation command, code edit, or downstream task execution begins.",
    "Generate an evaluation report that scores PRD completeness, task artifact traceability, task actionability, testability, and Spec Kit asset readiness.",
    "Create a Spec-Kit archive that bundles the eval report, PRD, task artifacts, grill-me skill, plugin manifest, and vendored Spec Kit assets.",
]

CANONICAL_GRILL_TO_SPEC_CONSTRAINTS = [
    "Run best in Codex interactive mode because the grill phase requires human-in-the-loop answers and approvals.",
    "Do not proceed to implementation until PRD.json, task artifacts, evaluation artifacts, and explicit user approval exist.",
    "Do not invoke implementation commands, auto-send implementation handoffs, edit product code, or mark downstream tasks complete during the grill-to-spec workflow.",
    "Use a dense forward-context summary between phases instead of relying on a long raw conversation transcript.",
    "Do not require a network server for Spec Kit workflows; use bundled scripts and templates from vendor/spec-kit.",
    "Keep archive generation dependency-free so users can share the evaluated handoff without extra setup.",
]

REQUIRED_SPEC_KIT_ASSETS = [
    "scripts/bash/check-prerequisites.sh",
    "scripts/bash/common.sh",
    "scripts/bash/create-new-feature.sh",
    "scripts/bash/setup-plan.sh",
    "scripts/bash/setup-tasks.sh",
    "scripts/powershell/check-prerequisites.ps1",
    "scripts/powershell/common.ps1",
    "scripts/powershell/create-new-feature.ps1",
    "scripts/powershell/setup-plan.ps1",
    "scripts/powershell/setup-tasks.ps1",
    "templates/commands/analyze.md",
    "templates/commands/checklist.md",
    "templates/commands/clarify.md",
    "templates/commands/constitution.md",
    "templates/commands/plan.md",
    "templates/commands/specify.md",
    "templates/commands/tasks.md",
    "templates/checklist-template.md",
    "templates/constitution-template.md",
    "templates/plan-template.md",
    "templates/spec-template.md",
    "templates/tasks-template.md",
    "workflows/speckit/workflow.yml",
]


@dataclass(frozen=True)
class ArtifactPaths:
    prd: Path
    task_artifacts: list[Path]
    task_artifact_index: Path
    evaluation: Path
    spec_kit_dir: Path | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "prd": self.prd,
            "task_artifacts": self.task_artifacts,
            "task_artifact_index": self.task_artifact_index,
            "evaluation": self.evaluation,
            "spec_kit_dir": self.spec_kit_dir,
        }


def slugify(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -\t\r\n")


def split_sentences(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+", clean_text(text))
    return [item.strip() for item in candidates if len(item.strip()) > 20]


def extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"overview": []}
    current = "overview"
    for line in text.splitlines():
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if heading:
            current = clean_text(heading.group(1)).lower()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def extract_bullets(section_text: str) -> list[str]:
    bullets: list[str] = []
    current: list[str] = []

    def flush_current() -> None:
        if current:
            bullets.append(clean_text(" ".join(current)))
            current.clear()

    for line in section_text.splitlines():
        match = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$", line)
        if match:
            flush_current()
            current.append(match.group(1))
            continue
        if current and line.strip() and re.match(r"^\s+", line):
            current.append(line.strip())
            continue
        if not line.strip():
            flush_current()
            continue
        flush_current()
    flush_current()
    return dedupe(bullets)


def find_section(sections: dict[str, str], *needles: str) -> str:
    for name, body in sections.items():
        if any(needle in name for needle in needles):
            return body
    return ""


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = clean_text(item)
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            output.append(normalized)
    return output


def is_grill_to_spec_source(source_text: str) -> bool:
    lowered = source_text.lower()
    has_grill = "grill-me" in lowered or "grill me" in lowered
    has_prd = "to-prd" in lowered or "prd.json" in lowered or "product requirements document" in lowered
    has_spec = "spec" in lowered or "spec-kit" in lowered or "task artifact" in lowered or "task_artifact" in lowered
    return has_grill and has_prd and has_spec


def derive_project_name(source_text: str, project_name: str | None) -> str:
    if project_name:
        return clean_text(project_name)
    for line in source_text.splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*$", line)
        if match:
            return clean_text(match.group(1))
    return "Grill to Spec Workflow"


def derive_goals(sections: dict[str, str], source_text: str) -> list[str]:
    if is_grill_to_spec_source(source_text):
        return CANONICAL_GRILL_TO_SPEC_GOALS

    goals = extract_bullets(find_section(sections, "goal", "objective"))
    if goals:
        return goals

    goalish: list[str] = []
    for sentence in split_sentences(source_text):
        lowered = sentence.lower()
        if any(word in lowered for word in ["create", "generate", "ask", "evaluate", "decompose"]):
            goalish.append(sentence)
    return dedupe(goalish[:7]) or [
        "Interview the user until the product and engineering intent is clear.",
        "Create a machine-actionable PRD.json artifact.",
        "Create traceable task artifacts with implementation-ready handoff tasks.",
        "Evaluate output quality with a repeatable rubric.",
    ]


def derive_constraints(sections: dict[str, str], source_text: str) -> list[str]:
    if is_grill_to_spec_source(source_text):
        return CANONICAL_GRILL_TO_SPEC_CONSTRAINTS

    constraints = extract_bullets(find_section(sections, "constraint", "non-functional", "guardrail"))
    if constraints:
        return constraints

    found: list[str] = []
    for sentence in split_sentences(source_text):
        lowered = sentence.lower()
        if any(word in lowered for word in ["must", "should", "avoid", "require", "interactive", "script", "template"]):
            found.append(sentence)
    return dedupe(found[:6])


def derive_acceptance_criteria(sections: dict[str, str], goals: list[str]) -> list[dict[str, str]]:
    raw = extract_bullets(find_section(sections, "acceptance", "criteria", "quality gate"))
    if not raw:
        raw = [
            "Given the resolved grill context, when PRD generation runs, then PRD.json includes goals, stories, requirements, and acceptance criteria.",
            "Given PRD.json, when task decomposition runs, then task artifacts contain vertical-slice tasks with PRD references.",
            "Given generated artifacts, when evaluation runs, then scores and findings justify output quality.",
        ]

    criteria: list[dict[str, str]] = []
    for index, statement in enumerate(raw, start=1):
        text = statement
        if not text.lower().startswith("given "):
            text = f"Given the workflow input, when requirement {index} is checked, then {text[0].lower() + text[1:]}"
        criteria.append({"id": f"AC-{index:03d}", "statement": text})

    if len(criteria) < min(3, len(goals)):
        for index, goal in enumerate(goals[len(criteria) :], start=len(criteria) + 1):
            criteria.append(
                {
                    "id": f"AC-{index:03d}",
                    "statement": f"Given the generated plan, when the user inspects it, then it satisfies: {goal}",
                }
            )
    return criteria


def derive_requirements(goals: list[str], constraints: list[str], acceptance: list[dict[str, str]]) -> list[dict[str, Any]]:
    source_items = dedupe(goals + constraints)
    if len(source_items) < 4:
        source_items = dedupe(source_items + [item["statement"] for item in acceptance])
    requirements: list[dict[str, Any]] = []
    for index, statement in enumerate(source_items[:12], start=1):
        acceptance_id = acceptance[(index - 1) % len(acceptance)]["id"]
        requirements.append(
            {
                "id": f"REQ-{index:03d}",
                "statement": statement,
                "priority": "must" if index <= max(4, len(goals)) else "should",
                "source_refs": [f"source:{index}"],
                "acceptance_criteria": [acceptance_id],
            }
        )
    return requirements


def derive_user_stories(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actors = ["Codex user", "Codex agent", "engineering team", "reviewer"]
    stories: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements[:8], start=1):
        actor = actors[(index - 1) % len(actors)]
        statement = requirement["statement"].rstrip(".")
        stories.append(
            {
                "id": f"US-{index:03d}",
                "actor": actor,
                "story": f"As a {actor}, I want the workflow to {statement[0].lower() + statement[1:]}, so that spec-driven work stays traceable.",
                "requirements": [requirement["id"]],
            }
        )
    return stories


def build_prd(source_text: str, project_name: str | None = None, source_path: str | None = None) -> dict[str, Any]:
    sections = extract_sections(source_text)
    name = derive_project_name(source_text, project_name)
    goals = derive_goals(sections, source_text)
    constraints = derive_constraints(sections, source_text)
    acceptance = derive_acceptance_criteria(sections, goals)
    requirements = derive_requirements(goals, constraints, acceptance)
    user_stories = derive_user_stories(requirements)

    problem = (
        "Ad-hoc agent prompts lose requirements, produce weak task breakdowns, "
        "and leave no auditable quality signal for generated planning artifacts."
    )
    if sections.get("overview"):
        first_sentence = split_sentences(sections["overview"])
        if first_sentence:
            problem = first_sentence[0]

    requirement_coverage = [
        {
            "requirement_id": requirement["id"],
            "user_story_ids": [
                story["id"] for story in user_stories if requirement["id"] in story["requirements"]
            ],
            "acceptance_criteria_ids": requirement["acceptance_criteria"],
        }
        for requirement in requirements
    ]

    return {
        "schema_version": "1.0",
        "project": {
            "name": name,
            "slug": slugify(name, "grill-to-spec"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "source": {
            "path": source_path,
            "summary": clean_text(source_text[:500]),
            "line_count": len(source_text.splitlines()),
        },
        "problem_statement": problem,
        "goals": goals,
        "non_goals": [
            "Do not implement product code before the PRD, task artifacts, and quality gates exist.",
            "Do not auto-send implementation handoffs or run Spec Kit implementation commands during planning handoff creation.",
            "Do not require a network server for local validation or Spec Kit handoff generation.",
            "Do not require third-party archive tooling beyond the Python standard library.",
        ],
        "actors": [
            {"name": "Codex user", "role": "Supplies answers and approves phase gates."},
            {"name": "Codex agent", "role": "Runs the skill chain and writes artifacts."},
            {"name": "reviewer", "role": "Uses eval output to judge planning quality."},
        ],
        "user_stories": user_stories,
        "requirements": requirements,
        "acceptance_criteria": acceptance,
        "implementation_decisions": [
            "Bundle grill-me, to-prd, to-spec, and evaluation as Codex skills in one plugin.",
            "Bundle Spec Kit scripts, command templates, and workflow metadata under vendor/spec-kit.",
            "Use deterministic local JSON artifacts as the fallback contract for tests and offline runs.",
            "Represent task artifacts as vertical slices with task-level PRD references and blocker metadata.",
            "Package the final evaluated handoff as a Spec-Kit archive that includes grill-me and local Spec Kit assets.",
            "Keep implementation execution as a separate approval-gated downstream step outside grill-to-spec completion.",
        ],
        "testing_decisions": [
            "Validate the generator with unit tests that read the emitted JSON artifacts.",
            "Treat traceability, actionability, and acceptance criteria coverage as first-class eval dimensions.",
            "Keep tests dependency-free so the plugin can be verified in a sandboxed Codex workspace.",
        ],
        "traceability": {
            "requirement_coverage": requirement_coverage,
            "artifact_contracts": [
                "PRD.json",
                "task-artifacts/index.json",
                "task-artifacts/TASKART-*.json",
                "evals/evaluation.json",
                "archive/*-spec-kit-archive.zip",
            ],
        },
        "quality_gates": [
            {"id": "QG-001", "name": "PRD schema completeness", "threshold": 1.0},
            {"id": "QG-002", "name": "Every task artifact has tasks", "threshold": 1.0},
            {"id": "QG-003", "name": "Every task has PRD references", "threshold": 1.0},
            {"id": "QG-004", "name": "Overall eval score", "threshold": 0.90},
            {"id": "QG-005", "name": "Archive contains eval and grill-me", "threshold": 1.0},
        ],
    }


def task_artifact_category(requirement: dict[str, Any]) -> tuple[str, str, str]:
    text = requirement["statement"].lower()

    def has_terms(*terms: str) -> bool:
        return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)

    if has_terms("evaluation", "evaluate", "eval", "evals", "score", "scores", "quality", "archive", "bundles", "share"):
        return ("TASKART-004", "Evaluate and validate outputs", "AFK")
    if has_terms("question", "interview", "grill", "grilling", "ask", "phase-gated", "interactive"):
        return ("TASKART-001", "Grill and phase-gate discovery", "HITL")
    if has_terms("spec kit", "spec-kit", "script", "scripts", "template", "templates", "workflow"):
        return ("TASKART-005", "Prepare Spec Kit local asset handoff", "AFK")
    if has_terms("prd", "prd.json", "requirement", "requirements", "story", "stories", "acceptance"):
        return ("TASKART-002", "Generate machine-actionable PRD", "AFK")
    if has_terms("task artifact", "task artifacts", "task_artifact", "task_artifacts", "task", "tasks", "decompose", "blocker", "blockers", "slice", "slices"):
        return ("TASKART-003", "Create traceable task artifacts and tasks", "AFK")
    return ("TASKART-003", "Create traceable task artifacts and tasks", "AFK")


def build_task_artifacts(prd: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    task_index = 1
    stories_by_requirement = {
        requirement_id: story["id"]
        for story in prd["user_stories"]
        for requirement_id in story.get("requirements", [])
    }
    criteria_by_id = {item["id"]: item["statement"] for item in prd["acceptance_criteria"]}

    for requirement in prd["requirements"]:
        task_artifact_id, title, task_artifact_type = task_artifact_category(requirement)
        grouped.setdefault(
            task_artifact_id,
            {
                "schema_version": "1.0",
                "id": task_artifact_id,
                "title": title,
                "type": task_artifact_type,
                "blocked_by": [],
                "user_stories": [],
                "tasks": [],
            },
        )
        story_id = stories_by_requirement.get(requirement["id"])
        if story_id and story_id not in grouped[task_artifact_id]["user_stories"]:
            grouped[task_artifact_id]["user_stories"].append(story_id)

        criteria = [
            criteria_by_id[criteria_id]
            for criteria_id in requirement.get("acceptance_criteria", [])
            if criteria_id in criteria_by_id
        ] or ["Generated artifact satisfies the linked PRD requirement."]

        grouped[task_artifact_id]["tasks"].append(
            {
                "id": f"TASK-{task_index:03d}",
                "title": requirement["statement"][:90].rstrip("."),
                "description": f"Plan or verify the workflow behavior for {requirement['id']} without executing downstream implementation.",
                "prd_refs": [requirement["id"], *requirement.get("acceptance_criteria", [])],
                "acceptance_criteria": criteria,
                "verification": [
                    "Run python3 -m unittest tests/test_grill_to_spec.py",
                    "Run python3 scripts/grill_to_spec.py validate --output spec",
                ],
            }
        )
        task_index += 1

    task_artifacts = [grouped[key] for key in sorted(grouped)]
    existing_ids = {item["id"] for item in task_artifacts}
    dependency_order = ["TASKART-001", "TASKART-002", "TASKART-003", "TASKART-004", "TASKART-005"]
    for task_artifact in task_artifacts:
        position = dependency_order.index(task_artifact["id"]) if task_artifact["id"] in dependency_order else 0
        blockers = [candidate for candidate in dependency_order[:position] if candidate in existing_ids]
        task_artifact["blocked_by"] = blockers[-1:] if blockers else []
    return task_artifacts


def validate_prd(prd: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_PRD_KEYS:
        if key not in prd:
            errors.append(f"PRD missing key: {key}")
    for key in ["goals", "user_stories", "requirements", "acceptance_criteria"]:
        if not prd.get(key):
            errors.append(f"PRD key must be non-empty: {key}")
    requirement_ids = {item.get("id") for item in prd.get("requirements", [])}
    coverage_ids = {
        item.get("requirement_id")
        for item in prd.get("traceability", {}).get("requirement_coverage", [])
    }
    if requirement_ids != coverage_ids:
        errors.append("PRD traceability does not cover every requirement")
    return errors


def validate_task_artifacts(task_artifacts: list[dict[str, Any]], prd: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prd_refs = {item["id"] for item in prd.get("requirements", [])}
    prd_refs.update(item["id"] for item in prd.get("acceptance_criteria", []))
    task_ids: set[str] = set()
    covered_requirements: set[str] = set()

    for task_artifact in task_artifacts:
        if not task_artifact.get("tasks"):
            errors.append(f"{task_artifact.get('id', '<unknown>')} has no tasks")
        for task in task_artifact.get("tasks", []):
            task_id = task.get("id")
            if task_id in task_ids:
                errors.append(f"Duplicate task id: {task_id}")
            task_ids.add(task_id)
            refs = set(task.get("prd_refs", []))
            if not refs:
                errors.append(f"{task_id} has no PRD references")
            if not refs.intersection(prd_refs):
                errors.append(f"{task_id} references unknown PRD ids")
            covered_requirements.update(ref for ref in refs if ref.startswith("REQ-"))
            if not task.get("acceptance_criteria"):
                errors.append(f"{task_id} has no acceptance criteria")

    expected_requirements = {item["id"] for item in prd.get("requirements", [])}
    if expected_requirements and covered_requirements != expected_requirements:
        missing = ", ".join(sorted(expected_requirements - covered_requirements))
        errors.append(f"Task artifacts do not cover every requirement: {missing}")
    return errors


def score_fraction(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)


def evaluate_outputs(
    prd: dict[str, Any],
    task_artifacts: list[dict[str, Any]],
    spec_kit_assets_path: Path | None = None,
) -> dict[str, Any]:
    prd_errors = validate_prd(prd)
    task_artifact_errors = validate_task_artifacts(task_artifacts, prd)
    tasks = [task for task_artifact in task_artifacts for task in task_artifact.get("tasks", [])]
    complete_prd_keys = sum(1 for key in REQUIRED_PRD_KEYS if prd.get(key))
    tasks_with_refs = sum(1 for task in tasks if task.get("prd_refs"))
    tasks_with_criteria = sum(1 for task in tasks if task.get("acceptance_criteria"))
    task_artifacts_with_tasks = sum(1 for task_artifact in task_artifacts if task_artifact.get("tasks"))
    requirements = prd.get("requirements", [])
    requirements_with_criteria = sum(1 for item in requirements if item.get("acceptance_criteria"))
    testing_decision_score = min(1.0, len(prd.get("testing_decisions", [])) / 3)
    requirement_testability = score_fraction(requirements_with_criteria, len(requirements))
    spec_kit_assets_path = spec_kit_assets_path or ROOT / "vendor" / "spec-kit"
    existing_assets = sum(
        1 for relative_path in REQUIRED_SPEC_KIT_ASSETS if (spec_kit_assets_path / relative_path).exists()
    )
    safety_findings = planning_safety_findings(spec_kit_assets_path)
    high_safety_findings = [
        finding for finding in safety_findings if finding["severity"] in {"critical", "high"}
    ]

    scores = {
        "prd_completeness": score_fraction(complete_prd_keys, len(REQUIRED_PRD_KEYS)),
        "task_artifact_traceability": score_fraction(tasks_with_refs + task_artifacts_with_tasks, len(tasks) + len(task_artifacts)),
        "task_actionability": score_fraction(tasks_with_criteria, len(tasks)),
        "testability": round((requirement_testability * 0.7) + (testing_decision_score * 0.3), 3),
        "spec_kit_asset_readiness": score_fraction(existing_assets, len(REQUIRED_SPEC_KIT_ASSETS)),
    }
    overall = round(sum(scores.values()) / len(scores), 3)

    risks = [
        "Implementation remains approval-gated after PRD, task artifacts, eval, archive, and validation are complete."
    ]
    if prd_errors or task_artifact_errors:
        risks.extend(prd_errors + task_artifact_errors)
    if high_safety_findings:
        risks.extend(finding["message"] for finding in high_safety_findings)
    elif existing_assets != len(REQUIRED_SPEC_KIT_ASSETS):
        missing_assets = [
            relative_path
            for relative_path in REQUIRED_SPEC_KIT_ASSETS
            if not (spec_kit_assets_path / relative_path).exists()
        ]
        risks.append(f"Missing bundled Spec Kit assets: {', '.join(missing_assets)}")
    else:
        risks.append("Spec Kit scripts and templates are bundled locally; no server startup is required.")

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall,
        "scores": scores,
        "strengths": [
            "PRD requirements, acceptance criteria, and task artifact tasks share stable IDs.",
            "Task artifacts are vertical slices with task-level verification commands.",
        ],
        "risks": risks,
        "planning_safety_findings": safety_findings,
        "recommendations": [
            "Review HITL task artifacts before requesting downstream implementation.",
            "Treat the quarantined Spec Kit implement reference as downstream-only material that requires separate explicit user approval.",
            "Use the vendored Spec Kit command templates and scripts when producing agent-native spec handoffs.",
            "Create the Spec-Kit archive after eval so the shared handoff contains the latest score.",
        ],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def infer_specs_output_dir(output_dir: Path | str) -> Path:
    output = Path(output_dir)
    if output.name == "spec":
        return output.parent / "specs"
    return output / "specs"


def resolve_specs_output_dir(output_dir: Path | str, specs_output_dir: Path | str | None) -> Path:
    return Path(specs_output_dir) if specs_output_dir is not None else infer_specs_output_dir(output_dir)


def requirement_number(requirement_id: str) -> int:
    match = re.search(r"(\d+)$", requirement_id)
    return int(match.group(1)) if match else 0


def functional_requirement_id(requirement_id: str) -> str:
    return f"FR-{requirement_number(requirement_id):03d}"


def task_number(task_id: str) -> int:
    match = re.search(r"(\d+)$", task_id)
    return int(match.group(1)) if match else 0


def spec_task_id(task_id: str) -> str:
    return f"T{task_number(task_id):03d}"


def story_label(story_id: str | None) -> str:
    if not story_id:
        return "US1"
    return f"US{requirement_number(story_id)}"


def requirement_story_map(prd: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for story in prd.get("user_stories", []):
        for requirement_id in story.get("requirements", []):
            mapping[requirement_id] = story.get("id", "")
    return mapping


def acceptance_by_id(prd: dict[str, Any]) -> dict[str, str]:
    return {item["id"]: item["statement"] for item in prd.get("acceptance_criteria", [])}


def render_spec_markdown(prd: dict[str, Any]) -> str:
    project = prd["project"]["name"]
    slug = prd["project"]["slug"]
    criteria = acceptance_by_id(prd)
    lines = [
        f"# Feature Specification: {project}",
        "",
        f"**Feature Branch**: `001-{slug}`",
        f"**Created**: {prd['project']['generated_at']}",
        "**Status**: Draft planning handoff",
        f"**Input**: `{prd['source'].get('path') or 'resolved grill context'}`",
        "",
        "## Planning Boundary",
        "",
        "This handoff is planning-only. It may guide a later implementation request, but it must not run implementation commands, edit product code, or mark tasks complete.",
        "",
        "## User Scenarios & Testing",
        "",
    ]

    for index, story in enumerate(prd.get("user_stories", []), start=1):
        story_id = story["id"]
        linked_criteria = [
            criteria[criteria_id]
            for requirement in prd.get("requirements", [])
            if requirement["id"] in story.get("requirements", [])
            for criteria_id in requirement.get("acceptance_criteria", [])
            if criteria_id in criteria
        ]
        lines.extend(
            [
                f"### User Story {index} - **{story_id}** (Priority: P{index})",
                "",
                story["story"],
                "",
                f"**Why this priority**: Covers {', '.join(story.get('requirements', []))}.",
                "",
                "**Independent Test**: Review the linked acceptance scenarios and verification commands without executing implementation.",
                "",
                "**Acceptance Scenarios**:",
                "",
            ]
        )
        for criteria_index, statement in enumerate(linked_criteria or ["Review the linked PRD requirement."], start=1):
            lines.append(f"{criteria_index}. {statement}")
        lines.extend(["", "---", ""])

    lines.extend(
        [
            "## Requirements",
            "",
            "### Functional Requirements",
            "",
        ]
    )
    for requirement in prd.get("requirements", []):
        fr_id = functional_requirement_id(requirement["id"])
        criteria_ids = ", ".join(requirement.get("acceptance_criteria", []))
        lines.append(f"- **{fr_id}** (`{requirement['id']}`): System MUST {requirement['statement'].rstrip('.')}. Acceptance: {criteria_ids}.")

    lines.extend(["", "### Traceability", ""])
    story_by_requirement = requirement_story_map(prd)
    for requirement in prd.get("requirements", []):
        fr_id = functional_requirement_id(requirement["id"])
        story_id = story_by_requirement.get(requirement["id"], "US-001")
        criteria_ids = ", ".join(requirement.get("acceptance_criteria", []))
        lines.append(f"- `{fr_id}` -> `{requirement['id']}` -> `{story_id}` -> {criteria_ids}")

    lines.extend(["", "## Success Criteria", ""])
    for gate in prd.get("quality_gates", []):
        lines.append(f"- **{gate['id']}**: {gate['name']} threshold `{gate['threshold']}`.")

    lines.extend(["", "## Assumptions", ""])
    for non_goal in prd.get("non_goals", []):
        lines.append(f"- {non_goal}")

    return "\n".join(lines)


def render_plan_markdown(prd: dict[str, Any], feature_dir: Path) -> str:
    project = prd["project"]["name"]
    slug = prd["project"]["slug"]
    lines = [
        f"# Implementation Plan: {project}",
        "",
        f"**Branch**: `001-{slug}` | **Date**: {prd['project']['generated_at']} | **Spec**: `spec.md`",
        f"**Input**: Feature specification from `{feature_dir.as_posix()}/spec.md`",
        "",
        "## Summary",
        "",
        prd["problem_statement"],
        "",
        "## Planning Boundary",
        "",
        "This plan is a Spec Kit-compatible handoff. Implementation requires a separate post-review request; this workflow stops after PRD, specs, tasks, eval, validation, and archive generation.",
        "",
        "## Technical Context",
        "",
        "**Language/Version**: NEEDS CLARIFICATION in downstream implementation plan",
        "**Primary Dependencies**: NEEDS CLARIFICATION in downstream implementation plan",
        "**Storage**: N/A unless the reviewed PRD adds persistence requirements",
        "**Testing**: Use the PRD acceptance criteria and generated task verification commands",
        "**Target Platform**: Codex workspace with local Spec Kit assets",
        "**Project Type**: Planning handoff",
        "**Constraints**: Planning artifacts only; no product source edits in this workflow",
        "",
        "## Constitution Check",
        "",
        "- PASS: PRD exists with stable user story, requirement, acceptance, and quality gate IDs.",
        "- PASS: Task artifacts remain unchecked and approval-gated.",
        "- PASS: Active Spec Kit command templates exclude implementation execution.",
        "",
        "## Traceability",
        "",
    ]
    for requirement in prd.get("requirements", []):
        fr_id = functional_requirement_id(requirement["id"])
        criteria_ids = ", ".join(requirement.get("acceptance_criteria", []))
        lines.append(f"- `{fr_id}` maps to `{requirement['id']}` and acceptance `{criteria_ids}`.")
    lines.extend(["", "## Quality Gates", ""])
    for gate in prd.get("quality_gates", []):
        lines.append(f"- `{gate['id']}` {gate['name']}: threshold `{gate['threshold']}`.")
    lines.extend(
        [
            "",
            "## Project Structure",
            "",
            "### Documentation (this feature)",
            "",
            "```text",
            f"{feature_dir.as_posix()}/",
            "|-- spec.md",
            "|-- plan.md",
            "|-- tasks.md",
            "|-- research.md",
            "|-- data-model.md",
            "|-- quickstart.md",
            "|-- contracts/",
            "`-- checklists/",
            "```",
        ]
    )
    return "\n".join(lines)


def task_requirement_ref(task: dict[str, Any]) -> str:
    for ref in task.get("prd_refs", []):
        if ref.startswith("REQ-"):
            return ref
    return "REQ-001"


def render_tasks_markdown(prd: dict[str, Any], task_artifacts: list[dict[str, Any]]) -> str:
    project = prd["project"]["name"]
    story_by_requirement = requirement_story_map(prd)
    lines = [
        f"# Tasks: {project}",
        "",
        f"**Input**: Design documents from `/specs/{prd['project']['slug']}/`",
        "**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/",
        "",
        "**Planning Boundary**: All tasks are unchecked handoff items. Do not mark any task complete or edit product source until the user makes a separate post-review implementation request.",
        "",
        "## Format: `[ID] [P?] [Story] Description`",
        "",
        "Tasks use Spec Kit checklist syntax and include PRD references for traceability.",
        "",
    ]

    phase = 1
    for task_artifact in task_artifacts:
        lines.extend(
            [
                f"## Phase {phase}: {task_artifact['title']} ({task_artifact['id']})",
                "",
                f"**Type**: {task_artifact['type']}",
                f"**Blocked By**: {', '.join(task_artifact.get('blocked_by', [])) or 'None'}",
                "",
            ]
        )
        for task in task_artifact.get("tasks", []):
            requirement_id = task_requirement_ref(task)
            label = story_label(story_by_requirement.get(requirement_id))
            fr_id = functional_requirement_id(requirement_id)
            marker = "[P] " if task_artifact["type"] == "AFK" else ""
            path = "spec/PRD.json"
            refs = ", ".join(task.get("prd_refs", []))
            lines.append(
                f"- [ ] {spec_task_id(task['id'])} {marker}[{label}] Execute downstream handoff item for {fr_id}/{requirement_id} using {path}; refs: {refs}"
            )
        lines.extend(["", "---", ""])
        phase += 1

    lines.extend(
        [
            "## Dependencies & Execution Order",
            "",
            "- Review `spec.md`, `plan.md`, and `spec/PRD.json` before selecting tasks.",
            "- Respect each task artifact's `blocked_by` list.",
            "- Keep all boxes unchecked in this planning handoff.",
            "- Implementation starts only after a separate explicit request.",
            "",
            "## Implementation Strategy",
            "",
            "Use User Story 1 as the first downstream slice after review. Run the listed verification commands before marking any later implementation task complete.",
        ]
    )
    return "\n".join(lines)


def render_checklist_markdown(prd: dict[str, Any]) -> str:
    lines = [
        f"# Requirements Checklist: {prd['project']['name']}",
        "",
        "## Planning Quality",
        "",
    ]
    for requirement in prd.get("requirements", []):
        fr_id = functional_requirement_id(requirement["id"])
        criteria_ids = ", ".join(requirement.get("acceptance_criteria", []))
        lines.append(f"- [ ] {fr_id} maps to `{requirement['id']}` and acceptance criteria `{criteria_ids}`.")
    lines.extend(
        [
            "- [ ] No task is checked complete in `tasks.md`.",
            "- [ ] Implementation remains a separate post-review request.",
        ]
    )
    return "\n".join(lines)


def render_research_markdown(prd: dict[str, Any]) -> str:
    lines = [f"# Research: {prd['project']['name']}", "", "## Goals", ""]
    lines.extend(f"- {goal}" for goal in prd.get("goals", []))
    lines.extend(["", "## Non-Goals", ""])
    lines.extend(f"- {item}" for item in prd.get("non_goals", []))
    lines.extend(["", "## Testing Decisions", ""])
    lines.extend(f"- {item}" for item in prd.get("testing_decisions", []))
    return "\n".join(lines)


def render_data_model_markdown(prd: dict[str, Any]) -> str:
    lines = [
        f"# Data Model: {prd['project']['name']}",
        "",
        "No product data entities were inferred by the deterministic fallback generator. The canonical machine-readable planning entities are:",
        "",
        "- PRD requirement: stable `REQ-###` item in `spec/PRD.json`.",
        "- User story: stable `US-###` item linked to one or more requirements.",
        "- Acceptance criterion: stable `AC-###` item linked through requirements.",
        "- Task artifact: vertical-slice JSON work item under `spec/task-artifacts/`.",
    ]
    return "\n".join(lines)


def render_contracts_markdown(prd: dict[str, Any]) -> str:
    lines = [f"# Acceptance Contracts: {prd['project']['name']}", ""]
    for criterion in prd.get("acceptance_criteria", []):
        lines.append(f"- **{criterion['id']}**: {criterion['statement']}")
    return "\n".join(lines)


def render_quickstart_markdown(prd: dict[str, Any]) -> str:
    slug = prd["project"]["slug"]
    return "\n".join(
        [
            f"# Quickstart: {prd['project']['name']}",
            "",
            "Review the generated handoff without starting implementation:",
            "",
            "```bash",
            "python3 -B scripts/grill_to_spec.py validate --output spec --specs-output specs",
            "python3 -B scripts/grill_to_spec.py eval --output spec",
            "python3 -B scripts/grill_to_spec.py archive --output spec --specs-output specs",
            "```",
            "",
            f"Spec Kit markdown lives in `specs/{slug}/`. Implementation requires a separate explicit request after review.",
        ]
    )


def materialize_spec_kit_handoff(
    output_dir: Path | str = "spec",
    specs_output_dir: Path | str | None = None,
) -> Path:
    output = Path(output_dir)
    specs_output = resolve_specs_output_dir(output, specs_output_dir)
    prd, task_artifacts = load_generated(output)
    feature_dir = specs_output / prd["project"]["slug"]

    write_markdown(feature_dir / "spec.md", render_spec_markdown(prd))
    write_markdown(feature_dir / "plan.md", render_plan_markdown(prd, feature_dir))
    write_markdown(feature_dir / "tasks.md", render_tasks_markdown(prd, task_artifacts))
    write_markdown(feature_dir / "checklists" / "requirements.md", render_checklist_markdown(prd))
    write_markdown(feature_dir / "research.md", render_research_markdown(prd))
    write_markdown(feature_dir / "data-model.md", render_data_model_markdown(prd))
    write_markdown(feature_dir / "contracts" / "acceptance-criteria.md", render_contracts_markdown(prd))
    write_markdown(feature_dir / "quickstart.md", render_quickstart_markdown(prd))
    return feature_dir


def validate_spec_kit_handoff(
    prd: dict[str, Any],
    task_artifacts: list[dict[str, Any]],
    specs_output_dir: Path,
) -> list[str]:
    errors: list[str] = []
    feature_dir = specs_output_dir / prd["project"]["slug"]
    required_files = [
        "spec.md",
        "plan.md",
        "tasks.md",
        "checklists/requirements.md",
    ]
    for relative_path in required_files:
        if not (feature_dir / relative_path).exists():
            errors.append(f"Missing specs/{prd['project']['slug']}/{relative_path}")
    if errors:
        return errors

    spec_text = (feature_dir / "spec.md").read_text()
    plan_text = (feature_dir / "plan.md").read_text()
    tasks_text = (feature_dir / "tasks.md").read_text()

    for requirement in prd.get("requirements", []):
        fr_id = functional_requirement_id(requirement["id"])
        if fr_id not in spec_text or requirement["id"] not in spec_text:
            errors.append(f"Spec markdown missing trace for {fr_id}/{requirement['id']}")
    for gate in prd.get("quality_gates", []):
        if gate["id"] not in plan_text:
            errors.append(f"Plan markdown missing quality gate {gate['id']}")
    if re.search(r"(?i)- \[x\]", tasks_text):
        errors.append("Spec Kit tasks.md contains completed tasks")
    for task_artifact in task_artifacts:
        for task in task_artifact.get("tasks", []):
            if spec_task_id(task["id"]) not in tasks_text:
                errors.append(f"Spec Kit tasks.md missing {spec_task_id(task['id'])}")
    return errors


def planning_safety_findings(spec_kit_assets_path: Path | None = None) -> list[dict[str, str]]:
    assets = spec_kit_assets_path or ROOT / "vendor" / "spec-kit"
    findings: list[dict[str, str]] = []
    active_implement = assets / "templates" / "commands" / "implement.md"
    if active_implement.exists():
        findings.append(
            {
                "severity": "high",
                "code": "active-implement-command",
                "message": "Active Spec Kit command templates include implement.md.",
            }
        )

    scans = [
        (assets / "templates" / "vscode-settings.json", "vscode-speckit-implement"),
        (assets / "workflows" / "speckit" / "workflow.yml", "workflow-speckit-implement"),
        (assets / "templates" / "commands" / "tasks.md", "tasks-implement-handoff"),
    ]
    forbidden = ["speckit.implement", "label: Implement Project", "agent: speckit.implement"]
    for path, code in scans:
        if not path.exists():
            continue
        text = path.read_text()
        if any(token in text for token in forbidden):
            findings.append(
                {
                    "severity": "high",
                    "code": code,
                    "message": f"Active Spec Kit asset still references implementation handoff behavior: {path.relative_to(assets)}.",
                }
            )
    return findings


def archive_entry(path: Path, arcname: str) -> tuple[Path, str]:
    if not path.exists():
        raise FileNotFoundError(f"Archive input is missing: {path}")
    return path, arcname


def collect_archive_entries(output_dir: Path, specs_output_dir: Path | None = None) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = [
        archive_entry(ROOT / "README.md", "README.md"),
        archive_entry(ROOT / ".codex-plugin" / "plugin.json", ".codex-plugin/plugin.json"),
        archive_entry(ROOT / "evals" / "rubric.json", "evals/rubric.json"),
        archive_entry(ROOT / "scripts" / "__init__.py", "scripts/__init__.py"),
        archive_entry(ROOT / "scripts" / "grill_to_spec.py", "scripts/grill_to_spec.py"),
    ]

    for directory in ["schemas", "skills", "vendor"]:
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file():
                entries.append(archive_entry(path, path.relative_to(ROOT).as_posix()))

    for path in sorted(output_dir.rglob("*.json")):
        relative = path.relative_to(output_dir)
        if "archive" in relative.parts:
            continue
        entries.append(archive_entry(path, f"spec/{relative.as_posix()}"))

    if specs_output_dir is not None and specs_output_dir.exists():
        for path in sorted(specs_output_dir.rglob("*")):
            if path.is_file():
                entries.append(archive_entry(path, f"specs/{path.relative_to(specs_output_dir).as_posix()}"))

    return entries


def create_archive(
    output_dir: Path | str = "spec",
    specs_output_dir: Path | str | None = None,
    archive_dir: Path | str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    specs_output = resolve_specs_output_dir(output, specs_output_dir)
    materialize_spec_kit_handoff(output_dir=output, specs_output_dir=specs_output)
    prd, task_artifacts = load_generated(output)
    evaluation = evaluate_outputs(prd, task_artifacts)
    eval_path = output / "evals" / "evaluation.json"
    write_json(eval_path, evaluation)

    validation_errors = validate_output_dir(output, specs_output_dir=specs_output)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    project_name = prd["project"]["name"]
    archive_output = Path(archive_dir) if archive_dir is not None else output / "archive"
    archive_output.mkdir(parents=True, exist_ok=True)
    archive_stem = f"{slugify(project_name, 'grill-to-spec')}-spec-kit-archive"
    archive_path = archive_output / f"{archive_stem}.zip"
    manifest_path = archive_output / f"{archive_stem}-manifest.json"
    entries = collect_archive_entries(output, specs_output_dir=specs_output)
    entry_names = [arcname for _, arcname in entries]
    entry_names.append("archive-manifest.json")

    manifest = {
        "schema_version": "1.0",
        "archive_format": "spec-kit",
        "project": project_name,
        "generated_at": evaluation["generated_at"],
        "archive": archive_path.name,
        "evaluation": "spec/evals/evaluation.json",
        "overall_score": evaluation["overall_score"],
        "planning_safety_findings": evaluation["planning_safety_findings"],
        "specs": f"specs/{prd['project']['slug']}/",
        "entries": entry_names,
    }
    write_json(manifest_path, manifest)

    with zipfile.ZipFile(archive_path, "w") as archive:
        for path, arcname in entries:
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo("archive-manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, manifest_path.read_bytes())

    return {
        "archive": archive_path,
        "manifest": manifest_path,
        "evaluation": eval_path,
        "entries": entry_names,
    }


def generate_artifacts(
    source_text: str,
    output_dir: Path | str,
    project_name: str | None = None,
    source_path: str | None = None,
    specs_output_dir: Path | str | None | object = DEFAULT_SPECS_OUTPUT,
) -> dict[str, Any]:
    output = Path(output_dir)
    prd = build_prd(source_text, project_name=project_name, source_path=source_path)
    task_artifacts = build_task_artifacts(prd)
    evaluation = evaluate_outputs(prd, task_artifacts)

    prd_path = output / "PRD.json"
    task_artifacts_dir = output / "task-artifacts"
    eval_path = output / "evals" / "evaluation.json"
    write_json(prd_path, prd)

    task_artifact_paths: list[Path] = []
    for task_artifact in task_artifacts:
        artifact_number = task_artifact["id"].split("-")[-1].lower()
        file_name = f"task-artifact-{artifact_number}-{slugify(task_artifact['title'])}.json"
        path = task_artifacts_dir / file_name
        write_json(path, task_artifact)
        task_artifact_paths.append(path)

    index = {
        "schema_version": "1.0",
        "project": prd["project"]["name"],
        "prd": "../PRD.json",
        "task_artifacts": [
            {
                "id": task_artifact["id"],
                "title": task_artifact["title"],
                "path": path.name,
                "task_count": len(task_artifact["tasks"]),
                "blocked_by": task_artifact["blocked_by"],
            }
            for task_artifact, path in zip(task_artifacts, task_artifact_paths)
        ],
        "task_count": sum(len(task_artifact["tasks"]) for task_artifact in task_artifacts),
    }
    index_path = task_artifacts_dir / "index.json"
    write_json(index_path, index)
    write_json(eval_path, evaluation)
    spec_kit_dir = None
    if specs_output_dir is DEFAULT_SPECS_OUTPUT:
        spec_kit_dir = materialize_spec_kit_handoff(output_dir=output, specs_output_dir=infer_specs_output_dir(output))
    elif specs_output_dir is not None:
        spec_kit_dir = materialize_spec_kit_handoff(output_dir=output, specs_output_dir=Path(specs_output_dir))

    return ArtifactPaths(
        prd=prd_path,
        task_artifacts=task_artifact_paths,
        task_artifact_index=index_path,
        evaluation=eval_path,
        spec_kit_dir=spec_kit_dir,
    ).as_dict()


def load_generated(output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prd_path = output_dir / "PRD.json"
    task_artifacts_dir = output_dir / "task-artifacts"
    prd = json.loads(prd_path.read_text())
    task_artifacts = [
        json.loads(path.read_text())
        for path in sorted(task_artifacts_dir.glob("TASKART-*.json"))
    ]
    if not task_artifacts:
        task_artifacts = [
            json.loads(path.read_text())
            for path in sorted(task_artifacts_dir.glob("task-artifact-*.json"))
            if path.name != "index.json"
        ]
    return prd, task_artifacts


def validate_output_dir(output_dir: Path, specs_output_dir: Path | str | None = None) -> list[str]:
    output_dir = Path(output_dir)
    errors: list[str] = []
    if not (output_dir / "PRD.json").exists():
        return ["Missing PRD.json"]
    if not (output_dir / "task-artifacts").exists():
        return ["Missing task-artifacts directory"]
    prd, task_artifacts = load_generated(output_dir)
    errors.extend(validate_prd(prd))
    errors.extend(validate_task_artifacts(task_artifacts, prd))
    report = evaluate_outputs(prd, task_artifacts)
    if report["overall_score"] < 0.90:
        errors.append(f"Overall eval score below 0.90: {report['overall_score']}")
    specs_output = resolve_specs_output_dir(output_dir, specs_output_dir)
    errors.extend(validate_spec_kit_handoff(prd, task_artifacts, specs_output))
    high_safety_findings = [
        finding
        for finding in planning_safety_findings()
        if finding["severity"] in {"critical", "high"}
    ]
    for finding in high_safety_findings:
        errors.append(f"Planning safety finding: {finding['message']}")
    if not (output_dir / "task-artifacts" / "index.json").exists():
        errors.append("Missing task-artifacts/index.json")
    if not (output_dir / "evals" / "evaluation.json").exists():
        errors.append("Missing evals/evaluation.json")
    return errors


def cmd_generate(args: argparse.Namespace) -> int:
    source_path = Path(args.source)
    source_text = source_path.read_text()
    artifacts = generate_artifacts(
        source_text=source_text,
        output_dir=Path(args.output),
        project_name=args.project_name,
        source_path=str(source_path),
        specs_output_dir=Path(args.specs_output),
    )
    printable = {
        key: [str(path) for path in value] if isinstance(value, list) else str(value)
        for key, value in artifacts.items()
    }
    print(json.dumps(printable, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate_output_dir(Path(args.output), specs_output_dir=Path(args.specs_output))
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"status": "passed", "output": args.output, "specs_output": args.specs_output}, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    prd, task_artifacts = load_generated(output_dir)
    report = evaluate_outputs(prd, task_artifacts)
    eval_path = output_dir / "evals" / "evaluation.json"
    write_json(eval_path, report)
    print(json.dumps(report, indent=2))
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    try:
        result = create_archive(
            output_dir=Path(args.output),
            specs_output_dir=Path(args.specs_output),
            archive_dir=Path(args.archive_dir) if args.archive_dir else None,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1

    printable = {
        key: [str(path) for path in value] if isinstance(value, list) else str(value)
        for key, value in result.items()
    }
    printable["status"] = "passed"
    print(json.dumps(printable, indent=2))
    return 0


def cmd_materialize(args: argparse.Namespace) -> int:
    try:
        feature_dir = materialize_spec_kit_handoff(
            output_dir=Path(args.output),
            specs_output_dir=Path(args.specs_output),
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps({"status": "passed", "spec_kit_dir": str(feature_dir)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and validate grill-to-spec artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate PRD.json, task artifacts, eval report, and Spec Kit markdown.")
    generate.add_argument("--source", required=True, help="Source research, grill summary, or PRD markdown.")
    generate.add_argument("--output", default="spec", help="Artifact output directory.")
    generate.add_argument("--specs-output", default="specs", help="Spec Kit markdown output directory.")
    generate.add_argument("--project-name", help="Override project name.")
    generate.set_defaults(func=cmd_generate)

    validate = subparsers.add_parser("validate", help="Validate generated artifacts.")
    validate.add_argument("--output", default="spec", help="Artifact output directory.")
    validate.add_argument("--specs-output", default="specs", help="Spec Kit markdown output directory.")
    validate.set_defaults(func=cmd_validate)

    evaluate = subparsers.add_parser("eval", help="Re-run the artifact quality eval.")
    evaluate.add_argument("--output", default="spec", help="Artifact output directory.")
    evaluate.set_defaults(func=cmd_eval)

    archive = subparsers.add_parser("archive", help="Create a Spec-Kit archive with evals and plugin assets.")
    archive.add_argument("--output", default="spec", help="Artifact output directory.")
    archive.add_argument("--specs-output", default="specs", help="Spec Kit markdown output directory.")
    archive.add_argument("--archive-dir", help="Archive output directory. Defaults to <output>/archive.")
    archive.set_defaults(func=cmd_archive)

    materialize = subparsers.add_parser("materialize", help="Render Spec Kit markdown from existing PRD and task artifacts.")
    materialize.add_argument("--output", default="spec", help="Artifact output directory.")
    materialize.add_argument("--specs-output", default="specs", help="Spec Kit markdown output directory.")
    materialize.set_defaults(func=cmd_materialize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
