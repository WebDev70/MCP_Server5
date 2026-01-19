from usaspending_mcp.award_types import (
    SCOPE_ALL_AWARDS,
    SCOPE_ASSISTANCE_ONLY,
    SCOPE_CONTRACTS_ONLY,
    SCOPE_GRANTS_ONLY,
    SCOPE_IDVS_ONLY,
    SCOPE_LOANS_ONLY,
    get_award_type_codes,
    infer_scope_mode,
)


def test_infer_scope_mode_contracts():
    assert infer_scope_mode("Show me top contracts for NASA") == SCOPE_CONTRACTS_ONLY
    assert infer_scope_mode("Who are the top vendors?") == SCOPE_CONTRACTS_ONLY
    assert infer_scope_mode("Procurement spending by agency") == SCOPE_CONTRACTS_ONLY


def test_infer_scope_mode_idvs():
    assert infer_scope_mode("List task orders under IDV 123") == SCOPE_IDVS_ONLY
    assert infer_scope_mode("Show me all IDVs for DoD") == SCOPE_IDVS_ONLY
    assert infer_scope_mode("GWAC spending in FY2024") == SCOPE_IDVS_ONLY
    assert infer_scope_mode("BPA awards for IT services") == SCOPE_IDVS_ONLY


def test_infer_scope_mode_grants():
    assert infer_scope_mode("How much in grants did we spend?") == SCOPE_GRANTS_ONLY
    assert infer_scope_mode("Top grant recipients") == SCOPE_GRANTS_ONLY
    assert infer_scope_mode("Cooperative agreements for research") == SCOPE_GRANTS_ONLY


def test_infer_scope_mode_loans():
    assert infer_scope_mode("Show loans for small business") == SCOPE_LOANS_ONLY
    assert infer_scope_mode("Direct loan programs") == SCOPE_LOANS_ONLY
    assert infer_scope_mode("Guaranteed loans in 2024") == SCOPE_LOANS_ONLY


def test_infer_scope_mode_all():
    assert infer_scope_mode("Show me all awards for DoD") == SCOPE_ALL_AWARDS
    assert infer_scope_mode("Top recipients in 2024") == SCOPE_ALL_AWARDS
    # Ambiguous/Both
    assert infer_scope_mode("Compare contracts and grants for DHS") == SCOPE_ALL_AWARDS


def test_get_award_type_codes():
    # All awards defaults to contracts (API requires codes from one group only)
    all_codes = get_award_type_codes(SCOPE_ALL_AWARDS)
    assert "A" in all_codes
    assert "02" not in all_codes

    # Contracts only
    contract_codes = get_award_type_codes(SCOPE_CONTRACTS_ONLY)
    assert "A" in contract_codes
    assert "IDV_A" not in contract_codes

    # IDVs only
    idv_codes = get_award_type_codes(SCOPE_IDVS_ONLY)
    assert "IDV_A" in idv_codes
    assert "A" not in idv_codes

    # Grants only
    grant_codes = get_award_type_codes(SCOPE_GRANTS_ONLY)
    assert "02" in grant_codes
    assert "07" not in grant_codes

    # Loans only
    loan_codes = get_award_type_codes(SCOPE_LOANS_ONLY)
    assert "07" in loan_codes
    assert "02" not in loan_codes

    # Assistance (alias for grants)
    assistance_codes = get_award_type_codes(SCOPE_ASSISTANCE_ONLY)
    assert "02" in assistance_codes
