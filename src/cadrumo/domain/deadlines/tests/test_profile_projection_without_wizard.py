"""Deciding what a taxpayer must file may not require a setup UI.

``taxpayer_profile_from_mapping`` is the front door to the deadline engine:
it turns stored profile facts into the :class:`TaxpayerProfile` that
schedule computation and modelo applicability read. It used to reach that
shape by walking the terminal wizard's question catalogue, so a process
that had never built an interactive setup surface could not compute a
schedule at all — the projection raised, and one caller swallowed the
error and quietly under-resolved.

The proof here is process isolation rather than patching: a child that
imports the domain and asserts that the wizard package was never imported.
Without that precondition the test could pass for the wrong reason.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from ....domain.calculations.registry.tests.published_authority import published_profile_schema
from ....domain.deadlines.setup_answer_projection import setup_answer_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


_CHILD_SCRIPT = r"""
import sys

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.deadlines.profiles import taxpayer_profile_from_mapping

with bundled_indexed_authority().operation():
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
print("WIZARD:" + ("IMPORTED" if "cadrumo.application.wizard" in sys.modules else "NOT_IMPORTED"))
"""


@dataclass(frozen=True)
class _ChildResult:
    """Captured result from the audited child-process boundary."""

    returncode: int
    stdout: str
    stderr: str


async def _run_child_async(*, cwd: Path) -> _ChildResult:
    """Run the fixed projection probe without importing the wizard in-process."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _CHILD_SCRIPT,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
    returncode = process.returncode
    if returncode is None:
        raise RuntimeError("the child process did not finish after communicate()")
    return _ChildResult(
        returncode=returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


def test_the_projection_runs_in_a_process_that_never_built_a_setup_ui(tmp_path: Path) -> None:
    """A schedule is computed from stored facts, not from a question catalogue."""
    child = asyncio.run(_run_child_async(cwd=tmp_path))
    out = child.stdout
    detail = f"\n--- stdout ---\n{out}\n--- stderr ---\n{child.stderr}"

    assert child.returncode == 0, f"child process failed{detail}"
    assert "WIZARD:NOT_IMPORTED" in out, f"test invalid - the child imported the wizard{detail}"
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
    schema = published_profile_schema()
    declared = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields}
    undeclared = sorted(spec.path for spec in setup_answer_fields().values() if spec.path not in declared)
    assert not undeclared, f"paths absent from the profile schema: {undeclared}"
