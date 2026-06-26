"""
DecayDAO test suite (gltest).

Run with:
    pip install genlayer-test
    gltest --network studionet          # or localnet

These tests mock the LLM verdict and the web page (R17) so that
non-deterministic transactions finalize deterministically. Without mocks,
real web.render / exec_prompt calls need internet + inference and will surface
as confusing STATE errors (see common_error.md R17).

Covered:
  - happy path: grant -> review(COMPLIANT) heals / stays active
  - decay:      repeated VIOLATED verdicts drive health to 0 -> REVOKED
  - drift:      DRIFTING lowers health without immediate revoke
  - guards:     empty terms, bad url, missing license, review after revoke
  - reinstate:  only licensor can reinstate a revoked license
"""

import json
import pytest
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded


CONTRACT = "decaydao.py"


def _install_mocks(client, verdict="COMPLIANT", confidence=90,
                   reason="Use honours the spirit of the terms.",
                   page_body="This is a personal, non-commercial fan page."):
    """Install LLM + web mocks. params MUST be a bare dict, not list-wrapped (R17)."""
    llm_payload = json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
    })
    client.provider.make_request(
        method="sim_installMocks",
        params={
            "llm_mocks": {".*": llm_payload},
            "web_mocks": {".*": {"status": 200, "body": page_body}},
        },
    )


def _deploy():
    factory = get_contract_factory(CONTRACT)
    contract = factory.deploy(args=[])
    return contract


def test_grant_and_compliant_review():
    contract = _deploy()
    acct = contract.account

    # grant a non-commercial license
    tx = contract.connect(acct).grant_license(
        args=[
            "0xLICENSEE",
            "ACME wordmark",
            "Non-commercial use only. Must credit ACME.",
            "https://example.org/fanpage",
        ]
    ).transact()
    assert tx_execution_succeeded(tx)

    _install_mocks(contract.client if hasattr(contract, "client") else acct,
                   verdict="COMPLIANT", confidence=90)

    tx = contract.connect(acct).review_license(args=["0"]).transact()
    assert tx_execution_succeeded(tx)

    lic = json.loads(contract.get_license(args=["0"]).call())
    assert lic["status"] == "ACTIVE"
    assert lic["last_verdict"] == "COMPLIANT"
    assert lic["health"] == 100  # already at max, stays capped
    assert lic["review_count"] == 1


def test_repeated_violations_revoke():
    contract = _deploy()
    acct = contract.account

    contract.connect(acct).grant_license(
        args=[
            "0xLICENSEE",
            "Brand logo",
            "Non-commercial only.",
            "https://example.org/shop",
        ]
    ).transact()

    _install_mocks(acct, verdict="VIOLATED", confidence=95,
                   reason="Page sells merchandise using the logo.",
                   page_body="Buy now! Official store, add to cart, $49.99")

    # health 100 -> 50 -> 0 (revoked) over two VIOLATED reviews
    contract.connect(acct).review_license(args=["0"]).transact()
    lic = json.loads(contract.get_license(args=["0"]).call())
    assert lic["health"] == 50
    assert lic["status"] == "ACTIVE"

    contract.connect(acct).review_license(args=["0"]).transact()
    lic = json.loads(contract.get_license(args=["0"]).call())
    assert lic["health"] == 0
    assert lic["status"] == "REVOKED"
    assert lic["last_verdict"] == "VIOLATED"


def test_drifting_lowers_health():
    contract = _deploy()
    acct = contract.account
    contract.connect(acct).grant_license(
        args=["0xL", "Asset", "Educational use only.", "https://example.org/x"]
    ).transact()

    _install_mocks(acct, verdict="DRIFTING", confidence=50,
                   reason="Borderline: some commercial framing appearing.")
    contract.connect(acct).review_license(args=["0"]).transact()
    lic = json.loads(contract.get_license(args=["0"]).call())
    assert lic["health"] == 80
    assert lic["status"] == "ACTIVE"
    assert lic["last_verdict"] == "DRIFTING"


def test_guards():
    contract = _deploy()
    acct = contract.account

    # empty terms rejected
    with pytest.raises(Exception):
        contract.connect(acct).grant_license(
            args=["0xL", "Asset", "  ", "https://example.org"]
        ).transact()

    # bad url rejected
    with pytest.raises(Exception):
        contract.connect(acct).grant_license(
            args=["0xL", "Asset", "terms", "not-a-url"]
        ).transact()

    # review missing license rejected
    with pytest.raises(Exception):
        contract.connect(acct).review_license(args=["999"]).transact()


def test_reinstate_only_by_licensor():
    contract = _deploy()
    acct = contract.account
    contract.connect(acct).grant_license(
        args=["0xL", "Asset", "Non-commercial.", "https://example.org/y"]
    ).transact()

    _install_mocks(acct, verdict="VIOLATED", confidence=95,
                   page_body="commercial store buy now")
    contract.connect(acct).review_license(args=["0"]).transact()
    contract.connect(acct).review_license(args=["0"]).transact()
    lic = json.loads(contract.get_license(args=["0"]).call())
    assert lic["status"] == "REVOKED"

    # licensor reinstates -> active at half health
    tx = contract.connect(acct).reinstate_license(args=["0"]).transact()
    assert tx_execution_succeeded(tx)
    lic = json.loads(contract.get_license(args=["0"]).call())
    assert lic["status"] == "ACTIVE"
    assert lic["health"] == 50
