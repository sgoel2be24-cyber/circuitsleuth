"""Exercise a running API/UI, including a real OpenCV inspection and PNG evidence.

Uses only Python's standard library. Intended for disposable CI/demo storage:
it creates one synthetic inspection and leaves its audit trail intact.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    def request(path: str, form: dict | None = None, *, post: bool = False) -> bytes:
        data = urllib.parse.urlencode(form).encode() if form is not None else (b"" if post else None)
        req = urllib.request.Request(base + path, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()

    def api(path: str, form: dict | None = None, *, post: bool = False):
        return json.loads(request(path, form, post=post))

    deadline = time.monotonic() + 120
    while True:
        try:
            health = api("/api/health")
            assert health["status"] == "ok" and health["opencv_version"].startswith("5."), health
            break
        except (urllib.error.URLError, TimeoutError):
            if time.monotonic() >= deadline:
                raise RuntimeError("API did not become healthy within 120 seconds") from None
            time.sleep(1)

    assert b'id="root"' in request("/new"), "SPA deep link did not return the frontend shell"
    scenarios = api("/api/demo/scenarios")
    assert len(scenarios) == 6, "Expected all six reproducible demo scenarios"
    inspection = api("/api/inspections", {"scenario_id": "scenario_01_clear_defects", "max_tool_calls": 12})
    iid = inspection["id"]
    prefix = f"/api/inspections/{iid}"
    assert api(prefix + "/start", post=True)["ok"]
    deadline = time.monotonic() + 60
    while True:
        state = api(prefix)
        if state["status"] in ("completed", "failed"):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Inspection {iid} did not finish within 60 seconds")
        time.sleep(0.2)
    assert state["status"] == "completed", state.get("stop_reason")
    report = api(prefix + "/report")
    assert report["inspection_id"] == iid and report["verdicts"], "Missing final evidence report"
    events = api(prefix + "/events/all")
    assert any(e["type"] == "plan_selected" for e in events), "No actual adaptive planning recorded"
    assert any(v["status"] == "CONFIRMED_DEFECT" for v in report["verdicts"]), "Expected evidence-backed defect"
    rid = report["verdicts"][0]["region_id"]
    for role in ("reference", "aligned_test", "difference"):
        assert request(prefix + f"/candidates/{rid}/crop/{role}").startswith(b"\x89PNG\r\n\x1a\n")
    print(json.dumps({"http_smoke": "passed", "opencv_version": health["opencv_version"],
                      "inspection_id": iid, "regions": len(report["verdicts"]), "events": len(events)}))


if __name__ == "__main__":
    main()
