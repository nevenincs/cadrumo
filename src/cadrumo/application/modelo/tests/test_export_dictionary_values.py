"""The export composer supplies the identity rows the renderer no longer knows.

``DPNIF_D`` and ``DP_APENOM_D`` used to be answered inside the XML-dictionary
renderer by two ``if entry.field_id == ...`` escapes -- the one thing a renderer
driven by AEAT's dictionary must not carry, because it makes the renderer the
second place that knows a field id. They are now composed here and handed over
through the typed dictionary-value channel, which is the same route the
registry-declared profile bindings will take.

The values are asserted against the sources the escapes read, so a divergence
between what the retired code wrote and what the composer writes shows up as a
failure here rather than as a changed byte in a filing artefact.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....application.filing import ModeloDraft, build_runtime_schema_provider
from ....core import Period
from ....domain.submission import ModeloDraftStatus
from .._export import _compose_export_dictionary_values
from ._export_test_support import _snapshot_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NIF = "12345678Z"
#: These cases cover the two identity rows the composer sources from the draft
#: and the headers, so they pass no export bindings. The resolver short-circuits
#: on an empty binding set and never opens the bucket, which is what lets these
#: stay unit tests rather than needing an isolated profile runtime.
_BUCKET_ID = "bucket-under-test"
_PERIOD = Period.from_year_and_code(2024, "0A")


def _draft() -> ModeloDraft:
    """Build a Modelo 100 draft against the live registry snapshot.

    The revision id and schema marker are read from the snapshot rather than
    written by hand: the draft model binds the two, so a hand-written pair is
    either rejected or, worse, agrees with itself while naming a revision the
    registry does not carry.
    """
    subview = build_runtime_schema_provider(filing_year=2024, period=_PERIOD, modelos=("100",)).get_subview("100")
    timestamp = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    return ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="100",
        period=_PERIOD,
        profile_tax_id=_NIF,
        subject_tax_id=_NIF,
        snapshot_ref=_snapshot_ref(modelo="100", period=_PERIOD, revision_id=subview.revision_id),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=timestamp,
        updated_at=timestamp,
        schema_version=subview.schema_version,
    )


def test_the_identity_rows_carry_what_the_retired_escapes_produced() -> None:
    """A natural person's NIF and full name land under AEAT's own field ids.

    The retired escapes read ``draft.profile_tax_id`` and joined the header
    ``surnames`` and ``name`` parts with a single space. Both sources are read
    here unchanged, which is what makes the exported bytes identical across the
    move rather than merely similar.
    """
    values = _compose_export_dictionary_values(
        draft=_draft(),
        headers={"surnames": "SURNAME BLANK", "name": "STATE", "tax_id": _NIF},
        bucket_id=_BUCKET_ID,
    )

    assert values == {"DPNIF_D": _NIF, "DP_APENOM_D": "SURNAME BLANK STATE"}


def test_a_legal_entity_name_is_not_padded_with_a_trailing_separator() -> None:
    """A blank individual-name slot contributes nothing, not an empty word.

    The export header composer populates ``surnames`` with the company name and
    leaves ``name`` blank for a legal entity outside the layouts that reserve
    that slot. Joining unconditionally would emit a trailing space into the
    declaration's name field.
    """
    values = _compose_export_dictionary_values(
        draft=_draft(),
        headers={"surnames": "EMPRESA EJEMPLO SL", "name": "", "tax_id": _NIF},
        bucket_id=_BUCKET_ID,
    )

    assert values["DP_APENOM_D"] == "EMPRESA EJEMPLO SL"


def test_the_taxpayer_identity_is_read_from_the_draft_not_from_the_headers() -> None:
    """The NIF comes from the draft the artefact is being written for.

    The header mapping carries a ``tax_id`` too, composed from the workflow
    profile. The two agree on the production path, and reading the draft is what
    keeps them agreeing: the draft is the record whose casilla values are being
    exported, so an identity taken from anywhere else could describe a different
    taxpayer than the numbers do.
    """
    values = _compose_export_dictionary_values(
        draft=_draft(),
        headers={"surnames": "SURNAME BLANK", "name": "STATE", "tax_id": "87654321X"},
        bucket_id=_BUCKET_ID,
    )

    assert values["DPNIF_D"] == _NIF
