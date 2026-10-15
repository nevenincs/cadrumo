"""Runtime presentation reads follow language changes without replacing edit witnesses.

The explicit read ports below exercise root orchestration and currentness,
not native admission, which the separate worker integration covers.
"""

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Never, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.language_resolver import register_language_resolver
from cadrumo.application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import profile_output_language_precedence
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.navigation import TuiScreenContextV1
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport import profile_language
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.profile_language import ProfileLanguage

from ....frontend.tui import runtime_initial_root, runtime_workbench

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _client(profile_id: UUID) -> FrontendClient:
    return cast(
        FrontendClient,
        SimpleNamespace(
            profile_id=profile_id,
            session_id=uuid4(),
            frontend=OperationFrontendProjection.TUI,
            subscribe_session_retirement=None,
            subscribe_lifecycle_notices=None,
            subscribe_profile_language_changes=None,
        ),
    )


def _overview(profile_id: UUID, language: OutputLanguage) -> ProfileOverview:
    return ProfileOverview(
        profile_id=str(profile_id),
        record_revision=1 if language is OutputLanguage.ES else 2,
        content_digest=("a" if language is OutputLanguage.ES else "b") * 64,
        label="Current profile",
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(
            ProfileSectionView(
                key="preferences",
                title=f"Preferences {language.value}",
                summary="",
                repeatable=False,
                fields=(
                    ProfileFieldView(
                        path=PROFILE_OUTPUT_LANGUAGE_PATH,
                        label=f"Language {language.value}",
                        value=language.value,
                        masked=False,
                        required=False,
                    ),
                ),
            ),
        ),
    )


async def _recovery() -> FrontendClient:
    raise AssertionError("language refresh cannot open another client")


def _operations() -> Never:
    raise AssertionError("language capture cannot compose operations")


def test_canonical_invalidation_updates_initial_root_and_new_profile_panes_off_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile_id = uuid4()
    client = _client(profile_id)
    reads: list[tuple[OutputLanguage, int]] = []

    def overview(_client: FrontendClient, *, profile_label: str, output_language: OutputLanguage) -> ProfileOverview:
        assert _client is client
        reads.append((output_language, threading.get_ident()))
        return _overview(profile_id, output_language)

    monkeypatch.setattr(runtime_initial_root, "read_profile_overview", overview)
    monkeypatch.setattr(runtime_initial_root.RuntimeInitialRoot, "_session", lambda _self: None)
    monkeypatch.setattr(
        profile_language, "read_profile_language", lambda _client: ProfileLanguage(OutputLanguage.CA, 2, "b" * 64)
    )
    root = runtime_initial_root.RuntimeInitialRoot(
        client,
        profile_label="Current profile",
        output_language=OutputLanguage.ES,
        open_recovery_client=_recovery,
        operation_registry=_operations,
    )
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language=""),
        profile_output_language_precedence(),
    ):
        register_language_resolver()
        try:
            binding = root.load()
            factories = binding.account_factories
            assert factories is not None and factories.refresh_language is not None
            context = TuiScreenContextV1(destination="workbench.profile")
            opened = factories.profile(context)
            old_revision, old_digest = opened.overview.record_revision, opened.overview.content_digest

            async def refresh_current_language() -> None:
                assert factories.refresh_language is not None
                await factories.refresh_language()

            asyncio.run(refresh_current_language())
            fresh = factories.profile(context)
            assert reads[0][0] is OutputLanguage.ES
            assert reads[-1][0] is OutputLanguage.CA
            assert reads[-1][1] != threading.get_ident()
            assert fresh.overview.sections[0].fields[0].label == "Language ca"
            assert fresh.overview.sections[0].fields[0].value == "ca"
            assert (fresh.overview.record_revision, fresh.overview.content_digest) == (2, "b" * 64)
            assert (opened.overview.record_revision, opened.overview.content_digest) == (old_revision, old_digest)
        finally:
            register_language_resolver()


def test_later_generation_and_profile_requests_use_one_updated_language_and_reject_inflight_old_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    client = _client(profile_id)
    requests: list[tuple[str, OutputLanguage]] = []
    interrupt = False

    def overview(_client: FrontendClient, *, profile_label: str, output_language: OutputLanguage) -> ProfileOverview:
        requests.append(("profile", output_language))
        return _overview(profile_id, output_language)

    def generation(_client: FrontendClient, *, output_language: OutputLanguage) -> SimpleNamespace:
        nonlocal interrupt
        requests.append(("generation", output_language))
        if interrupt:
            interrupt = False
            root.set_output_language(OutputLanguage.HU)
        return SimpleNamespace(home=SimpleNamespace(projection=object()))

    monkeypatch.setattr(runtime_workbench, "read_profile_overview", overview)
    monkeypatch.setattr(runtime_workbench, "read_workbench_generation", generation)
    monkeypatch.setattr(runtime_workbench, "read_runtime_account_session", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_initial_root, "read_profile_overview", overview)
    monkeypatch.setattr(runtime_initial_root.RuntimeInitialRoot, "_session", lambda _self: None)
    root = runtime_workbench.RuntimeWorkbenchRoot(
        client,
        profile_label="Current profile",
        output_language=OutputLanguage.ES,
        open_recovery_client=_recovery,
        operation_registry=_operations,
    )
    original = root._read()
    initial = runtime_initial_root.RuntimeInitialRoot(
        client,
        profile_label="Current profile",
        output_language=OutputLanguage.ES,
        open_recovery_client=_recovery,
        operation_registry=_operations,
    )
    initial._workbench_root = root
    initial._set_output_language(OutputLanguage.CA)
    requests.clear()
    assert root._read().profile.sections[0].fields[0].value == "ca"
    assert requests == [("generation", OutputLanguage.CA), ("profile", OutputLanguage.CA)]
    with pytest.raises(RefusalError) as stale:
        root._presentation(original)
    assert stale.value.reason is RefusalCode.UNAVAILABLE
    interrupt = True
    with pytest.raises(RefusalError) as changed:
        root._read()
    assert changed.value.reason is RefusalCode.UNAVAILABLE
    requests.clear()
    assert root._read().profile.sections[0].fields[0].value == "hu"
    assert requests == [("generation", OutputLanguage.HU), ("profile", OutputLanguage.HU)]
