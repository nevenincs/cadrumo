"""Provider settings on real disposable encrypted profiles.

Every test runs the application service and resolver against the encrypted
secure-object store of a genuinely provisioned profile bucket, through the
runtime-owned repository door. Keys are visibly fake.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from .....application.agent_host.controller import AgentGenerations, AgentHostError, AgentHostRefusal
from .....application.agent_host.credential_frame import wipe
from .....application.provider_settings.agent_credentials import ProviderSettingsAgentCredentialSource
from .....application.provider_settings.contracts import (
    ProviderCredentialSource,
    ProviderReadiness,
    ProviderSettingsActionAccepted,
    ProviderSettingsMode,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    ProviderStatusEntry,
    ProviderStatusReason,
)
from .....application.provider_settings.ports import ProviderCatalogSource
from .....application.provider_settings.resolution import (
    ProviderCredentialResolver,
    ProviderCredentialUnavailable,
    ProviderCredentialUnavailableReason,
    ResolvedDirectCredential,
    ResolvedProviderSignIn,
)
from .....application.provider_settings.service import AssistantAuthChoice, BaseUrlChange, ProviderSettingsService
from .....application.provider_settings.tests.synthetic_catalog import (
    BARE_GATEWAY_LANE,
    GATEWAY_DEFAULT_URL,
    GATEWAY_LANE,
    KEY_LANE,
    MISSING_LANE,
    OTHER_KEY_LANE,
    SIGN_IN_ONLY_LANE,
    THIRD_LANE,
    StaticCatalogSource,
    UnavailableCatalogSource,
    development_variable,
    synthetic_catalog,
)
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....core.storage_environment import StorageMode
from .....core.time.clock import now
from .....domain.provider_settings.catalog import ProviderConsumer
from ...storage.master_key.active_session import activate_session, current_active_bucket_session
from ...storage.master_key.bucket_session import BucketSession
from ...storage.secure_object_namespaces import PROVIDER_SETTINGS_NAMESPACE
from ...storage.tests.secure_sql import (
    TestRuntimeProfile,
    isolated_runtime_profile,
    isolated_two_bucket_runtime,
    read_db_at_rest_bytes,
)
from ..store import build_provider_settings_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KEY_A = "sk-test-NOT-A-REAL-KEY-profile-a-7f3e"
_KEY_B = "sk-test-NOT-A-REAL-KEY-profile-b-91c2"
_ENV_KEY = "sk-test-NOT-A-REAL-KEY-environment-55d0"
_BUCKET_ID = "6f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0"


def _environment_with_key() -> Mapping[str, str]:
    """Return an environment carrying a fake development key under the name constructed from the provider id."""
    return {development_variable(KEY_LANE): _ENV_KEY}


def _service(
    profile: TestRuntimeProfile,
    *,
    environment: Mapping[str, str] | None = None,
    storage_mode: StorageMode = StorageMode.DEVELOPMENT,
    catalog_source: ProviderCatalogSource | None = None,
) -> ProviderSettingsService:
    return ProviderSettingsService(
        store=build_provider_settings_store(bucket_id=profile.bucket_id, settings=profile.settings),
        catalog_source=catalog_source or StaticCatalogSource(),
        environment={} if environment is None else environment,
        storage_mode=storage_mode,
    )


def _resolver(
    profile: TestRuntimeProfile,
    *,
    environment: Mapping[str, str] | None = None,
    storage_mode: StorageMode = StorageMode.DEVELOPMENT,
    catalog_source: ProviderCatalogSource | None = None,
) -> ProviderCredentialResolver:
    return ProviderCredentialResolver(
        store=build_provider_settings_store(bucket_id=profile.bucket_id, settings=profile.settings),
        catalog_source=catalog_source or StaticCatalogSource(),
        environment={} if environment is None else environment,
        storage_mode=storage_mode,
    )


def _status(service: ProviderSettingsService) -> ProviderSettingsStatus:
    status = service.status()
    assert isinstance(status, ProviderSettingsStatus), status
    return status


def _entry(service: ProviderSettingsService, provider_id: str) -> ProviderStatusEntry:
    return next(entry for entry in _status(service).providers if entry.id == provider_id)


def _accepted(result: object) -> ProviderStatusEntry:
    assert isinstance(result, ProviderSettingsActionAccepted), result
    return result.entry


def _refusal_code(result: object) -> ProviderSettingsRefusalCode:
    assert isinstance(result, ProviderSettingsRefusal), result
    return result.code


def _direct(resolution: object) -> ResolvedDirectCredential:
    assert isinstance(resolution, ResolvedDirectCredential), resolution
    return resolution


def _unavailable_reason(resolution: object) -> ProviderCredentialUnavailableReason:
    assert isinstance(resolution, ProviderCredentialUnavailable), resolution
    return resolution.reason


def test_key_is_ciphertext_at_rest_and_never_in_status_or_reprs(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = _service(profile)

        result = service.set_credential(
            KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        entry = _accepted(result)
        status = _status(service)
        resolved = _direct(_resolver(profile).resolve(KEY_LANE, ProviderConsumer.ASSISTANT))
        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        raw_rows = [
            row
            for row in profile.repository.iter_all_records_raw()
            if row.namespace == PROVIDER_SETTINGS_NAMESPACE.namespace
        ]

    assert entry.mode is ProviderSettingsMode.KEY
    assert entry.source is ProviderCredentialSource.PROFILE
    assert entry.readiness is ProviderReadiness.NOT_VERIFIED
    assert resolved.secret.get_secret_value() == _KEY_A
    assert resolved.source is ProviderCredentialSource.PROFILE
    assert len(raw_rows) == 1
    assert _KEY_A.encode() not in raw_rows[0].payload
    assert _KEY_A.encode() not in at_rest
    assert b"NOT-A-REAL-KEY" not in at_rest
    for rendering in (
        status.model_dump_json(),
        result.model_dump_json(),
        repr(status),
        repr(resolved),
        str(resolved),
        resolved.model_dump_json(),
    ):
        assert _KEY_A not in rendering
        assert "NOT-A-REAL-KEY" not in rendering


def test_status_lists_every_catalogued_provider(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        status = _status(_service(profile, storage_mode=StorageMode.INSTALLED))

    assert tuple(entry.id for entry in status.providers) == synthetic_catalog().provider_ids
    by_id = {entry.id: entry for entry in status.providers}
    assert by_id[KEY_LANE].readiness is ProviderReadiness.MISSING
    assert by_id[KEY_LANE].reason is ProviderStatusReason.NOT_CONFIGURED
    assert by_id[SIGN_IN_ONLY_LANE].readiness is ProviderReadiness.SIGN_IN_REQUIRED
    assert by_id[GATEWAY_LANE].default_base_url == GATEWAY_DEFAULT_URL
    assert by_id[BARE_GATEWAY_LANE].default_base_url is None
    assert all(entry.mode is ProviderSettingsMode.UNSET for entry in status.providers)
    assert all(entry.revision == ABSENT_SECURE_OBJECT_REVISION_ID for entry in status.providers)
    assert all(entry.base_url is None for entry in status.providers)


def test_profiles_are_isolated(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        primary = runtime.primary
        secondary = runtime.secondary
        _accepted(
            _service(primary).set_credential(
                OTHER_KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            )
        )
        with runtime.switch_to_secondary():
            secondary_before = _entry(_service(secondary), OTHER_KEY_LANE)
            _accepted(
                _service(secondary).set_credential(
                    OTHER_KEY_LANE, secret=SecretStr(_KEY_B), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
                )
            )
            secondary_key = _direct(_resolver(secondary).resolve(OTHER_KEY_LANE, ProviderConsumer.ASSISTANT))
            primary_from_secondary = _resolver(primary).resolve(OTHER_KEY_LANE, ProviderConsumer.ASSISTANT)
        primary_key = _direct(_resolver(primary).resolve(OTHER_KEY_LANE, ProviderConsumer.ASSISTANT))

    assert secondary_before.mode is ProviderSettingsMode.UNSET
    assert secondary_key.secret.get_secret_value() == _KEY_B
    assert primary_key.secret.get_secret_value() == _KEY_A
    assert primary_key.generation != secondary_key.generation
    assert _unavailable_reason(primary_from_secondary) is ProviderCredentialUnavailableReason.NOT_SIGNED_IN


def test_locked_expired_and_signed_out_profiles_refuse(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _accepted(
            _service(profile).set_credential(
                KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            )
        )
        sealed = BucketSession.open_resumed(
            bucket_id=profile.bucket_id,
            dek=b"d" * 32,
            idle_minutes=15,
            opened_at=now(),
            idle_deadline=now() + timedelta(minutes=15),
            absolute_deadline=now() + timedelta(minutes=240),
        )
        sealed.close()
        with activate_session(sealed):
            sealed_status = _service(profile).status()
            sealed_resolution = _resolver(profile).resolve(KEY_LANE, ProviderConsumer.ASSISTANT)
        opened_at = datetime(2000, 1, 1, tzinfo=UTC)
        expired = BucketSession.open_resumed(
            bucket_id=profile.bucket_id,
            dek=b"d" * 32,
            idle_minutes=5,
            opened_at=opened_at,
            idle_deadline=opened_at + timedelta(minutes=5),
            absolute_deadline=opened_at + timedelta(minutes=240),
        )
        with activate_session(expired):
            expired_set = _service(profile).set_credential(
                OTHER_KEY_LANE, secret=SecretStr(_KEY_B), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            )
    signed_out_status = _service(profile).status()
    signed_out_resolution = _resolver(profile).resolve(KEY_LANE, ProviderConsumer.ASSISTANT)

    assert _refusal_code(sealed_status) is ProviderSettingsRefusalCode.PROFILE_LOCKED
    assert _unavailable_reason(sealed_resolution) is ProviderCredentialUnavailableReason.PROFILE_LOCKED
    assert _refusal_code(expired_set) is ProviderSettingsRefusalCode.PROFILE_LOCKED
    assert _refusal_code(signed_out_status) is ProviderSettingsRefusalCode.NOT_SIGNED_IN
    assert _unavailable_reason(signed_out_resolution) is ProviderCredentialUnavailableReason.NOT_SIGNED_IN


def test_malformed_record_fails_closed_until_reset(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        profile.repository.save(
            namespace=PROVIDER_SETTINGS_NAMESPACE.namespace,
            object_key=KEY_LANE,
            classification=PROVIDER_SETTINGS_NAMESPACE.sensitivity,
            schema_version=PROVIDER_SETTINGS_NAMESPACE.schema_version,
            written_at=now(),
            payload=b'{"schema_version":1,"provider":KEY_LANE,"credential_state":"configured"}',
        )
        service = _service(profile, environment=_environment_with_key())
        broken = _entry(service, KEY_LANE)
        resolution = _resolver(profile, environment=_environment_with_key()).resolve(
            KEY_LANE, ProviderConsumer.ASSISTANT
        )
        absent_guard = service.set_credential(
            KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        reset = _accepted(service.reset(KEY_LANE, expected_revision=broken.revision))

    assert broken.readiness is ProviderReadiness.UNUSABLE
    assert broken.reason is ProviderStatusReason.RECORD_UNREADABLE
    assert broken.available is False
    assert broken.revision != ABSENT_SECURE_OBJECT_REVISION_ID
    assert _unavailable_reason(resolution) is ProviderCredentialUnavailableReason.RECORD_UNREADABLE
    assert _refusal_code(absent_guard) is ProviderSettingsRefusalCode.REVISION_CONFLICT
    assert reset.mode is ProviderSettingsMode.UNSET
    assert reset.source is ProviderCredentialSource.ENVIRONMENT


def test_actions_are_revision_guarded(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = _service(profile)
        first = _accepted(
            service.set_credential(
                THIRD_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            )
        )
        stale_create = service.set_credential(
            THIRD_LANE, secret=SecretStr(_KEY_B), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        second = _accepted(
            service.set_credential(THIRD_LANE, secret=SecretStr(_KEY_B), expected_revision=first.revision)
        )
        stale_replace = service.set_credential(THIRD_LANE, secret=SecretStr(_KEY_A), expected_revision=first.revision)
        stale_reset = service.reset(THIRD_LANE, expected_revision=first.revision)
        malformed_guard = service.remove_credential(THIRD_LANE, expected_revision="not-a-revision")
        resolved = _direct(_resolver(profile).resolve(THIRD_LANE, ProviderConsumer.ASSISTANT))

    assert first.revision != second.revision
    assert _refusal_code(stale_create) is ProviderSettingsRefusalCode.REVISION_CONFLICT
    assert _refusal_code(stale_replace) is ProviderSettingsRefusalCode.REVISION_CONFLICT
    assert _refusal_code(stale_reset) is ProviderSettingsRefusalCode.REVISION_CONFLICT
    assert _refusal_code(malformed_guard) is ProviderSettingsRefusalCode.REVISION_CONFLICT
    assert resolved.secret.get_secret_value() == _KEY_B


def test_precedence_stored_disabled_environment_and_storage_mode(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        environment = _environment_with_key()
        development = _service(profile, environment=environment)
        dev_resolver = _resolver(profile, environment=environment)
        installed_resolver = _resolver(profile, environment=environment, storage_mode=StorageMode.INSTALLED)

        unset_dev = _entry(development, KEY_LANE)
        unset_installed = _entry(
            _service(profile, environment=environment, storage_mode=StorageMode.INSTALLED), KEY_LANE
        )
        from_environment = _direct(dev_resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT))
        installed_unset = installed_resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT)

        stored = _accepted(
            development.set_credential(KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=unset_dev.revision)
        )
        stored_dev = _direct(dev_resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT))
        stored_installed = _direct(installed_resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT))

        removed = _accepted(development.remove_credential(KEY_LANE, expected_revision=stored.revision))
        removed_dev = dev_resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT)

        reset = _accepted(development.reset(KEY_LANE, expected_revision=removed.revision))
        reset_dev = _direct(dev_resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT))

    assert unset_dev.source is ProviderCredentialSource.ENVIRONMENT
    assert unset_dev.reason is None
    assert unset_installed.reason is ProviderStatusReason.NOT_CONFIGURED
    assert removed.reason is ProviderStatusReason.TURNED_OFF
    assert unset_installed.readiness is ProviderReadiness.MISSING
    assert from_environment.secret.get_secret_value() == _ENV_KEY
    assert from_environment.source is ProviderCredentialSource.ENVIRONMENT
    assert _unavailable_reason(installed_unset) is ProviderCredentialUnavailableReason.CREDENTIAL_MISSING
    assert stored.source is ProviderCredentialSource.PROFILE
    assert stored_dev.secret.get_secret_value() == _KEY_A
    assert stored_installed.secret.get_secret_value() == _KEY_A
    assert removed.mode is ProviderSettingsMode.DISABLED
    assert removed.readiness is ProviderReadiness.DISABLED
    assert _unavailable_reason(removed_dev) is ProviderCredentialUnavailableReason.PROVIDER_DISABLED
    assert reset.mode is ProviderSettingsMode.UNSET
    assert reset.revision == ABSENT_SECURE_OBJECT_REVISION_ID
    assert reset_dev.secret.get_secret_value() == _ENV_KEY


def test_assistant_sign_in_choice_is_offered_only_to_a_lane_that_takes_nothing_else(tmp_path: Path) -> None:
    absent = ABSENT_SECURE_OBJECT_REVISION_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = _service(profile)
        resolver = _resolver(profile)
        unset_sign_in = resolver.resolve(SIGN_IN_ONLY_LANE, ProviderConsumer.ASSISTANT)
        chosen = _accepted(
            service.set_assistant_auth(
                SIGN_IN_ONLY_LANE, choice=AssistantAuthChoice.PROVIDER_SIGN_IN, expected_revision=absent
            )
        )
        resolved_sign_in = resolver.resolve(SIGN_IN_ONLY_LANE, ProviderConsumer.ASSISTANT)
        refused_direct = service.set_assistant_auth(
            SIGN_IN_ONLY_LANE, choice=AssistantAuthChoice.DIRECT_API, expected_revision=chosen.revision
        )
        refused_key = service.set_credential(SIGN_IN_ONLY_LANE, secret=SecretStr(_KEY_A), expected_revision=absent)
        refused_sign_in = service.set_assistant_auth(
            KEY_LANE, choice=AssistantAuthChoice.PROVIDER_SIGN_IN, expected_revision=absent
        )
        keyed = _accepted(service.set_credential(KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=absent))
        direct = _accepted(
            service.set_assistant_auth(
                KEY_LANE, choice=AssistantAuthChoice.DIRECT_API, expected_revision=keyed.revision
            )
        )
        resolved_key = _direct(resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT))

    assert isinstance(unset_sign_in, ResolvedProviderSignIn)
    assert chosen.mode is ProviderSettingsMode.PROVIDER_SIGN_IN
    assert chosen.readiness is ProviderReadiness.SIGN_IN_REQUIRED
    assert isinstance(resolved_sign_in, ResolvedProviderSignIn)
    assert _refusal_code(refused_direct) is ProviderSettingsRefusalCode.UNKNOWN
    assert _refusal_code(refused_key) is ProviderSettingsRefusalCode.UNKNOWN
    assert _refusal_code(refused_sign_in) is ProviderSettingsRefusalCode.UNKNOWN
    assert direct.mode is ProviderSettingsMode.KEY
    assert resolved_key.secret.get_secret_value() == _KEY_A


def test_input_refusals_and_base_urls(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = _service(profile)
        resolver = _resolver(profile)
        absent = ABSENT_SECURE_OBJECT_REVISION_ID
        masked = service.set_credential(
            GATEWAY_LANE, secret=SecretStr("sk-****************7f3e"), expected_revision=absent
        )
        blank = service.set_credential(GATEWAY_LANE, secret=SecretStr("   "), expected_revision=absent)
        plain_http = service.set_credential(
            GATEWAY_LANE, secret=SecretStr(_KEY_A), base_url="http://gateway.example.invalid", expected_revision=absent
        )
        qwen_without_url = service.set_credential(BARE_GATEWAY_LANE, secret=SecretStr(_KEY_A), expected_revision=absent)
        url_on_plain_key = service.set_credential(
            OTHER_KEY_LANE,
            secret=SecretStr(_KEY_A),
            base_url="https://gateway.example.invalid",
            expected_revision=absent,
        )
        unknown = service.set_credential(MISSING_LANE, secret=SecretStr(_KEY_A), expected_revision=absent)
        zai = _accepted(service.set_credential(GATEWAY_LANE, secret=SecretStr(_KEY_A), expected_revision=absent))
        qwen = _accepted(
            service.set_credential(
                BARE_GATEWAY_LANE,
                secret=SecretStr(_KEY_B),
                base_url="https://gateway.example.invalid/anthropic",
                expected_revision=absent,
            )
        )
        zai_resolved = _direct(resolver.resolve(GATEWAY_LANE, ProviderConsumer.ASSISTANT))
        qwen_resolved = _direct(resolver.resolve(BARE_GATEWAY_LANE, ProviderConsumer.ASSISTANT))
        gemini = resolver.resolve(MISSING_LANE, ProviderConsumer.ASSISTANT)

    assert _refusal_code(masked) is ProviderSettingsRefusalCode.INVALID_KEY_FORMAT
    assert _refusal_code(blank) is ProviderSettingsRefusalCode.INVALID_KEY_FORMAT
    assert _refusal_code(plain_http) is ProviderSettingsRefusalCode.BASE_URL_REJECTED
    assert _refusal_code(qwen_without_url) is ProviderSettingsRefusalCode.BASE_URL_REJECTED
    assert _refusal_code(url_on_plain_key) is ProviderSettingsRefusalCode.BASE_URL_REJECTED
    assert _refusal_code(unknown) is ProviderSettingsRefusalCode.UNKNOWN
    assert zai.base_url is None
    assert zai.default_base_url == GATEWAY_DEFAULT_URL
    assert qwen.base_url == "https://gateway.example.invalid/anthropic"
    assert zai_resolved.base_url == GATEWAY_DEFAULT_URL
    assert qwen_resolved.base_url == "https://gateway.example.invalid/anthropic"
    assert _unavailable_reason(gemini) is ProviderCredentialUnavailableReason.UNKNOWN_PROVIDER


def test_status_json_matches_the_desktop_contract(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = _service(profile)
        _accepted(
            service.set_credential(
                OTHER_KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            )
        )
        document = json.loads(_status(service).model_dump_json())

    assert set(document) == {"development", "providers"}
    assert document["development"] is True
    entries = {entry["id"]: entry for entry in document["providers"]}
    assert set(entries[OTHER_KEY_LANE]) == {
        "id",
        "provider",
        "transport",
        "display_name",
        "auth_kind",
        "consumers",
        "mode",
        "available",
        "source",
        "readiness",
        "reason",
        "base_url",
        "default_base_url",
        "cli_state",
        "revision",
    }
    assert entries[OTHER_KEY_LANE]["provider"] == "other"
    assert entries[OTHER_KEY_LANE]["transport"] == "api"
    assert entries[OTHER_KEY_LANE]["cli_state"] is None
    assert entries[SIGN_IN_ONLY_LANE]["cli_state"] == "unknown"
    assert entries[OTHER_KEY_LANE]["mode"] == "key"
    assert entries[OTHER_KEY_LANE]["readiness"] == "not_verified"
    assert entries[OTHER_KEY_LANE]["reason"] is None
    assert entries[OTHER_KEY_LANE]["revision"] != ABSENT_SECURE_OBJECT_REVISION_ID
    assert entries[THIRD_LANE]["revision"] == ABSENT_SECURE_OBJECT_REVISION_ID
    assert entries[SIGN_IN_ONLY_LANE]["reason"] == "sign_in_with_provider_tool"
    assert entries[BARE_GATEWAY_LANE]["default_base_url"] is None


def test_agent_credential_source_hands_fresh_buffers_under_current_generations(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = _service(profile)
        source = ProviderSettingsAgentCredentialSource(
            store=build_provider_settings_store(bucket_id=profile.bucket_id, settings=profile.settings),
            resolver=_resolver(profile),
            catalog_source=StaticCatalogSource(),
        )
        session = current_active_bucket_session()
        assert session is not None
        idle_before = session.idle_deadline
        empty = source.current_generations()
        observed_again = source.current_generations()
        idle_after_observing = session.idle_deadline

        _accepted(
            service.set_credential(
                GATEWAY_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            )
        )
        _accepted(
            service.set_credential(
                KEY_LANE, secret=SecretStr(_KEY_B), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            )
        )
        resolved = source.resolve_for_agent()
        current = source.current_generations()
        zai_secret = bytes(resolved.credentials["gateway"].secret)
        zai_url = resolved.credentials["gateway"].base_url
        anthropic_secret = bytes(resolved.credentials["example"].secret)
        providers = set(resolved.credentials)
        rendered = repr(resolved.credentials)
        for credential in resolved.credentials.values():
            wipe(credential.secret)
    signed_out = source.current_generations()
    with pytest.raises(AgentHostError) as refused:
        source.resolve_for_agent()

    assert isinstance(empty, AgentGenerations)
    assert observed_again == empty
    assert idle_after_observing == idle_before
    assert current == resolved.generations
    assert current is not None
    assert current.sign_in == empty.sign_in
    assert current.provider_settings != empty.provider_settings
    assert providers == {"gateway", "example"}
    assert anthropic_secret == _KEY_B.encode()
    assert zai_secret == _KEY_A.encode()
    assert zai_url == GATEWAY_DEFAULT_URL
    assert _KEY_A not in rendered
    assert signed_out is None
    assert refused.value.reason is AgentHostRefusal.SIGNED_OUT


def test_base_url_is_stored_kept_or_cleared(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = _service(profile)
        custom = "https://gateway.example.invalid/anthropic"
        stored = _accepted(
            service.set_credential(
                GATEWAY_LANE,
                secret=SecretStr(_KEY_A),
                expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
                base_url=custom,
            )
        )
        kept = _accepted(
            service.set_credential(GATEWAY_LANE, secret=SecretStr(_KEY_B), expected_revision=stored.revision)
        )
        cleared = _accepted(
            service.set_credential(
                GATEWAY_LANE, secret=SecretStr(_KEY_B), expected_revision=kept.revision, base_url=BaseUrlChange.CLEAR
            )
        )
        qwen = _accepted(
            service.set_credential(
                BARE_GATEWAY_LANE,
                secret=SecretStr(_KEY_A),
                expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
                base_url=custom,
            )
        )
        qwen_kept = _accepted(
            service.set_credential(BARE_GATEWAY_LANE, secret=SecretStr(_KEY_B), expected_revision=qwen.revision)
        )
        qwen_cleared = service.set_credential(
            BARE_GATEWAY_LANE,
            secret=SecretStr(_KEY_B),
            expected_revision=qwen_kept.revision,
            base_url=BaseUrlChange.CLEAR,
        )
        resolved = _direct(_resolver(profile).resolve(GATEWAY_LANE, ProviderConsumer.ASSISTANT))
        installed_status = _service(profile, storage_mode=StorageMode.INSTALLED).status()

    assert stored.base_url == custom
    assert kept.base_url == custom
    assert cleared.base_url is None
    assert resolved.base_url == GATEWAY_DEFAULT_URL
    assert qwen_kept.base_url == custom
    assert _refusal_code(qwen_cleared) is ProviderSettingsRefusalCode.BASE_URL_REJECTED
    assert isinstance(installed_status, ProviderSettingsStatus)
    assert installed_status.development is False


def test_an_agent_that_reports_no_providers_makes_settings_unavailable_and_not_empty(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        unavailable = UnavailableCatalogSource()
        status = _service(profile, catalog_source=unavailable).status()
        set_result = _service(profile, catalog_source=unavailable).set_credential(
            KEY_LANE, secret=SecretStr(_KEY_A), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        resolution = _resolver(profile, environment=_environment_with_key(), catalog_source=unavailable).resolve(
            KEY_LANE, ProviderConsumer.ASSISTANT
        )

    assert _refusal_code(status) is ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE
    assert _refusal_code(set_result) is ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE
    assert _unavailable_reason(resolution) is ProviderCredentialUnavailableReason.CATALOG_UNAVAILABLE


def test_the_development_variable_is_constructed_from_the_provider_of_any_reported_lane(tmp_path: Path) -> None:
    environment = {
        development_variable(OTHER_KEY_LANE): _ENV_KEY,
        development_variable(SIGN_IN_ONLY_LANE): _ENV_KEY,
        development_variable(BARE_GATEWAY_LANE): _ENV_KEY,
    }
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolver = _resolver(profile, environment=environment)
        other = _direct(resolver.resolve(OTHER_KEY_LANE, ProviderConsumer.ASSISTANT))
        same_provider_key_lane = _direct(resolver.resolve(KEY_LANE, ProviderConsumer.ASSISTANT))
        sign_in_only = resolver.resolve(SIGN_IN_ONLY_LANE, ProviderConsumer.ASSISTANT)
        no_gateway_url = resolver.resolve(BARE_GATEWAY_LANE, ProviderConsumer.ASSISTANT)
        unset_key_lane = resolver.resolve(THIRD_LANE, ProviderConsumer.ASSISTANT)

    assert other.source is ProviderCredentialSource.ENVIRONMENT
    assert other.secret.get_secret_value() == _ENV_KEY
    assert same_provider_key_lane.secret.get_secret_value() == _ENV_KEY
    assert isinstance(sign_in_only, ResolvedProviderSignIn)
    assert _unavailable_reason(no_gateway_url) is ProviderCredentialUnavailableReason.CREDENTIAL_MISSING
    assert _unavailable_reason(unset_key_lane) is ProviderCredentialUnavailableReason.CREDENTIAL_MISSING
