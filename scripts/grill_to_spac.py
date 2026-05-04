#!/usr/bin/env python3
"""Generate and evaluate PRD.json and spack task artifacts.

The plugin skills are conversational, but this script keeps the artifact format
deterministic so tests and evals can verify the workflow without an MCP server.
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

CANONICAL_GRILL_TO_SPAC_GOALS = [
    "Run a phase-gated Codex workflow that starts with Grill-Me discovery before implementation.",
    "Ask one question at a time during grilling and include the recommended answer.",
    "Create PRD.json with user stories, requirements, acceptance criteria, implementation decisions, testing decisions, and traceability.",
    "Create spacks that decompose PRD requirements into vertical-slice tasks with blockers, HITL/AFK classification, and PRD references.",
    "Register Spec-Kit MCP for init, specify, plan, tasks, analyze, and checklist workflows while preserving a local file fallback.",
    "Generate an evaluation report that scores PRD completeness, spack traceability, task actionability, testability, and MCP readiness.",
    "Create a Spec-Kit archive that bundles the eval report, PRD, spacks, grill-me skill, plugin manifest, and MCP config.",
]

CANONICAL_GRILL_TO_SPAC_CONSTRAINTS = [
    "Run best in Codex interactive mode because the grill phase requires human-in-the-loop answers and approvals.",
    "Do not proceed to implementation until PRD.json, spacks, and evaluation artifacts exist.",
    "Use a dense forward-context summary between phases instead of relying on a long raw conversation transcript.",
    "Use deterministic local JSON files when the Spec-Kit MCP server is not installed or reachable.",
    "Keep archive generation dependency-free so users can share the evaluated handoff without extra setup.",
]


@dataclass(frozen=True)
class ArtifactPaths:
    prd: Path
    spacks: list[Path]
    spack_index: Path
    evaluation: Path

    def as_dict(self) -> dict[str, Any]:
        return {
            "prd": self.prd,
            "spacks": self.spacks,
            "spack_index": self.spack_index,
            "evaluation": self.evaluation,
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
    for line in section_text.splitlines():
        match = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$", line)
        if match:
            bullets.append(clean_text(match.group(1)))
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


def is_grill_to_spac_source(source_text: str) -> bool:
    lowered = source_text.lower()
    has_grill = "grill-me" in lowered or "grill me" in lowered
    has_prd = "to-prd" in lowered or "prd.json" in lowered or "product requirements document" in lowered
    has_spac = "spac" in lowered or "spec-kit" in lowered or "spack" in lowered
    return has_grill and has_prd and has_spac


def derive_project_name(source_text: str, project_name: str | None) -> str:
    if project_name:
        return clean_text(project_name)
    for line in source_text.splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*$", line)
        if match:
            return clean_text(match.group(1))
    return "Grill to Spac Workflow"


def derive_goals(sections: dict[str, str], source_text: str) -> list[str]:
    if is_grill_to_spac_source(source_text):
        return CANONICAL_GRILL_TO_SPAC_GOALS

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
        "Create traceable spacks with implementation tasks.",
        "Evaluate output quality with a repeatable rubric.",
    ]


def derive_constraints(sections: dict[str, str], source_text: str) -> list[str]:
    if is_grill_to_spac_source(source_text):
        return CANONICAL_GRILL_TO_SPAC_CONSTRAINTS

    constraints = extract_bullets(find_section(sections, "constraint", "non-functional", "guardrail"))
    if constraints:
        return constraints

    found: list[str] = []
    for sentence in split_sentences(source_text):
        lowered = sentence.lower()
        if any(word in lowered for word in ["must", "should", "avoid", "require", "interactive", "mcp"]):
            found.append(sentence)
    return dedupe(found[:6])


def derive_acceptance_criteria(sections: dict[str, str], goals: list[str]) -> list[dict[str, str]]:
    raw = extract_bullets(find_section(sections, "acceptance", "criteria", "quality gate"))
    if not raw:
        raw = [
            "Given the resolved grill context, when PRD generation runs, then PRD.json includes goals, stories, requirements, and acceptance criteria.",
            "Given PRD.json, when task decomposition runs, then spacks contain vertical-slice tasks with PRD references.",
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
            "slug": slugify(name, "grill-to-spac"),
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
            "Do not implement product code before the PRD, spacks, and quality gates exist.",
            "Do not require the Spec-Kit MCP server for local validation when a file fallback can be used.",
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
            "Bundle grill-me, to-prd, to-spac, and evaluation as Codex skills in one plugin.",
            "Keep the portable .mcp.json example and document that Codex MCP servers are configured in ~/.codex/config.toml.",
            "Use deterministic local JSON artifacts as the fallback contract for tests and offline runs.",
            "Represent spacks as vertical slices with task-level PRD references and blocker metadata.",
            "Package the final evaluated handoff as a Spec-Kit archive that includes grill-me and MCP metadata.",
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
                "spacks/index.json",
                "spacks/SPACK-*.json",
                "evals/evaluation.json",
                "archive/*-spec-kit-archive.zip",
            ],
        },
        "quality_gates": [
            {"id": "QG-001", "name": "PRD schema completeness", "threshold": 1.0},
            {"id": "QG-002", "name": "Every spack has tasks", "threshold": 1.0},
            {"id": "QG-003", "name": "Every task has PRD references", "threshold": 1.0},
            {"id": "QG-004", "name": "Overall eval score", "threshold": 0.75},
            {"id": "QG-005", "name": "Archive contains eval and grill-me", "threshold": 1.0},
        ],
    }


def spack_category(requirement: dict[str, Any]) -> tuple[str, str, str]:
    text = requirement["statement"].lower()

    def has_terms(*terms: str) -> bool:
        return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)

    if has_terms("evaluation", "evaluate", "eval", "evals", "score", "scores", "quality", "archive", "bundles", "share"):
        return ("SPACK-004", "Evaluate and validate outputs", "AFK")
    if has_terms("question", "interview", "grill", "grilling", "ask", "phase-gated", "interactive"):
        return ("SPACK-001", "Grill and phase-gate discovery", "HITL")
    if has_terms("mcp", "spec-kit", "spac-kit"):
        return ("SPACK-005", "Prepare Spec-Kit MCP handoff", "AFK")
    if has_terms("prd", "prd.json", "requirement", "requirements", "story", "stories", "acceptance"):
        return ("SPACK-002", "Generate machine-actionable PRD", "AFK")
    if has_terms("spack", "spacks", "task", "tasks", "decompose", "blocker", "blockers", "slice", "slices"):
        return ("SPACK-003", "Create traceable spacks and tasks", "AFK")
    return ("SPACK-003", "Create traceable spacks and tasks", "AFK")


def build_spacks(prd: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    task_index = 1
    stories_by_requirement = {
        requirement_id: story["id"]
        for story in prd["user_stories"]
        for requirement_id in story.get("requirements", [])
    }
    criteria_by_id = {item["id"]: item["statement"] for item in prd["acceptance_criteria"]}

    for requirement in prd["requirements"]:
        spack_id, title, spack_type = spack_category(requirement)
        grouped.setdefault(
            spack_id,
            {
                "schema_version": "1.0",
                "id": spack_id,
                "title": title,
                "type": spack_type,
                "blocked_by": [],
                "user_stories": [],
                "tasks": [],
            },
        )
        story_id = stories_by_requirement.get(requirement["id"])
        if story_id and story_id not in grouped[spack_id]["user_stories"]:
            grouped[spack_id]["user_stories"].append(story_id)

        criteria = [
            criteria_by_id[criteria_id]
            for criteria_id in requirement.get("acceptance_criteria", [])
            if criteria_id in criteria_by_id
        ] or ["Generated artifact satisfies the linked PRD requirement."]

        grouped[spack_id]["tasks"].append(
            {
                "id": f"TASK-{task_index:03d}",
                "title": requirement["statement"][:90].rstrip("."),
                "description": f"Implement or verify the workflow behavior for {requirement['id']}.",
                "prd_refs": [requirement["id"], *requirement.get("acceptance_criteria", [])],
                "acceptance_criteria": criteria,
                "verification": [
                    "Run python3 -m unittest tests/test_grill_to_spac.py",
                    "Run python3 scripts/grill_to_spac.py validate --output spac",
                ],
            }
        )
        task_index += 1

    spacks = [grouped[key] for key in sorted(grouped)]
    existing_ids = {item["id"] for item in spacks}
    dependency_order = ["SPACK-001", "SPACK-002", "SPACK-003", "SPACK-004", "SPACK-005"]
    for spack in spacks:
        position = dependency_order.index(spack["id"]) if spack["id"] in dependency_order else 0
        blockers = [candidate for candidate in dependency_order[:position] if candidate in existing_ids]
        spack["blocked_by"] = blockers[-1:] if blockers else []
    return spacks


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


def validate_spacks(spacks: list[dict[str, Any]], prd: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prd_refs = {item["id"] for item in prd.get("requirements", [])}
    prd_refs.update(item["id"] for item in prd.get("acceptance_criteria", []))
    task_ids: set[str] = set()
    covered_requirements: set[str] = set()

    for spack in spacks:
        if not spack.get("tasks"):
            errors.append(f"{spack.get('id', '<unknown>')} has no tasks")
        for task in spack.get("tasks", []):
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
        errors.append(f"Spacks do not cover every requirement: {missing}")
    return errors


def score_fraction(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)


def evaluate_outputs(prd: dict[str, Any], spacks: list[dict[str, Any]], mcp_config_path: Path | None = None) -> dict[str, Any]:
    prd_errors = validate_prd(prd)
    spack_errors = validate_spacks(spacks, prd)
    tasks = [task for spack in spacks for task in spack.get("tasks", [])]
    complete_prd_keys = sum(1 for key in REQUIRED_PRD_KEYS if prd.get(key))
    tasks_with_refs = sum(1 for task in tasks if task.get("prd_refs"))
    tasks_with_criteria = sum(1 for task in tasks if task.get("acceptance_criteria"))
    spacks_with_tasks = sum(1 for spack in spacks if spack.get("tasks"))
    requirements = prd.get("requirements", [])
    requirements_with_criteria = sum(1 for item in requirements if item.get("acceptance_criteria"))
    testing_decision_score = min(1.0, len(prd.get("testing_decisions", [])) / 3)
    requirement_testability = score_fraction(requirements_with_criteria, len(requirements))
    mcp_config_path = mcp_config_path or ROOT / ".mcp.json"

    scores = {
        "prd_completeness": score_fraction(complete_prd_keys, len(REQUIRED_PRD_KEYS)),
        "spack_traceability": score_fraction(tasks_with_refs + spacks_with_tasks, len(tasks) + len(spacks)),
        "task_actionability": score_fraction(tasks_with_criteria, len(tasks)),
        "testability": round((requirement_testability * 0.7) + (testing_decision_score * 0.3), 3),
        "mcp_readiness": 1.0 if mcp_config_path.exists() else 0.75,
    }
    overall = round(sum(scores.values()) / len(scores), 3)

    risks = [
        "Human approval is still required after the grill phase before implementation begins."
    ]
    if prd_errors or spack_errors:
        risks.extend(prd_errors + spack_errors)
    else:
        risks.append("Spec-Kit MCP availability is environment-dependent; local artifacts are the fallback.")

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall,
        "scores": scores,
        "strengths": [
            "PRD requirements, acceptance criteria, and spack tasks share stable IDs.",
            "Spacks are vertical slices with task-level verification commands.",
        ],
        "risks": risks,
        "recommendations": [
            "Review HITL spacks before executing implementation tasks.",
            "Run Spec-Kit analyze/checklist tools when MCP is available to compare against local validation.",
            "Create the Spec-Kit archive after eval so the shared handoff contains the latest score.",
        ],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def archive_entry(path: Path, arcname: str) -> tuple[Path, str]:
    if not path.exists():
        raise FileNotFoundError(f"Archive input is missing: {path}")
    return path, arcname


def collect_archive_entries(output_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = [
        archive_entry(ROOT / "README.md", "README.md"),
        archive_entry(ROOT / ".codex-plugin" / "plugin.json", ".codex-plugin/plugin.json"),
        archive_entry(ROOT / ".mcp.json", ".mcp.json"),
        archive_entry(ROOT / "evals" / "rubric.json", "evals/rubric.json"),
        archive_entry(ROOT / "scripts" / "__init__.py", "scripts/__init__.py"),
        archive_entry(ROOT / "scripts" / "grill_to_spac.py", "scripts/grill_to_spac.py"),
    ]

    for directory in ["schemas", "skills"]:
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file():
                entries.append(archive_entry(path, path.relative_to(ROOT).as_posix()))

    for path in sorted(output_dir.rglob("*.json")):
        relative = path.relative_to(output_dir)
        if "archive" in relative.parts:
            continue
        entries.append(archive_entry(path, f"spac/{relative.as_posix()}"))

    return entries


def create_archive(
    output_dir: Path | str = "spac",
    archive_dir: Path | str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    prd, spacks = load_generated(output)
    evaluation = evaluate_outputs(prd, spacks)
    eval_path = output / "evals" / "evaluation.json"
    write_json(eval_path, evaluation)

    validation_errors = validate_output_dir(output)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    project_name = prd["project"]["name"]
    archive_output = Path(archive_dir) if archive_dir is not None else output / "archive"
    archive_output.mkdir(parents=True, exist_ok=True)
    archive_stem = f"{slugify(project_name, 'grill-to-spac')}-spec-kit-archive"
    archive_path = archive_output / f"{archive_stem}.zip"
    manifest_path = archive_output / f"{archive_stem}-manifest.json"
    entries = collect_archive_entries(output)
    entry_names = [arcname for _, arcname in entries]
    entry_names.append("archive-manifest.json")

    manifest = {
        "schema_version": "1.0",
        "archive_format": "spec-kit",
        "project": project_name,
        "generated_at": evaluation["generated_at"],
        "archive": archive_path.name,
        "evaluation": "spac/evals/evaluation.json",
        "overall_score": evaluation["overall_score"],
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
) -> dict[str, Any]:
    output = Path(output_dir)
    prd = build_prd(source_text, project_name=project_name, source_path=source_path)
    spacks = build_spacks(prd)
    evaluation = evaluate_outputs(prd, spacks)

    prd_path = output / "PRD.json"
    spacks_dir = output / "spacks"
    eval_path = output / "evals" / "evaluation.json"
    write_json(prd_path, prd)

    spack_paths: list[Path] = []
    for spack in spacks:
        file_name = f"{spack['id'].lower()}-{slugify(spack['title'])}.json"
        path = spacks_dir / file_name
        write_json(path, spack)
        spack_paths.append(path)

    index = {
        "schema_version": "1.0",
        "project": prd["project"]["name"],
        "prd": "../PRD.json",
        "spacks": [
            {
                "id": spack["id"],
                "title": spack["title"],
                "path": path.name,
                "task_count": len(spack["tasks"]),
                "blocked_by": spack["blocked_by"],
            }
            for spack, path in zip(spacks, spack_paths)
        ],
        "task_count": sum(len(spack["tasks"]) for spack in spacks),
    }
    index_path = spacks_dir / "index.json"
    write_json(index_path, index)
    write_json(eval_path, evaluation)

    return ArtifactPaths(
        prd=prd_path,
        spacks=spack_paths,
        spack_index=index_path,
        evaluation=eval_path,
    ).as_dict()


def load_generated(output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prd_path = output_dir / "PRD.json"
    spacks_dir = output_dir / "spacks"
    prd = json.loads(prd_path.read_text())
    spacks = [
        json.loads(path.read_text())
        for path in sorted(spacks_dir.glob("SPACK-*.json"))
    ]
    if not spacks:
        spacks = [
            json.loads(path.read_text())
            for path in sorted(spacks_dir.glob("spack-*.json"))
            if path.name != "index.json"
        ]
    return prd, spacks


def validate_output_dir(output_dir: Path) -> list[str]:
    errors: list[str] = []
    if not (output_dir / "PRD.json").exists():
        return ["Missing PRD.json"]
    if not (output_dir / "spacks").exists():
        return ["Missing spacks directory"]
    prd, spacks = load_generated(output_dir)
    errors.extend(validate_prd(prd))
    errors.extend(validate_spacks(spacks, prd))
    if not (output_dir / "spacks" / "index.json").exists():
        errors.append("Missing spacks/index.json")
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
    )
    printable = {
        key: [str(path) for path in value] if isinstance(value, list) else str(value)
        for key, value in artifacts.items()
    }
    print(json.dumps(printable, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate_output_dir(Path(args.output))
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"status": "passed", "output": args.output}, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    prd, spacks = load_generated(output_dir)
    report = evaluate_outputs(prd, spacks)
    eval_path = output_dir / "evals" / "evaluation.json"
    write_json(eval_path, report)
    print(json.dumps(report, indent=2))
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    try:
        result = create_archive(
            output_dir=Path(args.output),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and validate grill-to-spac artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate PRD.json, spacks, and eval report.")
    generate.add_argument("--source", required=True, help="Source research, grill summary, or PRD markdown.")
    generate.add_argument("--output", default="spac", help="Artifact output directory.")
    generate.add_argument("--project-name", help="Override project name.")
    generate.set_defaults(func=cmd_generate)

    validate = subparsers.add_parser("validate", help="Validate generated artifacts.")
    validate.add_argument("--output", default="spac", help="Artifact output directory.")
    validate.set_defaults(func=cmd_validate)

    evaluate = subparsers.add_parser("eval", help="Re-run the artifact quality eval.")
    evaluate.add_argument("--output", default="spac", help="Artifact output directory.")
    evaluate.set_defaults(func=cmd_eval)

    archive = subparsers.add_parser("archive", help="Create a Spec-Kit archive with evals and plugin assets.")
    archive.add_argument("--output", default="spac", help="Artifact output directory.")
    archive.add_argument("--archive-dir", help="Archive output directory. Defaults to <output>/archive.")
    archive.set_defaults(func=cmd_archive)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
