---
name: to-spac
description: Break PRD.json into traceable spacks with vertical-slice tasks, blockers, HITL/AFK classification, acceptance criteria, verification commands, and PRD references. Use when the user asks to create spacks, tasks, issues, or Spec-Kit/Spac-Kit work items from a PRD.
---

# To Spac

Convert PRD requirements into independently executable spacks.

## Spack Rules

- Use vertical slices that deliver a narrow end-to-end behavior.
- Avoid horizontal slices such as "database only" or "frontend only".
- Mark a spack `HITL` when it requires a human decision or approval.
- Mark a spack `AFK` when an agent can execute it from the PRD and tests.
- Publish blockers in dependency order.
- Each task must include:
  - `TASK-###` ID
  - concise title
  - PRD references
  - acceptance criteria
  - verification commands

## Spec-Kit MCP

If available, use the Spec-Kit MCP tools for init, specify, plan, tasks,
analyze, and checklist. Keep the bundled `.mcp.json` example for portable plugin
metadata. Codex's live MCP server entries belong in `~/.codex/config.toml`, for
example:

```toml
[mcp_servers.spec-kit]
command = "npx"
args = ["@speckit/mcp@latest"]
```

If MCP is unavailable, keep `spac/spacks/*.json` and `spac/spacks/index.json`
as the fallback work queue.
