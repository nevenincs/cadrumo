"""Deciding what a taxpayer must file may not require a setup UI.

``taxpayer_profile_from_mapping`` is the front door to the deadline engine:
it turns stored profile facts into the :class:`TaxpayerProfile` that
schedule computation and modelo applicability read. It used to reach that
shape by walking the terminal wizard's question catalogue, so a process
that had never built an interactive setup surface could not compute a
schedule at all — the projection raised, and one caller swallowed the
error and quietly under-resolved.

The proof here is process isolation rather than patching: a child that
imports the domain and never imports the wizard, asserting first that the
catalogue really is unregistered. Without that precondition the test would
pass for the wrong reason, since the root conftest registers the catalogue
for every ordinary pytest worker.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ....core.setup_answers import SETUP_ANSWER_FIELDS
from ....domain.user_profile.loader import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CHILD_SCRIPT = r"""
from cadrumo.core.wizard_catalogue import WizardCatalogueNotRegisteredError, get_setup_flow

try:
    get_setup_flow()
    print("CATALOGUE:REGISTERED")
    raise SystemExit(3)
except WizardCatalogueNotRegisteredError:
    print("CATALOGUE:UNREGISTERED")

from cadrumo.domain.deadlines.profiles import taxpayer_profile_from_mapping

profile = taxpayer_profile_from_mapping(
    {
        "identity.tax_id": "12345678Z",
        "activities.description": "asesoria fiscal",
        "taxpayer_type.entity_type": "natural_person",
        "taxpayer_type.irpf_income_categories": "actividad_economica",
        "withholding.has_employees": "true",
        "irpf.professional_income_withholding_ge_70pct": "true",
    },
    tax_id_default="00000000T",
)
print("TAX_ID:" + profile.tax_id)
print("ENTITY:" + str(profile.entity_type))
print("EMPLOYEES:" + str(profile.has_employees))
print("PROFESSIONAL_70PCT:" + str(profile.professional_income_withholding_ge_70pct))
"""


def test_the_projection_runs_in_a_process_that_never_built_a_setup_ui(tmp_path: Path) -> None:
    """A schedule is computed from stored facts, not from a question catalogue."""
    child = subprocess.run(  # noqa: S603 - fixed interpreter and in-module script constant
        [sys.executable, "-c", _CHILD_SCRIPT],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        cwd=tmp_path,
    )
    out = child.stdout
    detail = f"\n--- stdout ---\n{out}\n--- stderr ---\n{child.stderr}"

    assert "CATALOGUE:UNREGISTERED" in out, f"test invalid - the wizard catalogue was registered in the child{detail}"
    assert child.returncode == 0, f"child process failed{detail}"
    assert "TAX_ID:12345678Z" in out, detail
    assert "EMPLOYEES:True" in out, detail
    assert "PROFESSIONAL_70PCT:True" in out, (
        f"the art. 109 professional-withholding flag must reach the engine from the record{detail}"
    )


def test_every_projected_path_is_declared_in_the_profile_schema() -> None:
    """The schema stays the authority on which fields exist.

    The answer table records which stored fact feeds each answer field; it
    must not invent a path of its own, or the engine would be reading a
    fact nothing can ever write.
    """
    schema = load_user_profile_schema()
    declared = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}
    undeclared = sorted(spec.path for spec in SETUP_ANSWER_FIELDS.values() if spec.path not in declared)
    assert not undeclared, f"paths absent from the profile schema: {undeclared}"
