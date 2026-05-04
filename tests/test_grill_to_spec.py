import json
import re
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


SAMPLE_RESEARCH = """
# Conversational Recipe Builder

Build a Codex plugin that interviews a user before coding, converts the
answers into a machine-actionable PRD, and decomposes that PRD into task
artifacts.

## Goals

- Ask one grilling question at a time and include the recommended answer.
- Create a PRD.json artifact that contains user stories, requirements,
  acceptance criteria, implementation decisions, testing decisions, and
  traceability links.
- Create task artifacts that contain vertical-slice tasks with blockers, HITL/AFK
  classification, acceptance criteria, and PRD references.
- Evaluate the generated outputs so the agent can justify quality.
- Use vendored Spec Kit scripts and templates locally; do not start or require an MCP server.

## Constraints

- Run in Codex interactive mode.
- Use local Spec Kit assets instead of a network MCP bridge.
- Avoid coding until a PRD and task breakdown exist.

## Acceptance Criteria

- Given the source research, when the generator runs, then PRD.json is written.
- Given PRD.json, when task artifacts are generated, then every task artifact includes tasks.
- Given the artifacts, when evaluation runs, then scores and findings explain
  the output quality.
"""


DENSE_PRODUCT_RESEARCH = (
    "Architecting Spec-Driven Agentic Workflows: Implementing Compound Skill "
    "Chains in OpenAI Codex. This plugin orchestrates a sequential, phase-gated "
    "engineering pipeline: it initiates a rigorous multi-turn user interrogation "
    "process called Grill-Me, synthesizes the resulting context into a "
    "machine-actionable Product Requirements Document with To-PRD, decomposes "
    "that document into granular task artifacts with tasks, links the components through "
    "vendored Spec Kit scripts and templates, and adds evals to justify how good "
    "the outputs are."
)


class GrillToSpecTests(unittest.TestCase):
    def test_multiline_bullets_are_extracted_as_single_items(self):
        from scripts.grill_to_spec import extract_bullets

        bullets = extract_bullets(
            """
            - Given the plugin manifest, when Codex loads the plugin, then no
              server entry is registered or launched.
            - Given a marketplace install, when Codex copies the package, then
              runtime assets are available.
            """
        )

        self.assertEqual(
            bullets,
            [
                "Given the plugin manifest, when Codex loads the plugin, then no server entry is registered or launched.",
                "Given a marketplace install, when Codex copies the package, then runtime assets are available.",
            ],
        )

    def test_marketplace_uses_cacheable_plugin_source_layout(self):
        marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        plugin_entry = next(
            entry for entry in marketplace["plugins"] if entry["name"] == "grill-to-spec"
        )
        self.assertEqual(plugin_entry["source"]["path"], "./plugins/grill-to-spec")

        package_root = ROOT / "plugins/grill-to-spec"
        mirrored_files = [
            ".codex-plugin/plugin.json",
            "evals/rubric.json",
            "schemas/prd.schema.json",
            "schemas/task-artifact.schema.json",
            "scripts/__init__.py",
            "scripts/grill_to_spec.py",
            "skills/evaluate-spec-output/SKILL.md",
            "skills/grill-me/SKILL.md",
            "skills/grill-to-spec/SKILL.md",
            "skills/to-prd/SKILL.md",
            "skills/to-spec/SKILL.md",
            "vendor/spec-kit/LICENSE",
            "vendor/spec-kit/scripts/bash/check-prerequisites.sh",
            "vendor/spec-kit/scripts/bash/common.sh",
            "vendor/spec-kit/scripts/bash/create-new-feature.sh",
            "vendor/spec-kit/scripts/bash/setup-plan.sh",
            "vendor/spec-kit/scripts/bash/setup-tasks.sh",
            "vendor/spec-kit/scripts/powershell/check-prerequisites.ps1",
            "vendor/spec-kit/scripts/powershell/common.ps1",
            "vendor/spec-kit/scripts/powershell/create-new-feature.ps1",
            "vendor/spec-kit/scripts/powershell/setup-plan.ps1",
            "vendor/spec-kit/scripts/powershell/setup-tasks.ps1",
            "vendor/spec-kit/templates/checklist-template.md",
            "vendor/spec-kit/templates/commands/analyze.md",
            "vendor/spec-kit/templates/commands/checklist.md",
            "vendor/spec-kit/templates/commands/clarify.md",
            "vendor/spec-kit/templates/commands/constitution.md",
            "vendor/spec-kit/templates/commands/plan.md",
            "vendor/spec-kit/templates/commands/specify.md",
            "vendor/spec-kit/templates/commands/tasks.md",
            "vendor/spec-kit/templates/commands/taskstoissues.md",
            "vendor/spec-kit/templates/constitution-template.md",
            "vendor/spec-kit/templates/plan-template.md",
            "vendor/spec-kit/templates/spec-template.md",
            "vendor/spec-kit/templates/tasks-template.md",
            "vendor/spec-kit/templates/vscode-settings.json",
            "vendor/spec-kit/workflows/speckit/workflow.yml",
            "vendor/spec-kit/downstream-references/implement.md",
        ]
        for relative_path in mirrored_files:
            packaged = package_root / relative_path
            canonical = ROOT / relative_path
            self.assertTrue(packaged.is_file(), relative_path)
            self.assertFalse(packaged.is_symlink(), relative_path)
            self.assertEqual(packaged.read_text(), canonical.read_text())

    def test_plugin_package_does_not_register_mcp_servers(self):
        manifest_paths = [
            ROOT / ".codex-plugin/plugin.json",
            ROOT / "plugins/grill-to-spec/.codex-plugin/plugin.json",
        ]
        for manifest_path in manifest_paths:
            manifest = json.loads(manifest_path.read_text())
            self.assertNotIn("mcpServers", manifest)
            self.assertNotIn("MCP", manifest["interface"]["capabilities"])
            self.assertNotIn("@speckit/mcp", json.dumps(manifest))

        self.assertFalse((ROOT / ".mcp.json").exists())
        self.assertFalse((ROOT / "plugins/grill-to-spec/.mcp.json").exists())

    def test_active_spec_kit_assets_quarantine_implementation_command(self):
        from scripts import grill_to_spec

        active_command_paths = [
            ROOT / "vendor/spec-kit/templates/commands",
            ROOT / "plugins/grill-to-spec/vendor/spec-kit/templates/commands",
        ]
        for command_dir in active_command_paths:
            self.assertFalse((command_dir / "implement.md").exists())

        reference_paths = [
            ROOT / "vendor/spec-kit/downstream-references/implement.md",
            ROOT / "plugins/grill-to-spec/vendor/spec-kit/downstream-references/implement.md",
        ]
        for reference_path in reference_paths:
            self.assertTrue(reference_path.is_file())
            self.assertIn("downstream reference", reference_path.read_text().lower())

        self.assertNotIn("templates/commands/implement.md", grill_to_spec.REQUIRED_SPEC_KIT_ASSETS)

        active_vendor_files = [
            ROOT / "vendor/spec-kit/templates/vscode-settings.json",
            ROOT / "vendor/spec-kit/workflows/speckit/workflow.yml",
            ROOT / "plugins/grill-to-spec/vendor/spec-kit/templates/vscode-settings.json",
            ROOT / "plugins/grill-to-spec/vendor/spec-kit/workflows/speckit/workflow.yml",
        ]
        for path in active_vendor_files:
            text = path.read_text()
            self.assertNotIn("speckit.implement", text, path.relative_to(ROOT))

    def test_spec_kit_task_handoff_does_not_auto_start_implementation(self):
        task_template_paths = [
            ROOT / "vendor/spec-kit/templates/commands/tasks.md",
            ROOT / "plugins/grill-to-spec/vendor/spec-kit/templates/commands/tasks.md",
        ]
        forbidden = [
            "label: Implement Project",
            "agent: speckit.implement",
            "Start the implementation in phases",
        ]
        for template_path in task_template_paths:
            text = template_path.read_text()
            for token in forbidden:
                self.assertNotIn(token, text, f"{token} found in {template_path.relative_to(ROOT)}")
            self.assertIn("Implementation is approval-gated", text)
            self.assertIn("downstream-references/implement.md", text)

        skill_paths = [
            ROOT / "skills/grill-to-spec/SKILL.md",
            ROOT / "plugins/grill-to-spec/skills/grill-to-spec/SKILL.md",
        ]
        for skill_path in skill_paths:
            text = skill_path.read_text()
            self.assertIn("Planning Boundary", text)
            self.assertIn("Do not invoke implementation commands", text)
            self.assertNotIn("and implement flows", text)

    def test_public_plugin_names_use_spec_not_spac(self):
        plugin_manifest_paths = [
            ROOT / ".codex-plugin/plugin.json",
            ROOT / "plugins/grill-to-spec/.codex-plugin/plugin.json",
        ]
        for manifest_path in plugin_manifest_paths:
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["name"], "grill-to-spec")
            self.assertEqual(manifest["interface"]["displayName"], "Grill to Spec")
            self.assertNotIn("Spac", json.dumps(manifest))
            self.assertNotIn("grill-to-spac", json.dumps(manifest))

        public_paths = [
            ROOT / "README.md",
            ROOT / "skills/evaluate-spec-output/SKILL.md",
            ROOT / "skills/grill-me/SKILL.md",
            ROOT / "skills/grill-to-spec/SKILL.md",
            ROOT / "skills/to-prd/SKILL.md",
            ROOT / "skills/to-spec/SKILL.md",
        ]
        forbidden = [
            "Grill to Spac",
            "Spac-Kit",
            "grill-to-spac",
            "grill_to_spac",
            "to-spac",
            "evaluate-spac-output",
            "--output spac",
            "`spac/",
        ]
        for path in public_paths:
            text = path.read_text()
            for token in forbidden:
                self.assertNotIn(token, text, f"{token} found in {path.relative_to(ROOT)}")

    def test_task_artifact_names_do_not_use_spack_label(self):
        excluded = {
            ROOT / "tests/test_grill_to_spec.py",
        }
        forbidden = ["spack", "SPACK", "Spack"]
        for path in ROOT.rglob("*"):
            if path in excluded or ".git" in path.parts or path.suffix == ".zip" or not path.is_file():
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            for token in forbidden:
                self.assertNotIn(token, text, f"{token} found in {path.relative_to(ROOT)}")

    def test_generates_prd_json_with_required_traceable_sections(self):
        from scripts.grill_to_spec import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=Path(tmp),
                project_name="Conversational Recipe Builder",
            )

            prd_path = artifacts["prd"]
            self.assertEqual(prd_path.name, "PRD.json")
            self.assertTrue(prd_path.exists())

            prd = json.loads(prd_path.read_text())
            self.assertEqual(prd["schema_version"], "1.0")
            self.assertEqual(prd["project"]["name"], "Conversational Recipe Builder")

            for key in [
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
            ]:
                self.assertIn(key, prd)

            self.assertGreaterEqual(len(prd["user_stories"]), 4)
            self.assertGreaterEqual(len(prd["requirements"]), 4)
            self.assertGreaterEqual(len(prd["acceptance_criteria"]), 3)

            requirement_ids = {item["id"] for item in prd["requirements"]}
            trace_requirement_ids = {
                item["requirement_id"] for item in prd["traceability"]["requirement_coverage"]
            }
            self.assertEqual(requirement_ids, trace_requirement_ids)

    def test_generates_task_artifacts_with_tasks_and_prd_references(self):
        from scripts.grill_to_spec import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=Path(tmp),
                project_name="Conversational Recipe Builder",
            )

            task_artifact_paths = artifacts["task_artifacts"]
            self.assertGreaterEqual(len(task_artifact_paths), 3)

            seen_task_ids = set()
            for task_artifact_path in task_artifact_paths:
                task_artifact = json.loads(task_artifact_path.read_text())
                self.assertRegex(task_artifact["id"], r"^TASKART-\d{3}$")
                self.assertIn(task_artifact["type"], {"AFK", "HITL"})
                self.assertIsInstance(task_artifact["blocked_by"], list)
                self.assertGreaterEqual(len(task_artifact["tasks"]), 1)

                for task in task_artifact["tasks"]:
                    self.assertRegex(task["id"], r"^TASK-\d{3}$")
                    self.assertNotIn(task["id"], seen_task_ids)
                    seen_task_ids.add(task["id"])
                    self.assertGreaterEqual(len(task["acceptance_criteria"]), 1)
                    self.assertGreaterEqual(len(task["prd_refs"]), 1)

            index = json.loads(artifacts["task_artifact_index"].read_text())
            self.assertEqual(len(index["task_artifacts"]), len(task_artifact_paths))
            self.assertEqual(index["task_count"], len(seen_task_ids))

    def test_generate_emits_spec_kit_markdown_handoff(self):
        from scripts.grill_to_spec import generate_artifacts

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / "spec"
            specs_output = tmp_path / "specs"
            artifacts = generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=output_dir,
                specs_output_dir=specs_output,
                project_name="Conversational Recipe Builder",
            )

            spec_kit_dir = artifacts["spec_kit_dir"]
            self.assertEqual(spec_kit_dir, specs_output / "conversational-recipe-builder")
            expected_files = {
                "spec.md",
                "plan.md",
                "tasks.md",
                "research.md",
                "quickstart.md",
                "data-model.md",
                "checklists/requirements.md",
                "contracts/acceptance-criteria.md",
            }
            self.assertTrue({path.relative_to(spec_kit_dir).as_posix() for path in spec_kit_dir.rglob("*") if path.is_file()}.issuperset(expected_files))

            spec_md = (spec_kit_dir / "spec.md").read_text()
            plan_md = (spec_kit_dir / "plan.md").read_text()
            tasks_md = (spec_kit_dir / "tasks.md").read_text()
            checklist_md = (spec_kit_dir / "checklists" / "requirements.md").read_text()

            self.assertIn("**FR-001** (`REQ-001`)", spec_md)
            self.assertIn("**US-001**", spec_md)
            self.assertIn("AC-001", spec_md)
            self.assertIn("Planning Boundary", plan_md)
            self.assertIn("QG-004", plan_md)
            self.assertIn("REQ-001", tasks_md)
            self.assertRegex(tasks_md, r"(?m)^- \[ \] T\d{3} ")
            self.assertNotRegex(tasks_md, r"(?i)- \[x\]")
            self.assertNotIn("speckit.implement", tasks_md)
            self.assertIn("FR-001", checklist_md)

            task_lines = re.findall(r"(?m)^- \[ \] T\d{3} .+$", tasks_md)
            self.assertGreaterEqual(len(task_lines), 3)
            self.assertFalse((tmp_path / "src").exists())
            self.assertFalse((tmp_path / "app").exists())
            self.assertFalse((tmp_path / "backend").exists())

    def test_materialize_existing_prd_and_task_artifacts(self):
        from scripts.grill_to_spec import generate_artifacts, materialize_spec_kit_handoff

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / "spec"
            specs_output = tmp_path / "specs"
            generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=output_dir,
                specs_output_dir=None,
                project_name="Conversational Recipe Builder",
            )

            self.assertFalse(specs_output.exists())
            materialized = materialize_spec_kit_handoff(output_dir=output_dir, specs_output_dir=specs_output)

            self.assertEqual(materialized, specs_output / "conversational-recipe-builder")
            self.assertTrue((materialized / "spec.md").is_file())
            self.assertTrue((materialized / "plan.md").is_file())
            self.assertTrue((materialized / "tasks.md").is_file())

    def test_dense_product_research_uses_canonical_workflow_requirements(self):
        from scripts.grill_to_spec import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=DENSE_PRODUCT_RESEARCH,
                output_dir=Path(tmp),
                project_name="grill-to-spec",
            )

            prd = json.loads(artifacts["prd"].read_text())
            requirement_text = " ".join(item["statement"] for item in prd["requirements"]).lower()
            self.assertIn("one question at a time", requirement_text)
            self.assertIn("prd.json", requirement_text)
            self.assertIn("task artifacts", requirement_text)
            self.assertIn("spec kit scripts", requirement_text)
            self.assertIn("evaluation", requirement_text)
            self.assertIn("spec-kit archive", requirement_text)
            self.assertIn("explicit user approval", requirement_text)
            self.assertIn("auto-send implementation handoffs", requirement_text)
            self.assertNotIn("mcp", requirement_text)

            for story in prd["user_stories"]:
                self.assertLessEqual(len(story["story"]), 260)

            task_artifact_ids = {
                json.loads(path.read_text())["id"] for path in artifacts["task_artifacts"]
            }
            self.assertTrue(
                {
                    "TASKART-001",
                    "TASKART-002",
                    "TASKART-003",
                    "TASKART-004",
                    "TASKART-005",
                }.issubset(task_artifact_ids)
            )

    def test_evaluation_scores_explain_quality(self):
        from scripts.grill_to_spec import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=Path(tmp),
                project_name="Conversational Recipe Builder",
            )

            report = json.loads(artifacts["evaluation"].read_text())
            self.assertEqual(report["schema_version"], "1.0")
            self.assertGreaterEqual(report["overall_score"], 0.90)
            high_safety_findings = [
                finding
                for finding in report["planning_safety_findings"]
                if finding["severity"] in {"critical", "high"}
            ]
            self.assertEqual(high_safety_findings, [])

            for dimension in [
                "prd_completeness",
                "task_artifact_traceability",
                "task_actionability",
                "testability",
                "spec_kit_asset_readiness",
            ]:
                self.assertIn(dimension, report["scores"])
                self.assertGreaterEqual(report["scores"][dimension], 0.0)
                self.assertLessEqual(report["scores"][dimension], 1.0)

            self.assertGreaterEqual(report["scores"]["testability"], 0.90)
            self.assertGreaterEqual(len(report["strengths"]), 1)
            self.assertGreaterEqual(len(report["risks"]), 1)
            self.assertGreaterEqual(len(report["recommendations"]), 1)

    def test_creates_spec_kit_archive_with_eval_grill_me_and_specs_assets(self):
        from scripts.grill_to_spec import create_archive, generate_artifacts

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "spec"
            specs_output = Path(tmp) / "specs"
            archive_dir = Path(tmp) / "archive"
            generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=output_dir,
                specs_output_dir=specs_output,
                project_name="Conversational Recipe Builder",
            )

            result = create_archive(output_dir=output_dir, specs_output_dir=specs_output, archive_dir=archive_dir)

            archive_path = result["archive"]
            manifest_path = result["manifest"]
            self.assertEqual(archive_path.name, "conversational-recipe-builder-spec-kit-archive.zip")
            self.assertTrue(archive_path.exists())
            self.assertTrue(manifest_path.exists())

            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema_version"], "1.0")
            self.assertEqual(manifest["archive_format"], "spec-kit")
            self.assertEqual(manifest["project"], "Conversational Recipe Builder")
            self.assertGreaterEqual(manifest["overall_score"], 0.90)
            self.assertIn("spec/evals/evaluation.json", manifest["entries"])
            self.assertIn("specs/conversational-recipe-builder/spec.md", manifest["entries"])
            self.assertIn("specs/conversational-recipe-builder/plan.md", manifest["entries"])
            self.assertIn("specs/conversational-recipe-builder/tasks.md", manifest["entries"])
            self.assertIn("skills/grill-me/SKILL.md", manifest["entries"])

            with zipfile.ZipFile(archive_path) as archive:
                entries = set(archive.namelist())

            expected_entries = {
                "spec/PRD.json",
                "spec/evals/evaluation.json",
                "spec/task-artifacts/index.json",
                "specs/conversational-recipe-builder/spec.md",
                "specs/conversational-recipe-builder/plan.md",
                "specs/conversational-recipe-builder/tasks.md",
                "skills/grill-me/SKILL.md",
                "skills/grill-to-spec/SKILL.md",
                ".codex-plugin/plugin.json",
                "vendor/spec-kit/scripts/bash/setup-plan.sh",
                "vendor/spec-kit/templates/commands/specify.md",
            }
            self.assertTrue(expected_entries.issubset(entries))

    def test_archive_requirement_is_grouped_with_eval_task_artifact(self):
        from scripts.grill_to_spec import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=DENSE_PRODUCT_RESEARCH,
                output_dir=Path(tmp),
                project_name="grill-to-spec",
            )

            task_artifacts = {
                json.loads(path.read_text())["id"]: json.loads(path.read_text())
                for path in artifacts["task_artifacts"]
            }
            archive_tasks = [
                task
                for task in task_artifacts["TASKART-004"]["tasks"]
                if "Spec-Kit archive" in task["title"]
            ]
            misplaced_tasks = [
                task
                for task in task_artifacts["TASKART-001"]["tasks"]
                if "Spec-Kit archive" in task["title"]
            ]

            self.assertEqual(len(archive_tasks), 1)
            self.assertEqual(misplaced_tasks, [])


if __name__ == "__main__":
    unittest.main()
