"""Compose the existing profile manager over one exact runtime session."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....adapters.local_runtime.profile_mutations import (
    ProfileMutationCompletion,
    ProfileMutationRequest,
    run_profile_mutation,
)
from ....application.auth.operation_definitions import AuthConfigureOperationRequest
from ....application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from ....application.live.filed_history_operation import FILED_HISTORY_OPERATION_DEFINITION_ID
from ....application.operations.registry import OperationFrontendProjection
from ....application.operator_actions.models import ActionReference
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.acquisition_sources import ProfileAcquisitionSourceKey, ProfileAcquisitionSourceV1
from ....application.user_profile.censal_operation import CENSAL_OPERATION_DEFINITION_ID
from ....application.user_profile.completeness import AUTH_PROVIDER_PATH, CLAVE_MOVIL_ROUTE_PATH
from ....application.user_profile.overview import ProfileOverview
from ....application.user_profile.profile_operation_contracts import (
    ProfileCompleteSetupOperationProjection,
    ProfileCompleteSetupOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationProjection,
    ProfilePlantillaMediaOperationProjection,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaRemove,
    ProfilePlantillaMediaSet,
    ProfileRepeatableRowChangeOperationProjection,
    ProfileRepeatableRowMutationOperationProjection,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
    ProfileRepeatableRowValue,
)
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ....core.config import load_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.operations import OperationTerminalCondition
from ....domain.user_profile.errors import UserProfileValidationError
from ....domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear, plantilla_media_years
from ..aeat_sync.models import AeatSyncOperationRequestV1
from ..aeat_sync.runtime_handoff import compose_runtime_aeat_sync_handoff
from ..operations.modal import OperationModal, OperationModalOutcomeV1, OperationModalSettledOutcomeV1
from .overview import ProfileManagerScreen
from .runtime_auth_configuration import configure_runtime_auth
from .runtime_errors import ProfileManagerCompletedViewUnavailableError
from .runtime_overview import read_runtime_profile_overview

type _MutationRunner = Callable[[RuntimeFrontendClient, ProfileMutationRequest], ProfileMutationCompletion]
type _OverviewReader = Callable[[RuntimeFrontendClient, str, OutputLanguage], ProfileOverview]
type _AuthConfigurer = Callable[[RuntimeFrontendClient, AuthConfigureOperationRequest], AuthConfigurePublicResultV2]


def _read_overview(client: RuntimeFrontendClient, label: str, language: OutputLanguage) -> ProfileOverview:
    return read_runtime_profile_overview(client, profile_label=label, output_language=language)


def _require_projection_identity(
    projection: ProfileMutationOperationProjection,
    projection_type: type[ProfileMutationOperationProjection],
    profile_id: object,
    request: ProfileMutationRequest,
) -> None:
    if (
        type(projection) is not projection_type
        or projection.profile_id != profile_id
        or projection.record_revision < request.expected_revision
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _require_section_key(
    projection: ProfileMutationOperationProjection,
    section_key: str | None,
) -> None:
    row_projections = (ProfileRepeatableRowMutationOperationProjection, ProfileRepeatableRowChangeOperationProjection)
    if section_key is not None and (
        not isinstance(projection, row_projections) or projection.section_key != section_key
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _require_row_key(
    projection: ProfileMutationOperationProjection,
    row_key: str | None,
) -> None:
    if row_key is not None and (
        not isinstance(projection, ProfileRepeatableRowChangeOperationProjection) or projection.row_key != row_key
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _require_media_year(
    projection: ProfileMutationOperationProjection,
    year: int | None,
) -> None:
    if year is not None and (
        not isinstance(projection, ProfilePlantillaMediaOperationProjection) or projection.year != year
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


class RuntimeProfileManagerComposition:
    """Pin one TUI lease and supply the existing manager's synchronous doors."""

    def __init__(
        self,
        client: RuntimeFrontendClient,
        *,
        profile_label: str,
        output_language: OutputLanguage,
        mutation_runner: _MutationRunner = run_profile_mutation,
        overview_reader: _OverviewReader = _read_overview,
        auth_configurer: _AuthConfigurer = configure_runtime_auth,
    ) -> None:
        """Bind exact client coordinates and the supplied runtime doors."""
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
        self.client = client
        self.profile_id = client.profile_id
        self.session_id = client.session_id
        self.profile_label = profile_label
        self.output_language = output_language
        self._mutation_runner = mutation_runner
        self._overview_reader = overview_reader
        self._auth_configurer = auth_configurer
        self.screen: ProfileManagerScreen | None = None

    def _pin(self) -> None:
        if self.client.profile_id != self.profile_id or self.client.frontend is not OperationFrontendProjection.TUI:
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        if self.client.session_id != self.session_id:
            raise RuntimeFrontendRefusedError(AccessDenialCode.SESSION_INACTIVE.value)

    def _overview(self) -> ProfileOverview:
        self._pin()
        overview = self._overview_reader(self.client, self.profile_label, self.output_language)
        self._pin()
        if overview.profile_id != str(self.profile_id):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return overview

    def _current(self) -> ProfileOverview:
        screen = self.screen
        if screen is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return screen.overview

    def _mutate(
        self,
        request: ProfileMutationRequest,
        projection_type: type[ProfileMutationOperationProjection],
        *,
        section_key: str | None = None,
        row_key: str | None = None,
        year: int | None = None,
    ) -> ProfileOverview:
        self._pin()
        if request.profile_id != self.profile_id:
            raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        completed = self._mutation_runner(self.client, request)
        try:
            projection = completed.projection
            _require_projection_identity(projection, projection_type, self.profile_id, request)
            _require_section_key(projection, section_key)
            _require_row_key(projection, row_key)
            _require_media_year(projection, year)
            current = self._overview()
            if current.record_revision < projection.record_revision:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return current
        except Exception as error:
            raise ProfileManagerCompletedViewUnavailableError(completed) from error

    def _field(self, path: str, value: str, revision: int, digest: str) -> ProfileOverview:
        if path in {AUTH_PROVIDER_PATH, CLAVE_MOVIL_ROUTE_PATH}:
            configured = self._configure_auth(path, value, revision, digest)
            if configured is not None:
                return configured
        return self._mutate(
            ProfileFieldMutationOperationRequest(
                profile_id=self.profile_id,
                expected_revision=revision,
                expected_content_digest=digest,
                path=path,
                value=value,
            ),
            ProfileMutationOperationProjection,
        )

    def _configure_auth(self, path: str, value: str, revision: int, digest: str) -> ProfileOverview | None:
        """Save the provider or Cl@ve Móvil route through the shared authentication configuration.

        ``None`` leaves an ordinary field save: no provider is chosen yet, or a
        route is set while another provider is configured.
        """
        current = self._overview()
        stored = next(
            (
                field.value
                for section in current.sections
                for field in section.fields
                if field.path == AUTH_PROVIDER_PATH
            ),
            None,
        )
        provider = value if path == AUTH_PROVIDER_PATH else (stored or "")
        if not provider or (path == CLAVE_MOVIL_ROUTE_PATH and provider != AuthProviderKind.CLAVE_MOVIL.value):
            return None
        self._pin()
        self._auth_configurer(
            self.client,
            AuthConfigureOperationRequest(
                provider=AuthProviderKind(provider),
                clave_movil_route=ClaveMovilRoute(value) if path == CLAVE_MOVIL_ROUTE_PATH else None,
                expected_profile_revision=revision,
                expected_profile_digest=digest,
            ),
        )
        return self._overview()

    def _add_row(self, section: str, values: Mapping[str, str], revision: int, digest: str) -> ProfileOverview:
        return self._mutate(
            ProfileRepeatableRowMutationOperationRequest(
                profile_id=self.profile_id,
                expected_revision=revision,
                expected_content_digest=digest,
                section_key=section,
                values=tuple(
                    ProfileRepeatableRowValue(field_key=key, value=value) for key, value in sorted(values.items())
                ),
            ),
            ProfileRepeatableRowMutationOperationProjection,
            section_key=section,
        )

    def _update_row(
        self,
        section: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        return self._mutate(
            ProfileRepeatableRowUpdateOperationRequest(
                profile_id=self.profile_id,
                expected_revision=revision,
                expected_content_digest=digest,
                section_key=section,
                row_key=row_key,
                values=tuple(
                    ProfileRepeatableRowValue(field_key=key, value=value) for key, value in sorted(values.items())
                ),
                clear_fields=tuple(clear_fields),
            ),
            ProfileRepeatableRowChangeOperationProjection,
            section_key=section,
            row_key=row_key,
        )

    def _remove_row(self, section: str, row_key: str, revision: int, digest: str) -> ProfileOverview:
        return self._mutate(
            ProfileRepeatableRowRemoveOperationRequest(
                profile_id=self.profile_id,
                expected_revision=revision,
                expected_content_digest=digest,
                section_key=section,
                row_key=row_key,
            ),
            ProfileRepeatableRowChangeOperationProjection,
            section_key=section,
            row_key=row_key,
        )

    def _complete_setup(self) -> ProfileOverview:
        baseline = self._current()
        return self._mutate(
            ProfileCompleteSetupOperationRequest(
                profile_id=self.profile_id,
                expected_revision=baseline.record_revision,
                expected_content_digest=baseline.content_digest,
            ),
            ProfileCompleteSetupOperationProjection,
        )

    def _list_plantilla_media(self) -> tuple[PlantillaMediaYear, ...]:
        self._pin()
        collection = self.client.read_profile_view((ProfileViewPageKind.FACTS,), output_language=self.output_language)
        self._pin()
        if collection.profile_id != self.profile_id or collection.page_kinds != (ProfileViewPageKind.FACTS,):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        items = collection.items(ProfileViewPageKind.FACTS)
        if not all(isinstance(item, ProfileViewFactItem) for item in items):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        values = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
        if len(values) != len(items):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            return plantilla_media_years(values)
        except UserProfileValidationError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None

    def _set_plantilla_media(self, year: int, amount: Decimal, state: PlantillaMediaState) -> ProfileOverview:
        baseline = self._current()
        return self._mutate(
            ProfilePlantillaMediaOperationRequest(
                profile_id=self.profile_id,
                expected_revision=baseline.record_revision,
                expected_content_digest=baseline.content_digest,
                year=year,
                change=ProfilePlantillaMediaSet(average_workforce=str(amount), state=state),
            ),
            ProfilePlantillaMediaOperationProjection,
            year=year,
        )

    def _remove_plantilla_media(self, year: int) -> ProfileOverview:
        baseline = self._current()
        return self._mutate(
            ProfilePlantillaMediaOperationRequest(
                profile_id=self.profile_id,
                expected_revision=baseline.record_revision,
                expected_content_digest=baseline.content_digest,
                year=year,
                change=ProfilePlantillaMediaRemove(),
            ),
            ProfilePlantillaMediaOperationProjection,
            year=year,
        )

    def compose(self) -> ProfileManagerScreen:
        """Read the first overview before the screen enters Textual's event loop."""
        return self.compose_from_overview(self._overview())

    async def _launch_source(self, source: ProfileAcquisitionSourceV1) -> None:
        """Run onboarding acquisition through the same admitted workbench doors."""
        self._pin()
        screen = self.screen
        if screen is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if source.key is ProfileAcquisitionSourceKey.CENSAL_REVIEW:
            request = AeatSyncOperationRequestV1(
                action=ActionReference(action_id="operator.profile.edit"),
                operation=CENSAL_OPERATION_DEFINITION_ID,
            )
        else:
            request = AeatSyncOperationRequestV1(
                action=ActionReference(action_id="operator.live.filed.pull_all"),
                operation=FILED_HISTORY_OPERATION_DEFINITION_ID,
            )
        screen.disabled = True
        try:
            handoff, _ = await asyncio.to_thread(
                compose_runtime_aeat_sync_handoff,
                self.client,
                output_root=load_settings().cadrumo_filed_declarations_dir,
            )
            self._pin()
            if handoff is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            controller = await handoff(request)
            screen.app.push_screen(OperationModal(controller), self._source_settled)
        except Exception:
            # Runtime diagnostics can carry private provider evidence.
            screen.notify(tr("tui.aeat_sync.operation.failed"), severity="error")
        finally:
            screen.disabled = False

    async def _source_settled(self, outcome: OperationModalOutcomeV1 | None) -> None:
        """Read persisted profile facts again after a successful acquisition."""
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            return
        screen = self.screen
        if screen is None:
            return
        if outcome.view_model.projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            screen.notify(outcome.error_explanation or tr("tui.aeat_sync.operation.failed"), severity="error")
            return
        try:
            updated = await asyncio.to_thread(self._overview)
            self._pin()
            await screen._apply_overview(updated)
        except Exception:
            screen.notify(tr("tui.aeat_sync.operation.failed"), severity="error")

    def compose_from_overview(self, overview: ProfileOverview) -> ProfileManagerScreen:
        """Bind an already read exact-profile overview without blocking the UI."""
        self._pin()
        if overview.profile_id != str(self.profile_id):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        screen = ProfileManagerScreen(
            overview,
            persist=self._field,
            add_row=self._add_row,
            update_row=self._update_row,
            remove_row=self._remove_row,
            complete_setup=self._complete_setup,
            list_plantilla_media=self._list_plantilla_media,
            set_plantilla_media=self._set_plantilla_media,
            remove_plantilla_media=self._remove_plantilla_media,
            launch_source=self._launch_source,
        )
        self.screen = screen
        return screen


__all__ = [
    "RuntimeProfileManagerComposition",
]
