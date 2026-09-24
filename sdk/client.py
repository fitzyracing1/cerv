"""Python client for the Colossus Factor API mock."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ColossusFactorClient:
    def __init__(self, base_url: str = "http://127.0.0.1:3000", timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        req = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            try:
                payload = json.loads(e.read().decode())
            except Exception:
                payload = {"error": str(e)}
            raise RuntimeError(payload) from e
        except URLError as e:
            raise RuntimeError(f"cannot reach {self.base_url}: {e}") from e

    def health(self) -> dict:
        return self._request("GET", "/health")

    def factor(self, y: str | int, domain: str = "auto") -> dict:
        return self._request("POST", "/v1/factor", {"y": str(y), "domain": domain})

    def list_jobs(self, limit: int = 50) -> dict:
        return self._request("GET", f"/v1/jobs?limit={limit}")

    def get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/v1/jobs/{job_id}")

    def forwards(self) -> dict:
        return self._request("GET", "/v1/forwards")

    def full_flow_demo(self) -> dict:
        h = self.health()
        a = self.factor(84, "integer")
        b = self.factor("x^2 - 5x + 6", "poly")
        jobs = self.list_jobs(limit=5)
        return {"health": h, "integer": a, "poly": b, "jobs": jobs}


if __name__ == "__main__":
    c = ColossusFactorClient()
    print(json.dumps(c.full_flow_demo(), indent=2))
