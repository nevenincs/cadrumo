"""Removing the export-record extraction profiles left the PDF authority standing.

Modelos 111, 115 and 123 once declared an ``export_record`` extraction profile
beside their ``declaracion_pdf`` one. The export-record profiles were removed; the
PDF profiles must not have gone with them, because reading a filed declaration
back from its PDF is a capability in its own right and has nothing to do with
whether the modelo can currently emit a fichero BOE.

This asserts the surviving surface exactly rather than merely asserting the
removed ids are absent. An exact comparison is what makes over-deletion visible:
checking only for absence would pass just as happily if the PDF profiles had been
deleted too, which is the failure this guards.

Nothing here claims the export layouts SHOULD be absent. Which modelos can emit is
answered by the filing capability worklist, derived from the registry rather than
from a list maintained by hand.
"""

from __future__ import annotations

import pytest

from .....tests.registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The export-record profiles that were removed. Named so that reinstating one
#: silently, rather than by authoring a real layout, fails here.
_REMOVED_EXPORT_PROFILES = frozenset(
    {
        "modelo-111-export-record",
        "modelo-115-export-record",
        "modelo-123-2019-export-record",
        "modelo-123-export-record",
    },
)

_MODELOS_THAT_HELD_BOTH_PROFILES = frozenset({"111", "115", "123"})


def test_export_record_profiles_removed_without_deleting_pdf_authority() -> None:
    """The declaracion-PDF profiles survive the export-record profile removal.

    Read through the compiler rather than the validated authority. Which
    extraction profiles a revision declares is registry declaration data, not a
    filing artefact, and the full-tree validation now refuses while filing
    capability is absent. Reading through it would make this over-deletion guard
    unrunnable for reasons that have nothing to do with extraction profiles --
    and a guard that goes quiet whenever something else is broken is one nobody
    can rely on at the moment it matters.
    """
    modelos, _catalogues = bundled_registry_tree()
    by_id = {modelo.id: modelo for modelo in modelos}
    profiles = {
        profile.id: profile.surface
        for modelo_id in _MODELOS_THAT_HELD_BOTH_PROFILES
        for revision in by_id[modelo_id].revisions.values()
        for profile in revision.extraction_profiles
    }

    assert _REMOVED_EXPORT_PROFILES.isdisjoint(profiles)
    assert profiles == {
        "modelo-111-declaracion-pdf": "declaracion_pdf",
        "modelo-115-declaracion-pdf": "declaracion_pdf",
        "modelo-123-2019-declaracion-pdf": "declaracion_pdf",
        "modelo-123-declaracion-pdf": "declaracion_pdf",
    }
