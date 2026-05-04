import json
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
answers into a machine-actionable PRD, and decomposes that PRD into spacks.

## Goals

- Ask one grilling question at a time and include the recommended answer.
- Create a PRD.json artifact that contains user stories, requirements,
  acceptance criteria, implementation decisions, testing decisions, and
  traceability links.
- Create spacks that contain vertical-slice tasks with blockers, HITL/AFK
  classification, acceptance criteria, and PRD references.
- Evaluate the generated outputs so the agent can justify quality.

## Constraints

- Run in Codex interactive mode.
- Use local files when the Spec-Kit MCP server is unavailable.
- Avoid coding until a PRD and task breakdown exist.

## Acceptance Criteria

- Given the source research, when the generator runs, then PRD.json is written.
- Given PRD.json, when spacks are generated, then every spack includes tasks.
- Given the artifacts, when evaluation runs, then scores and findings explain
  the output quality.
"""


DENSE_PRODUCT_RESEARCH = (
    "Architecting Spec-Driven Agentic Workflows: Implementing Compound Skill "
    "Chains in OpenAI Codex. This plugin orchestrates a sequential, phase-gated "
    "engineering pipeline: it initiates a rigorous multi-turn user interrogation "
    "process called Grill-Me, synthesizes the resulting context into a "
    "machine-actionable Product Requirements Document with To-PRD, decomposes "
    "that document into granular spacks with tasks, links the components through "
    "Spac-Kit or Spec-Kit MCP integration, and adds evals to justify how good "
    "the outputs are."
)


class GrillToSpacTests(unittest.TestCase):
    def test_generates_prd_json_with_required_traceable_sections(self):
        from scripts.grill_to_spac import generate_artifacts

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

    def test_generates_spacks_with_tasks_and_prd_references(self):
        from scripts.grill_to_spac import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=Path(tmp),
                project_name="Conversational Recipe Builder",
            )

            spack_paths = artifacts["spacks"]
            self.assertGreaterEqual(len(spack_paths), 3)

            seen_task_ids = set()
            for spack_path in spack_paths:
                spack = json.loads(spack_path.read_text())
                self.assertRegex(spack["id"], r"^SPACK-\d{3}$")
                self.assertIn(spack["type"], {"AFK", "HITL"})
                self.assertIsInstance(spack["blocked_by"], list)
                self.assertGreaterEqual(len(spack["tasks"]), 1)

                for task in spack["tasks"]:
                    self.assertRegex(task["id"], r"^TASK-\d{3}$")
                    self.assertNotIn(task["id"], seen_task_ids)
                    seen_task_ids.add(task["id"])
                    self.assertGreaterEqual(len(task["acceptance_criteria"]), 1)
                    self.assertGreaterEqual(len(task["prd_refs"]), 1)

            index = json.loads(artifacts["spack_index"].read_text())
            self.assertEqual(len(index["spacks"]), len(spack_paths))
            self.assertEqual(index["task_count"], len(seen_task_ids))

    def test_dense_product_research_uses_canonical_workflow_requirements(self):
        from scripts.grill_to_spac import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=DENSE_PRODUCT_RESEARCH,
                output_dir=Path(tmp),
                project_name="grill-to-spac",
            )

            prd = json.loads(artifacts["prd"].read_text())
            requirement_text = " ".join(item["statement"] for item in prd["requirements"]).lower()
            self.assertIn("one question at a time", requirement_text)
            self.assertIn("prd.json", requirement_text)
            self.assertIn("spacks", requirement_text)
            self.assertIn("spec-kit mcp", requirement_text)
            self.assertIn("evaluation", requirement_text)
            self.assertIn("spec-kit archive", requirement_text)

            for story in prd["user_stories"]:
                self.assertLessEqual(len(story["story"]), 260)

            spack_ids = {
                json.loads(path.read_text())["id"] for path in artifacts["spacks"]
            }
            self.assertTrue(
                {"SPACK-001", "SPACK-002", "SPACK-003", "SPACK-004", "SPACK-005"}.issubset(spack_ids)
            )

    def test_evaluation_scores_explain_quality(self):
        from scripts.grill_to_spac import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=Path(tmp),
                project_name="Conversational Recipe Builder",
            )

            report = json.loads(artifacts["evaluation"].read_text())
            self.assertEqual(report["schema_version"], "1.0")
            self.assertGreaterEqual(report["overall_score"], 0.75)

            for dimension in [
                "prd_completeness",
                "spack_traceability",
                "task_actionability",
                "testability",
                "mcp_readiness",
            ]:
                self.assertIn(dimension, report["scores"])
                self.assertGreaterEqual(report["scores"][dimension], 0.0)
                self.assertLessEqual(report["scores"][dimension], 1.0)

            self.assertGreaterEqual(report["scores"]["testability"], 0.75)
            self.assertGreaterEqual(len(report["strengths"]), 1)
            self.assertGreaterEqual(len(report["risks"]), 1)
            self.assertGreaterEqual(len(report["recommendations"]), 1)

    def test_creates_spec_kit_archive_with_eval_and_grill_me_assets(self):
        from scripts.grill_to_spac import create_archive, generate_artifacts

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "spac"
            archive_dir = Path(tmp) / "archive"
            generate_artifacts(
                source_text=SAMPLE_RESEARCH,
                output_dir=output_dir,
                project_name="Conversational Recipe Builder",
            )

            result = create_archive(output_dir=output_dir, archive_dir=archive_dir)

            archive_path = result["archive"]
            manifest_path = result["manifest"]
            self.assertEqual(archive_path.name, "conversational-recipe-builder-spec-kit-archive.zip")
            self.assertTrue(archive_path.exists())
            self.assertTrue(manifest_path.exists())

            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema_version"], "1.0")
            self.assertEqual(manifest["archive_format"], "spec-kit")
            self.assertEqual(manifest["project"], "Conversational Recipe Builder")
            self.assertGreaterEqual(manifest["overall_score"], 0.75)
            self.assertIn("spac/evals/evaluation.json", manifest["entries"])
            self.assertIn("skills/grill-me/SKILL.md", manifest["entries"])

            with zipfile.ZipFile(archive_path) as archive:
                entries = set(archive.namelist())

            expected_entries = {
                "spac/PRD.json",
                "spac/evals/evaluation.json",
                "spac/spacks/index.json",
                "skills/grill-me/SKILL.md",
                "skills/grill-to-spac/SKILL.md",
                ".codex-plugin/plugin.json",
                ".mcp.json",
            }
            self.assertTrue(expected_entries.issubset(entries))

    def test_archive_requirement_is_grouped_with_eval_spack(self):
        from scripts.grill_to_spac import generate_artifacts

        with TemporaryDirectory() as tmp:
            artifacts = generate_artifacts(
                source_text=DENSE_PRODUCT_RESEARCH,
                output_dir=Path(tmp),
                project_name="grill-to-spac",
            )

            spacks = {
                json.loads(path.read_text())["id"]: json.loads(path.read_text())
                for path in artifacts["spacks"]
            }
            archive_tasks = [
                task
                for task in spacks["SPACK-004"]["tasks"]
                if "Spec-Kit archive" in task["title"]
            ]
            misplaced_tasks = [
                task
                for task in spacks["SPACK-001"]["tasks"]
                if "Spec-Kit archive" in task["title"]
            ]

            self.assertEqual(len(archive_tasks), 1)
            self.assertEqual(misplaced_tasks, [])


if __name__ == "__main__":
    unittest.main()
