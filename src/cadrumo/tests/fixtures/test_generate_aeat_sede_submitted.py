"""The committed carry-agreement fixture still matches its generator.

The generator writes into the committed fixture tree, so these tests exercise
its importable surface and the bytes already on disk rather than invoking the
writer -- the same shape the justificantes generator's tests use.

Regenerability is the property worth holding. A committed fixture whose
generator has drifted is worse than no fixture: it looks authoritative, its
sidecar digest still verifies against its own bytes, and nothing reveals that
re-running the generator would now produce something else.

The generator lives here rather than beside the artefacts it writes because
``aeat-sede/`` is a DATA directory -- its hyphen is load-bearing, since several
production modules read that path as a string -- and a hyphenated directory can
never be an importable package. A Python module placed there is unreachable by
construction, which is what left this one untested.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ._generate_aeat_sede_submitted import (
    _BASE_IMPONIBLE_AHORRO,
    _BASE_IMPONIBLE_GENERAL,
    _CARRY_AGREEMENT_NAME,
    _CARRY_AGREEMENT_XML,
    _SUBMITTED,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_UTF_8 = "utf-8"


def _committed_xml() -> Path:
    return _SUBMITTED / _CARRY_AGREEMENT_NAME


def _root() -> Element[str]:
    root = DefusedElementTree.fromstring(_CARRY_AGREEMENT_XML)
    assert root is not None
    return root


def test_the_committed_fixture_is_still_what_the_generator_produces() -> None:
    """Byte equality, so generator drift cannot hide behind a valid digest.

    The sidecar's ``output_sha256`` is a digest of the committed bytes, so it
    stays self-consistent no matter how far the generator moves away from them.
    Comparing the generator's own output against what is on disk is the only
    check that notices the drift.
    """
    committed = _committed_xml().read_bytes()

    assert committed == _CARRY_AGREEMENT_XML.encode(_UTF_8)


def test_the_sidecar_records_the_bytes_beside_it() -> None:
    """The recorded digest and size describe the committed artefact."""
    payload = _committed_xml().read_bytes()
    sidecar = json.loads(_committed_xml().with_suffix(".json").read_text(encoding=_UTF_8))

    assert sidecar["output_sha256"] == hashlib.sha256(payload).hexdigest()
    assert sidecar["output_size_bytes"] == len(payload)
    assert sidecar["provenance"] == "synthetic_generated"


def test_the_fixture_still_holds_the_property_it_exists_for() -> None:
    """Both rows of one casilla AGREE -- the case no redacted artefact can show.

    This fixture exists because the redactor assigns placeholders by field
    POSITION, so two rows carrying the same casilla always disagree in a
    redacted artefact. That makes the normal case for AEAT's carry fields --
    the two rows agreeing -- unreachable from real evidence.

    If a later edit made these values differ, the file would still parse, still
    validate, and still verify against its own digest, while having silently
    stopped being evidence for the thing it was authored to prove.
    """
    root = _root()
    general = [node.text for node in root.iter() if node.tag in {"BIGRALH", "BIGRALJ"}]
    ahorro = [node.text for node in root.iter() if node.tag in {"BIAHOH", "BIAHOJ"}]

    assert general == [_BASE_IMPONIBLE_GENERAL, _BASE_IMPONIBLE_GENERAL]
    assert ahorro == [_BASE_IMPONIBLE_AHORRO, _BASE_IMPONIBLE_AHORRO]


def test_the_mandatory_aux_block_is_present_and_first() -> None:
    """``Aux`` is ``minOccurs=1`` and no bundled dictionary declares its rows.

    Real submissions carry it, so a fixture standing in for one must too. It is
    also the element a document missing it fails on FIRST, which is what makes
    an omission masquerade as an unrelated validation error downstream.
    """
    root = _root()
    children = [node.tag for node in root]

    assert children[0] == "Aux"
