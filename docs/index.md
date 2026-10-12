# cerv

cerv is a local mock of an invented "Colossus Factor" cloud API. You submit `y`, and it returns the `x` values and factors that split `y`. "Forwarding to Colossus" is simulated: every POST body is appended to `logs/colossus_forward.jsonl`. The service needs no external network at runtime.

## Getting started

```bash
python mock_server.py --port 3000        # --host defaults to 0.0.0.0
curl http://127.0.0.1:3000/health
curl -X POST http://127.0.0.1:3000/v1/factor -H 'Content-Type: application/json' -d '{"y":"84","domain":"integer"}'
# or: docker compose up --build
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | service index |
| GET | `/health` | liveness |
| POST | `/v1/factor` | `{"y": ..., "domain": "integer\|poly\|expr\|auto"}` |
| GET | `/v1/jobs`, `/v1/jobs/{id}` | jobs |
| GET | `/v1/forwards` | forwarded envelopes |

Python SDK: `from sdk.client import ColossusFactorClient; ColossusFactorClient().factor(84)`

## Files
`mock_server.py` (server and factoring engine), `sdk/client.py`, `data/seed.json`, `Dockerfile`, `docker-compose.yml`, and `logs/`.

Note: the forward log stores the full payload, headers and client address. The repo has no tests and no CI.

MIT License. Copyright (c) 2026 Joshua Almeida
