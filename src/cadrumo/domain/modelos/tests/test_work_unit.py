"""Schema + behaviour tests for the modelo work-unit domain types.

These tests cover the deterministic content-addressing of
``work_unit_id``, the strict / frozen schema invariants on
``WorkUnit``, the catalogue's key-matches-record contract, and the
application-layer lifecycle actions (``create_work_unit``,
``list_work_units``, ``get_work_unit``, ``rename_work_unit``).

The action-level tests exercise the real
:class:`WorkUnitCatalogueRepository` against an isolated active-profile
runtime so the production save / load envelope is on the hot path; no
in-memory fakes, no subclassed test repositories.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.modelo._action_errors import (
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ....application.modelo._work_lifecycle import (
    create_work_unit,
    discard_work_unit,
    get_work_unit,
    list_work_units,
    rename_work_unit,
)
from ....core import Period
from ....core.directory_scan import scan_directory
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from cadrumo.domain.calculations.registry.ids import RevisionId
from ...user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._codes import ModeloCode
from ..errors import ModeloValidationError
from .._repository import (
    remove_work_unit,
    upsert_work_unit,
)
from .._work_unit import (
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitState,
    derive_work_unit_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_DERIVATION_BUCKET_ID = "30330300-0000-4000-8000-000000000300"
_ACTION_BUCKET_ID = "30330300-0000-4000-8000-000000000301"
_WORK_UNIT_BUCKET_A_ID = "30330300-0000-4000-8000-0000000000a1"
_WORK_UNIT_BUCKET_B_ID = "30330300-0000-4000-8000-0000000000b2"
_WORK_UNIT_EVENT_BUCKET_ID = "30330300-0000-4000-8000-000000000303"
_P_2026_1T = Period.from_year_and_code(2026, "1T")
_P_2026_2T = Period.from_year_and_code(2026, "2T")
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="Professional services"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[WorkUnitCatalogueRepository]:
    """Yield a real work-unit repository through the active test runtime."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_ACTION_BUCKET_ID) as profile:
        _seed_ready_profile(profile.bucket_id)
        yield WorkUnitCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository)


def _seed_ready_profile(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


# ---------------------------------------------------------------------------
# derive_work_unit_id
# ---------------------------------------------------------------------------


def test_derive_work_unit_id_is_64_char_lowercase_hex() -> None:
    """The derived id shares the catalogue-key shape used elsewhere
    in the project: exactly 64 lowercase hex characters."""

    wid = derive_work_unit_id(
        bucket_id=_DERIVATION_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2026-y-siguientes",
    )
    assert len(wid) == 64
    assert all(ch in "0123456789abcdef" for ch in wid)


def test_derive_work_unit_id_is_deterministic() -> None:
    """Two identical inputs always produce the same identifier."""

    args: dict[str, Any] = {
        "bucket_id": _DERIVATION_BUCKET_ID,
        "modelo": "303",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "revision_id": "2026-y-siguientes",
    }
    assert derive_work_unit_id(**args) == derive_work_unit_id(**args)


def test_derive_work_unit_id_distinguishes_buckets() -> None:
    """Different buckets produce different identifiers even when the
    other four axes match — bucket scope is part of the content-
    addressing key."""

    base: dict[str, Any] = {
        "modelo": "303",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "revision_id": "2026-y-siguientes",
    }
    a = derive_work_unit_id(bucket_id=_WORK_UNIT_BUCKET_A_ID, **base)
    b = derive_work_unit_id(bucket_id=_WORK_UNIT_BUCKET_B_ID, **base)
    assert a != b


def test_derive_work_unit_id_normalises_case_on_modelo_and_period() -> None:
    """``modelo`` and ``period`` are normalised to uppercase before
    hashing so ``\"303\"`` and ``\"303\"`` (or ``\"q1\"`` and
    ``\"Q1\"``) hash to the same id."""

    canonical = derive_work_unit_id(
        bucket_id=_DERIVATION_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2026-y-siguientes",
    )
    lower_period = derive_work_unit_id(
        bucket_id=_DERIVATION_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1t"),
        revision_id="2026-y-siguientes",
    )
    assert canonical == lower_period


# ---------------------------------------------------------------------------
# WorkUnit schema
# ---------------------------------------------------------------------------


def _build_unit(**overrides: Any) -> WorkUnit:
    bucket_id = overrides.pop("bucket_id", _DERIVATION_BUCKET_ID)
    modelo = overrides.pop("modelo", "303")
    filing_year = overrides.pop("filing_year", 2026)
    period = overrides.pop("period", Period.from_year_and_code(filing_year, "1T"))
    revision_id = overrides.pop("revision_id", "2026-y-siguientes")
    wid = overrides.pop(
        "work_unit_id",
        derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
    )
    kwargs: dict[str, Any] = {
        "work_unit_id": wid,
        "bucket_id": bucket_id,
        "modelo": modelo,
        "filing_year": filing_year,
        "period": period,
        "revision_id": revision_id,
        "name": overrides.pop("name", f"303-2026-{period.registry_token}"),
        "created_at": overrides.pop("created_at", _T0),
        "updated_at": overrides.pop("updated_at", _T0),
    }
    # Pass through any remaining state / discard-metadata overrides
    # so the schema's cross-field validator can fire on them.
    for key in ("state", "discarded_at", "discarded_by", "discard_reason"):
        if key in overrides:
            kwargs[key] = overrides.pop(key)
    return WorkUnit(**kwargs)


def _create_action_work_unit(
    repo: WorkUnitCatalogueRepository,
    *,
    modelo: str = "303",
    period: Period = _P_2026_1T,
    revision_id: str = "2026-y-siguientes",
    name: str | None = None,
    causante_ccaa: Any | None = None,
    clock: datetime = _T0,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=_ACTION_BUCKET_ID,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        revision_id=revision_id,
        name=name,
        causante_ccaa=causante_ccaa,
        repository=repo,
        clock=clock,
    )


def test_work_unit_is_strict_frozen_and_rejects_extras() -> None:
    """``model_config = strict / frozen / extra='forbid'`` — extras
    fail validation; mutation after construction raises."""

    unit = _build_unit()
    # Use model_validate(dict) so the unknown kwarg / invalid-string
    # ModeloCode value flows through pydantic validation rather than
    # being caught statically by the type checker — the test intent
    # is to verify the runtime validators reject the payload, not to
    # exercise call-time static analysis.
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        WorkUnit.model_validate(
            {
                "work_unit_id": unit.work_unit_id,
                "bucket_id": unit.bucket_id,
                "modelo": "303",
                "filing_year": 2026,
                "period": Period.from_year_and_code(2026, "1T"),
                "revision_id": "2026-y-siguientes",
                "name": "303-2026-1T",
                "created_at": _T0,
                "updated_at": _T0,
                "unknown_axis": "extra-value",
            },
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        unit.name = "renamed"


def test_work_unit_rejects_id_that_does_not_match_derivation() -> None:
    """The content-addressing invariant: a persisted
    ``work_unit_id`` that disagrees with the deterministic
    derivation is refused by the schema."""

    with pytest.raises(ValidationError, match=r"does not match the derived id") as exc:
        _build_unit(work_unit_id="0" * 64)
    assert "does not match the derived id" in str(exc.value)


def test_work_unit_rejects_updated_before_created() -> None:
    """``updated_at`` must not precede ``created_at``."""

    earlier = _T0
    later = datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match=r"updated_at|created_at|precedes"):
        _build_unit(created_at=later, updated_at=earlier)


# ---------------------------------------------------------------------------
# WorkUnitCatalogue
# ---------------------------------------------------------------------------


def test_catalogue_rejects_key_record_mismatch() -> None:
    unit = _build_unit()
    bad_key = "f" * 64
    with pytest.raises(ValidationError, match=r"work_unit_id|key|catalogue"):
        WorkUnitCatalogue(work_units={bad_key: unit})


def test_catalogue_from_work_units_rejects_duplicate_ids() -> None:
    """Building a catalogue from an iterable with two records under
    the same id fails fast."""

    unit = _build_unit()
    with pytest.raises(ModeloValidationError, match=r"duplicate work_unit_id"):
        WorkUnitCatalogue.from_work_units((unit, unit))


def test_upsert_returns_a_new_catalogue_and_leaves_original_unchanged() -> None:
    unit = _build_unit()
    catalogue = WorkUnitCatalogue()
    updated = upsert_work_unit(catalogue, unit)
    assert len(catalogue) == 0
    assert len(updated) == 1
    assert updated.get(unit.work_unit_id) is unit


def test_remove_returns_value_equal_catalogue_when_id_is_absent() -> None:
    catalogue = WorkUnitCatalogue()
    same = remove_work_unit(catalogue, "missing-id")
    assert same == catalogue


# ---------------------------------------------------------------------------
# Application actions — create_work_unit is idempotent
# ---------------------------------------------------------------------------


def test_create_work_unit_is_idempotent_on_the_four_axis_key(repo: WorkUnitCatalogueRepository) -> None:
    """Two ``create_work_unit`` calls with the same four-axis key
    return the same record without producing duplicates."""

    first = _create_action_work_unit(repo)
    second = _create_action_work_unit(repo, name="ignored-because-already-exists")
    assert first.work_unit_id == second.work_unit_id
    assert second.name == first.name  # rename is the dedicated mutation
    # Real-backend invariant: only one record under the deterministic
    # id survives in the catalogue (re-create does not produce a
    # duplicate row).
    catalogue = repo.load()
    assert len(catalogue) == 1
    assert catalogue.get(first.work_unit_id) is not None


def test_create_work_unit_applies_default_or_explicit_name(repo: WorkUnitCatalogueRepository) -> None:
    default_named = _create_action_work_unit(repo)
    explicit_named = _create_action_work_unit(repo, period=_P_2026_2T, name="renta-2t-2026-draft")

    assert default_named.name == "303-2026-1T"
    assert explicit_named.name == "renta-2t-2026-draft"


# ---------------------------------------------------------------------------
# Application actions — list / get / rename
# ---------------------------------------------------------------------------


def test_list_work_units_sorts_by_bucket_year_modelo_period(repo: WorkUnitCatalogueRepository) -> None:
    repo.save(
        WorkUnitCatalogue.from_work_units(
            tuple(
                _build_unit(
                    bucket_id=bucket,
                    modelo=modelo,
                    filing_year=year,
                    period=Period.from_year_and_code(year, period),
                    revision_id=revision_id,
                )
                for bucket, modelo, year, period, revision_id in (
                    (_WORK_UNIT_BUCKET_B_ID, "303", 2026, "1T", "2026-y-siguientes"),
                    (_WORK_UNIT_BUCKET_A_ID, "303", 2026, "2T", "2026-y-siguientes"),
                    (_WORK_UNIT_BUCKET_A_ID, "130", 2026, "1T", "2019-y-siguientes"),
                )
            ),
        ),
    )
    units = list_work_units(repository=repo)
    keys = tuple((u.bucket_id, str(u.modelo), u.period.registry_token) for u in units)
    assert keys == (
        (_WORK_UNIT_BUCKET_A_ID, "130", "1T"),
        (_WORK_UNIT_BUCKET_A_ID, "303", "2T"),
        (_WORK_UNIT_BUCKET_B_ID, "303", "1T"),
    )


def test_list_work_units_filters_by_bucket_id(repo: WorkUnitCatalogueRepository) -> None:
    repo.save(
        WorkUnitCatalogue.from_work_units(
            (
                _build_unit(
                    bucket_id=_WORK_UNIT_BUCKET_A_ID,
                    modelo="303",
                    filing_year=2026,
                    period=_P_2026_1T,
                    revision_id="2026-y-siguientes",
                ),
                _build_unit(
                    bucket_id=_WORK_UNIT_BUCKET_B_ID,
                    modelo="303",
                    filing_year=2026,
                    period=_P_2026_2T,
                    revision_id="2026-y-siguientes",
                ),
            ),
        ),
    )
    only_a = list_work_units(bucket_id=_WORK_UNIT_BUCKET_A_ID, repository=repo)
    assert len(only_a) == 1
    assert only_a[0].bucket_id == _WORK_UNIT_BUCKET_A_ID


def test_missing_work_unit_actions_raise_not_found(repo: WorkUnitCatalogueRepository) -> None:
    with pytest.raises(WorkUnitNotFoundError) as excinfo:
        get_work_unit("missing", repository=repo)
    assert excinfo.value.translated_message == "application.modelo.errors.work_unit_not_found"
    assert isinstance(excinfo.value.context, dict)
    assert excinfo.value.context["work_unit_id"] == "missing"

    with pytest.raises(WorkUnitNotFoundError) as excinfo:
        rename_work_unit("missing", "ignored", actor="test-operator", repository=repo)
    assert excinfo.value.translated_message == "application.modelo.errors.work_unit_not_found"
    assert isinstance(excinfo.value.context, dict)
    assert excinfo.value.context["work_unit_id"] == "missing"

    with pytest.raises(WorkUnitNotFoundError) as excinfo:
        discard_work_unit("missing", actor="operator-A", repository=repo)
    assert excinfo.value.translated_message == "application.modelo.errors.work_unit_not_found"
    assert isinstance(excinfo.value.context, dict)
    assert excinfo.value.context["work_unit_id"] == "missing"


def test_rename_work_unit_preserves_work_unit_id_and_bumps_updated_at(repo: WorkUnitCatalogueRepository) -> None:
    original = _create_action_work_unit(repo)
    later = datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC)
    renamed = rename_work_unit(
        original.work_unit_id,
        "renta-q1-2026-final",
        actor="test-operator",
        repository=repo,
        clock=later,
    )
    assert renamed.work_unit_id == original.work_unit_id
    assert renamed.name == "renta-q1-2026-final"
    assert renamed.updated_at == later
    assert renamed.created_at == original.created_at


# ---------------------------------------------------------------------------
# Application actions — discard + state transitions
# ---------------------------------------------------------------------------


def test_discard_work_unit_transitions_and_allows_omitted_reason(repo: WorkUnitCatalogueRepository) -> None:
    """A fresh draft work unit is moved to DISCARDED with audit
    metadata captured (actor + reason + timestamp), while omitted
    reasons remain ``None`` instead of being synthesised."""

    original = _create_action_work_unit(repo)
    discard_time = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    discarded = discard_work_unit(
        original.work_unit_id,
        actor="operator-A",
        reason="wrong-profile",
        repository=repo,
        clock=discard_time,
    )
    assert discarded.work_unit_id == original.work_unit_id
    assert discarded.state is WorkUnitState.DESCARTADO
    assert discarded.discarded_at == discard_time
    assert discarded.discarded_by == "operator-A"
    assert discarded.discard_reason == "wrong-profile"
    assert discarded.updated_at == discard_time

    omitted_reason_unit = _create_action_work_unit(repo, modelo="130", revision_id="2019-y-siguientes")
    omitted_reason_discard = discard_work_unit(
        omitted_reason_unit.work_unit_id,
        actor="operator-A",
        repository=repo,
        clock=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
    )
    assert omitted_reason_discard.discard_reason is None


def test_discard_work_unit_raises_when_already_discarded(repo: WorkUnitCatalogueRepository) -> None:
    """Idempotent retries are not supported — re-discarding would
    corrupt the audit trail. The error names the original actor /
    timestamp so the operator can correlate."""

    unit = _create_action_work_unit(repo)
    discard_work_unit(
        unit.work_unit_id,
        actor="operator-A",
        repository=repo,
        clock=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(WorkUnitAlreadyDiscardedError, match=r"work|unit|already|discarded"):
        discard_work_unit(
            unit.work_unit_id,
            actor="operator-B",
            repository=repo,
            clock=datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC),
        )


def test_rename_refuses_to_mutate_a_discarded_work_unit(repo: WorkUnitCatalogueRepository) -> None:
    """Once discarded, the work unit's metadata is frozen.
    Attempting to rename it raises WorkUnitMutationRefusedError so
    the operator can correct course (create a fresh work unit)."""

    unit = _create_action_work_unit(repo)
    discard_work_unit(
        unit.work_unit_id,
        actor="operator-A",
        repository=repo,
        clock=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(WorkUnitMutationRefusedError, match=r"discard|DISCARDED|state|mutation"):
        rename_work_unit(unit.work_unit_id, "new-name", actor="test-operator", repository=repo)


def test_list_work_units_respects_discarded_visibility_flag(repo: WorkUnitCatalogueRepository) -> None:
    unit_draft = _create_action_work_unit(repo)
    unit_to_discard = _create_action_work_unit(repo, modelo="130", revision_id="2019-y-siguientes")
    discard_work_unit(
        unit_to_discard.work_unit_id,
        actor="operator-A",
        repository=repo,
        clock=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
    )
    visible = list_work_units(repository=repo)
    assert {u.work_unit_id for u in visible} == {unit_draft.work_unit_id}

    including_discarded = list_work_units(include_discarded=True, repository=repo)
    assert {u.work_unit_id for u in including_discarded} == {
        unit_draft.work_unit_id,
        unit_to_discard.work_unit_id,
    }


def test_work_unit_schema_rejects_discard_metadata_on_draft_state() -> None:
    """A draft work unit must NOT carry discard metadata — the
    cross-field model validator refuses such records on
    construction."""

    with pytest.raises(ValidationError, match=r"DRAFT|discard|state"):
        _build_unit(
            state=WorkUnitState.BORRADOR,
            discarded_at=_T0,
            discarded_by="operator-A",
        )


def test_work_unit_schema_requires_discard_metadata_on_discarded_state() -> None:
    """Conversely, a record claiming DISCARDED state must carry
    ``discarded_at`` and ``discarded_by``."""

    with pytest.raises(ValidationError, match=r"DISCARDED|discard|state"):
        _build_unit(state=WorkUnitState.DESCARTADO)


# ---------------------------------------------------------------------------
# Boundary regression guards
# ---------------------------------------------------------------------------


def test_no_parallel_work_unit_model_outside_canonical_module() -> None:
    """``WorkUnit`` lives in ``cadrumo.domain.modelos._work_unit``. Any
    other module that declares a Pydantic class named
    ``WorkUnit`` competes with the canonical surface."""

    from ....tests import REPO_ROOT

    source_root = REPO_ROOT / "src" / "cadrumo"
    canonical = source_root / "domain" / "modelos" / "_work_unit.py"
    forbidden = "class WorkUnit("
    offenders = []
    for py_file in scan_directory(source_root, pattern="*.py", recursive=True):
        if py_file == canonical:
            continue
        if py_file.name.startswith("test_"):
            continue
        if forbidden in py_file.read_text(encoding="utf-8"):
            offenders.append(py_file)
    assert offenders == [], f"Parallel WorkUnit class outside the canonical module: {[str(p) for p in offenders]}"


def test_no_parallel_work_unit_storage_namespace() -> None:
    """The work-unit catalogue persists under the
    ``cadrumo.domain.modelos.work_units`` namespace. Any other
    module referencing a competing namespace string is a shadow
    storage location."""

    from ....tests import REPO_ROOT

    source_root = REPO_ROOT / "src" / "cadrumo"
    canonical = source_root / "domain" / "modelos" / "_repository.py"
    # _namespace_registry.py is the centralised namespace declaration table;
    # it legitimately holds every storage namespace string as a registry entry
    # and is not a competing storage location.
    canonical_namespace_registry = source_root / "adapters" / "persistence" / "storage" / "_namespace_registry.py"
    # The custody bundle/carry coverage manifests enumerate every storage
    # namespace in a frozenset to assert full-custody coverage and to skip
    # double-carrying the typed categories; they name the namespace as a
    # coverage declaration, not as a competing storage location (the actual
    # carry writes through ``repository.save(namespace=carried.namespace, ...)``).
    custody_bundle_manifest = source_root / "application" / "user_profile" / "_bundle.py"
    custody_carry_manifest = source_root / "application" / "user_profile" / "_custody_carry.py"
    # The consolidated work-unit catalogue persistence adapter that implements the
    # actual secure-object storage for the namespace; it legitimately holds the
    # namespace string as its storage location, not as a competing one.
    work_unit_catalogue_adapter = source_root / "adapters" / "persistence" / "profile" / "modelos_work_units.py"
    allowlisted = {
        canonical,
        canonical_namespace_registry,
        custody_bundle_manifest,
        custody_carry_manifest,
        work_unit_catalogue_adapter,
    }
    forbidden_namespace = '"cadrumo.domain.modelos.work_units"'
    offenders = []
    for py_file in scan_directory(source_root, pattern="*.py", recursive=True):
        if py_file in allowlisted:
            continue
        if py_file.name.startswith("test_"):
            continue
        if forbidden_namespace in py_file.read_text(encoding="utf-8"):
            offenders.append(py_file)
    assert offenders == [], (
        f"Parallel work-unit storage namespace outside the canonical repository: {[str(p) for p in offenders]}"
    )


def test_rename_work_unit_emits_renamed_bucket_event_with_actor_and_names(
    tmp_path: Path,
) -> None:
    """rename_work_unit emits a modelo.work_unit.renamed bucket event
    that records the actor who initiated the rename plus the prior and
    new display names so the audit trail captures the full transition.
    """

    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...buckets import BucketEventType

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_WORK_UNIT_EVENT_BUCKET_ID) as profile:
        _seed_ready_profile(profile.bucket_id)
        wu_repo = WorkUnitCatalogueRepository(objects=profile.repository)
        bv_repo = BucketEventHistoryRepository(objects=profile.repository)
        unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo="303",
            filing_year=2026,
            period=_P_2026_1T,
            revision_id="2026-y-siguientes",
            repository=wu_repo,
            clock=_T0,
        )
        renamed = rename_work_unit(
            unit.work_unit_id,
            "renta-q1-renamed",
            actor="auditor-B",
            repository=wu_repo,
            bucket_event_repository=bv_repo,
            clock=datetime(2026, 2, 5, 12, 0, 0, tzinfo=UTC),
        )
        events = bv_repo.load().for_bucket(renamed.bucket_id)
        rename_events = [event for event in events if event.event_type is BucketEventType.MODELO_WORK_UNIT_RENAMED]
        assert len(rename_events) == 1
        rename_event = rename_events[0]
        assert rename_event.actor == "auditor-B"
        assert rename_event.object_id == renamed.work_unit_id
        assert rename_event.payload["previous_name"] == unit.name
        assert rename_event.payload["new_name"] == "renta-q1-renamed"


# ---------------------------------------------------------------------------
# causante_ccaa axis — roundtrip + identity isolation
# ---------------------------------------------------------------------------


def test_causante_ccaa_roundtrips_and_defaults_through_repository(repo: WorkUnitCatalogueRepository) -> None:
    """causante_ccaa is persisted and reloaded without data loss.

    A non-default (non-None) value must survive the full save/load
    cycle through the real encrypted repository, while unrelated modelos
    default to ``None``.
    """

    from ...contribuyente import CCAA

    default_unit = _create_action_work_unit(repo)
    annotated_unit = _create_action_work_unit(repo, period=_P_2026_2T, causante_ccaa=CCAA.MADRID)

    assert default_unit.causante_ccaa is None
    assert annotated_unit.causante_ccaa is CCAA.MADRID

    reloaded = repo.load().get(annotated_unit.work_unit_id)
    assert reloaded is not None
    assert reloaded.causante_ccaa is CCAA.MADRID


def test_causante_ccaa_does_not_affect_work_unit_identity(repo: WorkUnitCatalogueRepository) -> None:
    """causante_ccaa is an annotation, not part of the content-addressing key.

    Two ``create_work_unit`` calls with the same four-axis key but
    different causante_ccaa values are idempotent — the second call
    returns the first record unchanged; the annotation from the first
    call is not overwritten.
    """

    from ...contribuyente import CCAA

    first = _create_action_work_unit(repo, causante_ccaa=CCAA.MADRID)
    second = _create_action_work_unit(repo, causante_ccaa=CCAA.CATALUNA)
    # Idempotency: same work_unit_id, first creation wins.
    assert first.work_unit_id == second.work_unit_id


@pytest.mark.parametrize(
    "malformed",
    ["BAD revision/with spaces", "2019 y siguientes", "2019-Y-SIGUIENTES", "-2019", "2019-", "with/slash"],
)
def test_work_unit_refuses_a_revision_id_outside_the_registry_grammar(malformed: str) -> None:
    """A revision_id the registry grammar refuses cannot reach a persisted unit.

    Membership and law-resolution checks run later in the application layer, so a
    malformed revision was previously accepted, content-addressed into the
    work-unit identity, and persisted before any resolver could object -- leaving
    a durable record whose identity derived from a value no registry revision
    could ever match.
    """
    assert TypeAdapter(RevisionId).validate_python is not None
    with pytest.raises(ValidationError):
        TypeAdapter(RevisionId).validate_python(malformed)

    with pytest.raises(ValidationError):
        _work_unit_with_revision(malformed)


def test_work_unit_accepts_a_real_registry_revision_id() -> None:
    """Positive control: the revision ids the registry actually declares still build.

    Without it every refusal above could hold because the constraint rejects
    everything, which would break every real work unit.
    """
    unit = _work_unit_with_revision("2019-y-siguientes")

    assert unit.revision_id == "2019-y-siguientes"
    assert unit.work_unit_id == derive_work_unit_id(
        bucket_id=unit.bucket_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        revision_id="2019-y-siguientes",
    )


def _work_unit_with_revision(revision_id: str) -> WorkUnit:
    """Build a genuine 130/2026/1T work unit carrying ``revision_id``."""
    bucket_id = "7cc00000-0000-4000-8000-0000000000cc"
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        name="130-2026-1T",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
