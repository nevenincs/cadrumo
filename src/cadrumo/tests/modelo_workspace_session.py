"""Public real-storage construction support for modelo workspace destinations.

Entrypoint tests consume this defining test-support module directly. It is not
an application-layer test helper or a package facade.

The seeding here previously existed only as a fixture inside the workspace view
tests' own conftest, which made it reachable from exactly one package. A second
suite needing a real admitted session -- the responsive-geometry proof over
every routed destination -- would otherwise have had to copy the profile facts,
the work-unit creation and the static-inspection resolution, and a copied
fixture agrees with its original only until one of them is edited. It lives
here for the same reason ``modelo_work_review`` does: more than one entrypoint
suite needs real encrypted storage behind the same screens.

The seeded taxpayer is deliberately a COMPLETE one. A workspace session refuses
admission for an incomplete profile, so a partial fixture would exercise the
refusal path in every test that meant to exercise a rendered destination -- and
a refusal renders a small surface that fits at any size, which would let a
geometry proof pass while proving nothing about the screens it names.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ..application.modelo.work_addressing import ModeloVisibleFilingTarget
from ..application.modelo.work_lifecycle import create_work_unit
from ..application.modelo.workspace import resolve_static_inspection_result
from ..application.modelo.workspace_models import ModeloWorkspaceResultV1, ModeloWorkspaceVisibleFilingTargetV1
from ..core.external_constants import OutputLanguage
from ..core.period import Period
from ..domain.calculations.registry.authority import bundled_authority
from ..domain.calculations.registry.temporal import select_revision
from ..domain.modelos.codes import ModeloCode
from ..domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .profile_capsule import seed_test_profile_record
from .secure_sql import isolated_runtime_profile

_BUCKET_ID = "13000000-0000-4000-8000-000000000451"
_REVISION = "2019-y-siguientes"
_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_MODELO = "130"
_FILING_YEAR = 2026
_PERIOD_CODE = "1T"

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Workspace"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


@dataclass(frozen=True, slots=True)
class _SeededWorkspace:
    """One seeded address, with the door to resolve it again at any language.

    Both halves are needed and neither substitutes for the other. ``result``
    is the ordinary single-language read. ``resolve`` exists because a locale
    comparison must hold the SAME seeded storage across every language it
    compares: resolving four languages from four separately seeded profiles
    would differ in bucket identity and creation instants, so any difference
    found could not be attributed to language.
    """

    resolve: Callable[[OutputLanguage], ModeloWorkspaceResultV1]
    result: ModeloWorkspaceResultV1


@contextmanager
def real_workspace_inspection_result(
    tmp_path: Path,
    *,
    language: OutputLanguage = OutputLanguage.ES,
    modelo: str = _MODELO,
    filing_year: int = _FILING_YEAR,
    period_code: str = _PERIOD_CODE,
    revision_id: str | None = None,
) -> Iterator[_SeededWorkspace]:
    """Yield one seeded workspace address over isolated encrypted storage.

    Held open as a context manager rather than returned, because the profile
    runtime must stay live for the whole test body: the workspace screens read
    through the capsule when they render, not only when the result is built.

    The address is a parameter so a caller can choose the SHAPE of the data it
    needs without synthesising any. A small quarterly modelo gives a compact
    session; a large annual one gives long labels, deeply nested sections and
    row counts past a single page. Both come from the bundled registry, so an
    adversarial layout case is real declared content rather than padding a
    fixture with invented rows -- which would prove the layout against data the
    product never produces.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        period = Period.from_year_and_code(filing_year, period_code)
        authority = bundled_authority()
        # Selected from the authority when the caller does not pin one, so a
        # caller choosing an address does not also have to know which revision
        # governs it -- a hand-written revision id is the shape that goes stale
        # silently when the legal window moves.
        selected_revision = revision_id or select_revision(
            authority.validate_modelo(ModeloCode(modelo)),
            filing_year=filing_year,
            period=period.registry_token,
        ).id
        create_work_unit(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=selected_revision,
            repository=repository,
            clock=_T0,
        )

        def resolve(at_language: OutputLanguage) -> ModeloWorkspaceResultV1:
            """Resolve the seeded address again at one language."""
            return resolve_static_inspection_result(
                ModeloWorkspaceVisibleFilingTargetV1(
                    target=ModeloVisibleFilingTarget(
                        modelo=modelo,
                        filing_year=filing_year,
                        period=period,
                    )
                ),
                bucket_id=profile.bucket_id,
                catalogue_repository=repository,
                authority=authority,
                output_language=at_language,
            )

        yield _SeededWorkspace(resolve=resolve, result=resolve(language))
