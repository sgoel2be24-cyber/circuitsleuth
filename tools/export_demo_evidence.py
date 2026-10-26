"""Run all six real API demos and export reports, events, PNGs and a hash manifest.

Creates inspections; use disposable demo storage. This is execution evidence,
not a new accuracy benchmark. It never infers AWS execution from a URL or flag.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

from tools.http_smoke_test import wait_for_health

SCENARIOS = [
    "scenario_01_clear_defects", "scenario_02_clean_board", "scenario_03_ambiguous_glare",
    "scenario_04_registration_failure", "scenario_05_no_second_view", "scenario_06_multiple_regions",
]


def check_behavior(scenario: str, state: dict, report: dict, events: list) -> None:
    assert state["status"] == "completed", state.get("stop_reason")
    verdicts = report["verdicts"]
    types = {event["type"] for event in events}
    if scenario == SCENARIOS[0]:
        assert any(v["status"] == "CONFIRMED_DEFECT" for v in verdicts)
    elif scenario == SCENARIOS[1]:
        assert not verdicts and state["stop_reason"] == "no_candidates"
    elif scenario == SCENARIOS[2]:
        assert any(e["type"] == "plan_selected" and e["evidence"]["tool"] == "adaptive_threshold"
                   for e in events), "Glare must influence tool selection"
    elif scenario == SCENARIOS[3]:
        assert state["stop_reason"] == "registration_failed" and "recovery_started" in types
        assert all(v["status"] == "NOT_EVALUABLE" for v in verdicts)
    elif scenario == SCENARIOS[4]:
        assert {"additional_capture_required", "human_review_requested"} <= types
        assert any(v["status"] == "NEEDS_REVIEW" for v in verdicts)
    elif scenario == SCENARIOS[5]:
        assert state["tool_calls_used"] <= 7 and len(verdicts) == 5


def export(base: str, destination: Path) -> dict:
    # Never overwrite an existing evidence packet or silently merge separate runs.
    destination.mkdir(parents=True, exist_ok=False)

    def request(path: str, form: dict | None = None, *, post: bool = False) -> bytes:
        data = urllib.parse.urlencode(form).encode() if form is not None else (b"" if post else None)
        with urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + path, data=data), timeout=15) as res:
            return res.read()

    def api(path: str, form: dict | None = None, *, post: bool = False):
        return json.loads(request(path, form, post=post))

    def save_json(path: Path, value) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n")

    health = wait_for_health(api)
    save_json(destination / "health.json", health)
    save_json(destination / "system-info.json", api("/api/system/info"))
    summary = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "synthetic": True,
               "aws_execution_verified": False,
               "cloud_proof": "Requires separately collected AWS identity, instance and command logs tied to these inspection IDs.",
               "cases": []}
    for scenario in SCENARIOS:
        folder = destination / scenario
        folder.mkdir()
        state = api("/api/inspections", {"scenario_id": scenario,
                                        "max_tool_calls": 7 if scenario == SCENARIOS[5] else 12})
        iid = state["id"]
        prefix = f"/api/inspections/{urllib.parse.quote(iid, safe='')}"
        assert api(prefix + "/start", post=True)["ok"]
        deadline = time.monotonic() + 90
        while True:
            state = api(prefix)
            if state["status"] in {"completed", "failed"}:
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"Inspection did not finish: {iid}")
            time.sleep(0.2)
        report, events = api(prefix + "/report"), api(prefix + "/events/all")
        save_json(folder / "report.json", report)
        save_json(folder / "events.json", events)
        plans = [{"event_index": i, "region_id": e.get("region_id"),
                  "observation_event_indices": [j for j in range(i) if events[j]["type"] in {
                      "candidate_found", "tool_executed", "candidate_verified", "registration_completed"}],
                  "message": e.get("message"), "evidence": e.get("evidence")}
                 for i, e in enumerate(events) if e["type"] == "plan_selected"]
        save_json(folder / "planning-trace.json", plans)
        for verdict in report["verdicts"]:
            rid = verdict["region_id"]
            if not rid.replace("_", "").isalnum():
                raise ValueError("Unsafe region identifier")
            for role in ("reference", "aligned_test", "difference"):
                png = request(prefix + f"/candidates/{rid}/crop/{role}")
                assert png.startswith(b"\x89PNG\r\n\x1a\n")
                (folder / f"{rid}-{role}.png").write_bytes(png)
        check_behavior(scenario, state, report, events)
        summary["cases"].append({"scenario": scenario, "inspection_id": iid,
                                 "stop_reason": state["stop_reason"], "tool_calls": state["tool_calls_used"],
                                 "verdicts": dict(Counter(v["status"] for v in report["verdicts"])),
                                 "plan_events": len(plans), "behavior_check": "passed"})
    save_json(destination / "summary.json", summary)
    hashes = {str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(destination.rglob("*")) if path.is_file()}
    save_json(destination / "SHA256SUMS.json", hashes)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.base_url, args.out), indent=2))


if __name__ == "__main__":
    main()
