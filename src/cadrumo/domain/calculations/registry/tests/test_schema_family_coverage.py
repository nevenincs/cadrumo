"""Schema-family enrolment and the per-revision coverage manifest.

Two subjects. The enrolment is a property of the schema itself: every collection
a revision declares must be a family, so its emptiness becomes a reported
disposition rather than an absence nobody looks at. The manifest is the
projection that reports them, one row per family, always.

The manifest tests build real :class:`ModeloRevision` objects and the loader
tests drive the real directory loader over real on-disk TOML. A test double
would only prove that the double reports what the test told it to.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import BaseModel, ValidationError

from .....core.schema_family_disposition import (
    RegistrySchemaFamilyDisposition,
    UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS,
)
from .....tests.registry_tree import bundled_registry_tree
from .._schema_family_coverage import (
    RevisionCoverageManifest,
    SchemaFamilyCoverageRow,
    build_revision_coverage_manifest,
)
from ..coverage import REQUIRED_COVERAGE_TIERS
from ..errors import RegistryLoadError
from ..loader import load_modelo_directory
from ..schema import (
    REVISION_COLLECTION_SHAPED_FIELDS,
    REVISION_MANIFEST_ONLY_FIELDS,
    REVISION_SCHEMA_FAMILY_FIELDS,
    ModeloRevision,
)
from ..schema_base import (
    SCHEMA_FAMILY,
    RegistryModel,
    schema_family_enrollment_failures,
)
from ..schema_surfaces import CasillaDefinition
from ._loader_directory_mode_support import _load_revision as _shared_load_revision
from ._loader_directory_mode_support import _write_modelo as _shared_write_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2025"
_LEGAL_REF = "ley-58-2003:art-29"
_MANIFEST_HOME_REFUSAL = "must be declared in the revision's revision.toml"

_CASILLA_FRAGMENT = f"""
[[revisions."{_REVISION_ID}".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["aeat-manual"]
""".lstrip()

_DISPOSITION_TOML = f"""
[revisions."{_REVISION_ID}".family_dispositions.formulas]
reason = "informative modelo computes no amounts"
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["aeat-manual"]
"""


def _write_modelo(root: Path, *, manifest_extra: str = "", fragment_extra: str = "") -> Path:
    return _shared_write_modelo(
        root,
        casilla_fragment=_CASILLA_FRAGMENT,
        revision_id=_REVISION_ID,
        manifest_extra=manifest_extra,
        fragment_extra=fragment_extra,
    )


def _load_revision(modelo_dir: Path) -> ModeloRevision:
    return _shared_load_revision(modelo_dir, revision_id=_REVISION_ID)


def _revision(**overrides: object) -> ModeloRevision:
    """Build a minimal valid revision, overriding whichever fields a test needs."""
    return ModeloRevision.model_validate(
        {
            "id": _REVISION_ID,
            "localization_key": "modelo.schema.999.revision.2025",
            "valid_from": datetime.date(2025, 1, 1),
            "period_selector": {"years": (2025,), "periods": ("0A",)},
            "legal_refs": (_LEGAL_REF,),
            "source_refs": ("aeat-manual",),
            **overrides,
        },
    )


def _row(manifest: RevisionCoverageManifest, family: str) -> SchemaFamilyCoverageRow:
    return next(row for row in manifest.rows if row.family == family)


# --------------------------------------------------------------------------
# Enrolment completeness, and the proof that its check bites
# --------------------------------------------------------------------------


def test_every_collection_the_revision_declares_is_an_enrolled_family() -> None:
    """The live schema satisfies the completeness rule."""
    assert schema_family_enrollment_failures(ModeloRevision) == ()
    assert REVISION_SCHEMA_FAMILY_FIELDS == REVISION_COLLECTION_SHAPED_FIELDS
    assert REVISION_SCHEMA_FAMILY_FIELDS


def test_a_collection_added_without_the_marker_reds_the_enrollment_check() -> None:
    """The planted defect, run through the same function the live gate runs.

    This is the addition case a marker alone cannot catch. A contributor adding
    a collection and forgetting to mark it would otherwise ship a family whose
    emptiness is never reported — invisible in exactly the way an unbuilt family
    must not be.
    """

    class _UnmarkedCollectionRevision(ModeloRevision):
        casilla_annexes: tuple[CasillaDefinition, ...] = ()

    failures = schema_family_enrollment_failures(_UnmarkedCollectionRevision)

    assert len(failures) == 1
    # Keyed on the field and the marker it lacks, not on the sentence joining them.
    # The diagnosis may be reworded; a refusal that stops naming either leaves a
    # reader knowing something is wrong without knowing what to add or where.
    assert "casilla_annexes" in failures[0], "the refusal does not name the unenrolled field"
    assert "SCHEMA_FAMILY" in failures[0], "the refusal does not name the marker the field is missing"


def test_marking_the_same_field_clears_the_enrollment_check() -> None:
    """Anti-tautology: the same field, marked and unmarked, flips the result.

    Without this pairing the refusal above could be firing because the
    derivation reports every field a subclass declares.
    """

    class _MarkedCollectionRevision(ModeloRevision):
        casilla_annexes: Annotated[tuple[CasillaDefinition, ...], SCHEMA_FAMILY] = ()

    assert schema_family_enrollment_failures(_MarkedCollectionRevision) == ()


def test_marking_a_field_that_is_not_a_collection_also_reds() -> None:
    """The opposite direction, which has the opposite fix.

    A marked scalar has no emptiness for a disposition to describe, so it would
    project a row that cannot be honest. Reporting it separately from the
    unmarked-collection case is what tells the author which way to fix it.
    """

    class _MarkedScalarRevision(ModeloRevision):
        annex_note: Annotated[str | None, SCHEMA_FAMILY] = None

    failures = schema_family_enrollment_failures(_MarkedScalarRevision)

    assert len(failures) == 1
    # Same shape: the field, and the structural property it fails, rather than the
    # sentence. A marked scalar is enrolled but uncollectable, and a reader needs
    # both halves to know the fix is the shape and not the marker.
    assert "annex_note" in failures[0], "the refusal does not name the offending field"
    assert "collection" in failures[0], (
        "the refusal no longer says the field fails because it is not a collection, so a reader "
        "cannot tell an enrolment problem from a shape problem"
    )


def test_family_enrolment_and_manifest_placement_are_disjoint_concepts() -> None:
    """Two markers, two questions, and no field is subject to both.

    Placement asks where a field may be written; enrolment asks whether its
    emptiness is a coverage claim. The sets being disjoint on the live schema is
    what shows the deliberate absence of a marker hierarchy is right rather than
    merely untested.
    """
    assert not (REVISION_SCHEMA_FAMILY_FIELDS & REVISION_MANIFEST_ONLY_FIELDS)


# --------------------------------------------------------------------------
# The manifest projection
# --------------------------------------------------------------------------


def test_the_manifest_reports_every_enrolled_family_exactly_once() -> None:
    """Exhaustive by construction, on a revision that declares almost nothing."""
    manifest = build_revision_coverage_manifest(modelo="999", revision=_revision())

    assert {row.family for row in manifest.rows} == REVISION_SCHEMA_FAMILY_FIELDS
    assert len(manifest.rows) == len(REVISION_SCHEMA_FAMILY_FIELDS)


def test_an_empty_undeclared_family_is_blocked_pending_evidence() -> None:
    """The fail-closed default, and the whole point of the vocabulary.

    An empty family nobody has explained is a visible worklist entry, never a
    silent pass — the distinction between 'this modelo computes nothing' and
    'nobody built the formulas yet'.
    """
    manifest = build_revision_coverage_manifest(modelo="999", revision=_revision())
    row = _row(manifest, "formulas")

    assert row.disposition is RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE
    assert row.populated_count == 0
    assert row.reason is None
    assert row in manifest.unresolved
    assert not manifest.fully_resolved


def test_a_family_holding_content_is_populated_with_its_count(tmp_path: Path) -> None:
    """Built through the real loader, so the counted members are real compiled ones."""
    revision = _load_revision(_write_modelo(tmp_path))
    row = _row(build_revision_coverage_manifest(modelo="999", revision=revision), "casillas")

    assert row.disposition is RegistrySchemaFamilyDisposition.POPULATED
    assert row.populated_count == len(revision.casillas) == 1
    assert row.reason is None


def test_a_declared_inapplicable_family_carries_its_reason_and_refs() -> None:
    """The only exit from the blocked default, and it costs a cited claim."""
    revision = _revision(
        family_dispositions={
            "formulas": {
                "reason": "informative modelo computes no amounts",
                "legal_refs": (_LEGAL_REF,),
                "source_refs": ("aeat-manual",),
            },
        },
    )
    row = _row(build_revision_coverage_manifest(modelo="999", revision=revision), "formulas")

    assert row.disposition is RegistrySchemaFamilyDisposition.NOT_APPLICABLE
    assert row.populated_count == 0
    assert row.reason == "informative modelo computes no amounts"
    assert row.legal_refs == (_LEGAL_REF,)
    assert row.source_refs == ("aeat-manual",)
    assert row not in build_revision_coverage_manifest(modelo="999", revision=revision).unresolved


def test_unresolved_is_read_from_the_shared_set_not_a_local_equality() -> None:
    """The consumer's question is membership, so a future member enrols itself."""
    manifest = build_revision_coverage_manifest(modelo="999", revision=_revision())

    assert all(row.disposition in UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS for row in manifest.unresolved)
    assert RegistrySchemaFamilyDisposition.POPULATED not in UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS
    assert RegistrySchemaFamilyDisposition.NOT_APPLICABLE not in UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS


# --------------------------------------------------------------------------
# The row and manifest refuse their own incoherent shapes
# --------------------------------------------------------------------------


def test_a_populated_row_reporting_no_members_is_refused() -> None:
    with pytest.raises(ValidationError, match="populated but reports no members"):
        SchemaFamilyCoverageRow(
            family="formulas",
            disposition=RegistrySchemaFamilyDisposition.POPULATED,
            populated_count=0,
        )


def test_an_unpopulated_row_reporting_members_is_refused() -> None:
    with pytest.raises(ValidationError, match="but is not populated"):
        SchemaFamilyCoverageRow(
            family="formulas",
            disposition=RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE,
            populated_count=3,
        )


def test_a_not_applicable_row_without_a_cited_reason_is_refused() -> None:
    """The claim is only worth more than an allowlist entry if it is backed."""
    with pytest.raises(ValidationError, match="requires a reason"):
        SchemaFamilyCoverageRow(
            family="formulas",
            disposition=RegistrySchemaFamilyDisposition.NOT_APPLICABLE,
            populated_count=0,
            reason="because",
        )


def test_a_blocked_row_carrying_refs_is_refused() -> None:
    """Refs on a blocked row would be a not-applicable claim wearing no name."""
    with pytest.raises(ValidationError, match="cannot carry a reason or refs"):
        SchemaFamilyCoverageRow(
            family="formulas",
            disposition=RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE,
            populated_count=0,
            legal_refs=(_LEGAL_REF,),
        )


def test_a_manifest_missing_a_family_is_refused() -> None:
    """Exhaustiveness is a property of the type, not of the builder."""
    full = build_revision_coverage_manifest(modelo="999", revision=_revision())

    with pytest.raises(ValidationError, match="exactly once"):
        RevisionCoverageManifest(modelo="999", revision=_REVISION_ID, rows=full.rows[1:])


def test_a_manifest_reporting_a_family_twice_is_refused() -> None:
    full = build_revision_coverage_manifest(modelo="999", revision=_revision())

    with pytest.raises(ValidationError, match="more than once"):
        RevisionCoverageManifest(modelo="999", revision=_REVISION_ID, rows=(*full.rows, full.rows[0]))


# --------------------------------------------------------------------------
# The declaration surface, through the real loader
# --------------------------------------------------------------------------


def test_a_disposition_for_an_unknown_family_is_refused() -> None:
    """A typo would resolve nothing while reading as though it resolved something."""
    with pytest.raises(ValidationError, match="is not a schema family"):
        _revision(
            family_dispositions={
                "formulae": {
                    "reason": "typo",
                    "legal_refs": (_LEGAL_REF,),
                    "source_refs": ("aeat-manual",),
                },
            },
        )


def test_a_disposition_against_a_populated_family_is_refused(tmp_path: Path) -> None:
    """Claiming the law does not require what the revision already declares.

    Driven through the loader because the contradiction only becomes reachable
    once a fragment has populated the family the manifest disclaims — which is
    exactly the shape a real authoring mistake takes.
    """
    conflicting = f"""
[revisions."{_REVISION_ID}".family_dispositions.casillas]
reason = "no casillas apply"
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["aeat-manual"]
"""
    with pytest.raises(RegistryLoadError, match="not applicable but also declares"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra=conflicting))


def test_a_disposition_declared_in_the_manifest_hydrates_through_the_loader(tmp_path: Path) -> None:
    """Real on-disk TOML, real loader, real typed declaration."""
    revision = _load_revision(_write_modelo(tmp_path, manifest_extra=_DISPOSITION_TOML))
    row = _row(build_revision_coverage_manifest(modelo="999", revision=revision), "formulas")

    assert row.disposition is RegistrySchemaFamilyDisposition.NOT_APPLICABLE
    assert row.reason == "informative modelo computes no amounts"


def test_a_disposition_declared_in_a_fragment_is_refused(tmp_path: Path) -> None:
    """Differential proof: identical text, manifest passes, fragment fails.

    An inapplicability claim lowers what a grade requires of the revision, so a
    fragment thousands deep supplying one is the same laundering hazard the
    manifest-only pin exists for — and the pairing is what shows the refusal is
    about placement rather than a malformed declaration.
    """
    accepted = _load_revision(_write_modelo(tmp_path / "manifest-home", manifest_extra=_DISPOSITION_TOML))
    assert "formulas" in accepted.family_dispositions

    with pytest.raises(RegistryLoadError, match=re.escape(_MANIFEST_HOME_REFUSAL)):
        load_modelo_directory(_write_modelo(tmp_path / "fragment-home", fragment_extra=_DISPOSITION_TOML))


# --------------------------------------------------------------------------
# The axis is not the evidence-tier axis
# --------------------------------------------------------------------------


def test_the_family_vocabulary_does_not_overlap_the_evidence_tier_vocabulary() -> None:
    """Three axes that all sound like completeness must not share a word.

    A shared token would be read as a shared meaning, and the whole reason the
    family axis exists is that a populated family with no legal authority and an
    empty family with impeccable authority are different findings.
    """
    dispositions = {member.value for member in RegistrySchemaFamilyDisposition}

    assert not (dispositions & set(REQUIRED_COVERAGE_TIERS))


def test_every_bundled_revision_projects_a_coherent_manifest() -> None:
    """The gate that gives this projection an executor over real data.

    The coverage module is imported by every registry load and executed by
    almost nothing, so a projection added here with no caller would inherit that
    invisibility. Running it across the whole corpus is what makes a regression
    in it observable.
    """
    modelos, _catalogues = bundled_registry_tree()
    revisions = [(modelo.id, revision) for modelo in modelos for revision in modelo.revisions.values()]

    assert revisions, "the bundled registry must load at least one revision"
    for modelo_id, revision in revisions:
        manifest = build_revision_coverage_manifest(modelo=modelo_id, revision=revision)
        assert {row.family for row in manifest.rows} == REVISION_SCHEMA_FAMILY_FIELDS
        for row in manifest.rows:
            assert (row.populated_count > 0) is (row.disposition is RegistrySchemaFamilyDisposition.POPULATED)


def test_the_family_models_are_registry_models_under_the_strict_config() -> None:
    """The declaration rides the same strict frozen base as the rest of the schema."""
    from ..schema import SchemaFamilyDispositionDeclaration

    assert issubclass(SchemaFamilyDispositionDeclaration, RegistryModel)
    assert issubclass(SchemaFamilyDispositionDeclaration, BaseModel)
