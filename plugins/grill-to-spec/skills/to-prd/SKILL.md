---
name: to-prd
description: Convert resolved grill context, product research, or planning notes into a machine-actionable PRD.json with user stories, requirements, acceptance criteria, implementation decisions, testing decisions, traceability, and quality gates. Use when the user asks to create or validate PRD.json.
---

# To PRD

Synthesize what is already known. Do not restart the interview unless critical
information is missing.

## Output Contract

Write `PRD.json` with:

- `schema_version`
- `project`
- `source`
- `problem_statement`
- `goals`
- `non_goals`
- `actors`
- `user_stories`
- `requirements`
- `acceptance_criteria`
- `implementation_decisions`
- `testing_decisions`
- `traceability`
- `quality_gates`

Every requirement must have a stable `REQ-###` ID and at least one acceptance
criterion reference. Every user story and acceptance criterion must use stable
IDs.

## Local Generator

For deterministic artifacts, run:

```bash
python3 scripts/grill_to_spec.py generate --source <source-file> --output spec --specs-output specs
```

Use the generated PRD as the source of truth for task artifact and Spec Kit
markdown creation.
