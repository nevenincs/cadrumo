"""``ModeloDraft`` enforces one taxpayer identity across its two identity axes.

``profile_tax_id`` and ``subject_tax_id`` are two axes of the same taxpayer:
:func:`application.filing.build_draft` copies one validated profile identity into
both, and no consumer reads them as different parties. Typing each as
:data:`~core.identity.SubjectTaxId` validates each value's AEAT checksum in
isolation, so two individually-valid but *different* NIFs were accepted — a draft
naming one taxpayer as the profile and another as the filing subject, which the
encrypted repository round-tripped unchanged. Only ``profile_tax_id`` feeds
``compute_modelo_draft_id``, so the divergence never surfaced in the identity
either.

These tests pin the refusal and confirm the coherent shape the builder emits
still constructs and rehydrates.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ...submission import ModeloDraftStatus
from ..schema import ModeloDraft, ModeloValue, ModeloValueKind, registry_schema_version

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TIMESTAMP = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
# Two independently valid Spanish NIFs: each passes the AEAT control-letter
# checksum on its own, which is exactly why per-field typing cannot catch the
# divergence between them.
_PROFILE_NIF = "12345678Z"
_OTHER_NIF = "87654321X"


def _draft_kwargs() -> dict[str, object]:
    return {
        "draft_id": "draft-identity-test",
        "modelo": "130",
        "period": Period.from_year_and_code(2026, "1T"),
        "snapshot_ref": RegistrySnapshotRef(
            modelo="130",
            revision_id="2019-y-siguientes",
            modelo_year=2026,
            period="1T",
        ),
        "status": ModeloDraftStatus.BORRADOR,
        "values": (
            ModeloValue(
                casilla_id="01",
                value=Decimal("1000.00"),
                kind=ModeloValueKind.LITERAL,
                source="registry input",
            ),
        ),
        "created_at": _TIMESTAMP,
        "updated_at": _TIMESTAMP,
        "schema_version": "registry:130:2019-y-siguientes",
    }


def test_draft_refuses_divergent_taxpayer_identity_axes() -> None:
    """A profile NIF and a different filing-subject NIF must not coexist on one draft."""
    with pytest.raises(ValidationError, match=r"draft taxpayer identity diverges"):
        ModeloDraft.model_validate(
            {
                "profile_tax_id": _PROFILE_NIF,
                "subject_tax_id": _OTHER_NIF,
                **_draft_kwargs(),
            },
        )


def test_both_nifs_are_individually_valid() -> None:
    """Prove the refusal is the cross-field rule, not one NIF failing its checksum.

    Without this control the divergence test would pass even if the invariant
    were absent and ``_OTHER_NIF`` simply had a bad control letter.
    """
    for nif in (_PROFILE_NIF, _OTHER_NIF):
        draft = ModeloDraft.model_validate(
            {
                "profile_tax_id": nif,
                "subject_tax_id": nif,
                **_draft_kwargs(),
            },
        )
        assert draft.profile_tax_id == nif
        assert draft.subject_tax_id == nif


def test_coherent_draft_rehydrates_from_its_persisted_json() -> None:
    """The builder's coherent shape survives the JSON boundary the store reads through."""
    draft = ModeloDraft.model_validate(
        {
            "profile_tax_id": _PROFILE_NIF,
            "subject_tax_id": _PROFILE_NIF,
            **_draft_kwargs(),
        },
    )

    reloaded = ModeloDraft.model_validate_json(draft.model_dump_json())

    assert reloaded == draft


def test_draft_refuses_a_schema_marker_naming_another_revision() -> None:
    """A fabricated or stale schema marker must not travel with a different snapshot.

    ``schema_version`` is a derived ``registry:{modelo}:{revision}`` marker over
    the same snapshot the draft already carries typed. Declared as an
    independent bare string, a stale marker rode alongside a different registry
    revision and stayed invisible until some downstream check happened to run.
    """
    kwargs = _draft_kwargs()
    kwargs["schema_version"] = registry_schema_version(modelo="130", revision_id="WRONG")

    with pytest.raises(ValidationError, match=r"does not match the registry marker"):
        ModeloDraft.model_validate(
            {
                "profile_tax_id": _PROFILE_NIF,
                "subject_tax_id": _PROFILE_NIF,
                **kwargs,
            },
        )


def test_draft_refuses_a_modelo_that_contradicts_its_snapshot() -> None:
    """The draft's modelo and its snapshot_ref's modelo are one axis, not two."""
    kwargs = _draft_kwargs()
    kwargs["modelo"] = "303"

    with pytest.raises(ValidationError, match=r"does not match its snapshot_ref modelo"):
        ModeloDraft.model_validate(
            {
                "profile_tax_id": _PROFILE_NIF,
                "subject_tax_id": _PROFILE_NIF,
                **kwargs,
            },
        )


def test_schema_marker_helper_is_the_shape_the_draft_requires() -> None:
    """The canonical helper's output is exactly what the coherence check accepts."""
    marker = registry_schema_version(modelo="130", revision_id="2019-y-siguientes")

    assert marker == "registry:130:2019-y-siguientes"

    draft = ModeloDraft.model_validate(
        {
            "profile_tax_id": _PROFILE_NIF,
            "subject_tax_id": _PROFILE_NIF,
            **_draft_kwargs(),
        },
    )
    assert draft.schema_version == marker


def test_rehydration_refuses_a_persisted_divergent_draft() -> None:
    """A draft already stored with divergent axes fails to load, rather than reading clean."""
    coherent = ModeloDraft.model_validate(
        {
            "profile_tax_id": _PROFILE_NIF,
            "subject_tax_id": _PROFILE_NIF,
            **_draft_kwargs(),
        },
    )
    tampered = json.loads(coherent.model_dump_json())
    tampered["subject_tax_id"] = _OTHER_NIF

    with pytest.raises(ValidationError, match=r"draft taxpayer identity diverges"):
        ModeloDraft.model_validate_json(json.dumps(tampered))
