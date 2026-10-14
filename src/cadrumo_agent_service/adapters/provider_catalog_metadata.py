"""Project the bundled agent's deterministic metadata through its public v1 DTO."""

from __future__ import annotations

import base64
import hashlib
from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from ..providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason

_MODULES = (
    "cadrumo_agent.api.schemas.provider_catalog",
    "cadrumo_agent.providers.served_catalog",
    "cadrumo_agent.providers.registry",
    "cadrumo_agent.providers.execution_modes",
    "cadrumo_agent.providers.provider_catalog",
    "cadrumo_agent.providers.catalog_recommendation",
    "cadrumo_agent.providers.effort",
    "cadrumo_agent.control.config",
)


def _cohort_modules() -> dict[str, Any]:
    """Refuse missing, editable or shadowed agent code before loading metadata APIs."""
    try:
        agent = distribution("cadrumo-agent")
        application = distribution("cadrumo")
        base = Path(str(agent.locate_file(""))).resolve(strict=True)
        if base != Path(str(application.locate_file(""))).resolve(strict=True):
            raise ValueError("different_wheel_cohort")
        records = {str(item).replace("\\", "/"): item for item in agent.files or ()}
        for module_name in ("cadrumo_agent", *_MODULES):
            spec = find_spec(module_name)
            if spec is None or spec.origin is None:
                raise ValueError("agent_module_unavailable")
            path = Path(spec.origin).resolve(strict=True)
            relative = path.relative_to(base).as_posix()
            record = records.get(relative)
            if record is None or record.hash is None or record.hash.mode != "sha256":
                raise ValueError("agent_module_not_in_wheel")
            digest = base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest()).rstrip(b"=").decode("ascii")
            if digest != record.hash.value:
                raise ValueError("agent_module_changed")
        return {name: import_module(name) for name in _MODULES}
    except (PackageNotFoundError, ImportError, OSError, ValueError) as error:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND) from error


def declared_provider_catalog_response(*, agent_source: str | None) -> dict[str, Any]:
    """Return actual model/control declarations with explicitly unobserved host readiness.

    This does not instantiate agent settings, resolve credentials, read provider
    homes, run readiness probes or start a model. The owning agent's schema
    validates every returned field. Readiness and capability evidence remain
    unknown until the running agent observes them.
    """
    if agent_source is not None:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND)
    modules = _cohort_modules()
    schema = modules["cadrumo_agent.api.schemas.provider_catalog"]
    catalogs = modules["cadrumo_agent.providers.served_catalog"]
    registry = modules["cadrumo_agent.providers.registry"]
    modes = modules["cadrumo_agent.providers.execution_modes"]
    records = modules["cadrumo_agent.providers.provider_catalog"]
    recommendations = modules["cadrumo_agent.providers.catalog_recommendation"]
    efforts = modules["cadrumo_agent.providers.effort"]
    configuration = modules["cadrumo_agent.control.config"]
    backend = configuration.Settings.model_fields["acp_backend"].default
    providers = []
    try:
        for lane in modes.EXTERNAL_EXECUTION_MODES:
            descriptor = registry.PROVIDERS[lane]
            mode = modes.external_execution_mode(lane, backend)
            catalog = catalogs.lane_catalog(lane, records.ProviderCatalogKey(lane.value, mode))
            controls = {control.control_id: control for control in catalog.native_controls}
            models = []
            for model in catalog.models:
                effort = efforts.effort_control(model, controls)
                models.append(
                    schema.ProviderCatalogEntryResponse(
                        entry_id=model.entry_id,
                        model=model.provider_value,
                        display_name=model.display_name,
                        description=model.description,
                        capabilities=list(model.capabilities),
                        native_control_ids=list(model.native_control_ids),
                        efforts=list(efforts.offered_efforts(effort)),
                        default_effort=efforts.default_effort(effort),
                    )
                )
            native_controls = [
                schema.ProviderNativeControlResponse(
                    control_id=control.control_id,
                    kind=control.kind,
                    display_name=control.display_name,
                    options=[
                        schema.ProviderNativeControlOptionResponse(
                            option_id=option.option_id,
                            display_name=option.display_name,
                            description=option.description,
                        )
                        for option in control.options
                    ],
                    default_option_id=control.default_option_id,
                    description=control.description,
                )
                for control in catalog.native_controls
            ]
            providers.append(
                schema.ProviderCatalogRecordResponse(
                    provider_id=descriptor.provider.provider,
                    transport=descriptor.provider.transport,
                    display_name=descriptor.display_name,
                    execution_mode=mode,
                    executable=descriptor.executable,
                    model_source=descriptor.model_source.value,
                    health=schema.ProviderHealthResponse(
                        configured=records.HealthState.UNKNOWN,
                        transport=records.HealthState.UNKNOWN,
                        authentication=records.AuthenticationState.UNKNOWN,
                        catalog=catalog.state.status,
                        admission=records.AdmissionState.UNKNOWN,
                        selectable=False,
                        reasons=[],
                        checked_at=catalog.state.checked_at,
                    ),
                    catalog=schema.ProviderLaneCatalogResponse(
                        state=schema.ProviderCatalogStateResponse(
                            status=catalog.state.status,
                            checked_at=catalog.state.checked_at,
                            revision=catalog.state.revision,
                            expires_at=catalog.state.expires_at,
                            reason=catalog.state.reason,
                        ),
                        recommended_entry_id=recommendations.recommended_entry_id(catalog),
                        models=models,
                        native_controls=native_controls,
                    ),
                    capability_proofs=[],
                )
            )
        return schema.ProviderCatalogResponse(providers=providers).model_dump(mode="json")
    except Exception as error:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED) from error
