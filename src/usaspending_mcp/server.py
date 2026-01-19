import uuid
from mcp.server.fastmcp import FastMCP

from usaspending_mcp.cache import Cache
from usaspending_mcp.router import Router
from usaspending_mcp.logging_config import log_context, setup_logging, get_logger
from usaspending_mcp.tools.agency_portfolio import AgencyPortfolioTool
from usaspending_mcp.tools.answer_award_spending_question import AnswerAwardSpendingQuestionTool
from usaspending_mcp.tools.award_explain import AwardExplainTool
from usaspending_mcp.tools.award_search import AwardSearchTool
from usaspending_mcp.tools.bootstrap_catalog import BootstrapCatalogTool
from usaspending_mcp.tools.data_freshness import DataFreshnessTool
from usaspending_mcp.tools.idv_vehicle_bundle import IDVVehicleBundleTool
from usaspending_mcp.tools.recipient_profile import RecipientProfileTool
from usaspending_mcp.tools.resolve_entities import ResolveEntitiesTool
from usaspending_mcp.tools.spending_rollups import SpendingRollupsTool
from usaspending_mcp.usaspending_client import USAspendingClient

# Setup logging
setup_logging()
logger = get_logger("server")

# Initialize Shared Dependencies
client = USAspendingClient()
cache = Cache()
router = Router(client, cache)

# Initialize Tool Instances
bootstrap_tool = BootstrapCatalogTool(client, cache)
resolve_tool = ResolveEntitiesTool(client, cache)
search_tool = AwardSearchTool(client)
explain_tool = AwardExplainTool(client)
rollups_tool = SpendingRollupsTool(client)
recipient_tool = RecipientProfileTool(client, cache)
agency_tool = AgencyPortfolioTool(client)
idv_tool = IDVVehicleBundleTool(client)
freshness_tool = DataFreshnessTool(client)
orchestrator_tool = AnswerAwardSpendingQuestionTool(router)

# Initialize FastMCP server
mcp = FastMCP("USAspending MCP", log_level="DEBUG")

# Register Tools
@mcp.tool()
def data_freshness(
    check_type: str = "submission_periods", 
    agency_code: str = None, 
    debug: bool = False
) -> dict:
    """
    Check data freshness/currency.
    Returns latest submission periods, agency status, or DB update time.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="data_freshness"):
        logger.info(f"Executing data_freshness check_type={check_type}")
        return freshness_tool.execute(check_type=check_type, agency_code=agency_code, debug=debug, request_id=request_id)

@mcp.tool()
def bootstrap_catalog(include: list[str] = None, force_refresh: bool = False) -> dict:
    """
    Loads/refreshes reference catalogs (agencies, award types).
    Recommended to run this once at session start.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="bootstrap_catalog"):
        logger.info(f"Executing bootstrap_catalog force_refresh={force_refresh}")
        return bootstrap_tool.execute(include=include, force_refresh=force_refresh, request_id=request_id)

@mcp.tool()
def resolve_entities(q: str, types: list[str] = None, limit: int = 10) -> dict:
    """
    Resolves natural language queries to canonical entities (Agencies, Recipients).
    Use this before searching if entity names are ambiguous.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="resolve_entities"):
        logger.info(f"Executing resolve_entities q='{q}'")
        return resolve_tool.execute(q=q, types=types, limit=limit, request_id=request_id)

@mcp.tool()
def award_search(
    time_period: list[dict] = None, 
    filters: dict = None, 
    fields: list[str] = None, 
    sort: str = "Award Amount", 
    order: str = "desc", 
    page: int = 1, 
    limit: int = 10, 
    mode: str = "list", 
    scope_mode: str = "all_awards"
) -> dict:
    """
    Searches for awards (Contracts, Grants, etc.) matching filters.
    Supports list and count modes.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="award_search"):
        logger.info(f"Executing award_search mode={mode} scope_mode={scope_mode}")
        return search_tool.execute(
            time_period=time_period, 
            filters=filters, 
            fields=fields, 
            sort=sort, 
            order=order, 
            page=page, 
            limit=limit, 
            mode=mode, 
            scope_mode=scope_mode,
            request_id=request_id
        )

@mcp.tool()
def award_explain(
    award_id: str, 
    include: list[str] = None, 
    transactions_limit: int = 25, 
    subawards_limit: int = 25, 
    scope_mode: str = "all_awards"
) -> dict:
    """
    Explains a specific award (Summary, Transactions, Subawards).
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="award_explain"):
        logger.info(f"Executing award_explain award_id={award_id}")
        return explain_tool.execute(
            award_id=award_id, 
            include=include, 
            transactions_limit=transactions_limit, 
            subawards_limit=subawards_limit, 
            scope_mode=scope_mode,
            request_id=request_id
        )

@mcp.tool()
def spending_rollups(
    time_period: list[dict] = None, 
    filters: dict = None, 
    group_by: str = "awarding_agency", 
    top_n: int = 10, 
    metric: str = "obligations", 
    scope_mode: str = "all_awards"
) -> dict:
    """
    Returns total spending or Top N breakdowns (e.g., by agency, recipient) without listing all awards.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="spending_rollups"):
        logger.info(f"Executing spending_rollups group_by={group_by}")
        return rollups_tool.execute(
            time_period=time_period, 
            filters=filters, 
            group_by=group_by, 
            top_n=top_n, 
            metric=metric, 
            scope_mode=scope_mode,
            request_id=request_id
        )

@mcp.tool()
def recipient_profile(
    recipient: str, 
    time_period: list[dict] = None, 
    include: list[str] = None, 
    scope_mode: str = "all_awards"
) -> dict:
    """
    Gets a profile for a recipient (Vendor/Grantee), including totals and top spending.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="recipient_profile"):
        logger.info(f"Executing recipient_profile recipient='{recipient}'")
        return recipient_tool.execute(
            recipient=recipient, 
            time_period=time_period, 
            include=include, 
            scope_mode=scope_mode,
            request_id=request_id
        )

@mcp.tool()
def agency_portfolio(
    toptier_code: str, 
    time_period: list[dict] = None, 
    views: list[str] = None, 
    scope_mode: str = "all_awards"
) -> dict:
    """
    Gets agency overview and top awards/recipients.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="agency_portfolio"):
        logger.info(f"Executing agency_portfolio toptier_code={toptier_code}")
        return agency_tool.execute(
            toptier_code=toptier_code, 
            time_period=time_period, 
            views=views, 
            scope_mode=scope_mode,
            request_id=request_id
        )

@mcp.tool()
def idv_vehicle_bundle(
    idv_award_id: str, 
    include: list[str] = None, 
    time_period: list[dict] = None, 
    scope_mode: str = "all_awards"
) -> dict:
    """
    Gets details for an IDV (Indefinite Delivery Vehicle) including Task Orders and Funding.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="idv_vehicle_bundle"):
        logger.info(f"Executing idv_vehicle_bundle idv_award_id={idv_award_id}")
        return idv_tool.execute(
            idv_award_id=idv_award_id, 
            include=include, 
            time_period=time_period, 
            scope_mode=scope_mode,
            request_id=request_id
        )

@mcp.tool()
def answer_award_spending_question(question: str) -> dict:
    """
    [ORCHESTRATOR] Intelligently answers a question about federal award spending.
    It plans the best tool to use, checks budgets, and returns a concise answer bundle.
    Use this for natural language questions.
    """
    request_id = str(uuid.uuid4())
    with log_context(request_id=request_id, tool_name="answer_award_spending_question"):
        logger.info(f"Executing answer_award_spending_question question='{question}'")
        return orchestrator_tool.execute(question=question, request_id=request_id)
