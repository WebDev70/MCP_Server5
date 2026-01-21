import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock USAspending API")

def load_fixture(filename):
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(path, "r") as f:
        return json.load(f)

def handle_scenario(request: Request):
    scenario = request.query_params.get("scenario")
    if scenario == "error_400":
        raise HTTPException(status_code=400, detail={"detail": "Mock Validation Error"})
    if scenario == "error_429":
        raise HTTPException(status_code=429, detail="Rate Limit Exceeded")
    if scenario == "error_500":
        raise HTTPException(status_code=500, detail="Upstream Error")
    if scenario == "empty":
        return {"results": []}
    return None

@app.middleware("http")
async def scenario_middleware(request: Request, call_next):
    # Check scenario param early
    # Note: query params are available in middleware
    scenario = request.query_params.get("scenario")
    if scenario == "error_400":
        return JSONResponse(status_code=400, content={"detail": "Mock Validation Error"})
    if scenario == "error_429":
        return JSONResponse(status_code=429, content={"detail": "Rate Limit Exceeded"})
    if scenario == "error_500":
        return JSONResponse(status_code=500, content={"detail": "Upstream Error"})
    
    response = await call_next(request)
    return response

# References
@app.get("/api/v2/references/toptier_agencies/")
async def toptier_agencies(request: Request):
    scen = handle_scenario(request)
    if scen: return scen
    return load_fixture("toptier_agencies.json")

@app.get("/api/v2/references/award_types/")
async def award_types(request: Request):
    return load_fixture("award_types.json")

@app.get("/api/v2/references/filter_tree/psc/")
async def filter_tree_psc(request: Request):
    return {"results": [{"id": "1", "code": "A", "description": "Research and Development", "children": []}]}

@app.get("/api/v2/references/cfda/totals/")
async def cfda_totals(request: Request):
    return {"results": [
        {"code": "20.205", "total_obligations": 1000000.0},
        {"code": "93.778", "total_obligations": 2000000.0},
        {"code": "47.050", "total_obligations": 500000.0}
    ]}

# Autocomplete
@app.post("/api/v2/autocomplete/recipient/")
async def autocomplete_recipient(request: Request):
    payload = await request.json()
    q = payload.get("search_text", "").lower()
    
    # Mock search logic
    if "boeing" in q:
        return {"results": [{"recipient_name": "BOEING COMPANY", "recipient_unique_id": "123456789", "recipient_hash": "hash-boeing-123"}]}
    if "lockheed" in q:
        return {"results": [{"recipient_name": "LOCKHEED MARTIN", "recipient_unique_id": "987654321", "recipient_hash": "hash-lockheed-987"}]}
    if "caci" in q:
        return {"results": [{"recipient_name": "CACI INC", "recipient_unique_id": "555555555", "recipient_hash": "hash-caci-555"}]}
    return {"results": []}

@app.post("/api/v2/autocomplete/naics/")
async def autocomplete_naics(request: Request):
    return {"results": [{"code": "541511", "description": "Custom Computer Programming Services"}]}

@app.post("/api/v2/autocomplete/psc/")
async def autocomplete_psc(request: Request):
    return {"results": [{"code": "D302", "description": "IT and Telecom - Systems Development"}]}

@app.post("/api/v2/autocomplete/assistance_listing/")
async def autocomplete_cfda(request: Request):
    return {"results": [{"code": "20.205", "description": "Highway Planning and Construction"}]}

# Search
@app.post("/api/v2/search/spending_by_award/")
async def spending_by_award(request: Request):
    return load_fixture("sample_awards.json")

@app.post("/api/v2/search/spending_by_award_count/")
async def spending_by_award_count(request: Request):
    return {"results": {"count": 1234}}

# Award Details
@app.get("/api/v2/awards/{award_id}/")
async def award_detail(award_id: str, request: Request):
    # Route based on ID prefix
    if "GRANT" in award_id:
        return load_fixture("sample_award_detail_grant.json")
    return load_fixture("sample_award_detail_contract.json")

@app.post("/api/v2/transactions/")
async def transactions(request: Request):
    return load_fixture("sample_transactions.json")

@app.post("/api/v2/subawards/")
async def subawards(request: Request):
    return {"results": [
        {"id": 1, "subaward_number": "SUB-001", "amount": 50000.00, "recipient_name": "Sub Recipient A"},
        {"id": 2, "subaward_number": "SUB-002", "amount": 25000.00, "recipient_name": "Sub Recipient B"}
    ], "page_metadata": {"total": 2, "page": 1}}

# Spending Rollups
@app.post("/api/v2/search/spending_by_category/awarding_agency/")
async def spending_by_category_agency(request: Request):
    return {"results": [
        {"name": "Department of Defense", "amount": 5000000000.0, "code": "097"},
        {"name": "Department of Health and Human Services", "amount": 3000000000.0, "code": "075"},
        {"name": "Department of Energy", "amount": 1000000000.0, "code": "089"}
    ], "page_metadata": {"total": 3, "page": 1}}

@app.post("/api/v2/search/spending_by_category/recipient/")
async def spending_by_category_recipient(request: Request):
    return {"results": [
        {"name": "BOEING COMPANY", "amount": 1000000000.0, "recipient_id": "123"},
        {"name": "LOCKHEED MARTIN", "amount": 800000000.0, "recipient_id": "456"}
    ], "page_metadata": {"total": 2, "page": 1}}

# Recipient
@app.get("/api/v2/recipient/{recipient_id}/")
async def recipient_profile(recipient_id: str):
    # Note: Real API path might differ (duns/uei), but our tool uses resolution.
    # Assuming tool hits this for generic profile if implemented.
    # Actually recipient profile uses rollups mostly.
    # But if we added direct profile endpoint:
    return load_fixture("sample_recipient.json")

# IDVs
@app.post("/api/v2/idvs/awards/")
async def idv_awards(request: Request):
    return load_fixture("sample_idv_orders.json")

@app.post("/api/v2/idvs/activity/")
async def idv_activity(request: Request):
    return {"results": [{"fiscal_year": "2024", "obligated_amount": 500000.0}]}

@app.post("/api/v2/idvs/funding_rollup/")
async def idv_funding(request: Request):
    return {
        "total_transaction_obligated_amount": 750000.0,
        "awarding_agency_count": 2,
        "funding_agency_count": 2,
        "federal_account_count": 3
    }

# Fallback for generic spending endpoint if used
@app.post("/api/v2/spending/")
async def spending_generic(request: Request):
    return {"results": [{"name": "Generic Ag", "amount": 100.0}]}
