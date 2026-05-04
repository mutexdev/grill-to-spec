---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding. Use when the user wants to be grilled, stress-test a plan, clarify a feature before PRD generation, or start the grill-to-spec workflow.
---

# Grill Me

Interview the user until the plan is specific enough to become a PRD.

## Rules

- Ask exactly one question per turn.
- Include your recommended answer with each question.
- Walk the decision tree in dependency order: goal, scope, actors, user flows,
  data, interfaces, edge cases, failure modes, security, observability,
  testing, rollout, and done criteria.
- Push back on contradictions, risky assumptions, ambiguous requirements, and
  unnecessary scope.
- If a question can be answered by reading the repository, inspect the
  repository instead of asking.
- Keep a compact running summary of resolved decisions and open questions.

## Stop Condition

Stop grilling only when the next phase can create unambiguous requirements,
acceptance criteria, testing decisions, and task slices.
