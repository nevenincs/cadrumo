"""Engine-side keying-invariant gate (per dual-keying design constraint D1/D2).

The dual-keying design contract is **engine-side**, not registry-data-side.
The registry's ``casilla.number`` field is honestly heterogeneous — id-mirror,
form-anchored, XSD-dictionary positional (``*06-09``), XSD-attribute
kebab-case (``tipo-declaracion``), dot-hierarchical XSD paths
(``2.devengo.ejercicio``), and uppercase XSD identifiers
(``SAL_RESERVA_DOTACION``) are ALL legitimate shapes that real AEAT modelos
declare. No single regex captures "legitimate ``number``" without becoming
``^.*$`` — and even if it could, the design contract doesn't actually constrain the
``number`` field's shape. The design contract constrains the **engine's canonical-key
contract**: every engine, verifier, and parser lookup MUST resolve through
``casilla.id``, never through ``casilla.number``.

This gate enforces that engine-side invariant by static-code ratchet:
production modules that own canonical casilla lookup MUST NOT contain
``casillas_by_number`` (the forbidden lookup-table identifier) and the
engine module MUST contain ``casillas_by_id`` (the canonical lookup-table
the design contract ratifies). Display-side references to ``casilla.number`` in error
messages or redacted-context dicts are NOT forbidden — those quote the
operator-facing form-field number as documentation; they do not key
engine state. The AEAT-workbook parity harness's ``inputs_by_number`` is
also fine — it lives at the operator/AEAT boundary and translates a
form-keyed scenario onto the engine's canonical id-keyed inputs.

A future commit that introduces ``casillas_by_number`` in any of the gated
modules fails this gate immediately. That's the actual #127 design
contract made executable.

(D1/D2/D4) for the convention rationale. A follow-up design amendment
explicitly ratifies the ``number`` field as documentary-and-heterogeneous,
with this gate as the load-bearing executable contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Module paths whose canonical casilla lookup must key on ``id``, never on
# ``number``. Each is the production module owning a layer of the
# calculate / verify / parse pipeline the design's D1/D2 names.
_AEAT_ROOT = Path(__file__).resolve().parents[4]
_ENGINE_MODULE = _AEAT_ROOT / "domain" / "calculations" / "registry" / "_formula_runtime.py"
_VERIFIER_MODULE = _AEAT_ROOT / "application" / "verification" / "_verify.py"
_PARSER_MODULE = _AEAT_ROOT / "adapters" / "inbound" / "declaracion" / "_parser.py"

# The forbidden lookup-table identifier: a dict keying canonical casilla
# state on ``.number`` would invert the design contract. Any production
# module that introduces it fails this gate.
_FORBIDDEN_LOOKUP_TABLE = "casillas_by_number"

# The required canonical lookup-table identifier: the engine's canonical-
# keying path must route through it. Its absence means the canonical
# lookup has been renamed or removed without updating this gate — either
# way, a structural change the team must adjudicate.
_CANONICAL_LOOKUP_TABLE = "casillas_by_id"


def _read(module_path: Path) -> str:
    assert module_path.is_file(), f"gated module {module_path!r} does not exist"
    return module_path.read_text(encoding="utf-8")


def test_engine_formula_runtime_keys_canonical_lookup_on_casilla_id() -> None:
    """``_formula_runtime`` indexes casillas by ``id``, never by ``number``.

    Display-side references to ``target_casilla.number`` (error messages,
    redacted context) are permitted — those are documentary uses of the
    operator-facing form-field number. The forbidden construct is the
    lookup dict ``casillas_by_number`` that would invert the design contract.
    """

    src = _read(_ENGINE_MODULE)
    assert _FORBIDDEN_LOOKUP_TABLE not in src, (
        f"{_ENGINE_MODULE} introduces {_FORBIDDEN_LOOKUP_TABLE!r}; the engine "
        f"must consult casilla.id, never casilla.number (per #127 D1/D2)"
    )
    assert _CANONICAL_LOOKUP_TABLE in src, (
        f"{_ENGINE_MODULE} no longer references {_CANONICAL_LOOKUP_TABLE!r}; "
        f"the canonical id-keyed lookup has been renamed or removed without "
        f"updating this gate (per #127 D1/D2)"
    )


def test_verifier_keys_canonical_lookup_on_casilla_id() -> None:
    """``_verify`` does not introduce a ``number``-keyed casilla lookup.

    The verifier consumes typed observations keyed on ``casilla_id`` (per
    the dual-keying design's Finding C). It must never gain a parallel
    ``number``-keyed lookup that would silently bypass the canonical
    identity.
    """

    src = _read(_VERIFIER_MODULE)
    assert _FORBIDDEN_LOOKUP_TABLE not in src, (
        f"{_VERIFIER_MODULE} introduces {_FORBIDDEN_LOOKUP_TABLE!r}; "
        f"verification must consult casilla.id, never casilla.number "
        f"(per #127 D1/D2 and Finding C)"
    )


def test_declaracion_parser_keys_canonical_lookup_on_casilla_id() -> None:
    """The PDF parser's extraction targets index on ``casilla_id``.

    The dual-keying design's Finding C confirmed the parser keys its
    extraction-target model on ``target.casilla_id``. A future commit
    that introduces a ``number``-keyed lookup at this boundary would
    re-open the dual-keying confusion the design closed.
    """

    src = _read(_PARSER_MODULE)
    assert _FORBIDDEN_LOOKUP_TABLE not in src, (
        f"{_PARSER_MODULE} introduces {_FORBIDDEN_LOOKUP_TABLE!r}; "
        f"the parser must consult casilla.id, never casilla.number "
        f"(per #127 D1/D2 and Finding C)"
    )
