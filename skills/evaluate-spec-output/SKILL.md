---
name: evaluate-spec-output
description: Evaluate generated PRD.json and task artifacts with a repeatable rubric so the agent can justify output quality. Use when the user asks for evals, quality scores, validation, or justification of grill-to-spec outputs.
---

# Evaluate Spec Output

Evaluate generated planning artifacts before implementation begins.

## Rubric

Use `evals/rubric.json` and score:

- PRD completeness
- task artifact traceability
- task actionability
- testability
- Spec Kit asset readiness

The minimum acceptable overall score is `0.90`, with zero critical/high
planning-safety findings.

## Commands

```bash
python3 scripts/grill_to_spec.py eval --output spec
python3 scripts/grill_to_spec.py archive --output spec --specs-output specs
python3 scripts/grill_to_spec.py validate --output spec --specs-output specs
```

Report the overall score, strongest evidence, risks, and recommended follow-up
before claiming the workflow is complete. When creating the archive, confirm it
contains `spec/evals/evaluation.json`, `specs/<feature-slug>/spec.md`,
`specs/<feature-slug>/tasks.md`, and `skills/grill-me/SKILL.md`.
