# Grill to Spec

Grill to Spec is a Codex plugin that turns rough product research into a
phase-gated spec workflow:

1. Grill the user one question at a time.
2. Generate a machine-actionable `PRD.json`.
3. Decompose the PRD into traceable spacks with tasks.
4. Register Spec-Kit MCP for external spec/task tooling.
5. Evaluate the generated outputs with a repeatable rubric.

The generated artifacts from the included product research live under
`spac/`.

## What Is Included

- `.codex-plugin/plugin.json` - Codex plugin manifest.
- `.mcp.json` - Spec-Kit MCP server registration.
- `skills/` - bundled Codex skills:
  - `grill-to-spac`
  - `grill-me`
  - `to-prd`
  - `to-spac`
  - `evaluate-spac-output`
- `scripts/grill_to_spac.py` - deterministic local generator, validator, and
  evaluator.
- `schemas/` - JSON schema references for PRD and spack artifacts.
- `evals/rubric.json` - scoring rubric.
- `tests/test_grill_to_spac.py` - regression tests for PRD, spack, and eval
  output.

## Install From Main Branch

After this repository is published at:

```text
https://github.com/mutexdev/grill-to-spec
```

add it to Codex with the plugin marketplace command:

```bash
codex plugin marketplace add mutexdev/grill-to-spec --ref main
```

This lets Codex fetch and register the plugin source directly. Users do not
need to clone this repository manually or edit `~/.agents/plugins/marketplace.json`
by hand.

Restart Codex, open `/plugins`, and install or enable **Grill to Spac** from
the marketplace entry. Then start Codex in a workspace and use one of the
plugin starter prompts:

```text
Run grill-to-spac for this feature.
Create PRD.json and spacks.
Evaluate PRD and spack quality.
```

If you only want one bundled skill instead of the full plugin, install a skill
from the `main` branch with Codex's skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo mutexdev/grill-to-spec \
  --ref main \
  --path skills/grill-to-spac
```

## Local Usage

Generate artifacts from the included research file:

```bash
python3 -B scripts/grill_to_spac.py generate \
  --source grill-to-spac.md \
  --output spac \
  --project-name grill-to-spac
```

Validate generated artifacts:

```bash
python3 -B scripts/grill_to_spac.py validate --output spac
```

Re-run the eval report:

```bash
python3 -B scripts/grill_to_spac.py eval --output spac
```

Run tests:

```bash
python3 -B -m unittest tests/test_grill_to_spac.py
```

## Spec-Kit MCP

The plugin keeps a portable `spec-kit` MCP server declaration in `.mcp.json`:

```json
{
  "mcpServers": {
    "spec-kit": {
      "command": "npx",
      "args": ["@speckit/mcp@latest"]
    }
  }
}
```

Codex's own MCP server configuration lives in `~/.codex/config.toml`. If you
want to register the same server directly with Codex, add:

```toml
[mcp_servers.spec-kit]
command = "npx"
args = ["@speckit/mcp@latest"]
```

When the MCP server is available, the `grill-to-spac` skill should prefer the
Spec-Kit flow: init, specify, plan, tasks, analyze, and checklist. When MCP is
not available, the local `spac/` JSON artifacts are the fallback source of
truth.

## Verification Status

Current local verification:

```text
python3 -B -m unittest tests/test_grill_to_spac.py
python3 -B scripts/grill_to_spac.py validate --output spac
python3 -B -m json.tool .codex-plugin/plugin.json
python3 -B -m json.tool .mcp.json
```

The generated eval report is written to `spac/evals/evaluation.json`.
