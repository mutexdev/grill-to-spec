# Research: grill-to-spec

## Goals

- Run a phase-gated Codex workflow that starts with Grill-Me discovery before implementation.
- Ask one question at a time during grilling and include the recommended answer.
- Create PRD.json with user stories, requirements, acceptance criteria, implementation decisions, testing decisions, and traceability.
- Create task artifacts that decompose PRD requirements into vertical-slice tasks with blockers, HITL/AFK classification, and PRD references.
- Use vendored Spec Kit scripts and templates for specify, clarify, plan, tasks, analyze, and checklist workflows.
- Require explicit user approval before any implementation command, code edit, or downstream task execution begins.
- Generate an evaluation report that scores PRD completeness, task artifact traceability, task actionability, testability, and Spec Kit asset readiness.
- Create a Spec-Kit archive that bundles the eval report, PRD, task artifacts, grill-me skill, plugin manifest, and vendored Spec Kit assets.

## Non-Goals

- Do not implement product code before the PRD, task artifacts, and quality gates exist.
- Do not auto-send implementation handoffs or run Spec Kit implementation commands during planning handoff creation.
- Do not require a network server for local validation or Spec Kit handoff generation.
- Do not require third-party archive tooling beyond the Python standard library.

## Testing Decisions

- Validate the generator with unit tests that read the emitted JSON artifacts.
- Treat traceability, actionability, and acceptance criteria coverage as first-class eval dimensions.
- Keep tests dependency-free so the plugin can be verified in a sandboxed Codex workspace.
