# Data Model: grill-to-spec

No product data entities were inferred by the deterministic fallback generator. The canonical machine-readable planning entities are:

- PRD requirement: stable `REQ-###` item in `spec/PRD.json`.
- User story: stable `US-###` item linked to one or more requirements.
- Acceptance criterion: stable `AC-###` item linked through requirements.
- Task artifact: vertical-slice JSON work item under `spec/task-artifacts/`.
