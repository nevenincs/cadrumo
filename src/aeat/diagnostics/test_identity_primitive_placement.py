"""Structural enforcement tests for typed-id alias placement.

Each test parses every Python module under :mod:`aeat` with the
standard-library :mod:`ast` module and asserts the absence of one
structural failure mode for the typed-id alias placement rule. The
tests are real-behavior: no mocks, no fakes, no skipped variants. A
violation surfaces as a precise ``path:line`` location in the
assertion message so the failure points the operator at the source.

Ten cumulative clauses:

* Clauses 1-4: inherited from the identity-primitives ADR.
* Clauses 5-10: new under core-authority ADR Rule 11.
"""

from __future__ import annotations

import pytest

from pathlib import Path

from aeat.diagnostics import _identity_placement
from aeat.diagnostics._identity_placement import (
    Finding,
    PROMOTE001_PROTECT_LIST,
    build_alias_inventory,
    build_kind_status_state_alias_inventory,
    find_bare_str_kind_status_state_fields,
    find_bare_str_typed_id_fields,
    find_misplaced_hex_length_constants,
    find_private_id_imports,
    find_private_name_cross_package_imports,
    find_same_name_constant_multi_declarations,
    find_sibling_domain_constant_imports,
    find_sibling_domain_enum_imports,
    find_sibling_domain_id_imports,
    find_sibling_domain_protocol_imports,
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

    The exhaustive full-tree enforcement is deferred until the
    cross-domain ADR-amendment surface the detector flags is
    adjudicated (54 known sites at last inventory).
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


def _seed_synthetic_aeat(tmp_path: Path) -> Path:
    """Create a minimal ``<tmp>/src/aeat`` tree the detectors can walk."""

    root = tmp_path / "src" / "aeat"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("")
    return root


def test_sibling_domain_detector_flags_synthetic_violation(tmp_path: Path) -> None:
    """Anti-tautology proof for clause 1.

    Construct a synthetic ``domain.a`` importing from ``domain.b._ids``,
    confirm the detector reports the violation, then remove the import
    and confirm the detector reports clean. A passing assertion in the
    presence of the synthetic violation proves the detector cannot
    silently miss the same shape in production code.
    """

    root = _seed_synthetic_aeat(tmp_path)
    domain = root / "domain"
    (domain).mkdir()
    (domain / "__init__.py").write_text("")
    for name in ("a", "b"):
        sub = domain / name
        sub.mkdir()
        (sub / "__init__.py").write_text("")
    (domain / "b" / "_ids.py").write_text(
        "from typing import Annotated\n"
        "from pydantic import StringConstraints\n"
        "ExampleId = Annotated[str, StringConstraints(min_length=1)]\n"
    )
    consumer = domain / "a" / "_consumer.py"
    consumer.write_text("from ..b._ids import ExampleId\n")

    findings = find_sibling_domain_id_imports(root)
    assert any("ExampleId" in f.message for f in findings), (
        "sibling-domain detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    consumer.write_text("ExampleId = str\n")
    assert find_sibling_domain_id_imports(root) == []


def test_private_name_detector_flags_synthetic_violation(tmp_path: Path) -> None:
    """Anti-tautology proof for clause 2."""

    root = _seed_synthetic_aeat(tmp_path)
    pkg = root / "application" / "x"
    pkg.mkdir(parents=True)
    (root / "application" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "_ids.py").write_text(
        "ExampleId = str\n"
        "_HEX_EXAMPLE_LENGTH = 64\n"
    )
    consumer = pkg / "_consumer.py"
    consumer.write_text("from ._ids import _HEX_EXAMPLE_LENGTH\n")

    findings = find_private_id_imports(root)
    assert any("_HEX_EXAMPLE_LENGTH" in f.message for f in findings), (
        "private-name detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    consumer.write_text("from ._ids import ExampleId\n")
    assert find_private_id_imports(root) == []


def test_hex_length_detector_flags_synthetic_violation(tmp_path: Path) -> None:
    """Anti-tautology proof for clause 3."""

    root = _seed_synthetic_aeat(tmp_path)
    pkg = root / "domain" / "x"
    pkg.mkdir(parents=True)
    (root / "domain" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    misplaced = pkg / "_models.py"
    misplaced.write_text("_HEX_EXAMPLE_ID_LENGTH = 64\n")

    findings = find_misplaced_hex_length_constants(root)
    assert any("_HEX_EXAMPLE_ID_LENGTH" in f.message for f in findings)

    misplaced.write_text("OK_NAME = 64\n")
    assert find_misplaced_hex_length_constants(root) == []


def test_detector_public_surface_is_pinned() -> None:
    """The helper module exposes the expected public detector surface.

    Pinning ``__all__`` keeps the test module's import contract stable
    and prevents an accidental removal of a detector from breaking the
    test surface silently.
    """

    expected = {
        "AEAT_ROOT",
        "AliasInventory",
        "Finding",
        "PROMOTE001_PROTECT_LIST",
        "build_alias_inventory",
        "build_kind_status_state_alias_inventory",
        "find_bare_str_kind_status_state_fields",
        "find_bare_str_typed_id_fields",
        "find_misplaced_hex_length_constants",
        "find_private_id_imports",
        "find_private_name_cross_package_imports",
        "find_same_name_constant_multi_declarations",
        "find_sibling_domain_constant_imports",
        "find_sibling_domain_enum_imports",
        "find_sibling_domain_id_imports",
        "find_sibling_domain_protocol_imports",
        "iter_aeat_modules",
    }
    assert set(_identity_placement.__all__) == expected


# ---------------------------------------------------------------------------
# Clauses 5-10 (core-authority ADR Rule 11)
# ---------------------------------------------------------------------------


# --- Clause 5: sibling-domain ``_enums`` import ----------------------------


def test_no_sibling_domain_enum_imports() -> None:
    """No ``domain.<a>`` module imports from ``domain.<b>._enums`` for ``a != b``."""

    findings = find_sibling_domain_enum_imports()
    assert findings == [], "sibling-domain _enums imports detected:\n" + _render(findings)


def test_sibling_domain_enum_detector_flags_synthetic_violation(tmp_path: Path) -> None:
    """Anti-tautology proof for clause 5.

    Construct a synthetic ``domain.a`` importing from ``domain.b._enums``,
    confirm the detector fires, then remove the import and confirm it clears.
    """

    root = _seed_synthetic_aeat(tmp_path)
    domain = root / "domain"
    domain.mkdir()
    (domain / "__init__.py").write_text("")
    for name in ("a", "b"):
        sub = domain / name
        sub.mkdir()
        (sub / "__init__.py").write_text("")
    (domain / "b" / "_enums.py").write_text(
        "import enum\n"
        "class ExampleKind(enum.Enum):\n"
        "    X = 'x'\n"
    )
    consumer = domain / "a" / "_consumer.py"
    consumer.write_text("from aeat.domain.b._enums import ExampleKind\n")

    findings = find_sibling_domain_enum_imports(root)
    assert any("ExampleKind" in f.message for f in findings), (
        "sibling-domain enum detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    consumer.write_text("ExampleKind = None\n")
    assert find_sibling_domain_enum_imports(root) == []


# --- Clause 6: sibling-domain ``_constants`` import ------------------------


def test_no_sibling_domain_constant_imports() -> None:
    """No ``domain.<a>`` module imports from ``domain.<b>._constants`` for ``a != b``."""

    findings = find_sibling_domain_constant_imports()
    assert findings == [], "sibling-domain _constants imports detected:\n" + _render(findings)


def test_sibling_domain_constant_detector_flags_synthetic_violation(tmp_path: Path) -> None:
    """Anti-tautology proof for clause 6."""

    root = _seed_synthetic_aeat(tmp_path)
    domain = root / "domain"
    domain.mkdir()
    (domain / "__init__.py").write_text("")
    for name in ("a", "b"):
        sub = domain / name
        sub.mkdir()
        (sub / "__init__.py").write_text("")
    (domain / "b" / "_constants.py").write_text("EXAMPLE_CONST = 'example'\n")
    consumer = domain / "a" / "_consumer.py"
    consumer.write_text("from aeat.domain.b._constants import EXAMPLE_CONST\n")

    findings = find_sibling_domain_constant_imports(root)
    assert any("EXAMPLE_CONST" in f.message for f in findings), (
        "sibling-domain constant detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    consumer.write_text("EXAMPLE_CONST = 'local'\n")
    assert find_sibling_domain_constant_imports(root) == []


# --- Clause 7: sibling-domain ``_protocols`` import ------------------------


def test_no_sibling_domain_protocol_imports() -> None:
    """No ``domain.<a>`` module imports from ``domain.<b>._protocols`` for ``a != b``."""

    findings = find_sibling_domain_protocol_imports()
    assert findings == [], "sibling-domain _protocols imports detected:\n" + _render(findings)


def test_sibling_domain_protocol_detector_flags_synthetic_violation(tmp_path: Path) -> None:
    """Anti-tautology proof for clause 7."""

    root = _seed_synthetic_aeat(tmp_path)
    domain = root / "domain"
    domain.mkdir()
    (domain / "__init__.py").write_text("")
    for name in ("a", "b"):
        sub = domain / name
        sub.mkdir()
        (sub / "__init__.py").write_text("")
    (domain / "b" / "_protocols.py").write_text(
        "from typing import Protocol\n"
        "class ExampleProtocol(Protocol):\n"
        "    def run(self) -> None: ...\n"
    )
    consumer = domain / "a" / "_consumer.py"
    consumer.write_text("from aeat.domain.b._protocols import ExampleProtocol\n")

    findings = find_sibling_domain_protocol_imports(root)
    assert any("ExampleProtocol" in f.message for f in findings), (
        "sibling-domain protocol detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    consumer.write_text("ExampleProtocol = None\n")
    assert find_sibling_domain_protocol_imports(root) == []


# --- Clause 8: private-name cross-package import --------------------------


def test_no_private_name_cross_package_imports() -> None:
    """No production module imports a ``_``-prefixed name from a cross-package module."""

    findings = find_private_name_cross_package_imports()
    assert findings == [], "private-name cross-package imports detected:\n" + _render(findings)


def test_private_name_cross_package_detector_flags_synthetic_violation(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof for clause 8."""

    root = _seed_synthetic_aeat(tmp_path)
    pkg_a = root / "domain" / "a"
    pkg_b = root / "domain" / "b"
    (root / "domain").mkdir()
    (root / "domain" / "__init__.py").write_text("")
    pkg_a.mkdir()
    (pkg_a / "__init__.py").write_text("")
    pkg_b.mkdir()
    (pkg_b / "__init__.py").write_text("")
    (pkg_b / "_utils.py").write_text("def _private_helper() -> None: ...\n")
    consumer = pkg_a / "_consumer.py"
    consumer.write_text("from aeat.domain.b._utils import _private_helper\n")

    findings = find_private_name_cross_package_imports(root)
    assert any("_private_helper" in f.message for f in findings), (
        "private-name cross-package detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    consumer.write_text("from aeat.domain.b._utils import public_helper\n")
    assert find_private_name_cross_package_imports(root) == []


# --- Clause 9 (CLEAR): same-name ``UPPER_SNAKE_CASE`` multi-declaration ---


def test_no_same_name_constant_multi_declarations() -> None:
    """No two production modules declare an ``UPPER_SNAKE_CASE`` constant
    with the same name and the same literal value.
    """

    findings = find_same_name_constant_multi_declarations()
    assert findings == [], (
        "same-name constant multi-declaration detected:\n" + _render(findings)
    )


def test_same_name_constant_detector_flags_synthetic_violation(tmp_path: Path) -> None:
    """Anti-tautology proof for clause 9."""

    root = _seed_synthetic_aeat(tmp_path)
    pkg_a = root / "application" / "a"
    pkg_b = root / "application" / "b"
    (root / "application").mkdir()
    (root / "application" / "__init__.py").write_text("")
    pkg_a.mkdir()
    (pkg_a / "__init__.py").write_text("")
    pkg_b.mkdir()
    (pkg_b / "__init__.py").write_text("")
    (pkg_a / "_constants.py").write_text("SHARED_LIMIT = 100\n")
    (pkg_b / "_constants.py").write_text("SHARED_LIMIT = 100\n")

    findings = find_same_name_constant_multi_declarations(root)
    assert any("SHARED_LIMIT" in f.message for f in findings), (
        "same-name constant detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    # rewrite one to a different name — violation clears
    (pkg_b / "_constants.py").write_text("LOCAL_LIMIT = 100\n")
    assert find_same_name_constant_multi_declarations(root) == []


# --- Clause 10 (BLOCKED): bare-``str`` ``_kind/_status/_state`` field -----
# application/ledger/_models.py has two bare-str review_status fields when
# ReviewStatus (Literal) exists.  Belongs to W12 (bare-str enrollment).


def test_kind_status_state_alias_inventory_discovers_known_aliases(tmp_path: Path) -> None:
    """The clause-10 alias inventory discovers ``Literal`` and ``Annotated[str]``
    aliases for ``Kind``/``Status``/``State``-suffixed names and ignores enum classes.
    """

    root = _seed_synthetic_aeat(tmp_path)
    pkg = root / "domain" / "review"
    pkg.mkdir(parents=True)
    (root / "domain" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "_schema.py").write_text(
        "from typing import Literal\n"
        "ReviewStatus = Literal['pending', 'approved', 'rejected']\n"
        "import enum\n"
        "class ReviewKindEnum(enum.Enum):\n"  # should NOT be inventoried
        "    A = 'a'\n"
    )

    inv = build_kind_status_state_alias_inventory(root)
    assert "review" in inv.aliases_by_owner, (
        f"inventory failed to discover ReviewStatus; got {sorted(inv.aliases_by_owner.keys())!r}"
    )
    assert "review_kind_enum" not in inv.aliases_by_owner, (
        "inventory should not discover enum classes"
    )


def test_bare_str_kind_status_state_detector_flags_synthetic_violation(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof for clause 10."""

    root = _seed_synthetic_aeat(tmp_path)
    pkg = root / "domain" / "review"
    pkg.mkdir(parents=True)
    (root / "domain" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "_schema.py").write_text(
        "from typing import Literal\n"
        "ReviewStatus = Literal['pending', 'approved']\n"
    )
    consumer = pkg / "_models.py"
    consumer.write_text(
        "from pydantic import BaseModel\n"
        "class ReviewRecord(BaseModel):\n"
        "    review_status: str\n"
    )

    inv = build_kind_status_state_alias_inventory(root)
    findings = find_bare_str_kind_status_state_fields(root, inv)
    assert any("ReviewRecord" in f.message for f in findings), (
        "clause-10 detector failed to surface synthetic violation; "
        f"findings={[f.render() for f in findings]!r}"
    )

    # fix: use the typed alias
    consumer.write_text(
        "from pydantic import BaseModel\n"
        "from ._schema import ReviewStatus\n"
        "class ReviewRecord(BaseModel):\n"
        "    review_status: ReviewStatus\n"
    )
    inv2 = build_kind_status_state_alias_inventory(root)
    assert find_bare_str_kind_status_state_fields(root, inv2) == []
