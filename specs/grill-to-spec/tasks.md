# Tasks: grill-to-spec

**Input**: Design documents from `/specs/grill-to-spec/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Planning Boundary**: All tasks are unchecked handoff items. Do not mark any task complete or edit product source until the user makes a separate post-review implementation request.

## Format: `[ID] [P?] [Story] Description`

Tasks use Spec Kit checklist syntax and include PRD references for traceability.

## Phase 1: Grill and phase-gate discovery (TASKART-001)

**Type**: HITL
**Blocked By**: None

- [ ] T001 [US1] Execute downstream handoff item for FR-001/REQ-001 using spec/PRD.json; refs: REQ-001, AC-001
- [ ] T002 [US2] Execute downstream handoff item for FR-002/REQ-002 using spec/PRD.json; refs: REQ-002, AC-002
- [ ] T009 [US1] Execute downstream handoff item for FR-009/REQ-009 using spec/PRD.json; refs: REQ-009, AC-001
- [ ] T011 [US1] Execute downstream handoff item for FR-011/REQ-011 using spec/PRD.json; refs: REQ-011, AC-003

---

## Phase 2: Generate machine-actionable PRD (TASKART-002)

**Type**: AFK
**Blocked By**: TASKART-001

- [ ] T003 [P] [US3] Execute downstream handoff item for FR-003/REQ-003 using spec/PRD.json; refs: REQ-003, AC-003
- [ ] T004 [P] [US4] Execute downstream handoff item for FR-004/REQ-004 using spec/PRD.json; refs: REQ-004, AC-004

---

## Phase 3: Create traceable task artifacts and tasks (TASKART-003)

**Type**: AFK
**Blocked By**: TASKART-002

- [ ] T006 [P] [US6] Execute downstream handoff item for FR-006/REQ-006 using spec/PRD.json; refs: REQ-006, AC-002
- [ ] T012 [P] [US1] Execute downstream handoff item for FR-012/REQ-012 using spec/PRD.json; refs: REQ-012, AC-004

---

## Phase 4: Evaluate and validate outputs (TASKART-004)

**Type**: AFK
**Blocked By**: TASKART-003

- [ ] T007 [P] [US7] Execute downstream handoff item for FR-007/REQ-007 using spec/PRD.json; refs: REQ-007, AC-003
- [ ] T008 [P] [US8] Execute downstream handoff item for FR-008/REQ-008 using spec/PRD.json; refs: REQ-008, AC-004
- [ ] T010 [P] [US1] Execute downstream handoff item for FR-010/REQ-010 using spec/PRD.json; refs: REQ-010, AC-002

---

## Phase 5: Prepare Spec Kit local asset handoff (TASKART-005)

**Type**: AFK
**Blocked By**: TASKART-004

- [ ] T005 [P] [US5] Execute downstream handoff item for FR-005/REQ-005 using spec/PRD.json; refs: REQ-005, AC-001

---

## Dependencies & Execution Order

- Review `spec.md`, `plan.md`, and `spec/PRD.json` before selecting tasks.
- Respect each task artifact's `blocked_by` list.
- Keep all boxes unchecked in this planning handoff.
- Implementation starts only after a separate explicit request.

## Implementation Strategy

Use User Story 1 as the first downstream slice after review. Run the listed verification commands before marking any later implementation task complete.
