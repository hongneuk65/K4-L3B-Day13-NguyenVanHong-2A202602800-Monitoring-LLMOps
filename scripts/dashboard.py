"""Serve a dependency-light six-panel dashboard from data/logs.jsonl.

The dashboard intentionally uses only the Python standard library plus PyYAML,
which is already part of the API requirements. It regenerates the page for
each request and the browser reloads it every 30 seconds, so new JSONL records
are visible without adding a plotting dependency to the API environment.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
WIDTH = 680
HEIGHT = 180


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percent / 100 * len(ordered)) - 1))
    return float(ordered[index])


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def minute_key(timestamp: datetime) -> datetime:
    return timestamp.replace(second=0, microsecond=0)


def load_data() -> tuple[list[dict[str, Any]], datetime]:
    records: list[dict[str, Any]] = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                record["_time"] = parse_ts(record["ts"])
                records.append(record)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
    end = max((record["_time"] for record in records), default=datetime.now(timezone.utc))
    start = end - timedelta(minutes=60)
    return [record for record in records if start <= record["_time"] <= end], end


def group(records: list[dict[str, Any]], predicate) -> dict[datetime, list[dict[str, Any]]]:
    values: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if predicate(record):
            values[minute_key(record["_time"])].append(record)
    return values


def dashboard_values(records: list[dict[str, Any]]) -> dict[str, Any]:
    responses = [r for r in records if r.get("event") == "response_sent"]
    requests = group(records, lambda r: r.get("event") == "request_received")
    response_minutes = group(records, lambda r: r.get("event") == "response_sent")
    error_minutes = group(records, lambda r: r.get("event") in {"request_received", "request_failed"})
    tool_records = [r for r in records if isinstance(r.get("tool_success"), bool)]

    latency = [float(r["latency_ms"]) for r in responses if isinstance(r.get("latency_ms"), (int, float))]
    ttft = [float(r["ttft_ms"]) for r in responses if isinstance(r.get("ttft_ms"), (int, float))]
    costs = [float(r["cost_usd"]) for r in responses if isinstance(r.get("cost_usd"), (int, float))]
    input_tokens = [float(r["tokens_in"]) for r in responses if isinstance(r.get("tokens_in"), (int, float))]
    output_tokens = [float(r["tokens_out"]) for r in responses if isinstance(r.get("tokens_out"), (int, float))]
    quality = [float(r["quality_score"]) for r in responses if isinstance(r.get("quality_score"), (int, float))]

    def series(mapping, calculation) -> list[float]:
        return [calculation(items) for _, items in sorted(mapping.items())]

    error_rate = series(
        error_minutes,
        lambda items: 100
        * sum(item.get("event") == "request_failed" for item in items)
        / max(1, sum(item.get("event") == "request_received" for item in items)),
    )
    retrieval_success = 100 * sum(record["tool_success"] for record in tool_records) / max(1, len(tool_records))
    return {
        "latency": {
            "series": [latency],
            "labels": ["latency_ms"],
            "summary": f"P50 {percentile(latency, 50):.0f} · P95 {percentile(latency, 95):.0f} · P99 {percentile(latency, 99):.0f} · TTFT P95 {percentile(ttft, 95):.0f} ms",
            "values": [percentile(latency, 95)],
        },
        "traffic": {
            "series": [series(requests, lambda items: float(len(items)))],
            "labels": ["requests/min"],
            "summary": f"{len(requests)} minute buckets · {sum(len(items) for items in requests.values())} requests",
            "values": [float(sum(len(items) for items in requests.values()))],
        },
        "errors": {
            "series": [error_rate],
            "labels": ["error_rate_pct"],
            "summary": f"Error rate {100 * sum(r.get('event') == 'request_failed' for r in records) / max(1, sum(r.get('event') == 'request_received' for r in records)):.2f}% · Retrieval success {retrieval_success:.1f}%",
            "values": [100 * sum(r.get("event") == "request_failed" for r in records) / max(1, sum(r.get("event") == "request_received" for r in records)), retrieval_success],
        },
        "cost": {
            "series": [series(response_minutes, lambda items: sum(float(item.get("cost_usd", 0)) for item in items))],
            "labels": ["usd/min"],
            "summary": f"Total ${sum(costs):.6f} · Average ${mean(costs):.6f}/request",
            "values": [sum(costs)],
        },
        "tokens": {
            "series": [
                series(response_minutes, lambda items: sum(float(item.get("tokens_in", 0)) for item in items)),
                series(response_minutes, lambda items: sum(float(item.get("tokens_out", 0)) for item in items)),
            ],
            "labels": ["input", "output"],
            "summary": f"Input {sum(input_tokens):.0f} · Output {sum(output_tokens):.0f} tokens",
            "values": [sum(input_tokens), sum(output_tokens)],
        },
        "quality": {
            "series": [series(response_minutes, lambda items: mean([float(item.get("quality_score", 0)) for item in items]))],
            "labels": ["score 0–1"],
            "summary": f"Mean quality proxy {mean(quality):.3f}",
            "values": [mean(quality)],
        },
    }


def svg_chart(panel: dict[str, Any], values: dict[str, Any]) -> str:
    series = values["series"]
    threshold = float(panel["threshold"]["value"])
    flat = [value for points in series for value in points]
    maximum = max([threshold, *flat, 1.0])
    minimum = min([0.0, *flat])
    span = max(1.0, maximum - minimum)

    def point(index: int, value: float, count: int) -> str:
        x = 35 + (WIDTH - 55) * (index / max(1, count - 1))
        y = 145 - (value - minimum) / span * 115
        return f"{x:.1f},{y:.1f}"

    lines = []
    colors = ["#38bdf8", "#f59e0b", "#a78bfa"]
    for index, points in enumerate(series):
        if points:
            coordinates = " ".join(point(i, value, len(points)) for i, value in enumerate(points))
            lines.append(f'<polyline points="{coordinates}" fill="none" stroke="{colors[index % len(colors)]}" stroke-width="3"/>')
    threshold_y = 145 - (threshold - minimum) / span * 115
    lines.append(f'<line x1="35" x2="{WIDTH - 20}" y1="{threshold_y:.1f}" y2="{threshold_y:.1f}" stroke="#ef4444" stroke-dasharray="7 5"/>')
    legend = " ".join(
        f'<span style="color:{colors[i % len(colors)]}">● {html.escape(label)}</span>'
        for i, label in enumerate(values["labels"])
    )
    return f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{html.escape(panel["title"])} chart">{"".join(lines)}<text x="40" y="20" fill="#fca5a5" font-size="12">threshold {html.escape(str(panel["threshold"]["value"]))}</text></svg><div class="legend">{legend} <span class="threshold">— threshold</span></div>'


def render() -> str:
    records, end = load_data()
    values = dashboard_values(records)
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    panels = {panel["id"]: panel for panel in config["panels"]}
    cards = []
    for panel_id in ("latency", "traffic", "errors", "cost", "tokens", "quality"):
        panel = panels[panel_id]
        data = values[panel_id]
        cards.append(
            f'<section class="panel"><h2>{html.escape(panel["title"])}</h2><div class="meta">Unit: {html.escape(panel["unit"])} · threshold {html.escape(panel["threshold"]["operator"])} {html.escape(str(panel["threshold"]["value"]))}</div><div class="summary">{html.escape(data["summary"])}</div>{svg_chart(panel, data)}</section>'
        )
    end_label = end.strftime("%Y-%m-%d %H:%M UTC")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="30"><title>{html.escape(config["title"])}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font:14px system-ui,sans-serif}}main{{max-width:1450px;margin:auto;padding:24px}}header{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:20px}}h1{{margin:0;font-size:25px}}h2{{margin:0 0 5px;font-size:17px}}.subtitle,.meta,.legend{{color:#94a3b8}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.panel{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;min-height:255px;box-shadow:0 5px 18px #02061766}}.summary{{font-weight:600;color:#f8fafc;margin:12px 0 0}}svg{{width:100%;height:165px;margin-top:4px;background:#111827;border-radius:6px}}.legend{{display:flex;gap:14px;margin-top:-4px;font-size:12px}}.threshold{{color:#fca5a5}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}</style></head>
<body><main><header><div><h1>{html.escape(config["title"])}</h1><div class="subtitle">Six panels · data/logs.jsonl · last 60 minutes · UTC</div></div><div class="subtitle">Window ends {end_label} · refresh 30s</div></header><div class="grid">{"".join(cards)}</div></main></body></html>'''


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        payload = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the six-panel Day 13 dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard: http://{args.host}:{args.port}/ (refreshes every 30 seconds)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()