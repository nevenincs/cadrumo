"""Fixed identity vectors for both Workspace admission capture sets."""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....core.revision_review import RevisionReviewStatus
from ..workspace_baseline import resolve_workspace_baseline
from ..workspace_models import (
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceSchemaIdentityV1,
)
from ..workspace_producers import (
    ModeloWorkspaceContributorKindV1,
    ModeloWorkspaceEpochV1,
    ModeloWorkspaceProducerStampV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KINDS = (
    ModeloWorkspaceContributorKindV1.WORK,
    ModeloWorkspaceContributorKindV1.REGISTRY,
    ModeloWorkspaceContributorKindV1.LOCALE_CATALOGUE,
    ModeloWorkspaceContributorKindV1.FIELD_MANIFEST,
    ModeloWorkspaceContributorKindV1.CALCULATION,
    ModeloWorkspaceContributorKindV1.BOUNDED_REVIEW,
    ModeloWorkspaceContributorKindV1.READINESS,
)


def _target() -> ModeloWorkspaceResolvedTargetV1:
    return ModeloWorkspaceResolvedTargetV1(
        bucket_id="workspace-bucket",
        modelo="130",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        law_selected_revision_id="2025-y-siguientes",
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        requested_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
        stored_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.STORED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
    )


def _schema() -> ModeloWorkspaceSchemaIdentityV1:
    return ModeloWorkspaceSchemaIdentityV1(
        schema_id="modelo-130-schema",
        schema_fingerprint="d" * 64,
        field_manifest_digest="e" * 64,
    )


def _locale() -> ModeloWorkspaceLocaleSummaryV1:
    return ModeloWorkspaceLocaleSummaryV1(
        requested_language=OutputLanguage.ES,
        resolved_language=OutputLanguage.ES,
        disposition=ModeloWorkspaceLocaleDisposition.EXACT,
        catalogue_digest="f" * 64,
    )


def _stamps(count: int) -> tuple[ModeloWorkspaceProducerStampV1, ...]:
    return tuple(
        ModeloWorkspaceProducerStampV1.model_validate(
            {
                "contributor_kind": kind,
                "contributor": {"owner": f"{kind.value}.owner", "producer": f"{kind.value}.projection"},
                "contract_digest": "a" * 64,
                "projection_discriminator": kind.value,
                "projection_contract_version": 1,
                "projection_schema_fingerprint": "b" * 64,
            }
        )
        for kind in _KINDS[:count]
    )


def _epochs(count: int) -> tuple[ModeloWorkspaceEpochV1, ...]:
    return tuple(
        ModeloWorkspaceEpochV1(owner=f"{kind.value}.owner", comparison_domain="c" * 64, generation=index + 1)
        for index, kind in enumerate(_KINDS[:count])
    )


@pytest.mark.parametrize(
    ("count", "stamp_digest", "epoch_digest", "token"),
    (
        (
            4,
            "94d98c26d05caedc1877b78a4c04064c5ca7a48f09f78c64a36a0664155be01a",
            "c9639c07ed59a4bf1c12b1141db0b2aa5c119b79c029835989a4896f56a4494a",
            "ae78e08e16e0e58e4284ebfced7c2f28f1b0a80907e5338890da8bb16bcb0113",
        ),
        (
            7,
            "3e8b3f68fe05fc850ee38b4de82ffd294302a0a1cafdac222d30bc22347c1b15",
            "63f18531600541d18d3624f08ec7f9b8d572787bfa8abc3e1f5914f9d7994898",
            "753a6ba9e5251388021911341c43a7b06241faf80889b74e59f79b700605520a",
        ),
    ),
)
def test_admission_capture_sets_keep_their_fixed_digest_vectors(
    count: int, stamp_digest: str, epoch_digest: str, token: str
) -> None:
    """Expected hashes come from explicit JSON records encoded with stdlib only."""
    target, schema, locale = _target(), _schema(), _locale()
    baseline = resolve_workspace_baseline(
        target, schema_identity=schema, locale=locale, stamps=_stamps(count), epochs=_epochs(count)
    )

    assert baseline.contributor_stamp_digest == stamp_digest
    assert baseline.contributor_epoch_digest == epoch_digest
    assert baseline.token == token
    assert baseline.target == target
    assert baseline.selected_revision_id == target.law_selected_revision_id
    assert baseline.schema_identity == schema
    assert baseline.locale_catalogue_digest == locale.catalogue_digest
    assert baseline == resolve_workspace_baseline(
        target, schema_identity=schema, locale=locale, stamps=_stamps(count), epochs=_epochs(count)
    )


@pytest.mark.parametrize("count", (4, 7))
@pytest.mark.parametrize("component", ("stamps", "epochs"))
def test_each_capture_order_participates_in_identity(count: int, component: str) -> None:
    stamps, epochs = _stamps(count), _epochs(count)
    original = resolve_workspace_baseline(
        _target(), schema_identity=_schema(), locale=_locale(), stamps=stamps, epochs=epochs
    )
    reordered = resolve_workspace_baseline(
        _target(),
        schema_identity=_schema(),
        locale=_locale(),
        stamps=tuple(reversed(stamps)) if component == "stamps" else stamps,
        epochs=tuple(reversed(epochs)) if component == "epochs" else epochs,
    )

    assert reordered.token != original.token
    assert (reordered.contributor_stamp_digest != original.contributor_stamp_digest) == (component == "stamps")
    assert (reordered.contributor_epoch_digest != original.contributor_epoch_digest) == (component == "epochs")


@pytest.mark.parametrize("component", ("target", "revision", "schema", "locale", "stamp", "epoch", "domain"))
def test_each_captured_coordinate_participates_in_identity(component: str) -> None:
    target, schema, locale = _target(), _schema(), _locale()
    stamps, epochs = _stamps(4), _epochs(4)
    original = resolve_workspace_baseline(target, schema_identity=schema, locale=locale, stamps=stamps, epochs=epochs)
    if component == "target":
        target = target.model_copy(update={"bucket_id": "other-bucket"})
    elif component == "revision":
        target = target.model_copy(update={"law_selected_revision_id": "2026-y-siguientes"})
    elif component == "schema":
        schema = schema.model_copy(update={"schema_fingerprint": "0" * 64})
    elif component == "locale":
        locale = locale.model_copy(update={"catalogue_digest": "0" * 64})
    elif component == "stamp":
        stamps = (stamps[0].model_copy(update={"contract_digest": "0" * 64}), *stamps[1:])
    elif component == "epoch":
        epochs = (epochs[0].model_copy(update={"generation": 2}), *epochs[1:])
    else:
        epochs = (epochs[0].model_copy(update={"comparison_domain": "0" * 64}), *epochs[1:])

    changed = resolve_workspace_baseline(target, schema_identity=schema, locale=locale, stamps=stamps, epochs=epochs)

    assert changed.token != original.token
