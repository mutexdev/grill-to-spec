---
name: to-spec
description: Break PRD.json into traceable task artifacts with vertical-slice tasks, blockers, HITL/AFK classification, acceptance criteria, verification commands, and PRD references. Use when the user asks to create task artifacts, tasks, issues, or Spec-Kit work items from a PRD.
---

# To Spec

Convert PRD requirements into independently executable task artifacts.

## Task Artifact Rules

- Use vertical slices that deliver a narrow end-to-end behavior.
- Avoid horizontal slices such as "database only" or "frontend only".
- Mark a task artifact `HITL` when it requires a human decision or approval.
- Mark a task artifact `AFK` when an agent can execute it from the PRD and tests.
- Publish blockers in dependency order.
- Each task must include:
  - `TASK-###` ID
  - concise title
  - PRD references
  - acceptance criteria
  - verification commands

## Spec Kit Local Assets

Use the bundled Spec Kit assets from `vendor/spec-kit/`:

- `templates/commands/specify.md`
- `templates/commands/plan.md`
- `templates/commands/tasks.md`
- `templates/commands/analyze.md`
- `templates/commands/checklist.md`
- `scripts/bash/*.sh` or `scripts/powershell/*.ps1`

Keep `spec/task-artifacts/*.json` and `spec/task-artifacts/index.json` as the
local work queue.
