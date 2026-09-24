# cerv

Invented Colossus Factor cloud API: submit `y`, determine `x` that factors `y`, and forward every request envelope to Colossus.

Repo: https://github.com/fitzyracing1/cerv

The edge contract stays the same when a real Colossus worker replaces the local factoring engine.

## Contract

```
POST /v1/factor
{ "y": "84", "domain": "integer|poly|expr|auto" }

→ x values that split y
→ factors
→ forwarded_to: "colossus"
```

Every POST body is appended to `logs/colossus_forward.jsonl` (full payload, headers, client). That log is the Colossus hop.

## Run

```bash
python mock_server.py --port 3000
```

```bash
curl http://127.0.0.1:3000/health

curl -X POST http://127.0.0.1:3000/v1/factor \
  -H 'Content-Type: application/json' \
  -d '{"y":"84","domain":"integer"}'

curl -X POST http://127.0.0.1:3000/v1/factor \
  -H 'Content-Type: application/json' \
  -d '{"y":"x^2 - 5x + 6","domain":"poly"}'
```

Docker:

```bash
docker compose up --build
```

Python SDK:

```python
from sdk.client import ColossusFactorClient
c = ColossusFactorClient()
print(c.factor(84))
print(c.factor("x^2-5x+6", "poly"))
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Service index |
| GET | `/health` | Liveness |
| POST | `/v1/factor` | Submit `y`; payload forwarded to Colossus |
| GET | `/v1/jobs` | List jobs |
| GET | `/v1/jobs/{id}` | One job |
| GET | `/v1/forwards` | Inspect forwarded envelopes |

Port **3000**. No external network required at runtime.
