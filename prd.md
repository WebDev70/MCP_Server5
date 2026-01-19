# Product Requirements Document (PRD) — USAspending MCP Server for All Award Types
**Document owner:** Ron  
**Last updated:** 2026-01-16  
**Status:** Draft (v0.2)

## 1. Summary
Build an **MCP (Model Context Protocol) Server** that enables ChatGPT to reliably answer **any question about U.S. federal award spending** using **USAspending.gov API v2**.

This PRD expands scope beyond contracts to support **all award/spending categories**, including:
- **Contracts**
- **Contract IDVs** (and task orders)
- **Grants**
- **Direct Payments**
- **Loans**
- **Other Assistance / Other Spending categories**

The server will expose a small, stable set of **MCP tools**, while orchestrating dozens of USAspending endpoints internally using a **router/planner** that selects the **cheapest, most reliable query path** (rollups → search → drilldown).

## Vision Statement
Make federal award spending instantly understandable—by giving ChatGPT a reliable, explainable, and scalable gateway to USAspending.gov that answers any award-spending question with the right mix of totals, lists, and drill-down evidence.

---

## 2. Problem Statement
Ron is building an MCP Server that lets ChatGPT answer a high-variance set of questions about federal award spending. Questions may reference:
- **Agencies** (awarding/funding, bureaus, subcomponents)
- **Recipients** (UEI/DUNS, parent/child relationships)
- **Awards** (specific award IDs, totals, modifications/transactions, subawards)
- **Contract vehicles / IDVs** (task orders under IDVs, funding/accounts, activity)
- **Assistance programs** (CFDA/Assistance Listing), assistance types, and related rollups
- **Accounting/funding** (TAS/federal accounts, object class, program activity)

Challenges:
- USAspending filters and payload requirements can produce **400 errors** if malformed.
- Questions require different endpoint strategies depending on intent (totals vs. lists vs. explainability).
- High-volume retrieval must avoid long paging and rate limits.
- Award-type families differ (e.g., procurement vs. assistance), so the server must **normalize across categories**.

---

## 3. Goals
### 3.1 Product Goals
1. **Broad coverage:** Answer most award-spending questions with a minimal set of MCP tools.
2. **Reliability:** Minimize 400 errors via **entity resolution**, **reference catalogs**, and **payload normalization**.
3. **Efficiency:** Prefer **rollup endpoints** for totals/top-N; avoid enumerating large award sets.
4. **Explainability:** Provide drill-down evidence (award details + transactions + subawards) when needed.
5. **Configurability:** Support **award scope modes** (all awards vs. contracts-only vs. assistance-only) without changing tool names.
6. **Operational readiness:** Run locally on macOS (Apple Silicon) and deploy to **Google Cloud Run**.

### 3.2 Success Metrics
- **Tool success rate:** ≥ 95% of tool calls return valid JSON without API errors in typical usage.
- **Latency:** P50 < 2s for cached/reference calls; P50 < 5s for typical rollups/search; P95 < 15s.
- **400 rate:** < 2% after normalization/resolution features are implemented.
- **Coverage:** ≥ 85% of representative question set answered without human intervention.
- **Observability:** Every tool supports `debug=true` returning sanitized payload + endpoint(s) used.
- **Correctness signaling:** Every numeric answer includes `meta.accuracy_tier` and `meta.endpoint_used` / `meta.endpoints_used`.
- **Cost efficiency:** average outbound USAspending requests per answered question ≤ 3 (P95 ≤ 5).
- **Response size control:** P95 tool response payload ≤ 200KB with `meta.truncated=true` when caps apply.

---

## 4. Non-Goals (v1)
- Building a UI/dashboard (MCP-first).
- Bulk dataset mirroring/warehousing as the primary approach (APIs are authoritative).
- Perfect totals for every edge case in v1; fallback tiers are allowed (see Accuracy Tiers).
- Building a general-purpose ETL pipeline (beyond optional “sync/change feed” checks).

---

## Scope
### In scope (v1)
- Award spending Q&A across **contracts and assistance** (grants, direct payments, loans, and other categories)
- Totals/top-N, award lists, award explainability (transactions/subawards)
- Entity resolution (agency/recipient/NAICS/PSC/CFDA/locations) and payload normalization
- Optional scope modes: `all_awards` (default), `contracts_only`, `assistance_only`
- Cloud Run deployment with private access controls (IAM)

### Out of scope (v1)
- User-facing dashboards
- Data lake/warehouse buildout
- “Real-time” streaming updates (near-real-time not guaranteed)
- Advanced entity resolution beyond USAspending’s references/autocomplete (can be v1.1+)

---

## 5. Users & Personas
1. **ChatGPT user (Analyst / PM / CO / Executive):** asks natural language questions about spending and awards.
2. **Developer (Ron):** builds/maintains MCP server, deploys to Cloud Run, extends endpoints.
3. **Future integrators:** want stable tool interfaces while internals evolve.

---

## 6. Assumptions & Constraints
- USAspending API v2 is the authoritative source.
- Development machine: **MacBook Pro (Apple Silicon / M5)**.
- Deployment target: **Google Cloud Run** (container-based, stateless).
- Dependency management: **uv** with `.venv` (or equivalent venv).
- **LLM token budget / response size:** Tool outputs must be capped and slimmed to prevent context-window saturation. Implement shared trimming (e.g., `trim_payload`) with env-tunable limits (e.g., `MAX_RESPONSE_BYTES`, `MAX_ITEMS_PER_LIST`) and set `meta.truncated=true` when applied.
- The server must support multiple award families. Therefore:
  - Award type codes and groupings must be loaded from **reference endpoints** (do not hardcode beyond safe fallbacks).
  - Router must select filters appropriate to the endpoint family being used.

---

## 7. High-Level Architecture
### 7.1 Components
- **MCP Server (FastMCP) with dual transports**
  - **stdio:** local clients (e.g., Claude Desktop) spawn the process
  - **Streamable HTTP:** Cloud Run deployment with `/mcp` endpoint
- **USAspending HTTP Client**
  - timeouts, retries, backoff (429/5xx), structured errors
  - in-memory TTL caching for reference + common queries
- **Tool Layer**
  - ~9 stable MCP tools (public interface)
- **Router/Planner**
  - Extract signals (award_id, agency/recipient, time, geography, “top N”, award category)
  - Resolve entities when needed
  - Choose primary tool + optional drilldown
- **Observability**
  - structured logs, request IDs, debug payload returns

### 7.2 Request Flow
1. User asks question in ChatGPT
2. Router extracts intent/signals and scope mode (default `all_awards`)
3. If entities ambiguous → `resolve_entities`
4. Choose cheapest path:
   - totals/top-N → `spending_rollups`
   - list awards → `award_search`
   - explain award → `award_explain`
   - agency/recipient/IDV deep dives → respective tools
5. Return JSON result + metadata for ChatGPT to summarize.

---

## 8. Functional Requirements (MCP Tool Surface)
**Design principle:** expose a small set of tools; orchestrate many endpoints internally.

### Response Contract (all tools)
All tools must return:
- `tool_version: "1.0"`
- `meta`: `{ request_id, scope_mode, endpoint_used/endpoints_used, time_period, warnings, accuracy_tier?, truncated?, truncation? }`
  - When trimming is applied, set `meta.truncated=true` and include `meta.truncation={reason, max_bytes, max_items_per_list, returned_items}`
- On error: `error`: `{ type, message, status_code?, endpoint?, remediation_hint? }`

### 8.1 Tool 1 — `bootstrap_catalog`
**Purpose:** Load/cache reference vocab needed for all-awards routing and validation.  
**Includes (suggested):**
- toptier agencies
- award types
- assistance listings (CFDA/Assistance Listing)
- NAICS/PSC references as needed
- submission periods (optional)  
**Cache:** 24h

### 8.2 Tool 2 — `resolve_entities`
**Purpose:** Convert user text to canonical entities usable in filters.  
**Resolves:** agency, recipient, NAICS, PSC, location/city, assistance listing (CFDA), program activity (where supported).  
**Cache:** 1h

### 8.3 Tool 3 — `award_search`
**Purpose:** Find awards matching filters; supports list/count/both.  
**Key requirement:** Works across award families by using `scope_mode` + `award_type_groups` (resolved via references).  
**Inputs:** time_period, filters, fields, sort/order, page/limit, mode, scope_mode, award_type_groups?, debug  
**Outputs:** results[], count, paging metadata, meta (accuracy, endpoints used)

### 8.4 Tool 4 — `award_explain`
**Purpose:** Explain a specific award: summary + transactions + optional subawards.  
**Inputs:** award_id, include[], limits, scope_mode, debug  
**Outputs:** bundle {summary, transactions, subawards, notes}

### 8.5 Tool 5 — `spending_rollups`
**Purpose:** Totals/top-N breakdowns without enumerating awards.  
**Inputs:** time_period, filters, group_by, top_n, metric, scope_mode, award_type_groups?, debug  
**Outputs:** totals + groups + meta.accuracy_tier + warnings  
**Fallback policy:** if rollup validation fails, fallback to award_search sampling + warn

### 8.6 Tool 6 — `recipient_profile`
**Purpose:** Vendor/recipient profile + hierarchy + rollups/counts.  
**Inputs:** recipient (id|uei|duns|name), time_period?, include[], scope_mode  
**Outputs:** profile + children + rollups + counts

### 8.7 Tool 7 — `agency_portfolio`
**Purpose:** Agency views (awards + object class + program activity + etc.).  
**Inputs:** toptier_code, time_period, views[], scope_mode  
**Outputs:** selected views + totals + metadata

### 8.8 Tool 8 — `idv_vehicle_bundle`
**Purpose:** IDV vehicle: task orders, activity, funding/accounts, rollups.  
**Inputs:** idv_award_id, include[], time_period?, scope_mode (must support contract IDVs)  
**Outputs:** vehicle bundle with orders/activity/funding/rollups

### 8.9 Tool 9 — `answer_award_spending_question`
**Purpose:** Orchestrator that returns `{plan, result}` and chooses the correct tool path.  
**Inputs:** question, debug  
**Outputs:** plan.actions[] + primary result + meta

---

## 9. Router/Planner Requirements
### 9.1 Scope Modes (v1)
- **all_awards (default):** include contracts + assistance + other categories
- **contracts_only:** contracts + IDVs
- **assistance_only:** grants/loans/direct payments/other assistance (no contracts)

### 9.2 Routing Principles
- Prefer rollups for “how much / total / top N”
- Prefer award_search for “list/show awards”
- Prefer award_explain when award_id present
- Prefer IDV bundle for “IDV/IDIQ/GWAC/BPA/task orders/vehicle”
- Prefer agency/recipient tools for portfolio/profile questions
- Always normalize filters and remove empty values
- Always label results with endpoint provenance + accuracy tier
- Avoid hardcoding award types; rely on references. If references unavailable, use safe fallbacks:
  - contracts fallback: A-D
  - assistance fallback: use assistance listing / CFDA filters when available
### 9.3 Cost-Optimized Routing Policy (Required)
To keep Cloud Run costs predictable and avoid large LLM contexts, routing MUST be **bounded** and **cheap-first**:
- **Cheap-first ordering:** rollups → search → drilldown. Never call `award_explain` unless an `award_id` is present.
- **Call budgets:** enforce per-question budgets (defaults; env-tunable):
  - `max_tool_calls_per_question=3`
  - `max_usaspending_requests=5`
  - `max_wall_ms=12000`
- **Summary-first output:** default `detail_level="summary"` and only expand to transactions/subawards when explicitly requested or `debug=true`.
- **Hard caps:** enforce `limit`/`top_n` maxima and apply shared `trim_payload(max_response_bytes, max_items_per_list)` before returning.
- **Early narrowing:** if answering would exceed budgets (e.g., entity resolution + deep drilldown), return a **refinement suggestion** instead of making expensive calls.
- **Telemetry:** every orchestrated answer returns `meta.route_name`, `meta.outbound_calls`, `meta.cache_hit` (when applicable), and `meta.truncated`.

### 9.4 router_rules.json (Policy File)
A repo-managed policy file **must** drive router decisions for repeatability and cost control:
- Location: `src/usaspending_mcp/router_rules.json`
- Minimum schema:
  - `version`
  - `budgets` (call/time/size)
  - `caching_ttl_seconds` (references/entity/rollups/details)
  - `defaults` (scope_mode, search limits, rollup top_n, output policy)
  - `routes[]` (ordered, cheap-first) with preconditions + cost hints
  - `fallbacks` per route
  - `deny_rules` (e.g., IDV routes denied for `assistance_only`)
- The router must load these rules at startup and expose the effective config in `debug=true` (sanitized).


---

## Data Quality and Provenance
- All numeric outputs include `meta.endpoint_used/endpoints_used`, `meta.time_period`, and `meta.warnings`.
- If totals are approximated (sampling), include `meta.accuracy_tier="C"` and warning `"approximate_total"`.
- Include enough identifiers to support drilldown (award_id, recipient_id, agency_code, etc.).

## Accuracy Tiers
- **Tier A (Exact):** true aggregation endpoints success.
- **Tier B (Near-exact):** award search + count + pagination up to configured max pages.
- **Tier C (Approximate):** award search sampling (fallback only).

---

## 10. Endpoint Coverage — High-Value Groups (All Awards)
> This is a functional grouping for implementation planning. Exact endpoint allowlists can be maintained per tool.

### 10.1 Search & rollups (core Q&A engine)
- Search by award (list + count)
- Spending rollups
- Federal obligations rollups

### 10.2 Award drilldown
- Award details
- Transactions
- Subawards
- Award funding/accounts rollups

### 10.3 Agencies
- Agency summary and awards views
- Budget function, object class, program activity, federal accounts
- Reporting & publish dates (data quality)

### 10.4 Recipients
- Recipient profile
- Children/hierarchy
- Recipient counts and geography (state)

### 10.5 Contract Vehicles (IDVs)
- IDV awards/orders
- IDV activity
- IDV funding/accounts/rollups

### 10.6 Assistance program references
- Assistance listings (CFDA/Assistance Listing)
- CFDA totals (where applicable)
- Assistance type references and filter trees (if used)

### 10.7 References & validation
- Award types, filter schemas, glossary, NAICS/PSC, toptier agencies, def codes, submission periods

---

## 11. Non-Functional Requirements
### 11.1 Reliability
- Retries/backoff on 429 and 5xx (max retries configurable)
- Structured API error objects returned to callers
- Aggressive payload sanitization (strip empty lists/dicts/nulls)
- Validate time windows; default last 12 months if unspecified

### 11.2 Performance
- Enforce outbound timeouts
- Cache reference data and common lookups
- Prefer rollups for totals/top-N
- Enforce caps (pages/limits) and warn when capped

### 11.3 Observability & Debugging
- `debug=true` returns sanitized payload(s), endpoint(s) used, and router decision
- Structured logs with request_id propagated through tool calls
- Metrics: error rate, 429 rate, P50/P95 latency, cache hit rate

### 11.4 Security & Access
- Default Cloud Run deployment private (IAM)
- Do not log sensitive user-provided identifiers beyond what’s needed
- Data retention: configurable; avoid persisting raw payloads

### 11.5 Error Handling & Recovery
- **400 (validation):** return `error.type="validation"` with remediation hint
- **429 (rate limit):** backoff + retry; return partial results if needed
- **5xx:** retry; fallback to safer path or return partial with warnings
- Never return stack traces to callers

### 11.6 Caching Strategy
- Reference catalog: TTL 24h
- Entity resolution: TTL 1h per normalized query
- Award summary: TTL 6–24h
- Transactions: TTL 1–6h
- Rollups: TTL 15–60m
- Cache keys derived from normalized payloads (sorted keys, stripped empties)

### 11.7 Cost & Quotas
- **Bounded work per question:** enforce router budgets (defaults; env-tunable):
  - `MAX_TOOL_CALLS_PER_QUESTION=3`
  - `MAX_USASPENDING_REQUESTS=5`
  - `MAX_WALL_MS=12000`
- **Response size guardrails:** enforce `MAX_RESPONSE_BYTES` and `MAX_ITEMS_PER_LIST` with `meta.truncated=true` + `meta.truncation` details.
- **Prefer rollups:** rollups are the default for totals/top-N; avoid enumerating large award sets.
- **Caching:** TTL caching (see 11.6) must be enabled for references, entity resolution, and common rollups.
- **Circuit breakers:** cap retries, cap total outbound calls, and fail fast with a refinement suggestion on repeated upstream errors.
- **Cloud Run cost settings (recommended defaults):**
  - min instances: 0 (scale-to-zero)
  - CPU allocated only during request (default)
  - set a sensible `--concurrency` (e.g., 20–80) and `--max-instances` to prevent burst cost spikes
  - request timeout aligned with budgets (e.g., 30–60s)
- **Tracking:** record average outbound calls per question and cache hit rate in metrics.

---

## 12. Test Plan
### 12.1 Unit Tests (no network)
- filter normalization / strip_empty
- time_period inference (FY, year, last N days)
- scope_mode handling + award type group selection
- rollup grouping and sorting

### 12.2 Mocked HTTP Tests
- Validate request payload shapes for award_search/rollups
- Simulate 429/5xx retries, 400 error mapping
- Validate endpoint provenance in meta

### 12.3 Live Smoke Tests (optional, gated)
- gated by env var `LIVE_TESTS=1`
- limited calls; no large paging

## Acceptance Test Suite (Golden Questions)
1. “Top 10 awards (all types) for DoD in FY2024”
2. “How much did DHS obligate last quarter on **grants**?”
3. “Explain award <award_id> and show key transactions”
4. “Top recipients for NIH **grants** in 2023”
5. “Task orders under IDV <idv_award_id> (contracts)”
6. “Resolve: ‘CACI’, ‘cloud PSC’, and ‘Assistance Listing 20.205’”
7. “Total loans by agency for FY2022”
8. “Direct payments by state for last year”

---

## 13. Deployment Plan (Google Cloud Run)
### 13.1 Local Dev (Apple Silicon)
- Use uv + `.venv`
- Prefer Cloud Run “deploy from source” to avoid ARM/AMD image mismatch

### 13.2 Cloud Run
- Deploy from source (`gcloud run deploy --source .`)
- Configure env vars:
  - USASPENDING_BASE_URL
  - USASPENDING_TIMEOUT_S
  - USASPENDING_MAX_RETRIES
  - USASPENDING_BACKOFF_BASE_S
  - DEFAULT_SCOPE_MODE (default: all_awards)
- Keep service private; grant IAM access to intended callers

### 13.3 CI/CD (Google Cloud Build)
- Use `cloudbuild.yaml` to run **unit tests** and **deterministic integration tests** (against a mock USAspending server) before pushing images.
- Recommended stages: lint/type checks (optional but recommended) → unit tests → docker build → integration tests (compose-style) → push to Artifact Registry → optional deploy.

### 13.4 IAM Model (Least Privilege)
- **Cloud Run runtime service account:** keep permissions minimal. If the service only calls the public USAspending API, it generally needs **no additional GCP roles** beyond defaults. If using Secret Manager, grant only `roles/secretmanager.secretAccessor` on specific secrets.
- **Cloud Build / deploy permissions:** prefer a dedicated deployer service account with only what is required to push to Artifact Registry and deploy Cloud Run. Common minimum set: `roles/artifactregistry.writer` (repo-scoped), `roles/run.admin`, and `roles/iam.serviceAccountUser` on the runtime SA.
- **Invoker access:** keep the Cloud Run service private by default; grant `roles/run.invoker` only to approved users/groups/workloads.

---

## 14. Milestones (Suggested)
### Sprint 1 (P0): Core loop (all_awards capable)
- bootstrap_catalog, resolve_entities, award_search, award_explain
- Router supports scope_mode detection (contracts vs grants keywords)
- HTTP client hardening + debug + tests

### Sprint 2 (P1): True rollups + profiles
- spending_rollups (true rollups + fallbacks)
- agency_portfolio, recipient_profile

### Sprint 3 (P2): IDV depth + reporting/data quality
- idv_vehicle_bundle
- awards/last_updated + reporting endpoints support for “data current?”

---

## 15. Open Questions
1. Should default for ambiguous questions remain `all_awards` or should it ask a clarifying question? (v1 default is all_awards.)
2. Standard metric: obligations vs outlays vs award_amount—should metric vary by award type?
3. How should the router choose between awarding vs funding agency by default?
4. How should we represent “award category” consistently across contracts and assistance in tool outputs?
5. Should `scope_mode` be inferred only, or also controllable via a request flag? (Recommended: both, with inferred default.)

---

## 16. Appendix — Repository Layout (Recommended)
```
.
├── src/
│   └── usaspending_mcp/
│       ├── __init__.py
│       ├── server.py              # FastMCP tool registry (mcp = FastMCP(...))
│       ├── stdio_server.py        # stdio transport entrypoint (mcp.run())
│       ├── http_app.py            # FastAPI app; mounts /mcp + /healthz,/readyz
│       ├── router.py
│       ├── router_rules.json
│       ├── usaspending_client.py
│       ├── cache.py
│       ├── response.py            # ok/fail + trim_payload token guardrails
│       ├── award_types.py
│       └── tools/
│           ├── bootstrap_catalog.py
│           ├── resolve_entities.py
│           ├── award_search.py
│           ├── award_explain.py
│           ├── spending_rollups.py
│           ├── recipient_profile.py
│           ├── agency_portfolio.py
│           ├── idv_vehicle_bundle.py
│           └── answer_award_spending_question.py
├── tests/
│   ├── test_client.py
│   ├── test_response.py
│   ├── test_award_types.py
│   ├── test_router.py
│   ├── test_golden_questions.py
│   └── integration/
│       ├── test_mcp_http_handshake.py
│       └── test_tools_against_mock.py
├── mock_usaspending/             # deterministic mock API for integration tests
├── scripts/
│   ├── bootstrap_gcp.sh
│   ├── deploy_cloud_run.sh
│   ├── smoke_test_cloud_run.sh
│   └── get_service_url.sh
├── Dockerfile
├── docker-compose.yml
├── cloudbuild.yaml
├── .gitignore
├── .dockerignore
├── .gcloudignore
├── .env.example
├── Makefile
├── pyproject.toml
└── README.md
```
