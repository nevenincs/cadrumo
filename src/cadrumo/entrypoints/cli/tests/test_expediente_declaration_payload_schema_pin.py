"""Golden-schema pin for `ExpedienteDeclarationPayload.expediente_id`.

`test_json_schema_conformance.py` is a deliberately STRUCTURAL-SHAPE-ONLY gate
(key parity between the Typer tree and the schema registry); it says so in its
own module docstring and does not assert constraint content. That leaves the
advertised JSON Schema *constraint* content of any one field free to drift
silently -- exactly what happened here: `expediente_id` was an unconstrained
bare `str` until it was retyped onto the shared `AeatExpedienteId` alias, and
nothing pinned the advertised `minLength` / `maxLength` / `pattern` before or
after that change.

This module pins the CURRENT (post-retype) shape only. The BEFORE shape (a
bare `str` producing `{"type": "string"}` with no length or pattern
constraint) is not reconstructed here -- building a second throwaway model to
fake the old shape would not exercise the real prior contract, and the real
prior contract is already preserved in git history. The reviewed before/after
fragment diff lives in the execution record for this step, not in this file.

The expected constraint values are hardcoded LITERALS, deliberately not
imported from `core.identity`'s `AEAT_EXPEDIENTE_ID_MIN_LENGTH` /
`AEAT_EXPEDIENTE_ID_MAX_LENGTH` / `AEAT_EXPEDIENTE_ID_PATTERN` constants and
not read off `AeatExpedienteId` at runtime. Deriving the expectation from the
alias under test would make the gate tautological: a future loosening of the
alias would move the expectation right along with it and the gate would never
fire. The literals below are copied by hand from the alias declaration
(`core/identity/_namespace.py`) at review time; a later widening of the alias
must touch this file too, and the reviewer looking at that diff is the point.
"""

from __future__ import annotations

import pytest

from .._app_live_payloads import ExpedienteDeclarationPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# Hand-copied from `core.identity.AeatExpedienteId` at review time. See the
# module docstring above for why these are literals, not an import.
_EXPECTED_EXPEDIENTE_ID_MIN_LENGTH = 12
_EXPECTED_EXPEDIENTE_ID_MAX_LENGTH = 32
_EXPECTED_EXPEDIENTE_ID_PATTERN = r"^[0-9]{4,}[A-Z0-9]+$"


def test_expediente_id_field_advertises_the_pinned_aeat_shape() -> None:
    """The advertised JSON Schema fragment for `expediente_id` is exactly this shape.

    Any of the following silently loosens (or accidentally tightens) the
    operator- and MCP-facing wire contract and must fail here:

    * dropping the AEAT-shape `pattern`
    * widening or narrowing `minLength` / `maxLength`
    * reverting the field to a bare unconstrained `string`
    """
    schema = ExpedienteDeclarationPayload.model_json_schema()
    fragment = schema["properties"]["expediente_id"]

    assert fragment == {
        "title": "Expediente Id",
        "type": "string",
        "minLength": _EXPECTED_EXPEDIENTE_ID_MIN_LENGTH,
        "maxLength": _EXPECTED_EXPEDIENTE_ID_MAX_LENGTH,
        "pattern": _EXPECTED_EXPEDIENTE_ID_PATTERN,
    }


def test_expediente_id_field_is_no_longer_an_unconstrained_bare_string() -> None:
    """Anchor against the pre-retype shape this pin replaces.

    Before `W02.P02.S11`, `expediente_id: str` advertised only
    `{"title": "Expediente Id", "type": "string"}` -- no length bound, no
    shape pattern. Asserting the negative here keeps the historical baseline
    legible from the test itself, alongside the positive pin above.
    """
    schema = ExpedienteDeclarationPayload.model_json_schema()
    fragment = schema["properties"]["expediente_id"]

    assert fragment != {"title": "Expediente Id", "type": "string"}
    assert "minLength" in fragment
    assert "maxLength" in fragment
    assert "pattern" in fragment
