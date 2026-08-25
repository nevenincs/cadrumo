"""Loader and schema behaviour for a revision's declared authority grade.

The grade is a claim about how far one revision's authority reaches, and three
properties have to hold before anything downstream can rely on it: the token
hydrates into the typed member at the loader boundary rather than surviving as a
string, an undeclared grade reads as the fail-closed floor rather than as
whatever the reader assumes, and the declaration is refused anywhere but the
revision's own ``revision.toml``.

Every test here drives the real directory loader over a real on-disk TOML tree,
and the bundled-corpus tests read the shipped registry. The subjects are where a
value may be WRITTEN and what the loader produces from it, so a test double
anywhere in this module would verify the double rather than the loader.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from .....core import UNDECLARED_REGISTRY_AUTHORITY_GRADE, RegistryAuthorityGrade
from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ..errors import RegistryLoadError
from ..loader import load_modelo_directory
from ..schema import (
    REVISION_GOVERNANCE_FIELDS,
    REVISION_MANIFEST_ONLY_FIELDS,
    ModeloRevision,
)
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


@pytest.mark.parametrize("grade", list(RegistryAuthorityGrade))
def test_a_declared_grade_hydrates_into_the_typed_member(tmp_path: Path, grade: RegistryAuthorityGrade) -> None:
    """Registry TOML stays free-form; the loader boundary produces the enum member.

    Parametrized over the enum itself, so a grade added to the vocabulary is
    covered by this hydration proof the moment its member lands.
    """
    revision = _load_revision(
        _write_modelo(tmp_path / grade.value, manifest_extra=f'authority_grade = "{grade.value}"\n'),
    )

    assert revision.authority_grade is grade
    assert revision.effective_authority_grade is grade
    assert revision.is_graded


def test_an_unknown_grade_token_is_refused_at_load(tmp_path: Path) -> None:
    """The vocabulary is closed at load time, not at a later branch on the string."""
    with pytest.raises(RegistryLoadError, match="RegistryAuthorityGrade"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra='authority_grade = "filing_ready"\n'))


def test_an_undeclared_grade_reads_as_the_fail_closed_floor(tmp_path: Path) -> None:
    """Absence confers scheduling reach and nothing more.

    Reading absence as the LOWEST rung is what makes the optional field safe to
    land: were it read as anything higher, an ungraded corpus would present
    every revision as authority it has never been checked to hold.
    """
    revision = _load_revision(_write_modelo(tmp_path))

    assert revision.authority_grade is None
    assert not revision.is_graded
    assert revision.effective_authority_grade is UNDECLARED_REGISTRY_AUTHORITY_GRADE
    assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY


def test_an_undeclared_grade_stays_distinguishable_from_one_declared_at_the_floor(tmp_path: Path) -> None:
    """The two agree on reach and disagree on whether anyone made the claim.

    Collapsing them — by defaulting the field to the floor instead of leaving it
    optional — would make the corpus-completeness question unanswerable: every
    revision would read as explicitly graded the day the field landed.
    """
    undeclared = _load_revision(_write_modelo(tmp_path / "undeclared"))
    declared = _load_revision(
        _write_modelo(tmp_path / "declared", manifest_extra='authority_grade = "applicability"\n'),
    )

    assert undeclared.effective_authority_grade is declared.effective_authority_grade
    assert not undeclared.is_graded
    assert declared.is_graded


def test_a_fragment_declared_grade_is_refused_and_the_same_text_passes_in_the_manifest(tmp_path: Path) -> None:
    """Differential proof that the refusal is about placement, not content.

    A revision compiles from its manifest plus up to several hundred fragments,
    and the merge takes a scalar from whichever file declares it. Without the
    refusal, a fragment thousands deep could grade the revision filing-grade
    while ``revision.toml`` read as though nobody had graded it at all. Pairing
    the refusal with an accepted manifest declaration of the IDENTICAL text is
    what proves the gate refuses the placement rather than a malformed value.
    """
    accepted = _load_revision(
        _write_modelo(tmp_path / "manifest-home", manifest_extra='authority_grade = "filing"\n'),
    )
    assert accepted.authority_grade is RegistryAuthorityGrade.FILING

    with pytest.raises(RegistryLoadError, match=re.escape(_MANIFEST_HOME_REFUSAL)):
        load_modelo_directory(
            _write_modelo(
                tmp_path / "fragment-home",
                fragment_extra=f'\n[revisions."{_REVISION_ID}"]\nauthority_grade = "filing"\n',
            ),
        )


def test_the_placement_refusal_names_the_manifest_rather_than_another_fragment_folder(tmp_path: Path) -> None:
    """The instructive refusal must win over the broader owned-section refusal.

    A section fragment folder may declare only its own section, so a foreign key
    is refused twice over. If the broader refusal ran first it would tell the
    author to find a different fragment folder for a field whose only legal home
    is ``revision.toml`` — a correct refusal carrying a wrong instruction.
    """
    with pytest.raises(RegistryLoadError) as refusal:
        load_modelo_directory(
            _write_modelo(
                tmp_path,
                fragment_extra=f'\n[revisions."{_REVISION_ID}"]\nauthority_grade = "filing"\n',
            ),
        )

    assert _MANIFEST_HOME_REFUSAL in str(refusal.value)
    assert "may declare only its owned section" not in str(refusal.value)


def test_a_planted_grade_reds_a_copy_of_a_real_shipped_revision(tmp_path: Path) -> None:
    """The gate bites on a real corpus revision, not only on a synthetic fixture.

    An anti-tautology proof over a hand-built fixture is necessary but not
    sufficient: it cannot catch a refusal that is correct on synthetic input and
    never reaches the shapes the shipped tree actually uses. This copies a real
    bundled fragmented modelo, plants the grade in a real section fragment,
    observes the refusal, removes the plant, and confirms the copy loads again.
    """
    source_modelo = _first_bundled_fragmented_modelo()
    modelo_dir = tmp_path / source_modelo.name
    shutil.copytree(source_modelo, modelo_dir)
    fragment = _first_section_fragment(modelo_dir)
    original_text = fragment.read_text(encoding="utf-8")
    revision_id = fragment.parents[1].name

    # The baseline is whatever the copied modelo's MANIFEST declares, read rather
    # than assumed absent. This asserted `is None`, true while nothing carried the
    # field and false once the corpus was graded -- and the grade it then saw was
    # declared in the manifest, its correct home, so the assertion failed on a
    # premise rather than on the property this test is named for.
    baseline = load_modelo_directory(modelo_dir).revisions[revision_id].authority_grade

    fragment.write_text(
        f'{original_text}\n[revisions."{revision_id}"]\nauthority_grade = "filing"\n',
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match=re.escape(_MANIFEST_HOME_REFUSAL)):
        load_modelo_directory(modelo_dir)

    fragment.write_text(original_text, encoding="utf-8")
    restored = load_modelo_directory(modelo_dir).revisions[revision_id].authority_grade
    assert restored == baseline, "removing the plant must restore the manifest's own declaration"
    # The refusal above plus this equality are the whole property: the planted
    # "filing" must never merge in, so the reload has to match the manifest's own
    # declaration exactly.


def _first_bundled_fragmented_modelo() -> Path:
    """Return the first bundled modelo directory carrying a fragmented revision."""
    modelos_dir = bundled_path("registry", "aeat") / "modelos"
    for candidate in scan_directory(modelos_dir, select=DirectoryEntryKind.DIRECTORIES):
        if any((candidate / "revisions").glob("*/revision.toml")):
            return candidate
    raise AssertionError(f"no bundled modelo under {modelos_dir} uses the fragmented revision layout")


def _first_section_fragment(modelo_dir: Path) -> Path:
    """Return the first per-section fragment file of the first fragmented revision."""
    for manifest in sorted((modelo_dir / "revisions").glob("*/revision.toml")):
        fragments = sorted(manifest.parent.glob("*/*.toml"))
        if fragments:
            return fragments[0]
    raise AssertionError(f"no fragmented revision under {modelo_dir} carries a section fragment")


def test_the_grade_enrols_into_placement_without_joining_the_governance_stamp() -> None:
    """Two subjects, two vocabularies: the grade is not a review attestation.

    The grade shares the stamp's manifest-only placement guarantee and nothing
    else. Were it enrolled in the stamp vocabulary, the conformance stamp writer
    would read and emit it as declared review provenance — turning an authority
    claim into an attestation about a person, which no program may write.
    """
    assert "authority_grade" in REVISION_MANIFEST_ONLY_FIELDS
    assert "authority_grade" not in REVISION_GOVERNANCE_FIELDS
    assert "authority_grade" in ModeloRevision.model_fields


def test_the_shipped_corpus_loads_and_every_revision_reads_a_valid_reach() -> None:
    """The optional field must describe the shipped tree, not break it.

    A required grade could not have landed here: it would refuse every bundled
    manifest at once. The proof is that the untouched corpus still loads and
    that every revision resolves a reach — declared where declared, the floor
    where not. Asserted as a property over whatever the corpus holds rather than
    against a revision tally, which would encode today's corpus and detect
    nothing tomorrow.
    """
    modelos, _catalogues = bundled_registry_tree()
    revisions = [revision for modelo in modelos for revision in modelo.revisions.values()]

    assert revisions, "the bundled registry must load at least one revision"
    for revision in revisions:
        reach = revision.effective_authority_grade
        assert reach in RegistryAuthorityGrade
        if revision.authority_grade is None:
            assert reach is UNDECLARED_REGISTRY_AUTHORITY_GRADE
        else:
            assert reach is revision.authority_grade
