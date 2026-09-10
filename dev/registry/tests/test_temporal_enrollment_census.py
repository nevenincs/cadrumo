"""Mutation proofs for yearless in-file temporal enrolment detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from dev.registry.compiler.authority import compiled_bundled_authority

from ..analysis.temporal_enrollment_census import (
    LiteralEnrollmentAudit,
    RegistryRevisionSubject,
    TemporalEnrollmentExclusionPin,
    audit_registry_test_enrollment_literals,
    audit_temporal_enrollment_source,
    law_selectable_revision_subjects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PATH = "dev/registry/tests/yearless_fixture.py"
_EXPECTED = frozenset(
    {
        RegistryRevisionSubject("390", "2022"),
        RegistryRevisionSubject("390", "2023"),
        RegistryRevisionSubject("390", "2024"),
    }
)


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def _audit(
    rows: str,
    authority: ValidatedRegistryAuthority,
    *,
    pins: tuple[TemporalEnrollmentExclusionPin, ...] = (),
) -> LiteralEnrollmentAudit:
    source = f"_GENERATED_TREES = (\n{rows}\n)\n"
    return audit_temporal_enrollment_source(
        source,
        path=_PATH,
        expected=_EXPECTED,
        authority=authority,
        pins=pins,
    )


def test_live_registry_tests_have_no_unaccounted_literal_revision_enrollment(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A yearless literal list cannot silently replace the derived denominator."""
    assert law_selectable_revision_subjects(authority), "the law-selectable denominator is empty"
    audit = audit_registry_test_enrollment_literals(authority)

    assert audit.clean, "\n".join(finding.detail for finding in audit.findings)


def test_yearless_constructor_collection_is_detected_without_filename_help(
    authority: ValidatedRegistryAuthority,
) -> None:
    audit = _audit(
        '    _GeneratedTree("390", "2022"),\n    _GeneratedTree("390", "2023"),\n    _GeneratedTree("390", "2024"),',
        authority,
    )

    assert audit.clean
    assert tuple(declaration.symbol for declaration in audit.declarations) == ("_GENERATED_TREES",)
    assert audit.declarations[0].subjects == tuple(sorted(_EXPECTED))


def test_removed_pair_reports_the_exact_missing_identity(authority: ValidatedRegistryAuthority) -> None:
    audit = _audit(
        '    _GeneratedTree("390", "2022"),\n    _GeneratedTree("390", "2024"),',
        authority,
    )

    assert len(audit.findings) == 1
    assert audit.findings[0].missing == (RegistryRevisionSubject("390", "2023"),)
    assert audit.findings[0].extra == ()


def test_altered_pair_reports_exact_missing_and_extra_identities(authority: ValidatedRegistryAuthority) -> None:
    audit = _audit(
        '    _GeneratedTree("390", "2022"),\n    _GeneratedTree("390", "2099"),\n    _GeneratedTree("390", "2024"),',
        authority,
    )

    assert len(audit.findings) == 1
    assert audit.findings[0].missing == (RegistryRevisionSubject("390", "2023"),)
    assert audit.findings[0].extra == (RegistryRevisionSubject("390", "2099"),)


def test_imported_enrollment_is_not_counted_as_a_second_literal_declaration(
    authority: ValidatedRegistryAuthority,
) -> None:
    source = "from sibling import GENERATED_TREES as _GENERATED_TREES\n_REEXPORTED_TREES = _GENERATED_TREES\n"

    audit = audit_temporal_enrollment_source(
        source,
        path=_PATH,
        expected=_EXPECTED,
        authority=authority,
    )

    assert audit.declarations == ()
    assert audit.findings == ()


def test_exclusion_pin_goes_dormant_when_its_source_is_reissued(
    authority: ValidatedRegistryAuthority,
) -> None:
    source = authority.catalogues.sources["aeat-dr-390-2023"]
    pin = TemporalEnrollmentExclusionPin(
        path=_PATH,
        symbol="_GENERATED_TREES",
        modelo="390",
        revision="2023",
        source_ref="aeat-dr-390-2023",
        source_sha256=source.sha256,
        reason="The isolated fixture deliberately withholds this subject.",
        reconsideration_condition="Re-enrol when the pinned design is reissued.",
    )
    rows = '    _GeneratedTree("390", "2022"),\n    _GeneratedTree("390", "2024"),'

    assert _audit(rows, authority, pins=(pin,)).clean

    reissued = pin.model_copy(update={"source_sha256": "0" * 64})
    dormant = _audit(rows, authority, pins=(reissued,))
    assert dormant.findings[0].missing == (RegistryRevisionSubject("390", "2023"),)
    assert dormant.findings[0].dormant_pins == (RegistryRevisionSubject("390", "2023"),)


def test_pin_cannot_survive_after_its_literal_declaration_is_removed(
    tmp_path: Path,
    authority: ValidatedRegistryAuthority,
) -> None:
    source = authority.catalogues.sources["aeat-dr-390-2023"]
    pin = TemporalEnrollmentExclusionPin(
        path=(tmp_path / "removed.py").as_posix(),
        symbol="_GENERATED_TREES",
        modelo="390",
        revision="2023",
        source_ref="aeat-dr-390-2023",
        source_sha256=source.sha256,
        reason="The declaration used to omit this subject.",
        reconsideration_condition="Remove this pin with its declaration.",
    )
    (tmp_path / "removed.py").write_text("VALUE = 1\n", encoding="utf-8")

    audit = audit_registry_test_enrollment_literals(authority, root=tmp_path, pins=(pin,))

    assert not audit.clean
    assert audit.findings[0].unnecessary_pins == (RegistryRevisionSubject("390", "2023"),)


def test_scanner_accepts_an_isolated_test_root_without_import_double_counting(
    tmp_path: Path,
    authority: ValidatedRegistryAuthority,
) -> None:
    (tmp_path / "literal.py").write_text(
        '_ROWS = (("390", "2022"), ("390", "2023"), ("390", "2024"))\n',
        encoding="utf-8",
    )
    (tmp_path / "consumer.py").write_text(
        "from .literal import _ROWS\n",
        encoding="utf-8",
    )

    audit = audit_registry_test_enrollment_literals(authority, root=tmp_path)

    assert len(audit.declarations) == 1
