# USAspending API – All Awards Endpoint Map

Goal: support an MCP server that can answer award spending questions across **Contracts**, **Contract IDVs**, **Grants**, **Direct Payments**, **Loans**, and **Other Financial Assistance**.

> **Note on repo naming:** In the USAspending API GitHub repo, the folder name `api_contracts/` refers to *API contract specs/tests*, not “contracts” as a spending category.

---

## 1) Award-type coverage you should implement

### The two major categories
USAspending treats award spending as two major categories:

- **Contract spending** (procurement)
- **Financial assistance spending** (e.g., grants, loans, direct payments)

(“Award spending” is the subset of government spending paid or obligated to non-federal recipients via contracts or financial assistance.)

### Code systems you must support
You will see award-type filters expressed as codes from the legacy source systems:

#### A) Procurement: “Award Type” (definitive awards)
These are the classic FPDS “Award Type” values:

- `A` = BPA Call
- `B` = Purchase Order
- `C` = Delivery Order / Task Order (under an IDV)
- `D` = Definitive Contract

#### B) Procurement: “IDV Type” (indefinite delivery vehicles)
IDVs are **mutually exclusive** from the definitive “Award Type” above:

- `A` = GWAC
- `B` = IDC
- `C` = FSS (GSA/VA Schedule)
- `D` = BOA
- `E` = BPA

#### C) Financial assistance: “Type of Assistance”
These FAADS+ “Type of Assistance” values cover grants, direct payments, loans, etc.:

- `02` Block Grant
- `03` Formula Grant
- `04` Project Grant
- `05` Cooperative Agreement
- `06` Direct payment for specified use
- `07` Direct loan
- `08` Guaranteed/insured loan
- `09` Insurance
- `10` Direct payment with unrestricted use
- `11` Other (reimbursable/contingent/indirect)

### Recommended user-facing groupings
To keep the MCP “natural language” layer simple, map user intent to these groupings:

- **Contracts (definitive)** → award type codes `A,B,C,D`
- **Contract IDVs** → IDV type codes `A,B,C,D,E` and/or the API’s IDV award grouping
- **Grants** → assistance codes `02,03,04,05`
- **Direct Payments** → assistance codes `06,10`
- **Loans** → assistance codes `07,08`
- **Other** → assistance codes `09,11` (insurance + other)

### Best-practice implementation pattern (avoid hardcoding)
1. **At server startup**, call the reference endpoint that returns a *map of award types by award grouping*.
2. Build an internal lookup like:
   - `group_name -> [award_type_codes]`
   - `award_type_code -> group_name`
3. When the user says “grants only” or “loans only,” translate that to the correct code list.

This approach prevents breakage if USAspending adds/renames award type groupings.

---

## 2) Endpoint categories

Below is a practical categorization for an MCP server. The emphasis is on endpoints that let you answer questions like:
- “How much did agency X obligate last FY?”
- “What are the top recipients for NAICS Y?”
- “Show me all awards matching filters Z.”

### A) Award endpoints (core Q&A)
These are your primary “answer engine” endpoints.

1. **Advanced Award Search**
   - `POST /api/v2/search/spending_by_award/`
   - Use for: filtered award lists + sorting + paging (contracts, grants, loans, etc.)

2. **Award Search – award type counts**
   - `POST /api/v2/search/spending_by_award_count/`
   - Use for: “How many awards are contracts vs grants vs loans…” for a filter set.

3. **Award details**
   - `GET /api/v2/awards/<award_id>/`
   - Use for: summary page facts (amounts, dates, recipient, agencies, etc.).

4. **Award funding & accounts rollups**
   - `GET /api/v2/awards/<award_id>/funding/`
   - `GET /api/v2/awards/<award_id>/funding_rollup/`
   - `GET /api/v2/awards/<award_id>/accounts/`
   - Use for: “which accounts funded this award?”, “funding path” questions.

5. **Award “last updated” metadata**
   - `GET /api/v2/awards/last_updated/`
   - Use for: freshness checks in answers.

6. **Transactions**
   - `POST /api/v2/transactions/` (and related transaction endpoints)
   - Use for: modification history, action dates, transaction amounts.

7. **Subawards**
   - `POST /api/v2/subawards/`
   - Use for: subrecipient/subaward analysis.

8. **IDV-specific award endpoints**
   - `GET /api/v2/idvs/awards/`
   - `GET /api/v2/idvs/activity/`
   - `GET /api/v2/idvs/funding/`
   - `GET /api/v2/idvs/funding_rollup/`
   - `GET /api/v2/idvs/accounts/`
   - Use for: “IDV vehicle-level” rollups and the awards/orders underneath.

### B) Agency endpoints (agency rollups & budget lenses)
Use these when the question is explicitly agency-centric or budget-structure-centric.

1. **Agency profile / overview**
   - `GET /api/v2/agency/<toptier_code>/`

2. **Agency awards rollups**
   - `GET /api/v2/agency/<toptier_code>/awards/`
   - plus related “count” endpoints in the agency namespace

3. **Agency budget structure lenses**
   - Budget functions, program activity, object class, federal accounts, sub-agencies, etc.
   - (all under `/api/v2/agency/<toptier_code>/...`)

4. **Financial balances & spending lenses**
   - `GET /api/v2/financial_balances/agencies/`
   - `POST /api/v2/financial_spending/object_class/`
   - `POST /api/v2/financial_spending/major_object_class/`

### C) Recipient endpoints (recipient profiles & recipient-centric rollups)
Use these when the user asks about companies/non-profits/individuals, parents/children, or geography-by-recipient.

1. **Recipient search / profile**
   - `POST /api/v2/recipient/`
   - `GET /api/v2/recipient/<recipient_id>/`

2. **Recipient counts and hierarchies**
   - `POST /api/v2/recipient/count/`
   - `GET /api/v2/recipient/children/<duns_or_uei>/`

3. **Recipient spending rollups**
   - `POST /api/v2/award_spending/recipient/`

4. **Recipient-by-state utilities**
   - `GET /api/v2/recipient/state/` and related state endpoints

---

## 3) Supporting endpoints (Reference + Autocomplete)

These aren’t usually “the answer,” but they make the MCP server robust and user-friendly.

### A) References (authoritative lookups)
- `GET /api/v2/references/award_types/`  (build your award-type grouping map)
- `GET /api/v2/references/assistance_listing/` (Assistance listings / CFDA-like)
- `GET /api/v2/references/naics/`
- `GET /api/v2/references/def_codes/`
- `GET /api/v2/references/toptier_agencies/`
- `GET /api/v2/references/data_dictionary/`
- `GET /api/v2/references/submission_periods/`
- Filter trees: PSC, TAS, etc.

### B) Autocomplete (query helper UX)
- `POST /api/v2/autocomplete/recipient/`
- `POST /api/v2/autocomplete/naics/`
- `POST /api/v2/autocomplete/psc/`
- `POST /api/v2/autocomplete/location/`
- `POST /api/v2/autocomplete/city/`
- `POST /api/v2/autocomplete/awarding_agency_office/`
- `POST /api/v2/autocomplete/funding_agency/`

---

## 4) “All awards” default filters (practical recipes)

Use these as *building blocks* for tool implementations that accept natural language and translate to API filter JSON.

### A) Default: All awards
- Don’t set award type filters unless the user asks.

### B) Contracts only (definitive)
```json
{ "filters": { "award_type_codes": ["A","B","C","D"] } }
```

### C) IDVs only
- Prefer: get the IDV award-type codes from `GET /api/v2/references/award_types/` and inject that list.
- If you need an FPDS-style fallback (vehicle classification): filter via IDV Type codes `A-E` where supported.

### D) Grants only
```json
{ "filters": { "award_type_codes": ["02","03","04","05"] } }
```

### E) Direct payments only
```json
{ "filters": { "award_type_codes": ["06","10"] } }
```

### F) Loans only
```json
{ "filters": { "award_type_codes": ["07","08"] } }
```

### G) Other financial assistance
```json
{ "filters": { "award_type_codes": ["09","11"] } }
```

