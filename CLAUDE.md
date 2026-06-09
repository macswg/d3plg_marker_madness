# Project conventions

## Versioning

Bump the `version` field in `package.json` with every commit. Use semantic
versioning (`MAJOR.MINOR.PATCH`):

- **PATCH** — bug fixes and small tweaks
- **MINOR** — new features
- **MAJOR** — breaking changes

The app displays this version in the footer (`src/App.vue`), so bumping it keeps
the visible version in sync. Include the bump in the same commit as the change.
