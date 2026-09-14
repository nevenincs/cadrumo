"""The manual-structure check reports only its own two failure modes.

An unrelated failure raised inside the guarded region - a removed symbol, a
malformed published artifact, a schema violation - must keep its own type and
message instead of being relabelled as a corpus-manual defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.config import Settings
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.static_inspection import StaticGeneratedArtifactSource
from cadrumo.domain.manuals.errors import ManualNotFoundError
from cadrumo.domain.manuals.ids import ManualId, ManualPart
from cadrumo.domain.manuals.schema import Manual

from ..corpus_catalogue import _verify_manual_structure

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_STRUCTURE_MESSAGE = "manual structure check failed for path"


class _UnrelatedArtifactError(RuntimeError):
    """Stands in for an ImportError or artifact-format error from deeper code."""


def _source(corpus_path: str) -> StaticGeneratedArtifactSource:
    return StaticGeneratedArtifactSource(
        id="manual-iva-2024",
        kind=RegistrySourceKind.MANUAL_PDF,
        corpus_path=corpus_path,
        sha256="0" * 64,
        bytes=1,
        applies_from=None,
        applies_to=None,
        record_design_epoch=None,
        corpus_tier=None,
    )


def test_malformed_corpus_path_is_reported_as_a_manual_structure_failure() -> None:
    source = _source("corpus/manuals/iva/source.pdf")

    with pytest.raises(RegistryValidationError) as caught:
        _verify_manual_structure(Path("."), source)

    assert _STRUCTURE_MESSAGE in str(caught.value)
    assert "corpus/manuals/<manual_id>/<year>[/<part>]/source.pdf" in str(caught.value)


def test_unknown_manual_identifier_is_reported_as_a_manual_structure_failure() -> None:
    source = _source("corpus/manuals/patrimonio/2024/source.pdf")

    with pytest.raises(RegistryValidationError) as caught:
        _verify_manual_structure(Path("."), source)

    assert _STRUCTURE_MESSAGE in str(caught.value)


def test_loader_failure_is_reported_as_a_manual_structure_failure() -> None:
    source = _source("corpus/manuals/iva/2024/source.pdf")

    def failing_load(*, manual_id: ManualId, year: int, part: ManualPart, settings: Settings) -> Manual:
        del manual_id, year, part, settings
        raise ManualNotFoundError("missing structure for iva/2024/single")

    with pytest.raises(RegistryValidationError) as caught:
        _verify_manual_structure(Path("."), source, load=failing_load)

    assert _STRUCTURE_MESSAGE in str(caught.value)
    assert "missing structure for iva/2024/single" in str(caught.value)


def test_unrelated_failure_propagates_with_its_own_type_and_message() -> None:
    source = _source("corpus/manuals/iva/2024/source.pdf")

    def broken_load(*, manual_id: ManualId, year: int, part: ManualPart, settings: Settings) -> Manual:
        del manual_id, year, part, settings
        raise _UnrelatedArtifactError("published authority artifact is malformed")

    with pytest.raises(_UnrelatedArtifactError) as caught:
        _verify_manual_structure(Path("."), source, load=broken_load)

    assert str(caught.value) == "published authority artifact is malformed"
    assert _STRUCTURE_MESSAGE not in str(caught.value)


def test_non_manual_source_is_not_checked() -> None:
    source = StaticGeneratedArtifactSource(
        id="boe-iva-ley",
        kind=RegistrySourceKind.INSTRUCTIONS,
        corpus_path="corpus/normatives/boe/ley-37-1992.pdf",
        sha256="0" * 64,
        bytes=1,
        applies_from=None,
        applies_to=None,
        record_design_epoch=None,
        corpus_tier=None,
    )

    def unreachable_load(*, manual_id: ManualId, year: int, part: ManualPart, settings: Settings) -> Manual:
        del manual_id, year, part, settings
        raise AssertionError("a non-manual source must not reach the manual loader")

    _verify_manual_structure(Path("."), source, load=unreachable_load)
