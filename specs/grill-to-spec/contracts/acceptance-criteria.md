# Acceptance Contracts: grill-to-spec

- **AC-001**: Given the plugin manifest, when Codex loads the plugin, then no server entry is registered or launched.
- **AC-002**: Given a marketplace install, when Codex copies `plugins/grill-to-spec/`, then the package includes skills, runtime scripts, schemas, eval rubric, and vendored Spec Kit assets.
- **AC-003**: Given product research, when `scripts/grill_to_spec.py generate` runs, then it writes `PRD.json`, task artifacts, Spec Kit markdown, and an eval report.
- **AC-004**: Given generated artifacts, when archive creation runs, then the archive contains the PRD, task artifacts, Spec Kit markdown, eval report, plugin manifest, grill-me skill, and vendored Spec Kit assets.
