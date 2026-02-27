# AGENTS

## Purpose
Lightweight contributor guidance for this repository.

## Basic Instructions
- Keep changes small, focused, and scoped to the requested task.
- Prefer secure defaults and avoid adding unnecessary privileges or side effects.
- Do not introduce network-dependent behavior; this app is offline-first.
- Preserve existing project style and structure.

## Development Method (TDD First)
- Use TDD as the main way to develop:
  1. Write or update a failing test for the intended behavior.
  2. Implement the minimal code change to make the test pass.
  3. Refactor safely while keeping tests green.
- Run relevant tests locally (or in Docker) before finishing.

## Documentation Rule
- Update `README.md` whenever changes affect:
  - behavior,
  - setup/run instructions,
  - security posture,
  - developer workflow.
