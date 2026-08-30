"""Shared reader for bundled manual worked-example oracle payloads.

Every AEAT manual worked-example test reads a payload from the same bundled
corpus directory through the same strict payload model; only the filename
varies per module. This is deliberately narrower than
:mod:`domain.calculations.registry._external_grounding`'s
``_read_oracle_payload``, which dispatches across every :class:`ExternalOracleCorpus`
member, cross-validates and returns the richer ``ExternalOracleEvidence`` the
grounding fold consumes -- a production contract these tests neither need nor
should couple to for a plain bundled-file read.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from ..external_grounding import ManualWorkedExamplePayload

__all__ = ["oracle_declared_figures", "read_manual_worked_example"]


def read_manual_worked_example(name: str) -> ManualWorkedExamplePayload:
    """Read a bundled manual worked-example oracle through the registry's strict payload model."""
    path = Path(bundled_path("corpus", "manual_oracles")) / name
    return ManualWorkedExamplePayload.model_validate_json(path.read_text(encoding="utf-8"))


def oracle_declared_figures(oracle_payload_name: str) -> dict[CasillaId, Decimal]:
    """The facts the manual PRINTS for a case, read from the named oracle's declaration.

    This test and the payload used to be two independent transcriptions of one worked
    example -- the test hardcoding both the inputs and the expected figures, the payload
    declaring the figures again for the grounding fold, and nothing anywhere checking
    the two agreed. They did agree; nothing made them.

    Named for what it returns (printed-manual figures), never "input": that word is
    reserved in this repo for the ``BindingSourceKind.MANUAL_INPUT`` allowlist hazard --
    the escape hatch that can silence a binding-source refusal and leave a casilla
    resolving to a silent blank. This helper means the opposite: a figure an AEAT
    manual states for a worked example, not an operator-declared substitute for one.
    """
    declared = read_manual_worked_example(oracle_payload_name).declared_inputs
    assert declared is not None, f"{oracle_payload_name} must declare its scenario inputs"
    return {
        validated_casilla_id(casilla_id, surface=casilla_id): Decimal(value)
        for casilla_id, value in declared.by_casilla_id.items()
    }
