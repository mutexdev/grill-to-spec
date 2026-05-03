---
name: grill-to-spac
description: Orchestrate the full Codex spec-driven chain from grill-me interrogation to PRD.json, spack task generation, Spec-Kit MCP handoff, and output evaluation. Use when the user asks to run grill-to-spac, grill-to-spec, create a PRD.json, create spacks/tasks, sync with Spec-Kit/Spac-Kit, or justify planning output quality.
---

# Grill to Spac

Run a phase-gated workflow. Do not write product implementation code until the
PRD, spacks, and eval report exist and the user approves implementation.

## Inputs

- Current conversation context, product research, or an explicit source file.
- Existing repository context, if available.
- Optional Spec-Kit MCP tools. Prefer them when available; use local artifacts
  when MCP is unavailable.

## Required Artifacts

Write artifacts under `spac/` unless the user names another output directory:

- `spac/PRD.json`
- `spac/spacks/index.json`
- `spac/spacks/SPACK-*.json`
- `spac/evals/evaluation.json`

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
     `python3 scripts/grill_to_spac.py generate --source <source> --output spac`.

4. **Create Spacks**
   - Use `to-spac` behavior.
   - Decompose the PRD into vertical slices, not horizontal implementation
     layers.
   - Each spack must include tasks, blockers, HITL/AFK type, PRD references,
     acceptance criteria, and verification commands.

5. **Spec-Kit MCP Handoff**
   - If the Spec-Kit MCP server is available, use its tools in this order:
     `speckit_init`, `speckit_specify`, `speckit_plan`, `speckit_tasks`,
     `speckit_analyze`, `speckit_checklist`.
   - If MCP is unavailable, keep the local `spac/` artifacts as the source of
     truth and state that fallback explicitly.

6. **Evaluate**
   - Use `evaluate-spac-output` behavior.
   - Run `python3 scripts/grill_to_spac.py eval --output spac`.
   - Report the overall score and any risks before implementation starts.

7. **Verify**
   - Run `python3 scripts/grill_to_spac.py validate --output spac`.
   - Run the plugin tests if this repository contains them:
     `python3 -m unittest tests/test_grill_to_spac.py`.

## Completion Rule

Do not call the workflow complete unless `PRD.json`, at least one spack file,
task entries, and `evals/evaluation.json` exist and validation passes.
