# Contributing to Screenux Screenshot

Thanks for contributing. Keep changes focused, secure, and aligned with the
project's offline-first behavior.

## Ground rules

- Keep PRs small and scoped to one concern.
- Preserve existing style and structure.
- Do not add network-dependent behavior.
- Prefer secure defaults and minimal privileges.

## Development workflow (TDD first)

1. Add or update a failing test for the behavior change.
2. Implement the smallest code change to make it pass.
3. Refactor while keeping tests green.

## Local setup

```bash
python3 -m pip install -r requirements-dev.txt
```

Run app locally:

```bash
./screenux-screenshot
```

## Validation before opening a PR

Run the project checks relevant to your change:

```bash
python3 -m py_compile src/screenux_screenshot.py
pytest -q
```

If your change touches shell scripts, also run shell checks used in CI.

## Commit and PR guidance

- Use clear commit messages in imperative mood.
- Include test updates with behavior changes.
- Describe user-visible impact in the PR description.
- Keep documentation in sync when behavior or workflow changes.

## Security and privacy expectations

- Keep runtime behavior offline-only.
- Do not broaden Flatpak/runtime permissions unless strictly required.
- Maintain safe file handling and local URI validation behavior.
