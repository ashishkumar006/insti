# archive/ — redundant files moved here, nothing deleted

- `caches/` — regenerable Python/pytest caches (`__pycache__`, `.pytest_cache`).
  Safe to delete outright; Python recreates them on next run.
  Moved (not deleted) on request. Restore: move back or just re-run the app/tests.

Nothing else is archived: every other file/folder in the workspace belongs to a
running service (old :8201 stack, new :8200 API, gateway :8109 config), the live
index (`indexes/`), the corpus (`data/`), tests, docs, or DB bootstrap (`var/`).
