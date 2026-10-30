"""The requests the desktop Assets forms make decode against the backend's own request contracts.

The frontend builds each create and correct request from what a person types, through its form
fields and request builders. The test runs those builders as they ship, on typed drafts, and
decodes the result with the request models the registered operations validate, so a field the
form states at the wrong place, or a fact it cannot state, fails here and not in the window.
A correction is built against the revision the create request produced, and chained to it by
the history's own rules.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
)
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetRevisionSnapshot
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FRONTEND = REPO_ROOT / "native" / "desktop" / "frontend"
_ENTRY = _FRONTEND / "tests" / "support" / "assetRequests.ts"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

_BUNDLE_SCRIPT = """
const esbuild = require(process.argv[1]);
esbuild.buildSync({
  entryPoints: [process.argv[2]],
  outfile: process.argv[3],
  bundle: true,
  platform: "node",
  format: "cjs",
  tsconfig: process.argv[4],
  logLevel: "error",
});
"""

_NEW = {
    "asset_kind": "material",
    "name": "Sierra de cinta",
    "serial_number": "SC-0412",
    "acquisition_shape": "primary_purchase",
    "in_service_date": "2026-06-15",
    "acquired_condition": "new",
    "basis_stage": "business_allocated",
    "basis_amount": "900.00",
    "non_deductible_iva": "0.00",
    "prior_allocation_provenance": "allocation booked in the ledger",
    "opening_status": "known",
    "opening_amount": "0.00",
    "method": "linear",
    "authority_class_key": "maquinaria",
}

#: Each scenario is the draft a person types, over the common one.
_CREATE: dict[str, dict[str, str]] = {
    "linear": {},
    "linear_elected_coefficient": {"linear_coefficient": "10"},
    "linear_used_known_price": {
        "acquired_condition": "used",
        "used_determination": "known",
        "used_price": "1500.00",
        "used_evidence": "invoice of the seller",
    },
    "linear_used_expert_valuation": {
        "acquired_condition": "used",
        "used_determination": "expert_valuation",
        "used_price": "1500.00",
        "used_evidence": "valuation report of the appraiser",
    },
    "opening_amount_known": {"opening_amount": "500.00", "opening_through": "2026", "opening_method": "linear"},
    "opening_missing": {"opening_status": "missing", "opening_amount": ""},
    "taxpayer_owned_basis": {"basis_stage": "taxpayer_owned", "business_use_share": "60"},
    "constant_percentage": {"method": "constant_percentage", "linear_coefficient": "10"},
    "sum_of_digits": {"method": "sum_of_digits", "digit_period": "8", "digit_order": "descending"},
    "low_value_free": {
        "method": "low_value_free",
        "authority_class_key": "",
        "basis_amount": "250.00",
        "low_value_election": "election recorded with the purchase",
        "low_value_evidence": "purchase invoice",
    },
    "research_development_free": {
        "method": "research_development_free",
        "authority_class_key": "maquinaria",
        "research_evidence": "technical report",
    },
    "intangible_linear": {"asset_kind": "intangible", "authority_class_key": "intangible-software"},
    "intangible_goodwill": {
        "asset_kind": "intangible",
        "method": "goodwill",
        "authority_class_key": "",
    },
}

#: Each correction changes what the person edits in the revision of the linear creation.
_CORRECT: dict[str, dict[str, str]] = {
    "basis": {"basis_amount": "1000.00"},
    "in_service_date": {"in_service_date": "2026-07-01"},
    "stage": {"basis_stage": "taxpayer_owned", "business_use_share": "75"},
    "method_with_class_kept": {"method": "constant_percentage", "linear_coefficient": "10"},
    "opening": {"opening_amount": "300.00", "opening_through": "2026", "opening_method": "linear"},
    "elected_coefficient": {"linear_coefficient": "9"},
}


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        raise AssertionError("node is needed to run the desktop request builders, and was not found")
    return node


def _bundle(tmp_path: Path) -> Path:
    esbuild = _FRONTEND / "node_modules" / "esbuild"
    assert esbuild.is_dir(), f"the desktop frontend's dependencies are not installed under {_FRONTEND}"
    out = tmp_path / "assetRequests.cjs"
    subprocess.run(  # noqa: S603 - fixed node program on repository files
        [
            _node(),
            "-e",
            _BUNDLE_SCRIPT,
            str(esbuild),
            str(_ENTRY),
            str(out),
            str(_FRONTEND / "tsconfig.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        creationflags=_NO_WINDOW,
    )
    return out


def _run(bundle: Path, scenarios: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    done = subprocess.run(  # noqa: S603 - fixed node program on a bundle built above
        [_node(), str(bundle)],
        input=json.dumps(scenarios),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=_NO_WINDOW,
    )
    return {item["id"]: item for item in json.loads(done.stdout)}


def _decode_create(made: dict[str, Any]) -> ActivityAssetCreateRequest:
    assert made["problems"] == {}, made["problems"]
    assert made["request"] is not None, "the form made no request from a complete draft"
    return ActivityAssetCreateRequest.model_validate_json(json.dumps({"profile_id": str(uuid4()), **made["request"]}))


@pytest.fixture(scope="module")
def created(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, dict[str, Any]]]:
    bundle = _bundle(tmp_path_factory.mktemp("asset-requests"))
    scenarios = [{"id": name, "kind": "create", "draft": {**_NEW, **changes}} for name, changes in _CREATE.items()]
    return bundle, _run(bundle, scenarios)


@pytest.mark.parametrize("name", sorted(_CREATE))
def test_a_create_request_the_form_makes_decodes_against_the_backend_contract(
    created: tuple[Path, dict[str, dict[str, Any]]], name: str
) -> None:
    request = _decode_create(created[1][name])

    revision = request.revision.to_domain()
    assert revision.revision_number == 1
    assert revision.asset_id == created[1][name]["request"]["revision"]["asset_id"]
    assert request.descriptor.name == "Sierra de cinta"
    assert len(revision.revision_id) == 64


def test_the_facts_the_form_states_reach_the_revision_where_the_backend_reads_them(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    used = _decode_create(created[1]["linear_used_expert_valuation"]).revision.to_domain()
    owned = _decode_create(created[1]["taxpayer_owned_basis"]).revision.to_domain()
    opening = _decode_create(created[1]["opening_amount_known"]).revision.to_domain()
    digits = _decode_create(created[1]["sum_of_digits"]).revision.to_domain()
    elected = _decode_create(created[1]["linear_elected_coefficient"]).revision.to_domain()

    assert used.amortization.used_original_price is not None
    assert used.amortization.used_original_price.determination.value == "expert_valuation"
    assert used.amortization.used_original_price.original_price == Decimal("1500.00")
    assert owned.basis.business_use_share is not None
    assert owned.basis.business_use_share == Decimal("0.6")
    assert opening.opening_history.covered_through_tax_year == 2026
    assert opening.opening_history.accumulated_amount == Decimal("500.00")
    assert digits.amortization.sum_of_digits_period_years == 8
    assert digits.amortization.digit_order is not None
    assert elected.amortization.linear_coefficient == Decimal("0.1")


@pytest.mark.parametrize("name", sorted(_CORRECT))
def test_a_correct_request_the_form_makes_decodes_and_chains_to_the_revision_it_supersedes(
    created: tuple[Path, dict[str, dict[str, Any]]], name: str
) -> None:
    bundle, made = created
    first = _decode_create(made["linear"]).revision.to_domain()
    base = {
        "revision": ActivityAssetRevisionSnapshot.from_domain(first).model_dump(mode="json"),
        "revision_id": first.revision_id,
    }
    claim_id = "e" * 64
    result = _run(
        bundle,
        [
            {
                "id": name,
                "kind": "correct",
                "base": base,
                "changes": _CORRECT[name],
                "supersede": [claim_id],
            },
        ],
    )[name]
    assert result["problems"] == {}, result["problems"]
    assert result["request"] is not None

    request = ActivityAssetCorrectRequest.model_validate_json(
        json.dumps({"profile_id": str(uuid4()), **result["request"]}),
    )
    second = request.revision.to_domain()
    assert second.revision_number == 2
    assert second.supersedes_revision_id == first.revision_id
    assert [claim.supersedes_claim_id for claim in request.superseding_claims] == [claim_id]
    ActivityAssetHistory().append_revision(first).append_revision(second)
