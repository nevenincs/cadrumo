"""The AEAT payload-element sets are held to AEAT's own record schemas.

``shape.py`` classifies a submission by looking for the payload elements the
two AEAT envelope schemas declare. Those names are spelled out there as
frozensets, which reads fine and rots silently: AEAT revises these schemas,
and a family added, renamed, or withdrawn upstream would leave the reader
reporting a real tax record as ``UNKNOWN`` with nothing failing.

This module is the join the bundled corpus was committed for. It derives the
element names mechanically from
``corpus/aeat_official/einvoice_record_schemas/`` and requires exact
agreement, so re-bundling a newer schema fails here rather than in the field.
The frozensets stay literal -- the probe must not read the filesystem on a
hot path -- but they are no longer unattested.

The regime scope ruling (``2026-07-02-verifactu-sii-scope-stance``) is not
weakened by any of this: recognising a shape is how the reader REFUSES a
record batch by name. Neither regime is transmitted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from .....core.resources.bundled_data import bundled_path
from ..shape import SII_PAYLOAD_ELEMENTS, VERIFACTU_PAYLOAD_ELEMENTS

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_XSD_NS = "{http://www.w3.org/2001/XMLSchema}"

_SCHEMA_ROOT = ("corpus", "aeat_official", "einvoice_record_schemas")

#: Every family the SII envelope declares, all seventeen. See the module
#: docstring on ``SII_PAYLOAD_ELEMENTS``: recognising a family is separate
#: from supporting it.
_SII_ENVELOPE = ("sii", "SuministroLR.xsd")

#: VERI*FACTU splits its payload names across BOTH files -- the envelope
#: declares ``RegFactuSistemaFacturacion`` and the base-types schema declares
#: the two bare record elements the envelope's ``choice`` references by
#: ``ref``. Real captures ship the bare forms with no envelope, so the reader
#: needs the union and this gate must read both.
_VERIFACTU_SCHEMAS = (
    ("verifactu", "SuministroLR.xsd"),
    ("verifactu", "SuministroInformacion.xsd"),
)


def _schema_path(*parts: str) -> Path:
    return Path(bundled_path(*_SCHEMA_ROOT, *parts))


def _global_element_names(*parts: str) -> frozenset[str]:
    """Return the names of the globally declared elements in one schema.

    Only top-level ``xs:element`` children of ``xs:schema`` count: those are
    the ones a submission may legally use as a payload element. Nested local
    elements (``Cabecera``, ``RegistroFactura``, and the hundreds of leaf
    fields) are structure INSIDE a payload, never a payload themselves, so
    admitting them would make the probe classify a fragment as a batch.
    """
    root = DefusedElementTree.parse(_schema_path(*parts)).getroot()
    assert root is not None, f"{'/'.join(parts)} is not a parseable schema"
    return frozenset(name for element in root.findall(f"{_XSD_NS}element") if (name := element.get("name")) is not None)


def test_sii_payload_elements_are_exactly_the_families_the_envelope_declares() -> None:
    """The reader's SII family set is AEAT's, name for name."""
    declared = _global_element_names(*_SII_ENVELOPE)

    assert declared, "the bundled SII envelope declares no global elements"
    assert declared == SII_PAYLOAD_ELEMENTS, (
        "shape.py's SII payload elements have drifted from "
        f"{'/'.join(_SII_ENVELOPE)}: missing {sorted(declared - SII_PAYLOAD_ELEMENTS)}, "
        f"unknown to AEAT {sorted(SII_PAYLOAD_ELEMENTS - declared)}"
    )


def test_verifactu_payload_elements_are_exactly_the_envelope_plus_the_bare_records() -> None:
    """The reader's VERI*FACTU set is the union the two schemas declare."""
    declared = frozenset[str]().union(*(_global_element_names(*parts) for parts in _VERIFACTU_SCHEMAS))

    assert declared, "the bundled VERI*FACTU schemas declare no global elements"
    assert declared == VERIFACTU_PAYLOAD_ELEMENTS, (
        "shape.py's VERI*FACTU payload elements have drifted from the bundled "
        f"schemas: missing {sorted(declared - VERIFACTU_PAYLOAD_ELEMENTS)}, "
        f"unknown to AEAT {sorted(VERIFACTU_PAYLOAD_ELEMENTS - declared)}"
    )


def test_the_two_regimes_share_no_payload_element_name() -> None:
    """A shared name would make the probe's ordered check decide the regime.

    ``_aeat_record_batch_shape`` tests SII first, so an overlap would silently
    classify a VERI*FACTU record as SII. The schemas keep them disjoint today;
    this states that the reader depends on it.
    """
    assert not (SII_PAYLOAD_ELEMENTS & VERIFACTU_PAYLOAD_ELEMENTS)


def test_each_family_directory_keeps_its_own_suministro_informacion() -> None:
    """Both regimes import a RELATIVE ``SuministroInformacion.xsd``.

    The two files share that name and are different schemas in different
    target namespaces, so flattening the tree would resolve one regime's
    import against the other's types. The layout is load-bearing, and this is
    the gate that says so.
    """
    sii = _schema_path("sii", "SuministroInformacion.xsd")
    verifactu = _schema_path("verifactu", "SuministroInformacion.xsd")

    assert sii.is_file() and verifactu.is_file()
    assert sii.read_bytes() != verifactu.read_bytes()


def test_manifest_pins_every_bundled_schema_by_hash_and_namespace() -> None:
    """No bundled schema is unmanifested, and no manifested one is missing.

    These artefacts carry no registry source entry, so the manifest is the
    only provenance they have. An unpinned file would be a schema nobody can
    trace back to AEAT.
    """
    root = Path(bundled_path(*_SCHEMA_ROOT))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    artefacts = {artefact["path"]: artefact for artefact in manifest["artefacts"]}

    on_disk = {path.relative_to(root).as_posix() for path in root.rglob("*.xsd")}
    assert on_disk == set(artefacts), "the manifest and the bundled schemas disagree on which files exist"

    for relative, artefact in artefacts.items():
        payload = (root / relative).read_bytes()
        assert len(payload) == artefact["bytes"], f"{relative} changed size since it was manifested"
        assert hashlib.sha256(payload).hexdigest() == artefact["sha256"], f"{relative} no longer matches its hash"

        root_element = DefusedElementTree.parse(root / relative).getroot()
        assert root_element is not None
        assert root_element.get("targetNamespace") == artefact["target_namespace"], (
            f"{relative} declares a target namespace the manifest does not record"
        )
