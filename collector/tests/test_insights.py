from datetime import date, datetime, timezone
from pathlib import Path

from collector.config import load_config
from collector.insights import build_digest
from collector.store import Store

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_digest_surfaces_anomalies_trends_and_coverage(tmp_path):
    cfg = load_config(REPO_ROOT / "config.yaml")
    store = Store(tmp_path / "t.db")

    spx_points = [(date(2026, 1, d), 100.0 + (d % 3)) for d in range(1, 29)]
    spx_points += [(date(2026, 2, 1), 130.0)]
    store.upsert_points("idx:SPX", spx_points)

    vix_points = [(date(2026, 1, d), 20.0 + (d % 2)) for d in range(1, 29)]
    vix_points += [(date(2026, 2, 1), 15.0)]
    store.upsert_points("cycle:vix", vix_points)

    store.put_doc("macro_calendar", {"releases": [{"name": "CPI"}]}, source="forexfactory")
    store.put_doc("news", {"items": [{"headline": "h"}]}, source="rss")
    store.put_doc("defi_pools", {"rows": [{"pool": "x"}]}, source="zyfai")
    store.put_doc("midnight_curve", {"rows": [{"market_id": "m"}]}, source="morpho")
    store.put_doc("morpho_markets", {"rows": [{"market_id": "m"}]}, source="morpho-blue")
    store.put_doc("rate_refs", {"rows": [{"id": "r"}]}, source="refs")

    digest = build_digest(store, cfg, now=datetime(2026, 2, 1, tzinfo=timezone.utc))

    assert digest["alerts"]
    assert digest["trends"]
    assert digest["predictions"]
    assert digest["newsletter"]["coverage"]["tracked_series"] >= digest["newsletter"]["coverage"]["active_series"]
    assert digest["newsletter"]["coverage"]["upcoming_macro"] == 1
    assert digest["newsletter"]["coverage"]["headlines"] == 1
