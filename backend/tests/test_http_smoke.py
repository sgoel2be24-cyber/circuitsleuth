"""The readiness check must tolerate a published, not-yet-listening container."""

from http.client import RemoteDisconnected
from urllib.error import URLError

import pytest

from tools import http_smoke_test as smoke


@pytest.mark.parametrize("error", [ConnectionResetError(), RemoteDisconnected(), URLError("starting"), TimeoutError()])
def test_startup_transport_failure_is_retried(monkeypatch, error):
    calls = []
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)

    def api(path):
        calls.append(path)
        if len(calls) == 1:
            raise error
        return {"status": "ok", "opencv_version": "5.0.0"}

    assert smoke.wait_for_health(api)["opencv_version"] == "5.0.0"
    assert calls == ["/api/health", "/api/health"]


def test_readiness_failure_remains_bounded(monkeypatch):
    clock = iter([0, 2])
    monkeypatch.setattr(smoke.time, "monotonic", lambda: next(clock))

    def unavailable(_):
        raise ConnectionResetError()

    with pytest.raises(RuntimeError, match="within 1 seconds"):
        smoke.wait_for_health(unavailable, timeout_s=1)


def test_incompatible_runtime_is_not_hidden_by_retry():
    with pytest.raises(AssertionError):
        smoke.wait_for_health(lambda _: {"status": "ok", "opencv_version": "4.13.0"})
