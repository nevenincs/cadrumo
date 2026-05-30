"""Structural enforcement tests for typed-id alias placement.

Each test parses every Python module under :mod:`aeat` with the
standard-library :mod:`ast` module and asserts the absence of one
structural failure mode for the typed-id alias placement rule. The
tests are real-behavior: no mocks, no fakes, no skipped variants. A
violation surfaces as a precise ``path:line`` location in the
assertion message so the failure points the operator at the source.
"""

from __future__ import annotations

import pytest

from aeat.diagnostics._identity_placement import (
    Finding,
    build_alias_inventory,
    find_bare_str_typed_id_fields,
    find_misplaced_hex_length_constants,
    find_private_id_imports,
    find_sibling_domain_id_imports,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _render(findings: list[Finding]) -> str:
    return "\n".join(finding.render() for finding in findings)


def test_no_sibling_domain_id_imports() -> None:
    """No ``domain.<a>`` module imports from ``domain.<b>._ids`` for ``a != b``.

    The registry-aliases module (``aeat.domain.calculations.registry._ids``)
    is the one explicit exception declared by the placement rule and is
    accepted from any domain.
    """

    findings = find_sibling_domain_id_imports()
    assert findings == [], "sibling-domain _ids imports detected:\n" + _render(findings)


def test_no_private_id_imports() -> None:
    """No adapter / application / entrypoint module imports a private name from an ``_ids.py``.

    Consumers consume the typed alias names directly. Reaching for the
    underlying regex constants, length constants, or private
    re-aliases is a type-system escape under the calculation-grounding
    rule.
    """

    findings = find_private_id_imports()
    assert findings == [], "private-name imports from _ids modules detected:\n" + _render(findings)


def test_no_misplaced_hex_length_constants() -> None:
    """No ``_HEX_*_LENGTH`` constant lives outside the owning ``_ids.py`` module."""

    findings = find_misplaced_hex_length_constants()
    assert findings == [], "misplaced _HEX_*_LENGTH constants detected:\n" + _render(findings)


def test_alias_inventory_discovers_known_owners() -> None:
    """The alias-inventory walker discovers every typed-id alias under aeat.

    The mapping is itself part of the test contract: if a typed alias
    is added or renamed, the inventory must reflect it. The assertion
    pins the known owners present in the post-Wave-2 tree; new aliases
    extend the set.
    """

    inventory = build_alias_inventory()
    required_owners = {
        "bucket",
        "profile",
        "snapshot",
        "transaction",
        "work_unit",
        "calculation_revision",
        "filing_record",
        "verification_report",
        "invoice",
        "attachment",
        "bundle",
        "evidence",
        "casilla",
        "formula",
        "revision",
        "modelo",
    }
    missing = required_owners - inventory.aliases_by_owner.keys()
    assert not missing, (
        f"alias inventory missing owners {sorted(missing)!r}; "
        f"discovered {sorted(inventory.aliases_by_owner.keys())!r}"
    )


def test_bare_str_typed_id_detector_recognises_synthetic_violation(tmp_path) -> None:
    """Sanity-check the bare-``str`` detector against a controlled fixture.

    The detector parses every ``BaseModel`` subclass under the tree
    root and flags ``<owner>_id`` fields annotated as bare ``str`` (or
    ``str | None``) when the alias inventory carries a typed alias for
    that owner. The synthetic fixture exercises three shapes — bare
    ``str``, ``str | None``, and the accepted typed-alias form — to
    confirm the detector reports the two bare shapes and accepts the
    typed shape.

    The exhaustive full-tree enforcement is deferred to a follow-up
    Wave that adjudicates the cross-domain ADR-amendment surface the
    detector surfaces (see W05.P19.S68 step record for the inventory
    of 54 known sites the detector flags against the post-W04 tree).
    """

    fixture_root = tmp_path / "src" / "aeat"
    diagnostics_dir = fixture_root / "diagnostics"
    diagnostics_dir.mkdir(parents=True)
    (fixture_root / "__init__.py").write_text("")
    (diagnostics_dir / "__init__.py").write_text("")

    invoices_dir = fixture_root / "domain" / "invoices"
    invoices_dir.mkdir(parents=True)
    (fixture_root / "domain" / "__init__.py").write_text("")
    (invoices_dir / "__init__.py").write_text("")
    (invoices_dir / "_ids.py").write_text(
        "from typing import Annotated\n"
        "from pydantic import StringConstraints\n"
        "InvoiceId = Annotated[str, StringConstraints(min_length=64, max_length=64)]\n"
        '__all__ = ("InvoiceId",)\n'
    )

    consumer = invoices_dir / "_consumer.py"
    consumer.write_text(
        "from pydantic import BaseModel, Field\n"
        "from ._ids import InvoiceId\n"
        "class BareField(BaseModel):\n"
        "    invoice_id: str = Field(min_length=64, max_length=64)\n"
        "class OptionalBareField(BaseModel):\n"
        "    invoice_id: str | None = None\n"
        "class TypedField(BaseModel):\n"
        "    invoice_id: InvoiceId\n"
    )

    inventory = build_alias_inventory(fixture_root)
    assert "invoice" in inventory.aliases_by_owner, (
        f"alias inventory failed to discover InvoiceId; got "
        f"{sorted(inventory.aliases_by_owner.keys())!r}"
    )

    findings = find_bare_str_typed_id_fields(fixture_root, inventory)
    classes_flagged = sorted(f.message.split(" ")[3].split(".")[0] for f in findings)
    assert classes_flagged == ["BareField", "OptionalBareField"], (
        f"detector mis-classifies typed alias usage; flagged {classes_flagged!r}"
    )
