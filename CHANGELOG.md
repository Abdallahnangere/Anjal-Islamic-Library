# Changelog

All notable changes to this project are documented in this file.

## [2.0.0] - 2026-11-17

### Changed
- Converted the repository into a headless structured dataset pipeline and FastAPI JSON data service.
- Replaced the HTML root page with a structured JSON service manifest (`GET /`) and added `/redoc` alongside `/docs` and `/openapi.json`.
- Updated `README.md` to document the dataset schemas, export pipeline, and API contract (and fixed the GitHub repository link typo).

### Added
- JSON Schema (Draft 2020-12) definitions under `schemas/` for all 6 datasets and `manifest.json`.
- `scripts/export_json.py` for deterministic JSON/JSONL dataset export, snapshot compression, and `data/manifest.json` verification.
- Automated `pytest` suite (`tests/test_api.py`, `tests/test_dataset_pipeline.py`) and GitHub Actions CI workflow (`.github/workflows/ci.yml`).

### Removed
- Removed the embedded HTML website (`GET /`, `GET /developers`) and `app/static/` media gallery assets (~24.5 MB).

## [1.1.0] - 2026-04-29

### Added
- API key authentication support for protected API consumption workflows.
- Rate-limiting behavior and accompanying integration-facing response controls.
- Pagination support for high-volume listing and search endpoints.
- Extended filtering capabilities across query-based endpoint usage.
- New SDK-style client examples and documentation updates for cURL, JavaScript, and Python.

## [1.0.0] - 2026-04-29

### Added
- Initial `v1` API with Quran, Hadith, Hijri, and Prayer endpoints.
- SQLite indexing pipeline (`scripts/build_db.py`) with FTS5 search for Quran and Hadith.
- Vercel serverless entrypoint (`api/index.py`) and runtime routing (`vercel.json`).
- Metadata endpoint and structured dataset counts.

### Changed
- Improved ingestion normalization for Arabic text handling.

### Fixed
- Serverless filesystem crash by honoring writable `ANJAL_DB_PATH` path.
