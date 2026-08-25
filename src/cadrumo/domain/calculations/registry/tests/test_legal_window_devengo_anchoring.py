"""Substantive-law legal windows are devengo-anchored; procedural ones are not.

``_check_revision_scoped_legal_windows`` (``_snapshot.py``) previously accepted
ANY overlap between a legal reference's effective window and the revision's
presentation-extended applicability window (``RevisionLegalApplicabilityWindow``,
``valid_from`` through the latest declared deadline-window close). That let a
substantive-law redaction whose era only began partway through the FOLLOWING
calendar year -- while the return was still being filed -- ground a tax period
it never actually governed: the M100 2020-2023 defect fixed by the
``ley-35-2006:art-52``/``art-63``/``art-66``/``art-68``/``art-75``/``art-76``/
``art-87``/``art-91`` version-scoped entries.

``_legal_window_covers_devengo`` closes this for substantive-law reference
``kind``s (ley, real_decreto*, reglamento, directiva, acuerdo_internacional) by
anchoring them to the revision's own devengo date (``valid_to``, the 31
December IRPF art. 12 fixes the tax period's close on) instead of the
presentation-extended window. Procedural/administrative kinds (orden, manual,
instruction) keep the original presentation-tolerant check unchanged, matching
the same distinction ``validate_orden_aplicabilidad`` already draws for the
``orden_aplicabilidad`` field -- verified real in the shipped tree, not
assumed: the M100 2025 revision's own ``orden-hac-277-2026:art-7``/``art-10``
citations are published 2026-03-28, three months after the 2025 devengo date,
and are correctly accepted.

These tests drive the real bundled M100 2025 authority through the real
``_check_revision_scoped_legal_windows`` path (no doubles), proving the
predicate has teeth in both directions: it REJECTS a substantive-law citation
mutated into the exact era the OLD overlap logic accepted, and it ACCEPTS a
procedural (orden) citation mutated into the identical era.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import TypeAdapter

from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, RegistryCatalogues
from ..snapshot import _check_revision_scoped_legal_windows, collect_snapshot_ref_ids
from .._validate_orden_aplicabilidad import RevisionLegalApplicabilityWindow
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "100"
_REVISION = "2025"

#: One day after the 2025 revision's devengo date (``valid_to``). The OLD
#: overlap logic accepts any reference whose ``effective_from`` falls anywhere
#: up to the presentation-extended ``closes_on`` (well past mid-2026), so this
#: date is squarely inside the window the old check accepted for every kind.
_JUST_AFTER_DEVENGO = date(2026, 1, 2)
_DATE_ADAPTER: TypeAdapter[date] = TypeAdapter(date)


def _modelo_and_catalogues() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo(_MODELO)


def _revision_scoped_legal_ids_by_kind(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> dict[str, str]:
    """Return one revision-scoped legal id per distinct ``kind`` present."""
    legal_ids, _source_ids = collect_snapshot_ref_ids(modelo, modelo.revisions[_REVISION])
    scoped = legal_ids - set(modelo.legal_refs)
    by_kind: dict[str, str] = {}
    for legal_id in sorted(scoped):
        reference = catalogues.legal.get(legal_id)
        if reference is None or reference.kind in by_kind:
            continue
        by_kind[reference.kind] = legal_id
    return by_kind


def test_shipped_2025_revision_confirms_the_precondition_this_module_relies_on() -> None:
    """Positive control: the devengo date and presentation window this module
    reasons about actually hold for the shipped M100 2025 revision, and the
    revision genuinely owns both a substantive-law and a procedural reference.
    """
    modelo, catalogues = _modelo_and_catalogues()
    revision = modelo.revisions[_REVISION]
    applicability_window = RevisionLegalApplicabilityWindow.from_revision(revision)

    assert revision.valid_to == date(2025, 12, 31)
    assert applicability_window.closes_on is not None
    assert applicability_window.closes_on >= _JUST_AFTER_DEVENGO, (
        "the presentation-extended window must still cover the mutated date for the old-overlap "
        "comparison below to mean anything"
    )

    by_kind = _revision_scoped_legal_ids_by_kind(modelo, catalogues)
    assert "ley" in by_kind, "the 2025 revision must own a substantive-law (ley) reference"
    assert "orden" in by_kind, "the 2025 revision must own a procedural (orden) reference"


def test_devengo_anchoring_rejects_a_mis_eras_substantive_law_citation() -> None:
    """TEETH, direction 1: a ``ley`` reference mutated to start the day after
    devengo is refused, even though it is well inside the presentation window
    the old overlap check alone would have accepted for this exact date.
    """
    modelo, catalogues = _modelo_and_catalogues()
    by_kind = _revision_scoped_legal_ids_by_kind(modelo, catalogues)
    legal_id = by_kind["ley"]
    reference = catalogues.legal[legal_id]
    assert reference.kind == "ley"

    mutated = reference.model_copy(update={"effective_from": _JUST_AFTER_DEVENGO, "effective_to": None})
    mutated_catalogues = catalogues.model_copy(update={"legal": {**catalogues.legal, legal_id: mutated}})

    # Prove the OLD (presentation-overlap-only) logic would have accepted this
    # exact mutation, so the failure below is attributable to the devengo
    # anchoring and not to some other window boundary.
    applicability_window = RevisionLegalApplicabilityWindow.from_revision(modelo.revisions[_REVISION])
    assert applicability_window.overlaps(mutated), (
        "the mutated reference must still satisfy the old overlap-only check for this to be a meaningful teeth proof"
    )

    with pytest.raises(RegistryValidationError, match="does not cover revision '2025''s devengo date"):
        _check_revision_scoped_legal_windows(modelo, modelo.revisions[_REVISION], mutated_catalogues)


def test_devengo_anchoring_still_accepts_a_legitimately_late_orden_ref() -> None:
    """TEETH, direction 2: an ``orden`` reference mutated to the SAME date is
    still accepted -- the carve-out survives the tightening. Without this, a
    future tightening could silently re-break the 13 real orden pairs (the
    modelo-form-approval and TFI-documentation annex orders published, by
    design, in the months after the tax year the modelo form belongs to).
    """
    modelo, catalogues = _modelo_and_catalogues()
    by_kind = _revision_scoped_legal_ids_by_kind(modelo, catalogues)
    legal_id = by_kind["orden"]
    reference = catalogues.legal[legal_id]
    assert reference.kind == "orden"

    mutated = reference.model_copy(update={"effective_from": _JUST_AFTER_DEVENGO, "effective_to": None})
    mutated_catalogues = catalogues.model_copy(update={"legal": {**catalogues.legal, legal_id: mutated}})

    # No exception: the orden carve-out keeps the presentation-tolerant check.
    _check_revision_scoped_legal_windows(modelo, modelo.revisions[_REVISION], mutated_catalogues)


def test_shipped_orden_refs_are_genuinely_late_not_a_coincidence() -> None:
    """The carve-out is exercised by real shipped data, not just this module's
    synthetic mutation: ``orden-hac-277-2026`` is published three months after
    the 2025 devengo date and grounds the revision's TFI/deadline casillas.
    """
    modelo, catalogues = _modelo_and_catalogues()
    revision = modelo.revisions[_REVISION]

    for ref_id in ("orden-hac-277-2026:art-7", "orden-hac-277-2026:art-10"):
        reference = catalogues.legal[ref_id]
        assert reference.kind == "orden"
        assert reference.effective_from is not None, f"{ref_id} must declare an effective-from date"
        assert revision.valid_to is not None, f"{_REVISION} must declare its devengo date"
        effective_from = _DATE_ADAPTER.validate_python(reference.effective_from)
        devengo_date = _DATE_ADAPTER.validate_python(revision.valid_to)
        assert effective_from > devengo_date, (
            f"{ref_id} must genuinely postdate the 2025 devengo date for this precondition to hold"
        )

    # Refusing this call would mean the shipped tree itself no longer loads.
    _check_revision_scoped_legal_windows(modelo, revision, catalogues)
