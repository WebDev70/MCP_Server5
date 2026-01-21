import httpx
import pytest
import respx

from usaspending_mcp.tools.data_freshness import DataFreshnessTool
from usaspending_mcp.usaspending_client import USAspendingClient


@pytest.fixture
def tool():
    client = USAspendingClient()
    return DataFreshnessTool(client)

@respx.mock
def test_data_freshness_submission_periods(tool):
    url = f"{tool.client.base_url}/references/submission_periods/"
    
    mock_periods = [
        {
            "submission_fiscal_year": 2024,
            "submission_fiscal_quarter": 3,
            "submission_due_date": "2024-08-14",
            "period_end_date": "2024-06-30",
            "is_quarter": True
        },
        {
            "submission_fiscal_year": 2024,
            "submission_fiscal_quarter": 2,
            "period_end_date": "2024-03-31",
            "is_quarter": True
        }
    ]
    
    respx.get(url).mock(return_value=httpx.Response(200, json={"available_periods": mock_periods}))
    
    result = tool.execute(check_type="submission_periods")
    
    assert "freshness" in result
    latest = result["freshness"]["latest_period"]
    assert latest["fy"] == 2024
    assert latest["quarter"] == 3
    assert "days_since_period_close" in result["freshness"]

@respx.mock
def test_data_freshness_last_updated(tool):
    url = f"{tool.client.base_url}/awards/last_updated/"
    
    # Mock date
    respx.get(url).mock(return_value=httpx.Response(200, json={"last_updated": "2024-08-10"}))
    
    result = tool.execute(check_type="last_updated")
    
    assert result["freshness"]["data_as_of"] == "2024-08-10"
    assert "days_since_update" in result["freshness"]

@respx.mock
def test_data_freshness_agency_reporting(tool):
    agency_code = "097"
    url = f"{tool.client.base_url}/reporting/agencies/{agency_code}/overview/"
    
    respx.get(url).mock(
        return_value=httpx.Response(200, json={
            "fiscal_year": 2024, 
            "toptier_code": "097", 
            "total_dollars_obligated": 1000.0
        })
    )
    
    result = tool.execute(check_type="agency_reporting", agency_code=agency_code)
    
    assert "agency_status" in result["freshness"]
    assert result["freshness"]["agency_status"]["toptier_code"] == "097"

def test_data_freshness_agency_required(tool):
    result = tool.execute(check_type="agency_reporting")
    assert "error" in result
    assert result["error"]["type"] == "validation"
