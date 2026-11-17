from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


def call_asgi(path: str, params: dict[str, object] | None = None) -> tuple[int, dict[str, str], bytes]:
    query_string = urlencode({k: v for k, v in (params or {}).items() if v is not None}).encode("utf-8")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string,
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    messages: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in start.get("headers", [])}
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return int(start["status"]), headers, body


class TestAnjalApi(unittest.TestCase):
    def test_root_returns_headless_json_manifest(self) -> None:
        status, headers, raw = call_asgi("/")
        self.assertEqual(status, 200)
        self.assertTrue(headers["content-type"].startswith("application/json"))
        text = raw.decode("utf-8")
        self.assertNotIn("At-Tibyan", text)
        body = json.loads(text)
        self.assertTrue(body["ok"])
        self.assertEqual(body["api_version"], "v1")
        self.assertIn("endpoints", body)

    def test_website_routes_and_static_removed(self) -> None:
        self.assertEqual(call_asgi("/developers")[0], 404)
        self.assertEqual(call_asgi("/static/attibyan-logo.png")[0], 404)

    def test_openapi_and_docs_available(self) -> None:
        docs_status, _, docs_raw = call_asgi("/docs")
        self.assertEqual(docs_status, 200)
        self.assertIn("SwaggerUIBundle", docs_raw.decode("utf-8"))

        redoc_status, _, redoc_raw = call_asgi("/redoc")
        self.assertEqual(redoc_status, 200)
        self.assertIn("redoc", redoc_raw.decode("utf-8").lower())

        schema_status, _, schema_raw = call_asgi("/openapi.json")
        self.assertEqual(schema_status, 200)
        schema = json.loads(schema_raw.decode("utf-8"))
        self.assertIn("/v1/health", schema["paths"])
        self.assertIn("/v1/quran/ayah/{surah}/{ayah}", schema["paths"])

    def test_health_and_meta(self) -> None:
        status, _, raw = call_asgi("/v1/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["ok"])

        meta_status, _, meta_raw = call_asgi("/v1/meta")
        self.assertEqual(meta_status, 200)
        counts = json.loads(meta_raw)["counts"]
        self.assertEqual(counts["quran_ayahs"], 6236)
        self.assertGreater(counts["hadith_entries"], 30000)
        self.assertGreater(counts["hijri_dates"], 50000)
        self.assertGreater(counts["prayer_times"], 800)

    def test_quran_endpoints(self) -> None:
        status, _, raw = call_asgi("/v1/quran/surahs")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["count"], 114)

        ayah_status, _, ayah_raw = call_asgi("/v1/quran/ayah/1/1")
        self.assertEqual(ayah_status, 200)
        ayah_body = json.loads(ayah_raw)
        self.assertTrue(ayah_body["found"])
        self.assertIn("Merciful", ayah_body["data"]["text_english_sahih"])

        search_status, _, search_raw = call_asgi("/v1/quran/search", {"q": "mercy", "limit": 5})
        self.assertEqual(search_status, 200)
        search_body = json.loads(search_raw)
        self.assertGreaterEqual(search_body["count"], 1)
        self.assertLessEqual(search_body["count"], 5)

    def test_hadith_endpoints(self) -> None:
        col_status, _, col_raw = call_asgi("/v1/hadith/collections")
        self.assertEqual(col_status, 200)
        self.assertGreaterEqual(json.loads(col_raw)["count"], 1)

        hadith_status, _, hadith_raw = call_asgi("/v1/hadith/nawawi/1")
        self.assertEqual(hadith_status, 200)
        self.assertTrue(json.loads(hadith_raw)["found"])

        search_status, _, search_raw = call_asgi(
            "/v1/hadith/search", {"q": "prayer", "collection": "bukhari", "limit": 3}
        )
        self.assertEqual(search_status, 200)
        search_body = json.loads(search_raw)
        self.assertGreaterEqual(search_body["count"], 1)
        self.assertLessEqual(search_body["count"], 3)

    def test_hijri_endpoints(self) -> None:
        status, _, raw = call_asgi("/v1/hijri/to-gregorian", {"year": 1447, "month": 11, "day": 12})
        self.assertEqual(status, 200)
        body = json.loads(raw)
        self.assertTrue(body["found"])
        greg = body["gregorian_iso"]

        status2, _, raw2 = call_asgi("/v1/hijri/from-gregorian", {"date": greg})
        self.assertEqual(status2, 200)
        body2 = json.loads(raw2)
        self.assertTrue(body2["found"])
        self.assertEqual(body2["hijri_iso"], "1447-11-12")

    def test_prayer_endpoints(self) -> None:
        c_status, _, c_raw = call_asgi("/v1/prayer/countries")
        self.assertEqual(c_status, 200)
        self.assertIn("Nigeria", json.loads(c_raw)["countries"])

        city_status, _, city_raw = call_asgi("/v1/prayer/cities", {"country": "Nigeria", "limit": 10})
        self.assertEqual(city_status, 200)
        self.assertEqual(json.loads(city_raw)["count"], 10)

        t_status, _, t_raw = call_asgi("/v1/prayer/times", {"country": "Nigeria", "city": "Lagos Island"})
        self.assertEqual(t_status, 200)
        t_body = json.loads(t_raw)
        self.assertTrue(t_body["found"])
        self.assertTrue(t_body["data"]["fajr"])


if __name__ == "__main__":
    unittest.main()
