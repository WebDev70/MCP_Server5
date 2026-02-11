# Option 1 - Gemini Token Usage Optimization Analysis

This document outlines strategies to reduce token consumption and improve the efficiency of the USAspending MCP Server. Currently, the server can consume significant LLM context due to the verbose nature of the USAspending.gov API responses.

## 1. Schema Pruning (High Impact)
The USAspending API returns many fields that are secondary to most analytical questions (e.g., internal IDs, multiple URI variations, or redundant metadata).
*   **Recommendation:** Implement a "Field Allowlist" in each tool class. Filter the raw API JSON to only the top 10–15 most relevant fields (e.g., `award_id`, `recipient_name`, `amount`, `date`, `description`) before returning the result to the LLM.

## 2. Summary-First Defaults
Returning 50 search results by default consumes a large number of tokens.
*   **Recommendation:** 
    *   Change the default `limit` for `award_search` from 50 to **5**.
    *   Change the default `top_n` for `spending_rollups` from 10 to **5**.
    *   Instruct the LLM via tool descriptions to use the `page` or `limit` parameters only when a summary is insufficient.

## 3. Semantic Truncation
The current `trim_payload` function uses a "brute force" approach, cutting lists in half until they fit a byte limit.
*   **Recommendation:** Implement **Analytical Truncation**. If a list is truncated, return the first few items plus a summary object of the remaining data:
    ```json
    {
      "results": [...],
      "truncation_summary": {
        "remaining_count": 195,
        "remaining_obligations_total": 45000000.00
      }
    }
    ```

## 4. Entity Resolution Masking
The `resolve_entities` tool can return a large list of possible matches, creating noise.
*   **Recommendation:** If a match has a high confidence score (e.g., > 90%), return only that single match. For multiple lower-confidence matches, strip all metadata except for the canonical `name` and `id` until the user confirms the selection.

## 5. Description Compression
Long tool and parameter descriptions are sent in every MCP prompt.
*   **Recommendation:** Use "Telegraphic Speech" for tool and parameter descriptions in `server.py`.
    *   *Current:* "Returns total spending or Top N breakdowns (e.g., by agency, recipient) without listing all awards."
    *   *Optimized:* "Get spending totals/Top-N breakdowns by agency/recipient. No award lists."

## 6. Key Aliasing (Shortening JSON Keys)
USAspending uses very long keys (e.g., `awarding_sub_tier_agency_name`).
*   **Recommendation:** Map long keys to shorter versions in the `response.py` layer.
    *   `awarding_sub_tier_agency_name` → `sub_agency`
    *   `recipient_legal_entity_name` → `recipient`

## 7. Orchestrator-Internal Summarization
The `answer_award_spending_question` (Orchestrator) currently processes raw tool outputs.
*   **Recommendation:** When tools are called internally by the Orchestrator, have them return a **textual summary string** instead of a full JSON object. The LLM processes natural language summaries more efficiently than large JSON blocks.

## Implementation Path
1.  **Phase 1:** Update `router_rules.json` with lower default limits.
2.  **Phase 2:** Update `server.py` descriptions for brevity.
3.  **Phase 3:** Update `response.py` to support field filtering/allowlists.

---

# Option 2 - Claude Detailed Code-Level Token Optimization Audit

The following is a file-by-file audit of token consumption with specific code locations, estimated savings, and prioritized recommendations.

---

## Tier 1 — Highest ROI (implement first)

### 1. Strip "Description" from default award search fields
**File:** `tools/award_search.py` — `_get_default_fields()`

The default fields include `"Description"`, which is often 200-500 chars per award. With 50 results, that's ~15KB of descriptions alone. Removing it from defaults and making it opt-in saves **300-500 tokens per call**.

### 2. Lower default result limits across all tools
Current defaults are generous and rarely needed at full size:

| Tool | File | Current Default | Suggested |
|---|---|---|---|
| `award_search` limit | `award_search.py` | 50 | 20 |
| `award_explain` transactions_limit | `award_explain.py` | 25 | 10 |
| `award_explain` subawards_limit | `award_explain.py` | 25 | 10 |
| `resolve_entities` limit | `resolve_entities.py` | 10 per type | 3 per type |
| `idv_vehicle_bundle` orders | `idv_vehicle_bundle.py` | 10 | 5 |

Estimated savings: **500-1000 tokens per call chain**.

### 3. Strip response metadata bloat
**File:** `response.py` — response envelope construction

Every response envelope includes fields the LLM never acts on:
- `request_id` (36-char UUID) — useless to the LLM
- `endpoints_used` (list of 5-10 API paths) — debugging info, not decision-making
- `cache_hit` boolean — irrelevant to answer quality
- Nested `truncation` object with `max_bytes`, `max_items`, `returned_items`

Keep only: `scope_mode`, `accuracy_tier`, `warnings` (if non-empty). Savings: **200-400 tokens per response**.

### 4. Minimize `resolve_entities` output
**File:** `tools/resolve_entities.py`

Returns full API objects for every match (agency metadata, NAICS descriptions, recipient details). Should return only `(id, name)` tuples instead. With 5 entity types x 10 matches x ~500 bytes each, this is substantial. Savings: **400-600 tokens per call**.

### 5. Shorten tool descriptions in `server.py`
**File:** `server.py` — tool docstrings (lines ~50-240)

Tool docstrings are sent to the LLM at session init. Current descriptions are 1-3 sentences with implementation details like `[ORCHESTRATOR]` and behavioral guidance. Cut each to a single terse line. Savings: **400-600 tokens per session**.

Current examples:
```python
# Current
"""
[ORCHESTRATOR] Intelligently answers a question about federal award spending.
It plans the best tool to use, checks budgets, and returns a concise answer bundle.
Use this for natural language questions.
"""

# Optimized
"""Answer a natural-language federal spending question."""
```

---

## Tier 2 — Medium Priority

### 6. Filter `bootstrap_catalog` fields
**File:** `tools/bootstrap_catalog.py` (line ~48)

Returns full agency objects (name, code, abbreviation, agency_id, budgetary_resources, etc.) and all historical submission periods. Should return only `(name, toptier_code)` for agencies and only the current FY period. Savings: **500-1000 tokens** (cached, so once per session).

### 7. Remove nested metadata duplication
**Files:** `tools/recipient_profile.py`, `tools/agency_portfolio.py`

These chain sub-tool calls and pass through their metadata (`endpoints_used`, `meta_extras`). The parent response wraps the child's meta, creating duplication. Flatten and deduplicate. Savings: **200-300 tokens per profile call**.

### 8. Collapse remediation hints
**File:** `response.py` — `REMEDIATION_HINTS` dictionary (lines ~5-29)

Verbose hints with full examples are embedded in error responses. Replace with terse error codes; the LLM can infer the fix from context. Savings: **100-200 tokens per error**.

### 9. Clean up `router_rules.json`
**File:** `router_rules.json`

Unused fields that are loaded but never read by `router.py`:
- `scope_mode_control`
- `scope_mode_param_name`
- `award_category_normalization.values`

Remove dead config. Savings: **100-150 tokens**.

### 10. Cap IDV bundle responses
**File:** `tools/idv_vehicle_bundle.py`

Returns orders (10 x 1KB), activity timeline (50+ months), and full funding rollup. Limit to 5 orders with minimal fields, last 6 months of activity, and totals-only for funding. Savings: **300-500 tokens per call**.

---

## Tier 3 — Structural Improvements

### 11. Move `scope_mode` to session context
Every tool accepts `scope_mode` as a parameter, inflating every tool's JSON schema. Since it's inferred from the question and applies globally, set it once as session context rather than per-tool. Saves schema tokens across all 10 tools.

### 12. Response compression / field selection pattern
Add a global `fields` or `verbosity` parameter (e.g., `"compact"` vs `"full"`) that tools respect. Compact mode returns only decision-critical fields. This is a cross-cutting change but would have the biggest long-term impact.

### 13. Smarter caching with size limits
**File:** `cache.py`

No size limits on cached objects. In long sessions, cache grows unbounded. Add LRU eviction and max entry size to prevent stale large objects from persisting.

---

## Per-Tool Response Payload Analysis

### award_search (tools/award_search.py)
- Default 7 fields per award x 50 results = 350+ fields
- `"Description"` field averages 200-500 chars, causing majority of bloat
- Page metadata copied wholesale (total counts, page numbers)
- **Token cost:** ~1500-2500 per call

### award_explain (tools/award_explain.py)
- Returns 3 endpoints: summary (~5KB), transactions (25 x 500B), subawards (25 x 500B)
- No field selection — all fields from API response included
- Summary object has deeply nested recipient/agency data
- **Token cost:** ~3000-4000 per call

### spending_rollups (tools/spending_rollups.py)
- No field filtering on group results
- `total_groups` sometimes 10,000+ even when only top 10 returned
- Fallback method creates 100 award intermediate (50KB before aggregation)
- **Token cost:** ~800-1200 per call

### recipient_profile / agency_portfolio
- Chain sub-tool calls, duplicating metadata
- Recipient info includes all resolver fields
- Agency summary is unfiltered full object with all budget detail
- **Token cost:** ~1200-1800 per call

### resolve_entities (tools/resolve_entities.py)
- Default 10 matches per type x 5 types = up to 50 result objects
- Full API objects returned (not just id/name)
- Can hit multiple endpoints even if user only needs 1 entity type
- **Token cost:** ~1000-1500 per call

### idv_vehicle_bundle (tools/idv_vehicle_bundle.py)
- Calls up to 4 endpoints
- Activity timeline includes all historical months
- Funding rollup returns deeply nested structure
- **Token cost:** ~1500-2000 per call

---

## Estimated Total Savings

| Scenario | Tokens Saved |
|---|---|
| Single tool call (e.g., award_search) | 800-1500 |
| Orchestrated question (router -> resolve -> search -> explain) | 2500-4500 |
| Session initialization (tool schemas + bootstrap) | 900-1600 |
| **Typical full question lifecycle** | **~3000-5000** |

The biggest wins come from three things: **smaller default limits**, **field filtering on API responses**, and **stripping metadata the LLM doesn't need**. These are all low-risk changes that don't affect functionality.

---

# Option 3 - Codex Token Usage Optimization Audit (Feb 10, 2026)

Below is a focused audit of current token drivers and concrete recommendations. No code changes were made.

## High-Impact Findings

1. Double-wrapping responses and duplicated metadata
   The router wraps tool outputs that already include an `ok(...)` envelope, creating redundant `tool_version`, `meta`, and payload duplication.
   Recommendation: Return the tool response directly or move envelope responsibility to a single layer.

2. `trim_payload` only trims `results`
   Large lists like `transactions`, `subawards`, `groups`, or nested arrays are not trimmed unless they live under `results`.
   Recommendation: Make trimming recursive and list-aware, or add per-tool trimming for those fields.

3. `award_search` default fields include `Description`
   The default field set includes long text fields that multiply tokens across 50 results.
   Recommendation: Introduce a thin field profile and only include `Description` when explicitly requested.

## Medium-Impact Findings

4. `fields_profile` defined but not enforced
   `router_rules.json` declares `defaults.award_search.fields_profile: "thin"` but the router never applies it.
   Recommendation: Have the router select and pass a thin field list, or make the tool honor a `fields_profile` argument.

5. Metadata includes empty arrays and unused keys
   `_build_meta` always includes `warnings: []`, plus optional fields that often remain empty.
   Recommendation: Only emit non-empty fields in `meta`.

6. `award_explain` returns full summary payload
   The `/awards/{id}/` response is large and returned wholesale alongside transactions/subawards.
   Recommendation: Return a concise summary subset by default and make full summary opt-in.

## Lower-Impact Wins

7. Reduce default limits
   Defaults are generous for typical use.
   Recommendation: Lower defaults for `award_search` limit, `spending_rollups` top_n, and `award_explain` transactions/subawards.

8. Route totals/top-N to rollups more aggressively
   Many total/top questions can use compact rollups instead of list-heavy search.
   Recommendation: Tighten intent detection to prefer rollups for total/top queries.

9. Avoid returning `page_metadata` unless requested
   `award_search` copies `page_metadata` by default, which is often unused.
   Recommendation: Include only key metadata fields or make it optional.

## Recommended Implementation Path (If Changes Are Approved)

1. Remove router outer envelope or stop tools from wrapping with `ok(...)`.
2. Replace `trim_payload` with recursive trimming that handles any list.
3. Implement and enforce thin field profiles for `award_search`.
4. Drop empty `meta` keys and optionalize `page_metadata`.
5. Reduce default limits in `router_rules.json`.
6. Return compact summaries in `award_explain` by default.
