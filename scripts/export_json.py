from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import ensure_db

DATA_SOURCE_DIR = ROOT / "data" / "source"
DATA_INDEX_DIR = ROOT / "data" / "index"
SCHEMAS_DIR = ROOT / "schemas"
DEFAULT_EXPORT_DIR = ROOT / "data" / "export"
DEFAULT_MANIFEST_PATH = ROOT / "data" / "manifest.json"
DEFAULT_DB_GZ_PATH = DATA_INDEX_DIR / "library.db.gz"

DATASET_SPECS: dict[str, dict[str, str]] = {
    "quran_surahs": {
        "table": "quran_surahs",
        "source_csv": "data/source/surahs_ar_en.csv",
        "schema": "schemas/quran_surahs.schema.json",
        "primary_key": "surah_number",
        "order_by": "surah_number ASC",
    },
    "quran_ayahs": {
        "table": "quran_ayahs",
        "source_csv": "data/source/ayahs_ar_en.csv",
        "schema": "schemas/quran_ayahs.schema.json",
        "primary_key": "ayah_global_number",
        "order_by": "id ASC",
    },
    "hadith_collections": {
        "table": "hadith_collections",
        "source_csv": "data/source/collections_summary.csv",
        "schema": "schemas/hadith_collections.schema.json",
        "primary_key": "collection_key",
        "order_by": "collection_key ASC",
    },
    "hadith_entries": {
        "table": "hadith_entries",
        "source_csv": "data/source/hadith_all_collections_ar_en.csv",
        "schema": "schemas/hadith_entries.schema.json",
        "primary_key": "id",
        "order_by": "id ASC",
    },
    "hijri_dates": {
        "table": "hijri_dates",
        "source_csv": "data/source/ummalqura_1343_1500.csv",
        "schema": "schemas/hijri_dates.schema.json",
        "primary_key": "rjd",
        "order_by": "rjd ASC",
    },
    "prayer_times": {
        "table": "prayer_times",
        "source_csv": "data/source/prayer_times_selected_plus_all_nigeria.csv",
        "schema": "schemas/prayer_times.schema.json",
        "primary_key": "id",
        "order_by": "id ASC",
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_row(dataset_key: str, row: dict[str, Any]) -> dict[str, Any]:
    if dataset_key == "hadith_entries" and isinstance(row.get("grades"), str):
        raw_grades = row["grades"].strip()
        if raw_grades.startswith("["):
            try:
                row["grades"] = json.loads(raw_grades)
            except json.JSONDecodeError:
                pass
    return row


def build_manifest(conn: sqlite3.Connection) -> dict[str, Any]:
    datasets_meta: dict[str, Any] = {}
    for key, spec in DATASET_SPECS.items():
        csv_path = ROOT / spec["source_csv"]
        row_count = conn.execute(f"SELECT COUNT(*) FROM {spec['table']}").fetchone()[0]
        datasets_meta[key] = {
            "table": spec["table"],
            "source_csv": spec["source_csv"],
            "source_sha256": sha256_file(csv_path),
            "schema": spec["schema"],
            "row_count": int(row_count),
            "primary_key": spec["primary_key"],
        }

    return {
        "dataset_name": "Anjal Islamic Library",
        "dataset_version": "2.0.0",
        "license": "MIT",
        "api_version": "v1",
        "sqlite_snapshot": {
            "path": "data/index/library.db.gz",
            "sha256": sha256_file(DEFAULT_DB_GZ_PATH),
            "size_bytes": DEFAULT_DB_GZ_PATH.stat().st_size,
        },
        "datasets": datasets_meta,
    }


def write_manifest(conn: sqlite3.Connection, manifest_path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    manifest = build_manifest(conn)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def compress_db_snapshot(db_path: Path, gz_path: Path = DEFAULT_DB_GZ_PATH) -> None:
    gz_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = gz_path.with_suffix(".db.gz.tmp")
    with db_path.open("rb") as fin, gzip.open(tmp_path, "wb", compresslevel=6) as fout:
        while chunk := fin.read(65536):
            fout.write(chunk)
    os.replace(tmp_path, gz_path)


def export_datasets(
    conn: sqlite3.Connection,
    out_dir: Path,
    fmt: str = "jsonl",
    only: list[str] | None = None,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = only or list(DATASET_SPECS.keys())
    written: dict[str, Path] = {}

    for key in keys:
        if key not in DATASET_SPECS:
            raise ValueError(f"Unknown dataset '{key}'. Valid keys: {', '.join(DATASET_SPECS)}")
        spec = DATASET_SPECS[key]
        cur = conn.execute(f"SELECT * FROM {spec['table']} ORDER BY {spec['order_by']}")
        cols = [d[0] for d in cur.description]

        if fmt == "jsonl":
            target = out_dir / f"{key}.jsonl"
            with target.open("w", encoding="utf-8", newline="\n") as f:
                for raw_row in cur:
                    obj = _normalize_row(key, dict(zip(cols, raw_row)))
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        elif fmt == "json":
            target = out_dir / f"{key}.json"
            records = [_normalize_row(key, dict(zip(cols, r))) for r in cur]
            target.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        written[key] = target
    return written


def verify_manifest(conn: sqlite3.Connection, manifest_path: Path = DEFAULT_MANIFEST_PATH) -> list[str]:
    errors: list[str] = []
    if not manifest_path.exists():
        return [f"Missing manifest file: {manifest_path}"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = build_manifest(conn)

    if manifest.get("sqlite_snapshot") != expected["sqlite_snapshot"]:
        errors.append("sqlite_snapshot metadata in data/manifest.json is out of sync with data/index/library.db.gz")

    for key, exp_ds in expected["datasets"].items():
        actual_ds = manifest.get("datasets", {}).get(key)
        if actual_ds != exp_ds:
            errors.append(f"Dataset '{key}' in data/manifest.json does not match DB/CSV state")
        schema_file = ROOT / exp_ds["schema"]
        if not schema_file.exists():
            errors.append(f"Missing schema file: {schema_file}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export normalized JSON/JSONL datasets and manage data/manifest.json."
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_EXPORT_DIR, help="Output directory for exported files.")
    parser.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="Export file format.")
    parser.add_argument("--datasets", nargs="*", help="Subset of dataset keys to export.")
    parser.add_argument("--write-manifest", action="store_true", help="Regenerate data/manifest.json from DB and CSVs.")
    parser.add_argument("--compress-db", action="store_true", help="Refresh data/index/library.db.gz from active SQLite DB.")
    parser.add_argument("--verify", action="store_true", help="Verify data/manifest.json and schema files without writing exports.")
    args = parser.parse_args()

    db_path = Path(ensure_db())
    conn = sqlite3.connect(db_path)

    try:
        if args.compress_db:
            compress_db_snapshot(db_path)
            print(f"Compressed snapshot written: {DEFAULT_DB_GZ_PATH}")

        if args.write_manifest:
            manifest = write_manifest(conn)
            print(f"Manifest written: {DEFAULT_MANIFEST_PATH} ({len(manifest['datasets'])} datasets)")

        if args.verify:
            errors = verify_manifest(conn)
            if errors:
                for err in errors:
                    print(f"ERROR: {err}", file=sys.stderr)
                raise SystemExit(1)
            print("Manifest and schemas verified successfully.")
            return

        if not args.write_manifest and not args.compress_db or args.datasets is not None:
            written = export_datasets(conn, args.out_dir, fmt=args.format, only=args.datasets)
            for key, path in written.items():
                print(f"Exported {key} -> {path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
