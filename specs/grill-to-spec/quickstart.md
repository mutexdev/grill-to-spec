# Quickstart: grill-to-spec

Review the generated handoff without starting implementation:

```bash
python3 -B scripts/grill_to_spec.py validate --output spec --specs-output specs
python3 -B scripts/grill_to_spec.py eval --output spec
python3 -B scripts/grill_to_spec.py archive --output spec --specs-output specs
```

Spec Kit markdown lives in `specs/grill-to-spec/`. Implementation requires a separate explicit request after review.
