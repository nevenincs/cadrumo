"""A design's hand-authored annotation reaches it from whichever root ships it.

THE DEFECT THIS EXISTS FOR. The corpus is split across distributions by file
SUFFIX, not by directory: the design workbooks and PDFs are shed from the
command-bearing wheel and ship in the ``cadrumo_data`` companions, while the
derived text and the hand-authored declarations that annotate them stay behind.
In a source checkout the two sit in one directory and a sibling read finds the
annotation. After an install they sit under two different package roots, and a
sibling read finds nothing.

Nothing said so. ``load_corrections`` and ``load_declared_non_record_sheet_reasons``
both treat "no annotation here" as the ordinary case of none having been
authored, which is correct for the overwhelming majority of the corpus -- so an
annotation made unreachable by packaging produced exactly the answer an absent
one does. Every annotated design then read as PARTIAL, or worse read as complete
with its corrections silently not applied, on a filing-grade surface.

WHAT THE FIXTURE DOES, AND WHY IT IS NOT A MOCK. Each test below builds a real
temporary portion of the ``cadrumo_data`` PEP 420 implicit namespace package on
``sys.path`` and copies ONLY the design binary into it, at the same
``_data``-relative position the companion build hook maps it to. That reproduces
the installed layout exactly: the binary resolves under the companion root, the
annotation exists only under the ``cadrumo`` root, and the real parser reads the
real design through the real resource seam. Nothing tracked is mutated -- the
fixture copies out of the source tree and never writes into it.

Every test here fails against a sibling-only reader, which is what makes them a
detector rather than a description.
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from .....core.external_constants import UTF_8_ENCODING
from .....core.resources.bundled_data import bundled_path
from ..errors import RegistryValidationError
from ..record_design import extract_record_design
from ..record_design_sources import load_corrections, load_declared_non_record_sheet_reasons

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGNS = "corpus/aeat_official/disenos_registro"

#: A design whose completeness depends on a MODELO-level declaration living one
#: directory above it: Modelo 232 reads every record sheet and skips only its
#: adjudicated ``TABLAS`` lookup tab.
_MODELO_232 = (
    f"{_DESIGNS}/modelo_232/files"
    "/01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx"
)
_MODELO_232_DECLARATION = f"{_DESIGNS}/modelo_232/declared-non-record-sheets.json"

#: A design whose completeness depends on a SIBLING correction sidecar. The two
#: annotation shapes are exercised separately because they navigate differently
#: from the binary, and a fix that spanned the roots for only one of them would
#: leave the other silently broken.
_MODELO_280 = f"{_DESIGNS}/modelo_280/files/DR_280_2022.pdf"
_MODELO_280_CORRECTION = f"{_MODELO_280}.record-design-correction.json"


@pytest.fixture
def companion_portion(tmp_path: Path) -> Iterator[Callable[[str], Path]]:
    """Install a real temporary ``cadrumo_data`` portion and yield a file placer.

    The yielded callable takes a ``_data``-relative corpus path, copies the
    source tree's file to that same position under the portion, and returns the
    portion-side path -- the path an installed cohort would resolve the binary
    to. The portion carries no ``__init__.py``, matching the shipped companions,
    so ``cadrumo_data`` stays a namespace package.

    Yields:
        The placer.
    """
    portion_root = tmp_path / "portion"
    data_root = portion_root / "cadrumo_data" / "_data"
    data_root.mkdir(parents=True)

    def place(relative: str) -> Path:
        destination = data_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled_path() / relative, destination)
        return destination

    sys.modules.pop("cadrumo_data", None)
    sys.path.insert(0, str(portion_root))
    importlib.invalidate_caches()
    try:
        yield place
    finally:
        sys.modules.pop("cadrumo_data", None)
        if str(portion_root) in sys.path:
            sys.path.remove(str(portion_root))
        importlib.invalidate_caches()


def test_the_fixture_really_separates_the_annotation_from_its_design(
    companion_portion: Callable[[str], Path],
) -> None:
    """Anti-vacuity, and the assertion the rest of this module rests on.

    If the placer ever copied a whole directory, every test below would pass
    while proving nothing: the annotation would sit beside the binary again and
    a sibling read would find it. This pins the separation itself -- the
    companion-side design has no annotation next to it and no modelo-level
    declaration above it, exactly as the shipped companions carry none.
    """
    workbook = companion_portion(_MODELO_232)
    document = companion_portion(_MODELO_280)

    assert not (workbook.parent.parent / "declared-non-record-sheets.json").exists()
    assert not document.with_name(document.name + ".record-design-correction.json").exists()
    # ...and the annotations really are present under the cadrumo root, so the
    # tests below are separated rather than merely missing their subject.
    assert (bundled_path() / _MODELO_232_DECLARATION).is_file()
    assert (bundled_path() / _MODELO_280_CORRECTION).is_file()


def test_a_modelo_declaration_reaches_a_design_resolved_from_the_companion_root(
    companion_portion: Callable[[str], Path],
) -> None:
    """Modelo 232's adjudicated lookup tab stays adjudicated after the split.

    Against a sibling-only reader this design reports an undeclared skip and
    therefore an incomplete read -- a filing-grade surface downgraded by a
    packaging accident, with no diagnostic anywhere.
    """
    workbook = companion_portion(_MODELO_232)

    reasons = load_declared_non_record_sheet_reasons(workbook)
    extraction = extract_record_design(workbook)

    assert "TABLAS" in reasons
    assert reasons["TABLAS"].strip()
    assert extraction.skipped, "this design is expected to skip its adjudicated lookup tab"
    assert all(item.declared_non_record for item in extraction.skipped)
    assert extraction.unread_record_sheets == ()
    assert extraction.is_complete


def test_a_correction_sidecar_reaches_a_design_resolved_from_the_companion_root(
    companion_portion: Callable[[str], Path],
) -> None:
    """Modelo 280's declared correction still applies after the split.

    Against a sibling-only reader the correction is not found, the sheet it
    repairs is skipped, and the design reports an incomplete read.
    """
    document = companion_portion(_MODELO_280)

    corrections = load_corrections(document)
    extraction = extract_record_design(document)

    declared = (
        len(corrections.type_corrections)
        + len(corrections.header_corrections)
        + len(corrections.single_position_corrections)
        + len(corrections.range_start_corrections)
    )
    assert declared, "the sidecar's declared correction must be loaded from the root that ships it"
    assert extraction.corrections, "the declared correction must reach the design it repairs"
    assert all(item.editions_read and item.reason.strip() for item in extraction.corrections)
    assert extraction.is_complete


def test_the_companion_copy_reads_identically_to_the_source_tree_copy(
    companion_portion: Callable[[str], Path],
) -> None:
    """The two layouts are one product, so they must not disagree about a design.

    Stated as a comparison rather than as pinned counts: what matters is that
    moving a design between distributions changes nothing about how it reads,
    and a pinned tally would encode today's parse instead.
    """
    for relative in (_MODELO_232, _MODELO_280):
        installed = extract_record_design(companion_portion(relative))
        checkout = extract_record_design(bundled_path() / relative)

        assert installed.is_complete == checkout.is_complete
        assert len(installed.corrections) == len(checkout.corrections)
        assert [(item.name, item.declared_non_record) for item in installed.skipped] == [
            (item.name, item.declared_non_record) for item in checkout.skipped
        ]


def test_an_annotation_published_differently_under_two_roots_is_refused(
    companion_portion: Callable[[str], Path],
) -> None:
    """The other direction the split can go wrong: two roots, two answers.

    Spanning the roots to FIND an annotation means a badly re-partitioned cohort
    can now offer two, and picking either would let installation order decide a
    grounding question. The reader refuses instead, which is the loud failure the
    silent PARTIAL never was.
    """
    workbook = companion_portion(_MODELO_232)
    companion_declaration = companion_portion(_MODELO_232_DECLARATION)
    companion_declaration.write_text(
        json.dumps({"declared_non_record_sheets": [{"sheet": "TABLAS", "reason": "a different adjudication"}]}),
        encoding=UTF_8_ENCODING,
    )

    with pytest.raises(RegistryValidationError, match="more than one installed data root"):
        load_declared_non_record_sheet_reasons(workbook)


def test_an_annotation_mirrored_identically_under_two_roots_is_not_refused(
    companion_portion: Callable[[str], Path],
) -> None:
    """The refusal above must bite on DIVERGENCE, not on mere duplication.

    A cohort that ships the same bytes twice has answered the grounding question
    consistently; refusing it would make the check fire on a harmless mirror and
    train the next reader to weaken it.
    """
    workbook = companion_portion(_MODELO_232)
    companion_portion(_MODELO_232_DECLARATION)

    assert "TABLAS" in load_declared_non_record_sheet_reasons(workbook)


def test_a_design_outside_every_bundled_root_still_reads_its_own_neighbours(
    tmp_path: Path,
) -> None:
    """A file with no position in the bundled tree keeps plain sibling semantics.

    Fixtures and operator-supplied designs are not part of the logical corpus, so
    re-homing their annotation lookup onto the shipped roots would be a claim the
    seam cannot support -- and would silently attach a bundled modelo's grounding
    to an unrelated workbook.
    """
    files_dir = tmp_path / "modelo_probe" / "files"
    files_dir.mkdir(parents=True)
    design = files_dir / "probe.xlsx"
    design.write_bytes(b"not a workbook")
    (tmp_path / "modelo_probe" / "declared-non-record-sheets.json").write_text(
        json.dumps({"declared_non_record_sheets": [{"sheet": "PROBE", "reason": "a local fixture adjudication"}]}),
        encoding=UTF_8_ENCODING,
    )

    assert load_declared_non_record_sheet_reasons(design) == {"PROBE": "a local fixture adjudication"}
    assert load_corrections(design).type_corrections == {}
