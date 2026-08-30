"""Contract tests for flat root-callback output payloads."""

from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import BaseModel, ValidationError

from ....application.operator_surface.help import build_help_document
from ....application.operator_surface.help_models import RootLandingReport
from ....application.overview.calendar_models import OverviewStatusReport
from ....core.json_contract import strict_round_trip
from .._root_payloads import AppRootResult, RootStatusResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "source",
    (
        build_help_document("root"),
        RootLandingReport(
            active_profile=None,
            command="aeat config profile create NAME",
            message="Create a profile before starting tax work.",
        ),
        OverviewStatusReport(
            transactions=0,
            invoices=0,
            drafts=0,
            unreadable_rows=0,
        ),
    ),
)
def test_root_status_payload_preserves_each_canonical_branch(source: BaseModel) -> None:
    payload = source.model_dump(mode="json")
    assert strict_round_trip(RootStatusResult, source).model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "payload",
    ({}, {"bogus": "value"}, {"transactions": -1, "unexpected": True}),
)
def test_root_status_payload_rejects_noncanonical_branches(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RootStatusResult.model_validate(payload)


def test_app_root_payload_accepts_only_the_canonical_help_document() -> None:
    document = build_help_document("app")
    payload = document.model_dump(mode="json")

    assert strict_round_trip(AppRootResult, document).model_dump(mode="json") == payload
    with pytest.raises(ValidationError):
        AppRootResult.model_validate({"bogus": "value"})


# Run out-of-process: this module imports OverviewStatusReport at module scope,
# so the in-process sys.modules is already poisoned for an import-absence check.
_HELP_BRANCH_IMPORT_PROBE = """
import sys

from cadrumo.application.operator_surface.help import build_help_document
from cadrumo.core.json_contract import strict_round_trip
from cadrumo.entrypoints.cli._root_payloads import RootStatusResult

document = build_help_document("root")
projected = strict_round_trip(RootStatusResult, document)
assert projected.model_dump(mode="json") == document.model_dump(mode="json")
print("overview" if "cadrumo.application.overview" in sys.modules else "clean")
"""


def test_help_branch_round_trip_does_not_import_the_overview_graph() -> None:
    """The help branch matches first, so the overview branch must stay unimported.

    ``cadrumo.application.overview`` drags in the calculation, ledger, and
    registry import graph. Rendering ``aeat --help`` performs no domain work and
    must not pay for it. This pins the deferral: hoisting the overview branch
    back to an eager import in ``_root_payloads`` reds this test.
    """
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv with in-test script.
        [sys.executable, "-c", _HELP_BRANCH_IMPORT_PROBE],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "clean", (
        "rendering the root help document imported cadrumo.application.overview; "
        "the help branch must resolve without the overview import graph"
    )
