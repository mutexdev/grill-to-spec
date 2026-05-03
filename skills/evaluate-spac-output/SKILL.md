---
name: evaluate-spac-output
description: Evaluate generated PRD.json and spack task artifacts with a repeatable rubric so the agent can justify output quality. Use when the user asks for evals, quality scores, validation, or justification of grill-to-spac outputs.
---

# Evaluate Spac Output

Evaluate generated planning artifacts before implementation begins.

## Rubric

Use `evals/rubric.json` and score:

- PRD completeness
- spack traceability
- task actionability
- testability
- MCP readiness

The minimum acceptable overall score is `0.75`.

## Commands

```bash
python3 scripts/grill_to_spac.py eval --output spac
python3 scripts/grill_to_spac.py validate --output spac
```

Report the overall score, strongest evidence, risks, and recommended follow-up
before claiming the workflow is complete.
