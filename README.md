# O2C Graph Intelligence

A graph-based data modeling and query system over SAP Order-to-Cash (O2C) process data. Natural language queries are answered by a 4-stage LLM pipeline that routes to DuckDB SQL or NetworkX graph traversal, then streams a narrated response back to the browser.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (React + Sigma.js)                                     │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │  Graph Canvas        │  │  Chat Panel (SSE stream)         │ │
│  │  Sigma.js + Graphology│  │  4-stage LLM agent              │ │
│  └──────────────────────┘  └──────────────────────────────────┘ │
└────────────────────────────────┬────────────────────────────────┘
                                 │ HTTP / SSE
┌────────────────────────────────▼────────────────────────────────┐
│  FastAPI (Python 3.11)                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────────┐ │
│  │  /api/graph/*  │  │  /api/chat     │  │  LLM Agent        │ │
│  │  REST JSON     │  │  SSE stream    │  │  guardrail→       │ │
│  └────────┬───────┘  └────────┬───────┘  │  classify→        │ │
│           │                   │          │  execute→         │ │
│  ┌────────▼───────────────────▼────────┐ │  narrate (stream) │ │
│  │  DuckDB 0.10  │  NetworkX DiGraph   │ └───────────────────┘ │
│  │  19 tables    │  Louvain clusters   │                       │
│  └─────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Why DuckDB + NetworkX?

- **DuckDB** handles all aggregate analytics (SUM, GROUP BY, window functions) directly on the JSONL files ingested into columnar tables — fast, embedded, zero ops.
- **NetworkX** serves graph traversal queries (shortest path, BFS neighbours, reachability) that are cumbersome in SQL. Built once on startup, cached as a pickle.
- **No external infra** — both are in-process libraries, keeping the deployment to a single container.

---

## Graph Schema

### Node Types (10 total)

| Prefix | Entity | Key field |
|--------|--------|-----------|
| `C_`   | Customer | `soldToParty` |
| `SO_`  | Sales Order | `salesDocument` |
| `SOI_` | Sales Order Item | `salesDocument + item` |
| `P_`   | Product (Material) | `material` |
| `PL_`  | Plant | `plant` |
| `D_`   | Delivery Document | `deliveryDocument` |
| `DI_`  | Delivery Item | `deliveryDocument + item` |
| `BD_`  | Billing Document | `billingDocument` |
| `JE_`  | Journal Entry | `companyCode + fiscalYear + accountingDocument + lineItem` |
| `PAY_` | Payment | `paymentDocument` |

### Edge Types (9 total)

| Edge | From → To | FK |
|------|-----------|----|
| `PLACED_BY` | SalesOrder → Customer | `soldToParty` |
| `CONTAINS` | SalesOrder → SalesOrderItem | — |
| `ORDERS` | SalesOrderItem → Product | `material` |
| `SHIPS_FROM` | SalesOrderItem → Plant | `plant` |
| `DELIVERED_VIA` | SalesOrder → Delivery | `salesDocument` header |
| `FULFILLED_BY` | SalesOrderItem → DeliveryItem | `referenceSdDocument` (zero-pad aware) |
| `BILLED_VIA` | DeliveryItem → BillingDocument | `referenceSdDocument` |
| `HAS_JOURNAL` | BillingDocument → JournalEntry | `accountingDocument`/`referenceDocument` |
| `SETTLED_BY` | JournalEntry → Payment | `paymentDocument` |

---

## LLM Pipeline

Every chat message passes through 4 sequential stages:

```
1. GUARDRAIL  — pattern-match reject list (poems, sports, recipes, …)
               + domain keyword whitelist check
               → off-topic messages blocked before any LLM call

2. CLASSIFIER — Mixtral decides intent:
               GRAPH_TRAVERSAL | AGGREGATE_ANALYTICS |
               ENTITY_LOOKUP   | ANOMALY_DETECTION   | OFF_TOPIC

3. EXECUTE    — routed to appropriate executor:
               GRAPH_TRAVERSAL  → NetworkX BFS / shortest_path
               AGGREGATE_*      → DuckDB SQL (allowlisted tables, SELECT-only)
               ANOMALY_*        → pre-built graph heuristics (no-billing, no-delivery)

4. NARRATE    — Mixtral streams a plain-English answer referencing the raw data.
               Last line: REFERENCED_NODES: ["SO_12345", "BD_9876", …]
               Frontend parses this to highlight those nodes in the graph.
```

Model: `mistralai/mistral-large-3-675b-instruct-2512` via [NVIDIA NIM](https://build.nvidia.com/) (free tier).

---

## Guardrails

Two-layer approach in `backend/app/llm/guardrails.py`:

1. **Reject patterns** — hard regex blocks for clearly off-topic requests (write a poem, sports score, recipe, translate text, …)
2. **Domain whitelist** — message must contain at least one O2C keyword (`invoice`, `delivery`, `sales order`, `billing`, `customer`, `payment`, `journal`, …)

Off-topic queries get a polite redirect without consuming any LLM tokens.

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 20+
- NVIDIA NIM API key (free at [build.nvidia.com](https://build.nvidia.com))

### Backend

```bash
cd backend
cp .env.example .env
# edit .env and set NVIDIA_API_KEY=nvapi-...

pip install -r requirements.txt

# Ingest SAP O2C JSONL data into DuckDB
python -m app.etl.ingest

# Build NetworkX graph + Louvain clusters
python -m app.graph.builder

# Start API server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### Docker Compose

```bash
cp backend/.env.example backend/.env
# set NVIDIA_API_KEY in backend/.env
# optional (recommended for large datasets): keep ENABLE_LOUVAIN=false

docker compose up --build
# frontend: http://localhost:80
# backend:  http://localhost:8000

# Startup note:
# On first run, backend ingests JSONL and builds graph cache.
# /health may not respond until startup completes.
```

---

## Deploying to Railway

1. Push this repo to GitHub.
2. Create a new Railway project → "Deploy from GitHub repo".
3. Add two services: `backend/` and `frontend/`.
4. Set `NVIDIA_API_KEY` environment variable on the backend service.
5. Set `VITE_API_URL=https://<backend-railway-domain>` as a build variable on the frontend service.

---

## Project Structure

```
graph-data/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers (chat, graph)
│   │   ├── core/          # Config, DuckDB singleton
│   │   ├── etl/           # JSONL → DuckDB ingestion
│   │   ├── graph/         # Schema, builder, Pydantic models
│   │   └── llm/           # Agent, guardrails, prompts, memory, executors
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios client
│   │   ├── components/    # GraphCanvas, ChatPanel, NodeDrawer
│   │   ├── hooks/         # useGraph, useChat
│   │   └── store/         # Zustand global state
│   ├── package.json
│   └── Dockerfile
├── sap-o2c-data/          # JSONL source files (not committed)
├── docker-compose.yml
└── railway.toml
```
