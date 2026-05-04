# Upstream Spec Kit Assets

These files are vendored from GitHub Spec Kit so the plugin can run without
starting a server or downloading command templates at runtime.

- Source: https://github.com/github/spec-kit
- Last checked upstream commit: `259494a328e13df32e18b2df31abd421c881c071`
- Vendored paths:
  - `scripts/bash/`
  - `scripts/powershell/`
  - `templates/`
  - `workflows/speckit/`
  - `downstream-references/implement.md` (quarantined from active templates)

Refresh by copying those paths from a reviewed upstream checkout, moving
`templates/commands/implement.md` back to
`downstream-references/implement.md`, removing active implement handoffs, and
rerunning `python3 -B -m unittest tests/test_grill_to_spec.py`.

Local note: `templates/commands/taskstoissues.md` keeps the upstream behavior but
uses generic GitHub issue-tool wording and omits the upstream issue-tool
frontmatter so this plugin does not imply a server startup requirement.
