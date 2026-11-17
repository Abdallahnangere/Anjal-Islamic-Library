# Anjal Islamic Library — Structured Dataset & Data API

[![CI](https://github.com/Abdallahnangere/Anjal-Islamic-Library/actions/workflows/ci.yml/badge.svg)](https://github.com/Abdallahnangere/Anjal-Islamic-Library/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-OpenAPI_3-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

Headless, versioned Islamic reference datasets and FastAPI JSON data service covering **Quran**, **Hadith**, **Umm al-Qura Hijri calendar**, and **Prayer Times** (including all Nigerian LGAs/cities and selected international cities).

- **GitHub:** `https://github.com/Abdallahnangere/Anjal-Islamic-Library`
- **Production API:** `https://islamiclibrary.anjalventures.com` *(HTTPS-only)*
- **Interactive OpenAPI Docs:** `/docs` · **ReDoc:** `/redoc` · **OpenAPI JSON:** `/openapi.json`
- **Maintainer:** Abdallah Nangere (`founder@ramadanbot.app`)

---

## Included Structured Datasets

| Dataset Key | Source CSV | JSON Schema | Records |
| --- | --- | --- | ---: |
| `quran_surahs` | [`data/source/surahs_ar_en.csv`](./data/source/surahs_ar_en.csv) | [`schemas/quran_surahs.schema.json`](./schemas/quran_surahs.schema.json) | 114 |
| `quran_ayahs` | [`data/source/ayahs_ar_en.csv`](./data/source/ayahs_ar_en.csv) | [`schemas/quran_ayahs.schema.json`](./schemas/quran_ayahs.schema.json) | 6,236 |
| `hadith_collections` | [`data/source/collections_summary.csv`](./data/source/collections_summary.csv) | [`schemas/hadith_collections.schema.json`](./schemas/hadith_collections.schema.json) | 10 |
| `hadith_entries` | [`data/source/hadith_all_collections_ar_en.csv`](./data/source/hadith_all_collections_ar_en.csv) | [`schemas/hadith_entries.schema.json`](./schemas/hadith_entries.schema.json) | 36,512 |
| `hijri_dates` | [`data/source/ummalqura_1343_1500.csv`](./data/source/ummalqura_1343_1500.csv) | [`schemas/hijri_dates.schema.json`](./schemas/hijri_dates.schema.json) | 55,991 |
| `prayer_times` | [`data/source/prayer_times_selected_plus_all_nigeria.csv`](./data/source/prayer_times_selected_plus_all_nigeria.csv) | [`schemas/prayer_times.schema.json`](./schemas/prayer_times.schema.json) | 836 |

- Dataset checksums, counts, and SQLite snapshot hashes are tracked in [`data/manifest.json`](./data/manifest.json) (validated against [`schemas/manifest.schema.json`](./schemas/manifest.schema.json)).
- Pre-built compressed SQLite FTS5 snapshot: [`data/index/library.db.gz`](./data/index/library.db.gz).

---

## Dataset Pipeline & Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # On macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

# 1. Build SQLite FTS5 index from CSV sources
python scripts/build_db.py

# 2. Verify UTF-8 / Arabic normalization (zero mojibake)
python scripts/verify_text_encoding.py

# 3. Export normalized JSONL or JSON datasets (written to data/export/)
python scripts/export_json.py --format jsonl

# 4. Verify data/manifest.json & JSON Schemas match the database
python scripts/export_json.py --verify

# 5. Run the automated test suite
pytest -v

# 6. Start the headless JSON API locally
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## Repository Layout

```text
api/                        # Vercel ASGI entrypoint
app/
  main.py                   # Headless FastAPI service, auth/rate-limit middleware, /docs & /openapi.json
  bootstrap.py              # Hydrates library.db from library.db.gz snapshot
  db.py                     # SQLite connection helper
  i18n.py                   # English / Arabic response localization
  routers/                  # /v1/meta, /v1/quran, /v1/hadith, /v1/hijri, /v1/prayer
data/
  source/                   # Canonical UTF-8 CSV datasets
  index/                    # Compressed SQLite FTS5 snapshot (library.db.gz)
  manifest.json             # SHA-256 checksums, record counts & schema registry
schemas/                    # JSON Schema (Draft 2020-12) definitions
scripts/
  build_db.py               # Normalizes CSVs (BOM/NFC/mojibake) & builds SQLite FTS5 DB
  export_json.py            # Exports typed JSON/JSONL & verifies manifest/schemas
  verify_text_encoding.py   # Scans SQLite text columns for encoding corruption
tests/                      # Pytest suite for FastAPI endpoints & dataset pipeline
examples/                   # Python & JavaScript client wrappers
```

---

## API Endpoints (`v1`)

| Group | Endpoints |
| --- | --- |
| **Service** | `GET /`, `GET /v1/health`, `GET /v1/meta`, `GET /docs`, `GET /redoc`, `GET /openapi.json` |
| **Quran** | `GET /v1/quran/surahs`, `GET /v1/quran/ayah/{surah}/{ayah}`, `GET /v1/quran/search?q=...` |
| **Hadith** | `GET /v1/hadith/collections`, `GET /v1/hadith/{collection}/{hadith_number}`, `GET /v1/hadith/search?q=...` |
| **Hijri** | `GET /v1/hijri/to-gregorian?year=...&month=...&day=...`, `GET /v1/hijri/from-gregorian?date=YYYY-MM-DD` |
| **Prayer** | `GET /v1/prayer/countries`, `GET /v1/prayer/cities?country=...`, `GET /v1/prayer/times?country=...&city=...`, `GET /v1/prayer/search-city?q=...` |

Optional environment controls:
- `ANJAL_API_KEYS`: comma-separated keys enforced via `X-API-Key` or `Authorization: Bearer <key>` on `/v1/*` when set.
- `ANJAL_RATE_LIMIT_WINDOW_SEC` / `ANJAL_RATE_LIMIT_MAX_REQUESTS`: sliding-window rate limit controls.
- `ANJAL_DB_PATH` / `ANJAL_DISABLE_RUNTIME_DB_BUILD`: runtime SQLite path and cold-start guard (used by Vercel in `api/index.py`).

### Client Examples
- Python: [`examples/python_client.py`](./examples/python_client.py)
- JavaScript: [`examples/js_client.mjs`](./examples/js_client.mjs)

---

## License

Released under the [MIT License](./LICENSE).
