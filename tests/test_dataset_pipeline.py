from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import ensure_db
from scripts.export_json import DATASET_SPECS
from scripts.export_json import export_datasets
from scripts.export_json import verify_manifest

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover - optional locally, installed in CI
    jsonschema = None


def _basic_validate_record(record: dict, schema: dict) -> None:
    for req in schema.get("required", []):
        if req not in record:
            raise AssertionError(f"Missing required field '{req}' in record")
    allowed = set(schema.get("properties", {}).keys())
    if schema.get("additionalProperties") is False and allowed:
        extra = set(record.keys()) - allowed
        if extra:
            raise AssertionError(f"Unexpected properties {extra}")


class TestDatasetPipeline(unittest.TestCase):
    def test_manifest_matches_database_and_schema(self) -> None:
        manifest_path = ROOT / "data" / "manifest.json"
        manifest_schema_path = ROOT / "schemas" / "manifest.schema.json"
        self.assertTrue(manifest_path.exists())
        self.assertTrue(manifest_schema_path.exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
        if jsonschema is not None:
            jsonschema.validate(instance=manifest, schema=manifest_schema)
        else:
            _basic_validate_record(manifest, manifest_schema)

        db_path = Path(ensure_db())
        conn = sqlite3.connect(db_path)
        try:
            errors = verify_manifest(conn, manifest_path)
            self.assertEqual(errors, [])
        finally:
            conn.close()

    def test_json_exporter_and_schemas(self) -> None:
        db_path = Path(ensure_db())
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            conn = sqlite3.connect(db_path)
            try:
                written = export_datasets(conn, tmp_path, fmt="jsonl")
            finally:
                conn.close()

            self.assertEqual(set(written.keys()), set(DATASET_SPECS.keys()))

            for key, jsonl_path in written.items():
                schema = json.loads((ROOT / DATASET_SPECS[key]["schema"]).read_text(encoding="utf-8"))
                validator = jsonschema.Draft202012Validator(schema) if jsonschema is not None else None
                with jsonl_path.open("r", encoding="utf-8") as f:
                    lines = [next(f) for _ in range(5)]
                self.assertEqual(len(lines), 5)
                for line in lines:
                    record = json.loads(line)
                    if validator is not None:
                        validator.validate(record)
                    else:
                        _basic_validate_record(record, schema)


if __name__ == "__main__":
    unittest.main()
