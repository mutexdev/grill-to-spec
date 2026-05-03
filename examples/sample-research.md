# Grill to Spac Sample

Build a Codex plugin that interviews a user before coding, converts the
answers into a machine-actionable PRD, decomposes that PRD into spacks, and
evaluates output quality.

## Goals

- Ask one grilling question at a time and include the recommended answer.
- Create a PRD.json artifact with user stories, requirements, acceptance
  criteria, implementation decisions, testing decisions, and traceability.
- Create spacks with vertical-slice tasks, blockers, HITL/AFK classification,
  acceptance criteria, and PRD references.
- Evaluate the generated artifacts so the agent can justify output quality.

## Acceptance Criteria

- Given source research, when the generator runs, then PRD.json is written.
- Given PRD.json, when spacks are generated, then every spack includes tasks.
- Given artifacts, when evaluation runs, then scores and findings explain quality.
