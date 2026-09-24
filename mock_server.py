#!/usr/bin/env python3
"""Colossus Factor API — local mock.

Accepts y, determines x that factors y, and records every payload
as forwarded to Colossus. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "seed.json"
LOG_DIR = ROOT / "logs"
JOBS_PATH = LOG_DIR / "jobs.json"
PORT_DEFAULT = 3000

LOG_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "data").mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_JOBS: list[dict[str, Any]] = []
_LOADED = False


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_jobs() -> list[dict[str, Any]]:
    global _LOADED, _JOBS
    if _LOADED:
        return _JOBS
    if JOBS_PATH.exists():
        try:
            _JOBS = json.loads(JOBS_PATH.read_text())
        except Exception:
            _JOBS = []
    if not _JOBS:
        try:
            seed = json.loads(DATA.read_text())
            _JOBS = list(seed.get("jobs", []))
        except Exception:
            _JOBS = []
    _LOADED = True
    return _JOBS


def save_jobs(jobs: list[dict[str, Any]]) -> None:
    global _JOBS
    _JOBS = jobs
    try:
        JOBS_PATH.write_text(json.dumps(jobs, indent=2))
    except OSError:
        pass


def forward_to_colossus(payload: dict[str, Any]) -> None:
    """Persist the full request body as if shipped to Colossus."""
    line = {
        "ts": utc_now(),
        "destination": "colossus",
        "payload": payload,
    }
    log_file = LOG_DIR / "colossus_forward.jsonl"
    with _lock:
        with log_file.open("a") as f:
            f.write(json.dumps(line) + "\n")


def factor_integer(n: int) -> dict[str, Any]:
    n_abs = abs(n)
    if n_abs <= 1:
        return {
            "x": [n],
            "factors": [[1, n]],
            "prime_factors": [n] if n not in (0, 1, -1) else [n],
            "method": "trivial",
        }
    primes: list[int] = []
    m = n_abs
    d = 2
    while d * d <= m:
        while m % d == 0:
            primes.append(d)
            m //= d
        d += 1 if d == 2 else 2
    if m > 1:
        primes.append(m)

    xs: list[int] = []
    pairs: list[list[int]] = []
    for i in range(1, int(n_abs**0.5) + 1):
        if n_abs % i == 0:
            xs.append(i)
            if i != n_abs // i:
                xs.append(n_abs // i)
            pairs.append([i, n // i if n < 0 and i != 0 else (n_abs // i) * (1 if n > 0 else -1)])
    xs = sorted(set(xs))
    if n < 0:
        xs = [-x for x in xs] + xs
        xs = sorted(set(xs), key=lambda v: (abs(v), v))
    return {
        "x": xs,
        "factors": pairs,
        "prime_factors": ([-1] + primes) if n < 0 else primes,
        "method": "trial_division",
    }


def parse_poly(s: str) -> list[int]:
    text = s.replace(" ", "").replace("\u2212", "-")
    text = text.replace("X", "x")
    if not text:
        raise ValueError("empty polynomial")
    text = re.sub(r"(^|[+\-])x\^", r"\g<1>1x^", text)
    text = re.sub(r"(^|[+\-])x(?!\^)", r"\g<1>1x", text)
    if re.fullmatch(r"[+\-]?\d+", text):
        return [0, 0, 0, int(text)]

    a = b = c = d = 0
    m = re.search(r"([+\-]?\d+)x\^3", text)
    if m:
        a = int(m.group(1))
    m = re.search(r"([+\-]?\d+)x\^2", text)
    if m:
        b = int(m.group(1))
    m = re.search(r"([+\-]?\d+)x(?!\^)", text)
    if m:
        c = int(m.group(1))
    rest = re.sub(r"[+\-]?\d+x(?:\^\d+)?", "", text)
    if rest:
        m = re.search(r"[+\-]?\d+", rest)
        if m:
            d = int(m.group(0))
    return [a, b, c, d]


def rational_roots(coeffs: list[int]) -> list[int]:
    while coeffs and coeffs[0] == 0:
        coeffs = coeffs[1:]
    if not coeffs:
        return []
    const = coeffs[-1]
    lead = coeffs[0]
    if const == 0:
        return [0]

    def divisors(n: int) -> list[int]:
        n = abs(n)
        out = []
        for i in range(1, int(n**0.5) + 1):
            if n % i == 0:
                out.extend([i, n // i])
        return sorted(set(out))

    cands = []
    for p in divisors(const) or [1]:
        for q in divisors(lead) or [1]:
            if q == 0:
                continue
            if p % q == 0:
                cands.append(p // q)
    cands = sorted(set([v for c in cands for v in (c, -c)]))

    def eval_poly(xs: int) -> int:
        acc = 0
        for co in coeffs:
            acc = acc * xs + co
        return acc

    return [r for r in cands if eval_poly(r) == 0]


def factor_poly(expr: str) -> dict[str, Any]:
    coeffs = parse_poly(expr)
    roots = rational_roots(coeffs[:])
    factors = [f"(x - {r})" if r >= 0 else f"(x + {abs(r)})" for r in roots]
    return {
        "x": roots,
        "factors": factors,
        "coeffs": coeffs,
        "method": "rational_root",
    }


def run_worker(y: str, domain: str) -> dict[str, Any]:
    domain = (domain or "auto").lower()
    if domain == "auto":
        if re.search(r"x", y, re.I):
            domain = "poly"
        else:
            domain = "integer"
    if domain == "integer":
        cleaned = y.replace(",", "").strip()
        n = int(cleaned)
        out = factor_integer(n)
        out["domain"] = "integer"
        out["y"] = str(n)
        return out
    if domain == "poly":
        out = factor_poly(y)
        out["domain"] = "poly"
        out["y"] = y
        return out
    if domain == "expr":
        try:
            return run_worker(y, "integer")
        except Exception:
            return run_worker(y, "poly")
    raise ValueError(f"unknown domain: {domain}")


class Handler(BaseHTTPRequestHandler):
    server_version = "ColossusFactorAPI/1.0"

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json(self, code: int, body: Any) -> None:
        raw = json.dumps(body, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        if path == "/":
            return self._json(
                200,
                {
                    "service": "colossus-factor-api",
                    "destination": "colossus",
                    "docs": {
                        "POST /v1/factor": "submit y; all data forwarded to colossus",
                        "GET /v1/jobs": "list jobs",
                        "GET /v1/jobs/{id}": "get one job",
                        "GET /v1/forwards": "inspect forwarded payloads",
                        "GET /health": "liveness",
                    },
                },
            )
        if path == "/health":
            return self._json(200, {"ok": True, "forward": "colossus", "ts": utc_now()})
        if path == "/v1/jobs":
            jobs = load_jobs()
            limit = int(qs.get("limit", ["50"])[0])
            return self._json(200, {"jobs": jobs[:limit], "count": len(jobs)})
        if path.startswith("/v1/jobs/"):
            jid = path.split("/")[-1]
            for job in load_jobs():
                if job["id"] == jid:
                    return self._json(200, job)
            return self._json(404, {"error": "job not found", "id": jid})
        if path == "/v1/forwards":
            log_file = LOG_DIR / "colossus_forward.jsonl"
            rows = []
            if log_file.exists():
                for line in log_file.read_text().splitlines()[-100:]:
                    if line.strip():
                        rows.append(json.loads(line))
            return self._json(200, {"forwards": rows, "count": len(rows)})
        return self._json(404, {"error": "not found", "path": path})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})

        if path == "/v1/factor":
            y = body.get("y")
            domain = body.get("domain", "auto")
            if y is None or str(y).strip() == "":
                return self._json(400, {"error": "y is required"})

            envelope = {
                "id": "job_" + uuid.uuid4().hex[:12],
                "received_at": utc_now(),
                "headers": {k: v for k, v in self.headers.items()},
                "body": body,
                "client": self.client_address[0],
            }
            forward_to_colossus(envelope)

            job = {
                "id": envelope["id"],
                "y": str(y),
                "domain": domain,
                "status": "queued",
                "forwarded_to": "colossus",
                "received_at": envelope["received_at"],
            }
            with _lock:
                jobs = load_jobs()
                jobs.insert(0, job)
                save_jobs(jobs)

            try:
                t0 = time.time()
                result = run_worker(str(y), str(domain))
                job.update(result)
                job["status"] = "completed"
                job["elapsed_ms"] = int((time.time() - t0) * 1000)
                job["colossus_ack"] = True
            except Exception as exc:
                job["status"] = "failed"
                job["error"] = str(exc)
                job["colossus_ack"] = False

            with _lock:
                jobs = load_jobs()
                for i, existing in enumerate(jobs):
                    if existing["id"] == job["id"]:
                        jobs[i] = job
                        break
                save_jobs(jobs)
            return self._json(201 if job["status"] == "completed" else 422, job)

        return self._json(404, {"error": "not found", "path": path})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utc_now()}] {self.address_string()} {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT_DEFAULT)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    load_jobs()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Colossus Factor API on http://{args.host}:{args.port}")
    print("POST /v1/factor  GET /v1/jobs  GET /health")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
