
import httpx
import pytest
import respx

from usaspending_mcp.usaspending_client import APIError, USAspendingClient


@pytest.fixture
def client():
    return USAspendingClient()

@respx.mock
def test_successful_request(client):
    endpoint = "references/toptier_agencies/"
    url = f"{client.base_url}/{endpoint}"
    
    mock_data = {"results": [{"agency_id": 1, "toptier_code": "001"}]}
    respx.get(url).mock(return_value=httpx.Response(200, json=mock_data))
    
    response = client.request("GET", endpoint, tool_name="test_tool")
    assert response == mock_data

@respx.mock
def test_validation_error_400(client):
    endpoint = "search/spending_by_award/"
    url = f"{client.base_url}/{endpoint}"
    
    respx.post(url).mock(return_value=httpx.Response(400, json={"detail": "Invalid filter"}))
    
    with pytest.raises(APIError) as excinfo:
        client.request("POST", endpoint, tool_name="test_tool", json_data={"filters": {}})
    
    assert excinfo.value.error_type == "validation"
    assert excinfo.value.status_code == 400

@respx.mock
def test_rate_limit_retry_success(client):
    # Should retry on 429 and eventually succeed
    endpoint = "search/spending_by_award/"
    url = f"{client.base_url}/{endpoint}"
    
    route = respx.post(url)
    # Fail twice with 429, then succeed
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(429),
        httpx.Response(200, json={"results": []})
    ]
    
    response = client.request("POST", endpoint, tool_name="test_tool", json_data={"filters": {}})
    assert response == {"results": []}
    assert route.call_count == 3

@respx.mock
def test_upstream_error_retry_failure(client):
    # Should retry on 500 and eventually fail
    endpoint = "broken_endpoint/"
    url = f"{client.base_url}/{endpoint}"
    
    # Configure client to fail fast for test
    client.max_retries = 2
    client.backoff_base = 0.01
    
    route = respx.get(url)
    route.mock(return_value=httpx.Response(500))
    
    with pytest.raises(APIError) as excinfo:
        client.request("GET", endpoint, tool_name="test_tool")
        
    assert excinfo.value.error_type == "upstream"
    assert excinfo.value.status_code == 500
    # Initial call + 2 retries = 3 calls
    assert route.call_count == 3

@respx.mock
def test_network_error(client):
    endpoint = "network_error/"
    url = f"{client.base_url}/{endpoint}"
    
    client.max_retries = 1
    client.backoff_base = 0.01
    
    respx.get(url).mock(side_effect=httpx.NetworkError("Connection failed"))
    
    with pytest.raises(APIError) as excinfo:
        client.request("GET", endpoint, tool_name="test_tool")
        
    assert excinfo.value.error_type == "network"
