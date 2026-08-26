"""Loader behaviour for the revision scalars pinned to ``revision.toml``.

A revision compiles from its own manifest plus up to several hundred per-section
fragment files, and the merge takes a scalar from whichever file declares it. For
a legally load-bearing scalar that is a readability hazard with real stakes: the
approving orden, the legal grounding and the validity end date can be declared
thousands of files deep while ``revision.toml`` reads as though they were never
declared at all.

Every test here drives the real directory loader over a real on-disk TOML tree.
The subject is where a value may be WRITTEN, so a test double anywhere in this
module would verify the double rather than the placement.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import pytest

import cadrumo.domain.calculations.registry.loader as _loader

from .....tests.registry_tree import bundled_registry_tree
from ..errors import RegistryLoadError
from ..loader import load_modelo_directory
from ..schema import (
    REVISION_GOVERNANCE_FIELDS,
    REVISION_MANIFEST_ONLY_FIELDS,
    ModeloRevision,
)
from ..schema_base import (
    GOVERNANCE_STAMP,
    MANIFEST_ONLY,
    GovernanceStampMarker,
    ManifestOnlyMarker,
    governance_stamp_fields,
    manifest_only_fields,
)
from ._loader_directory_mode_support import _load_revision as _shared_load_revision
from ._loader_directory_mode_support import _standard_revision_preamble_text
from ._loader_directory_mode_support import _write_modelo as _shared_write_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2025"
_ORDEN_REF = "orden-hac-277-2026:art-3"
_OTHER_ORDEN_REF = "orden-hfp-1000-2025:art-1"
_LEGAL_REF = "ley-58-2003:art-29"

#: A TOML literal for each manifest-only scalar, so the parametrized refusal
#: can write a well-formed value for whichever field the marker enrols.
_FIELD_LITERALS: dict[str, str] = {
    "authority_grade": '"calculation"',
    "legal_refs": f'["{_LEGAL_REF}"]',
    "orden_aplicabilidad": f'["{_ORDEN_REF}"]',
    "valid_to": "2025-12-31",
    "engineered_by": '"registry schema campaign"',
    "review_status": '"pending_review"',
    "reviewed_by": '"operator"',
    "reviewed_at": "2026-07-27",
    # An inline table, because this field is a Mapping of declarations rather
    # than a scalar: the refusal must fire on WHERE the field is declared, so the
    # value has to be well-formed enough to reach the placement check.
    "family_dispositions": (
        '{ casilla_continuidad_evolutions = { reason = "declared for the placement refusal", '
        f'legal_refs = ["{_LEGAL_REF}"], source_refs = ["aeat-manual"] }} }}'
    ),
}

_CASILLA_FRAGMENT = f"""
[[revisions."{_REVISION_ID}".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["aeat-manual"]
""".lstrip()


def _revision_manifest_text(*, declare_legal_refs: bool = True, extra: str = "") -> str:
    """Build a ``revision.toml`` scalar manifest, optionally omitting ``legal_refs``.

    The omission matters: the pre-existing redeclaration guard only fires when
    the manifest already carries the field, so a manifest that never mentions
    its legal grounding is exactly the shape a fragment could have supplied it
    for, unchallenged.
    """
    return _standard_revision_preamble_text(declare_legal_refs=declare_legal_refs) + extra


def _write_modelo(
    root: Path,
    *,
    manifest_text: str | None = None,
    fragment_extra: str = "",
) -> Path:
    return _shared_write_modelo(
        root,
        casilla_fragment=_CASILLA_FRAGMENT,
        revision_id=_REVISION_ID,
        manifest_text=manifest_text,
        fragment_extra=fragment_extra,
    )


def _load_revision(modelo_dir: Path) -> ModeloRevision:
    return _shared_load_revision(modelo_dir, revision_id=_REVISION_ID)


def _fragment_declaring(field_name: str, literal: str) -> str:
    return f'\n[revisions."{_REVISION_ID}"]\n{field_name} = {literal}\n'


@pytest.mark.parametrize("field_name", sorted(REVISION_MANIFEST_ONLY_FIELDS))
def test_a_manifest_only_field_declared_in_a_section_fragment_is_refused(tmp_path: Path, field_name: str) -> None:
    """Every marked scalar is refused in a fragment, whichever marker enrolled it.

    Parametrized over the DERIVED set rather than a written-out list, so a field
    marked tomorrow is covered by this gate the moment its marker lands.
    """
    assert field_name in _FIELD_LITERALS, f"{field_name} is marked manifest-only but has no literal here"
    fragment_extra = _fragment_declaring(field_name, _FIELD_LITERALS[field_name])

    with pytest.raises(RegistryLoadError, match=re.escape("must be declared in the revision's revision.toml")):
        load_modelo_directory(_write_modelo(tmp_path, fragment_extra=fragment_extra))


def test_the_refusal_is_about_placement_not_content(tmp_path: Path) -> None:
    """Differential proof: identical ``valid_to`` text, manifest passes, fragment fails.

    Without this pairing the refusal above could be passing because the value is
    malformed rather than misplaced.
    """
    accepted = _load_revision(
        _write_modelo(
            tmp_path / "manifest-home", manifest_text=_revision_manifest_text(extra="valid_to = 2025-12-31\n")
        ),
    )
    assert accepted.valid_to is not None
    assert accepted.valid_to.isoformat() == "2025-12-31"

    with pytest.raises(RegistryLoadError, match=re.escape("must be declared in the revision's revision.toml")):
        load_modelo_directory(
            _write_modelo(tmp_path / "fragment-home", fragment_extra=_fragment_declaring("valid_to", "2025-12-31")),
        )


def test_a_fragment_cannot_append_a_second_approving_orden(tmp_path: Path) -> None:
    """The append-array case, which no redeclaration guard could ever have caught.

    ``orden_aplicabilidad`` merges by APPENDING, so before this refusal a
    fragment adding an orden did not collide with the manifest's - it silently
    extended the set of ministerial ordenes the revision claims approve its
    form, while ``revision.toml`` still named only one.
    """
    control = _load_revision(
        _write_modelo(
            tmp_path / "manifest-home",
            manifest_text=_revision_manifest_text(extra=f'orden_aplicabilidad = ["{_ORDEN_REF}"]\n'),
        ),
    )
    assert control.orden_aplicabilidad == (_ORDEN_REF,)

    with pytest.raises(RegistryLoadError, match=re.escape("must be declared in the revision's revision.toml")):
        load_modelo_directory(
            _write_modelo(
                tmp_path / "fragment-home",
                manifest_text=_revision_manifest_text(extra=f'orden_aplicabilidad = ["{_ORDEN_REF}"]\n'),
                fragment_extra=_fragment_declaring("orden_aplicabilidad", f'["{_OTHER_ORDEN_REF}"]'),
            ),
        )


def test_a_fragment_cannot_supply_legal_grounding_the_manifest_never_declares(tmp_path: Path) -> None:
    """The omission case, the other shape the redeclaration guard cannot see.

    A manifest silent on ``legal_refs`` collides with nothing, so a fragment
    could hand the revision its entire legal grounding and the manifest would
    still read as though the revision cited no law at all.
    """
    control = _load_revision(_write_modelo(tmp_path / "manifest-home"))
    assert control.legal_refs == (_LEGAL_REF,)

    with pytest.raises(RegistryLoadError, match=re.escape("must be declared in the revision's revision.toml")):
        load_modelo_directory(
            _write_modelo(
                tmp_path / "fragment-home",
                manifest_text=_revision_manifest_text(declare_legal_refs=False),
                fragment_extra=_fragment_declaring("legal_refs", f'["{_LEGAL_REF}"]'),
            ),
        )


def test_the_governance_stamp_is_manifest_only_by_type_not_by_a_second_marker() -> None:
    """The two subjects stay distinct; the placement guarantee is shared by construction.

    Governance provenance and legal grounding are different claims, so they are
    different markers. If they were siblings, a governance field added tomorrow
    would need BOTH markers to keep its placement guarantee, and forgetting the
    second is the same failure the derived set exists to remove. Making the
    governance marker a subclass means it cannot be forgotten.
    """
    assert issubclass(GovernanceStampMarker, ManifestOnlyMarker)
    assert isinstance(GOVERNANCE_STAMP, ManifestOnlyMarker)
    assert not isinstance(MANIFEST_ONLY, GovernanceStampMarker)
    assert REVISION_MANIFEST_ONLY_FIELDS > REVISION_GOVERNANCE_FIELDS


def test_the_manifest_only_set_is_exactly_todays_marked_fields() -> None:
    """Pin the derived set, so a marker lost in a rebase is a red test."""
    expected = REVISION_GOVERNANCE_FIELDS | {
        "authority_grade",
        "family_dispositions",
        "legal_refs",
        "orden_aplicabilidad",
        "valid_to",
    }

    assert expected == REVISION_MANIFEST_ONLY_FIELDS
    assert set(ModeloRevision.model_fields) >= REVISION_MANIFEST_ONLY_FIELDS


def test_the_placement_refusal_reads_the_derived_set_itself() -> None:
    """The loader gate and the declarations must be one set, not two.

    Deriving the set is worthless if the loader consults a second copy, so this
    pins the gate's input to the object the declarations produce.
    """
    assert _loader.REVISION_MANIFEST_ONLY_FIELDS is REVISION_MANIFEST_ONLY_FIELDS


def test_a_newly_marked_field_enrols_itself_into_the_right_set() -> None:
    """The addition case, and the separation of the two subjects in one proof.

    A field marked manifest-only enrols into the placement set without joining
    the governance stamp vocabulary; a field marked governance joins both; an
    unmarked sibling joins neither. Enrolment tracks the marker rather than
    counting whatever a subclass happens to declare.
    """

    class _ExtendedRevision(ModeloRevision):
        superseded_on: Annotated[str | None, MANIFEST_ONLY] = None
        countersigned_by: Annotated[str | None, GOVERNANCE_STAMP] = None
        internal_note: str | None = None

    placement = manifest_only_fields(_ExtendedRevision)
    stamp = governance_stamp_fields(_ExtendedRevision)

    assert placement == REVISION_MANIFEST_ONLY_FIELDS | {"superseded_on", "countersigned_by"}
    assert stamp == REVISION_GOVERNANCE_FIELDS | {"countersigned_by"}
    assert "superseded_on" not in stamp
    assert "internal_note" not in placement
    assert "internal_note" not in stamp


def test_dropping_the_marker_drops_the_field_from_the_gate() -> None:
    """Anti-tautology: the same field, marked and unmarked, flips the assertion.

    Without this pairing the enrolment proof above could be passing because the
    derivation returns every field a subclass declares.
    """

    class _MarkedRevision(ModeloRevision):
        superseded_on: Annotated[str | None, MANIFEST_ONLY] = None

    class _UnmarkedRevision(ModeloRevision):
        superseded_on: str | None = None

    assert "superseded_on" in manifest_only_fields(_MarkedRevision)
    assert "superseded_on" not in manifest_only_fields(_UnmarkedRevision)


def test_the_shipped_registry_still_loads_under_the_widened_refusal() -> None:
    """The refusal must describe the shipped tree, not break it.

    A placement rule no bundled revision satisfies would take the whole product
    with it, so the tightening is only legitimate if every shipped revision
    already declares these scalars in its own manifest.
    """
    modelos, _catalogues = bundled_registry_tree()
    revisions = [revision for modelo in modelos for revision in modelo.revisions.values()]

    assert revisions, "the bundled registry must load at least one revision"
    assert all(revision.legal_refs for revision in revisions)
