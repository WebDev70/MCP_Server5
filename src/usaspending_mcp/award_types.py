import re
from typing import Any, Dict, List, Optional

# Scope Modes - API requires codes from ONE group only
SCOPE_ALL_AWARDS = "all_awards"  # Defaults to contracts
SCOPE_CONTRACTS_ONLY = "contracts_only"
SCOPE_IDVS_ONLY = "idvs_only"
SCOPE_GRANTS_ONLY = "grants_only"
SCOPE_LOANS_ONLY = "loans_only"
SCOPE_DIRECT_PAYMENTS_ONLY = "direct_payments_only"
SCOPE_OTHER_ASSISTANCE_ONLY = "other_assistance_only"
SCOPE_ASSISTANCE_ONLY = "assistance_only"  # Alias for grants (most common)

# Regex patterns for inference
CONTRACT_KEYWORDS = [
    r"\bcontracts?\b", r"\bprocurement\b", r"\bpurchase orders?\b",
    r"\bdefinitives?\b", r"\bvendors?\b", r"\bcontractors?\b"
]
IDV_KEYWORDS = [
    r"\bidvs?\b", r"\bidiq\b", r"\bgwac\b", r"\bbpa\b",
    r"\btask orders?\b", r"\bdelivery orders?\b", r"\bindefinite delivery\b",
    r"\bfss\b", r"\bfederal supply schedule\b", r"\bgsa\s*(mas|schedule)\b",
    r"\bboa\b", r"\bbasic ordering agreement\b", r"\bblanket purchase\b"
]
GRANT_KEYWORDS = [
    r"\bgrants?\b", r"\bcooperative agreements?\b", r"\bblock grants?\b",
    r"\bformula grants?\b", r"\bproject grants?\b"
]
LOAN_KEYWORDS = [
    r"\bloans?\b", r"\bdirect loans?\b", r"\bguaranteed loans?\b",
    r"\binsured loans?\b"
]
DIRECT_PAYMENT_KEYWORDS = [
    r"\bdirect payments?\b"
]
OTHER_ASSISTANCE_KEYWORDS = [
    r"\binsurance\b", r"\bother.*assistance\b"
]

# Fallback Codes - each is a separate API group
FALLBACK_CONTRACT_CODES = ["A", "B", "C", "D"]
#Non-IDV procurement “Award Type” codes (definitive instruments)
#   A — BPA Call (call against a BPA)
#   B — Purchase Order
#   C — Delivery Order / Task Order (order under an IDV)
#   D — Definitive Contract

# IDV (Indefinite Delivery Vehicle) Codes:
#   IDV_A   — GWAC (Government-Wide Acquisition Contract, OMB-approved)
#   IDV_B   — IDC (Indefinite Delivery Contract)
#   IDV_B_A — IDC / Requirements
#   IDV_B_B — IDC / Indefinite Quantity (IDIQ)
#   IDV_B_C — IDC / Definite Quantity
#   IDV_C   — FSS (GSA MAS or VA Federal Supply Schedule)
#   IDV_D   — BOA (Basic Ordering Agreement)
#   IDV_E   — BPA (Blanket Purchase Agreement)
FALLBACK_IDV_CODES = ["IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"]

FALLBACK_GRANT_CODES = ["02", "03", "04", "05"]
FALLBACK_LOAN_CODES = ["07", "08"]
FALLBACK_DIRECT_PAYMENT_CODES = ["06", "10"]
FALLBACK_OTHER_ASSISTANCE_CODES = ["09", "11"]


# Specific IDV subtype keywords that unambiguously refer to IDVs
# These take priority even when "contract" is also mentioned (e.g., "FSS contracts")
SPECIFIC_IDV_KEYWORDS = [
    r"\bgwac\b", r"\bidiq\b", r"\bbpa\b", r"\bfss\b", r"\bboa\b",
    r"\bfederal supply schedule\b", r"\bgsa\s*(mas|schedule)\b",
    r"\bbasic ordering agreement\b", r"\bblanket purchase\b"
]


def infer_scope_mode(question: str) -> str:
    """
    Analyzes the question for keywords to determine the likely scope mode.
    Returns the most specific match, defaulting to SCOPE_ALL_AWARDS.
    """
    q_lower = question.lower()

    # Check for specific IDV subtypes first - these always mean IDV
    has_specific_idv = any(re.search(p, q_lower) for p in SPECIFIC_IDV_KEYWORDS)
    if has_specific_idv:
        return SCOPE_IDVS_ONLY

    # Check for general type keywords
    has_idv = any(re.search(p, q_lower) for p in IDV_KEYWORDS)
    has_contract = any(re.search(p, q_lower) for p in CONTRACT_KEYWORDS)
    has_grant = any(re.search(p, q_lower) for p in GRANT_KEYWORDS)
    has_loan = any(re.search(p, q_lower) for p in LOAN_KEYWORDS)
    has_direct_payment = any(re.search(p, q_lower) for p in DIRECT_PAYMENT_KEYWORDS)
    has_other_assistance = any(re.search(p, q_lower) for p in OTHER_ASSISTANCE_KEYWORDS)

    # Return most specific match
    if has_idv and not (has_contract or has_grant or has_loan):
        return SCOPE_IDVS_ONLY
    if has_loan and not (has_grant or has_contract):
        return SCOPE_LOANS_ONLY
    if has_direct_payment and not (has_grant or has_loan):
        return SCOPE_DIRECT_PAYMENTS_ONLY
    if has_grant and not (has_contract or has_loan):
        return SCOPE_GRANTS_ONLY
    if has_other_assistance:
        return SCOPE_OTHER_ASSISTANCE_ONLY
    if has_contract and not (has_grant or has_loan):
        return SCOPE_CONTRACTS_ONLY

    # Default to all awards (which uses contracts)
    return SCOPE_ALL_AWARDS


def get_award_type_codes(
    scope_mode: str,
    catalog: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Returns the list of award_type_codes for the API filters based on scope_mode.
    The USAspending API requires award_type_codes from ONE group only.
    """
    scope_to_codes = {
        SCOPE_ALL_AWARDS: FALLBACK_CONTRACT_CODES,  # Default to contracts
        SCOPE_CONTRACTS_ONLY: FALLBACK_CONTRACT_CODES,
        SCOPE_IDVS_ONLY: FALLBACK_IDV_CODES,
        SCOPE_GRANTS_ONLY: FALLBACK_GRANT_CODES,
        SCOPE_ASSISTANCE_ONLY: FALLBACK_GRANT_CODES,  # Alias
        SCOPE_LOANS_ONLY: FALLBACK_LOAN_CODES,
        SCOPE_DIRECT_PAYMENTS_ONLY: FALLBACK_DIRECT_PAYMENT_CODES,
        SCOPE_OTHER_ASSISTANCE_ONLY: FALLBACK_OTHER_ASSISTANCE_CODES,
    }

    return scope_to_codes.get(scope_mode, FALLBACK_CONTRACT_CODES)


def normalize_award_category(raw_type: str) -> str:
    """
    Maps USAspending award type codes to canonical categories:
    contract, idv, grant, loan, direct_payment, other_assistance
    """
    if not raw_type:
        return "other_assistance"

    t = raw_type.upper()

    if t in FALLBACK_CONTRACT_CODES:
        return "contract"
    if t in FALLBACK_IDV_CODES or t.startswith("IDV"):
        return "idv"
    if t in FALLBACK_GRANT_CODES:
        return "grant"
    if t in FALLBACK_LOAN_CODES:
        return "loan"
    if t in FALLBACK_DIRECT_PAYMENT_CODES:
        return "direct_payment"

    return "other_assistance"
