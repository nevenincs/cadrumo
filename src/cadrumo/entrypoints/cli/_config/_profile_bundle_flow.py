"""Interactive flow surface for the profile bundle export / import verbs.

``aeat config profile export`` and ``import`` gain an interactive mode:
when the operator omits the destination / transport (export) or the
bundle path (import) on a host that can prompt, a small
:class:`~cadrumo.application.flows.FlowDefinition` collects exactly the
missing answers and hands them back to the command, which then routes
through the identical canonical path a fully-specified invocation takes
(:func:`~cadrumo.application.user_profile.export_profile_bundle`, the
import validation gates, and :func:`~cadrumo.application.user_profile.deserialize_profile_bundle`).
This module builds and drives the definitions only — it performs no
serialization, no persistence, and no passphrase collection.

The bundle passphrase deliberately never enters a flow page: the shared
:mod:`._secure_input` channel (hidden confirm-retype prompt or one
bounded ``--secrets-stdin`` object) stays the single passphrase
authority, so no secret ever lands in a :class:`FlowState` answer map.
Both definitions declare checkpointing UNAVAILABLE in every mode for the
same reason: nothing collected here may be persisted mid-run.

Frontend choice is the substrate's single selection primitive —
:func:`~cadrumo.application.flows.detect_frontend_capability` classifies
the host and :func:`~cadrumo.adapters.inbound.tui.select_flow_frontend`
constructs the full-screen Textual app or the line-mode frontend; a
non-interactive host never reaches this module (the command keeps its
typed refusal instead).

Profile display names are data, not prose: the export profile SELECT
resolves its choice labels through a per-run ``SCHEMA_FIELD`` copy table
served by this module's registered resolver, mirroring the
modelo-work-wizard pattern, so the definition itself carries references
only. Static prose stays in the locale catalogues via ``LOCALE_KEY``
references.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel

from ....application.flows import (
    CopyRef,
    FlowChoice,
    FlowDefinition,
    FlowPage,
    FlowRunAbandonedError,
    FlowSection,
    LineFlowFrontend,
    detect_frontend_capability,
    register_copy_source,
)
from ....core import STRICT_FROZEN_CONFIG
from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
    FrontendCapability,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ....application.flows import FlowState
    from ....application.workflow import ProfileBucketPointer

_COPY_NAMESPACE = "profile-bundle"

_ACTIVE_RUNS: dict[str, dict[str, str]] = {}
"""Per-run copy tables for profile display names, keyed by run token.

Every reference embeds its run token
(``profile-bundle:<run-token>:<entry>``) so the registered resolver reads
only the addressed run's table; two interleaved runs in one process never
clear each other's entries, and each table is dropped at its own run end.
"""


def _resolve_profile_bundle_copy(ref: str) -> str | None:
    prefix = f"{_COPY_NAMESPACE}:"
    if not ref.startswith(prefix):
        return None
    run_token, _, _ = ref[len(prefix) :].partition(":")
    table = _ACTIVE_RUNS.get(run_token)
    return table.get(ref) if table is not None else None


register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_profile_bundle_copy)


@contextmanager
def registered_run_copy_table(run_token: str) -> Iterator[dict[str, str]]:
    """Register the per-run copy table for ``run_token``, dropping it at run end.

    The collector wraps its whole flow run in this; a frontend-level test
    that renders a definition directly uses the same seam so the profile
    choice labels resolve through the production resolver.
    """
    table: dict[str, str] = {}
    _ACTIVE_RUNS[run_token] = table
    try:
        yield table
    finally:
        _ACTIVE_RUNS.pop(run_token, None)


class _ProfileBundleFlowAnswers(BaseModel):
    """Empty typed shell: the commands read answers off the flow state directly."""

    model_config = STRICT_FROZEN_CONFIG


_EXPORT_PROFILE_PAGE = "profile"
_EXPORT_DESTINATION_PAGE = "destination"
_EXPORT_TRANSPORT_PAGE = "transport"
_IMPORT_PATH_PAGE = "bundle-path"
_IMPORT_LABEL_PAGE = "label"

_NO_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


@dataclass(frozen=True, slots=True)
class ExportFlowRequest:
    """Answers an interactive export run collected for the command to act on."""

    profile_name: str | None
    destination: Path
    encrypt: bool


@dataclass(frozen=True, slots=True)
class ImportFlowRequest:
    """Answers an interactive import run collected for the command to act on."""

    path: Path
    label: str | None


def _locale_ref(key: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


def build_export_flow_definition(
    *,
    run_token: str,
    copy_table: dict[str, str],
    profile_labels: tuple[str, ...],
    active_label: str | None,
    include_profile_page: bool,
    include_destination_page: bool,
    include_transport_page: bool,
) -> FlowDefinition:
    """Build the export definition carrying exactly the missing pages.

    ``profile_labels`` feeds the profile SELECT through the addressed
    run's copy table (labels are data — the choice label reference
    resolves to the display name itself); the page is built only when
    the command received no NAME argument and at least one profile
    exists. ``active_label`` pre-selects the active profile.
    """
    from ....application.user_profile import ProfileBundleExportTransport

    pages: list[FlowPage] = []
    if include_profile_page and profile_labels:
        choices: list[FlowChoice] = []
        for label in profile_labels:
            ref = f"{_COPY_NAMESPACE}:{run_token}:profile:{label}"
            copy_table[ref] = label
            choices.append(FlowChoice(value=label, label=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=ref)))
        pages.append(
            FlowPage(
                id=_EXPORT_PROFILE_PAGE,
                widget=FlowWidgetKind.SELECT,
                prompt=_locale_ref("cli.config.profile.export_name_help"),
                choices=tuple(choices),
                default=active_label if active_label in profile_labels else None,
                answer_type=str,
            ),
        )
    if include_destination_page:
        pages.append(
            FlowPage(
                id=_EXPORT_DESTINATION_PAGE,
                widget=FlowWidgetKind.PATH,
                prompt=_locale_ref("cli.config.profile.export_out_help"),
                answer_type=Path,
            ),
        )
    if include_transport_page:
        pages.append(
            FlowPage(
                id=_EXPORT_TRANSPORT_PAGE,
                widget=FlowWidgetKind.SELECT,
                prompt=_locale_ref("cli.config.profile.bundle_flow.transport_prompt"),
                choices=(
                    FlowChoice(
                        value=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED.value,
                        label=_locale_ref("cli.config.profile.bundle_flow.transport_encrypted_label"),
                        description=_locale_ref("cli.config.profile.bundle_flow.transport_encrypted_description"),
                    ),
                    FlowChoice(
                        value=ProfileBundleExportTransport.CLEARTEXT_LOCAL.value,
                        label=_locale_ref("cli.config.profile.bundle_flow.transport_cleartext_label"),
                        description=_locale_ref("cli.config.profile.bundle_flow.transport_cleartext_description"),
                    ),
                ),
                default=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED.value,
                answer_type=str,
            ),
        )
    return FlowDefinition(
        id="profile-bundle-export",
        title=_locale_ref("cli.config.profile.export_help"),
        description=_locale_ref("cli.config.profile.export_help"),
        sections=(
            FlowSection(
                id="export",
                title=_locale_ref("cli.config.profile.bundle_flow.export_section_title"),
                items=tuple(pages),
            ),
        ),
        answers_model=_ProfileBundleFlowAnswers,
        checkpoint=dict(_NO_CHECKPOINT),
    )


def build_import_flow_definition(*, include_label_page: bool) -> FlowDefinition:
    """Build the import definition: the bundle path plus the optional label."""
    pages: list[FlowPage] = [
        FlowPage(
            id=_IMPORT_PATH_PAGE,
            widget=FlowWidgetKind.PATH,
            prompt=_locale_ref("cli.config.profile.import_path_help"),
            answer_type=Path,
        ),
    ]
    if include_label_page:
        pages.append(
            FlowPage(
                id=_IMPORT_LABEL_PAGE,
                widget=FlowWidgetKind.TEXT,
                prompt=_locale_ref("cli.config.profile.import_label_help"),
                required=False,
                answer_type=str,
            ),
        )
    return FlowDefinition(
        id="profile-bundle-import",
        title=_locale_ref("cli.config.profile.import_help"),
        description=_locale_ref("cli.config.profile.import_help"),
        sections=(
            FlowSection(
                id="import",
                title=_locale_ref("cli.config.profile.bundle_flow.import_section_title"),
                items=tuple(pages),
            ),
        ),
        answers_model=_ProfileBundleFlowAnswers,
        checkpoint=dict(_NO_CHECKPOINT),
    )


def interactive_capability() -> FrontendCapability | None:
    """Classify the host, returning ``None`` when no frontend can prompt.

    The commands use this single probe to decide between launching the
    flow and keeping their typed non-interactive refusal.
    """
    capability = detect_frontend_capability()
    if capability is FrontendCapability.NON_INTERACTIVE:
        return None
    return capability


def _run_flow(definition: FlowDefinition, capability: FrontendCapability) -> FlowState:
    """Drive ``definition`` on the selected frontend and return the final state.

    An abandoned full-screen run (Textual returned without a submit)
    refuses with the substrate's typed abandonment error rather than
    acting on a half-answered state — mirroring the modelo-work wizard.
    """
    from ....adapters.inbound.tui import select_flow_frontend

    frontend = select_flow_frontend(definition, mode=FlowMode.CREATE, capability=capability)
    if isinstance(frontend, LineFlowFrontend):
        state, _projection = frontend.run(mode=FlowMode.CREATE)
        return state
    frontend.run()
    if frontend.final_state is None:
        raise FlowRunAbandonedError(
            translated_message="errors.refused.refused_flow_run_abandoned",
            context={"flow_id": definition.id},
        )
    return frontend.final_state


def collect_export_request_interactively(
    *,
    name: str | None,
    destination: Path | None,
    encrypt: bool,
    cleartext_local: bool,
    capability: FrontendCapability,
) -> ExportFlowRequest:
    """Run the export flow for the missing answers and merge with argv values.

    Values the operator already supplied on the command line are never
    re-asked; the flow carries only the residual pages. The returned
    request is complete: a destination is always present and exactly one
    transport is chosen (encrypted when the operator picked it in the
    flow or passed ``--encrypt``).
    """
    from ....application.workflow import list_profile_buckets

    run_token = uuid4().hex
    with registered_run_copy_table(run_token) as copy_table:
        profile_labels: tuple[str, ...] = ()
        active_label: str | None = None
        if name is None:
            pointers = tuple(list_profile_buckets().values())
            profile_labels = tuple(pointer.label for pointer in pointers)
            active_label = _resolve_active_label(pointers)
        definition = build_export_flow_definition(
            run_token=run_token,
            copy_table=copy_table,
            profile_labels=profile_labels,
            active_label=active_label,
            include_profile_page=name is None,
            include_destination_page=destination is None,
            include_transport_page=not encrypt and not cleartext_local,
        )
        state = _run_flow(definition, capability)

    return export_request_from_state(
        state,
        name=name,
        destination=destination,
        encrypt=encrypt,
        cleartext_local=cleartext_local,
    )


def export_request_from_state(
    state: FlowState,
    *,
    name: str | None,
    destination: Path | None,
    encrypt: bool,
    cleartext_local: bool,
) -> ExportFlowRequest:
    """Merge a completed export flow state with the argv-supplied values."""
    from ....application.user_profile import ProfileBundleExportTransport

    profile_name = name
    selected = (state.answers.get(_EXPORT_PROFILE_PAGE) or "").strip()
    if profile_name is None and selected:
        profile_name = selected
    resolved_destination = destination
    if resolved_destination is None:
        resolved_destination = Path((state.answers.get(_EXPORT_DESTINATION_PAGE) or "").strip())
    resolved_encrypt = encrypt
    if not encrypt and not cleartext_local:
        transport_token = (state.answers.get(_EXPORT_TRANSPORT_PAGE) or "").strip()
        resolved_encrypt = transport_token == ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED.value
    return ExportFlowRequest(
        profile_name=profile_name,
        destination=resolved_destination,
        encrypt=resolved_encrypt,
    )


def collect_import_request_interactively(
    *,
    label: str | None,
    capability: FrontendCapability,
) -> ImportFlowRequest:
    """Run the import flow for the bundle path (and label when not supplied)."""
    definition = build_import_flow_definition(include_label_page=label is None)
    state = _run_flow(definition, capability)
    return import_request_from_state(state, label=label)


def import_request_from_state(state: FlowState, *, label: str | None) -> ImportFlowRequest:
    """Merge a completed import flow state with the argv-supplied label."""
    resolved_label = label
    if resolved_label is None:
        answered = (state.answers.get(_IMPORT_LABEL_PAGE) or "").strip()
        resolved_label = answered or None
    return ImportFlowRequest(
        path=Path((state.answers.get(_IMPORT_PATH_PAGE) or "").strip()),
        label=resolved_label,
    )


def _resolve_active_label(pointers: tuple[ProfileBucketPointer, ...]) -> str | None:
    from ....core import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    if active is None:
        return None
    for pointer in pointers:
        if pointer.bucket_id == active:
            return pointer.label
    return None


__all__ = [
    "ExportFlowRequest",
    "ImportFlowRequest",
    "build_export_flow_definition",
    "build_import_flow_definition",
    "collect_export_request_interactively",
    "collect_import_request_interactively",
    "export_request_from_state",
    "import_request_from_state",
    "interactive_capability",
    "registered_run_copy_table",
]
