"""Automated market-digest generation from stored series and panel docs."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

from collector.changes import apply_transform, ref_close
from collector.config import Config
from collector.store import Store

ANOMALY_Z = 2.2
TREND_Z = 1.15
HISTORY_MIN = 20
WINDOW = 180
PREDICTION_MIN = 20
PREDICTION_WINDOW_DAYS = 180
PREDICTION_SIGNAL = 0.8


@dataclass(frozen=True)
class DigestSeries:
    series_id: str
    store_id: str
    name: str
    unit: str
    transform: str = "none"


def _series_catalog(cfg: Config) -> list[DigestSeries]:
    items = [
        *[
            DigestSeries(s.id, f"macro:{s.id}", s.name, s.unit, s.transform)
            for s in cfg.series
        ],
        *[
            DigestSeries(s.id, f"cycle:{s.id}", s.name, s.unit, s.transform)
            for s in cfg.cycle_series
            if not s.hidden
        ],
        *[
            DigestSeries(i.symbol, f"idx:{i.symbol}", i.name, "px")
            for i in cfg.indexes
        ],
        *[
            DigestSeries(f"{b.country}{b.tenor}", f"yield:{b.country}{b.tenor}",
                         f"{b.country} {b.tenor} yield", "%")
            for b in cfg.bonds
        ],
        *[
            DigestSeries(f"{c.country}CB", f"cb:{c.country}", c.label, "%")
            for c in cfg.cb_rates
        ],
        *[
            DigestSeries(a.supply_id, f"ref:{a.supply_id}", a.supply_label, "%")
            for a in cfg.refs.aave
        ],
        *[
            DigestSeries(a.borrow_id, f"ref:{a.borrow_id}", a.borrow_label, "%")
            for a in cfg.refs.aave
        ],
        *[
            DigestSeries(p.implied_id, f"ref:{p.implied_id}", p.implied_label, "%")
            for p in cfg.refs.pendle
        ],
        *[
            DigestSeries(p.underlying_id, f"ref:{p.underlying_id}", p.underlying_label, "%")
            for p in cfg.refs.pendle
        ],
        *[
            DigestSeries(f.id, f"ref:{f.id}", f.label, "%")
            for f in cfg.refs.funding
        ],
    ]
    deduped: list[DigestSeries] = []
    seen: set[str] = set()
    for item in items:
        if item.store_id in seen:
            continue
        seen.add(item.store_id)
        deduped.append(item)
    return deduped


def _fmt_value(value: float, unit: str) -> str:
    if unit == "%":
        return f"{value:.2f}%"
    if unit == "px":
        return f"{value:,.1f}"
    if unit in {"k", "m", "idx", "pts", "ratio"}:
        return f"{value:.2f}"
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.2f}"


def _coverage(store: Store, tracked_series: int, active_series: int) -> dict:
    macro = store.doc("macro_calendar")
    news = store.doc("news")
    defi = store.doc("defi_pools")
    midnight = store.doc("midnight_curve")
    morpho = store.doc("morpho_markets")
    refs = store.doc("rate_refs")
    return {
        "tracked_series": tracked_series,
        "active_series": active_series,
        "upcoming_macro": len((macro.payload.get("releases") if macro else []) or []),
        "headlines": len((news.payload.get("items") if news else []) or []),
        "defi_rows": len((defi.payload.get("rows") if defi else []) or []),
        "midnight_rows": len((midnight.payload.get("rows") if midnight else []) or []),
        "morpho_rows": len((morpho.payload.get("rows") if morpho else []) or []),
        "refs_rows": len((refs.payload.get("rows") if refs else []) or []),
    }


def _slope_per_day(ordered: list[tuple]) -> float | None:
    if len(ordered) < 2:
        return None
    anchor = ordered[0][0]
    xs = [(d - anchor).days for d, _ in ordered]
    ys = [v for _, v in ordered]
    x_mean = mean(xs)
    y_mean = mean(ys)
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return None
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=False))
    return num / den


def build_digest(store: Store, cfg: Config, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    anomalies = []
    trends = []
    predictions = []
    active_series = 0
    for item in _series_catalog(cfg):
        points = apply_transform(store.points(item.store_id), item.transform)
        if len(points) < 2:
            continue
        ordered = sorted(points.items())
        active_series += 1
        latest_date, latest_value = ordered[-1]
        baseline = [v for _, v in ordered[:-1][-WINDOW:]]
        if len(baseline) >= HISTORY_MIN:
            sigma = pstdev(baseline)
            if sigma > 0:
                level_mean = mean(baseline)
                z_score = round((latest_value - level_mean) / sigma, 2)
                if abs(z_score) >= ANOMALY_Z:
                    anomalies.append({
                        "id": f"anomaly:{item.series_id}",
                        "series_id": item.series_id,
                        "name": item.name,
                        "unit": item.unit,
                        "value": round(latest_value, 2),
                        "direction": "up" if z_score > 0 else "down",
                        "z_score": z_score,
                        "summary": f"{_fmt_value(latest_value, item.unit)} is {abs(z_score):.2f}σ "
                                   f"{'above' if z_score > 0 else 'below'} trend",
                        "as_of": latest_date.isoformat(),
                    })
                ref_1m = ref_close(points, latest_date, "1m")
                if ref_1m is not None:
                    delta = round(latest_value - ref_1m, 2)
                    trend_score = round(abs(delta) / sigma, 2)
                    if delta != 0 and trend_score >= TREND_Z:
                        trends.append({
                            "id": f"trend:{item.series_id}",
                            "series_id": item.series_id,
                            "name": item.name,
                            "unit": item.unit,
                            "value": round(latest_value, 2),
                            "previous": round(ref_1m, 2),
                            "delta": delta,
                            "direction": "up" if delta > 0 else "down",
                            "trend_score": trend_score,
                            "summary": f"{delta:+.2f} vs 1m ({trend_score:.2f}σ move)",
                            "as_of": latest_date.isoformat(),
                        })
        recent = [(d, v) for d, v in ordered if d >= latest_date - timedelta(days=PREDICTION_WINDOW_DAYS)]
        if len(recent) >= PREDICTION_MIN:
            slope = _slope_per_day(recent)
            if slope is not None and slope != 0:
                sigma = pstdev([v for _, v in recent])
                projected_7d = round(latest_value + slope * 7, 2)
                projected_30d = round(latest_value + slope * 30, 2)
                delta_30d = round(projected_30d - latest_value, 2)
                signal = 0.0 if sigma <= 0 else round(abs(delta_30d) / sigma, 2)
                if signal >= PREDICTION_SIGNAL:
                    predictions.append({
                        "id": f"prediction:{item.series_id}",
                        "series_id": item.series_id,
                        "name": item.name,
                        "unit": item.unit,
                        "value": round(latest_value, 2),
                        "projected_7d": projected_7d,
                        "projected_30d": projected_30d,
                        "delta_30d": delta_30d,
                        "direction": "up" if delta_30d > 0 else "down",
                        "signal_score": signal,
                        "summary": f"30d projection {delta_30d:+.2f} ({signal:.2f}σ)",
                        "as_of": latest_date.isoformat(),
                    })
    anomalies.sort(key=lambda row: abs(row["z_score"]), reverse=True)
    trends.sort(key=lambda row: row["trend_score"], reverse=True)
    predictions.sort(key=lambda row: row["signal_score"], reverse=True)
    coverage = _coverage(store, tracked_series=len(_series_catalog(cfg)), active_series=active_series)
    lead = anomalies[0]["name"] if anomalies else trends[0]["name"] if trends else "No strong moves yet"
    newsletter = {
        "headline": (
            f"{len(anomalies)} anomalies, {len(trends)} strong trends, "
            f"and {len(predictions)} predictions across "
            f"{coverage['active_series']} live series"
        ),
        "bullets": [
            f"Lead signal: {lead}.",
            f"Calendar: {coverage['upcoming_macro']} upcoming releases and "
            f"{coverage['headlines']} headlines monitored.",
            f"Cross-market coverage: {coverage['defi_rows']} DeFi rows, "
            f"{coverage['midnight_rows']} Midnight maturities, "
            f"{coverage['morpho_rows']} Morpho markets, {coverage['refs_rows']} rate refs.",
        ] + [
            f"Anomaly — {row['name']}: {row['summary']}."
            for row in anomalies[:2]
        ] + [
            f"Trend — {row['name']}: {row['summary']}."
            for row in trends[:2]
        ] + [
            f"Prediction — {row['name']}: {row['summary']}."
            for row in predictions[:2]
        ],
        "coverage": coverage,
    }
    digest_id = hashlib.sha256(json.dumps(
        {
            "alerts": [{k: row[k] for k in ("series_id", "direction", "summary")} for row in anomalies[:8]],
            "trends": [{k: row[k] for k in ("series_id", "direction", "summary")} for row in trends[:8]],
            "predictions": [
                {k: row[k] for k in ("series_id", "direction", "summary")}
                for row in predictions[:8]
            ],
            "newsletter": newsletter,
        },
        sort_keys=True,
    ).encode("utf-8")).hexdigest()[:16]
    return {
        "digest_id": digest_id,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "alerts": anomalies[:8],
        "trends": trends[:8],
        "predictions": predictions[:8],
        "newsletter": newsletter,
    }


async def refresh_digest(store: Store, cfg: Config) -> str:
    store.put_doc("insights", build_digest(store, cfg), source="local-analysis")
    return "local-analysis"
