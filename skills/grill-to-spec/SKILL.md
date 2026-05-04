---
name: grill-to-spec
description: Orchestrate the full Codex spec-driven chain from grill-me interrogation to PRD.json, task artifact generation, local Spec Kit handoff, and output evaluation. Use when the user asks to run grill-to-spec, create a PRD.json, create task artifacts/tasks, prepare Spec Kit assets, or justify planning output quality.
---

# Grill to Spec

Run a phase-gated workflow. Do not write product implementation code until the
PRD, task artifacts, and eval report exist and the user approves implementation.

## Inputs

- Current conversation context, product research, or an explicit source file.
- Existing repository context, if available.
- Bundled Spec Kit scripts, command templates, and workflow metadata under
  `vendor/spec-kit/`.

## Required Artifacts

Write artifacts under `spec/` unless the user names another output directory:

- `spec/PRD.json`
- `spec/task-artifacts/index.json`
- `spec/task-artifacts/TASKART-*.json`
- `spec/evals/evaluation.json`
- `spec/archive/*-spec-kit-archive.zip`

## Workflow

1. **Grill**
   - Use `grill-me` behavior.
   - Ask exactly one question at a time.
   - Include your recommended answer with each question.
   - If the answer can be discovered from the repo, inspect the repo instead of
     asking the user.
   - Continue until architecture, edge cases, scope, dependencies, testing, and
     quality gates are resolved.

2. **Forward Context**
   - Summarize resolved decisions into a dense handoff:
     problem, goals, non-goals, actors, requirements, constraints, edge cases,
     dependencies, acceptance criteria, and testing decisions.
   - Treat this summary as the sole input to PRD generation.

3. **Create PRD.json**
   - Use `to-prd` behavior.
   - Generate a machine-actionable JSON PRD with stable IDs for user stories,
     requirements, acceptance criteria, traceability, and quality gates.
   - Prefer the local deterministic generator for file output:
     `python3 scripts/grill_to_spec.py generate --source <source> --output spec`.

4. **Create Task Artifacts**
   - Use `to-spec` behavior.
   - Decompose the PRD into vertical slices, not horizontal implementation
     layers.
   - Each task artifact must include tasks, blockers, HITL/AFK type, PRD references,
     acceptance criteria, and verification commands.

5. **Spec Kit Local Handoff**
   - Use the bundled `vendor/spec-kit/templates/commands/*.md` command templates
     for specify, clarify, plan, tasks, analyze, checklist, and implement flows.
   - Use the bundled `vendor/spec-kit/scripts/` shell or PowerShell helpers when
     a project needs the upstream Spec Kit file layout.
   - Keep the local `spec/` artifacts as the source of truth.

6. **Evaluate**
   - Use `evaluate-spec-output` behavior.
   - Run `python3 scripts/grill_to_spec.py eval --output spec`.
   - Report the overall score and any risks before implementation starts.

7. **Archive**
   - Run `python3 scripts/grill_to_spec.py archive --output spec`.
   - The archive must include `spec/evals/evaluation.json`,
     `skills/grill-me/SKILL.md`, `.codex-plugin/plugin.json`, and
     `vendor/spec-kit/`.
   - Use the generated manifest as the shareable handoff inventory.

8. **Verify**
   - Run `python3 scripts/grill_to_spec.py validate --output spec`.
   - Run the plugin tests if this repository contains them:
     `python3 -m unittest tests/test_grill_to_spec.py`.

## Completion Rule

Do not call the workflow complete unless `PRD.json`, at least one task artifact file,
task entries, `evals/evaluation.json`, and a Spec-Kit archive exist and
validation passes.
