"""Tests for the apoderado application service."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.config import Settings, override_settings
from ....core.flows import FlowMode
from ....core.time import now
from ....domain.auth.apoderamientos import UnknownScopeError
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, isolated_two_bucket_runtime
from ...flows import FlowPage, run_scripted_flow
from .._apoderado import (
    ApoderadoConfiguration,
    ApoderadoConfigurationIdentityError,
    ApoderadoLiveCheckUnavailableError,
    ApoderadoRepresentedNifInvalidError,
    ApoderadoService,
    _ApoderadoConfigRepository,
    _canonical_bucket_id,
)
from .._apoderado_flow import (
    REPRESENTED_NIF_PAGE_ID,
    SCOPES_PAGE_ID,
    apoderado_answers_from_state,
    build_apoderado_flow_definition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_BUCKET_ID = "26262626-2626-4262-8262-262626262626"
_APODERADO_BUCKET_ID = _PROFILE_BUCKET_ID
_SECONDARY_PROFILE_BUCKET_ID = "27272727-2727-4272-8272-272727272727"


@pytest.fixture
def isolated_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Run apoderado tests against a per-test active-profile runtime."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def isolated_settings(isolated_profile: TestRuntimeProfile) -> Settings:
    return isolated_profile.settings


class TestStatus:
    def test_status_on_unconfigured_bucket_reports_not_configured(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is False
        assert status.represented_nif is None
        assert status.granted_scopes == ()


class TestConfigure:
    def test_configure_persists_canonical_scopes(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA", "RENT"),
        )
        assert config.represented_nif == "12345678Z"
        assert config.granted_scopes == ("IVA", "RENT")
        assert config.catalogue_version.startswith("2026")

    def test_configure_dedupes_repeated_scopes(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA", "RENT", "IVA"),
        )
        assert config.granted_scopes == ("IVA", "RENT")

    def test_configure_expands_all_token(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("ALL",),
        )
        assert set(config.granted_scopes) == svc.catalogue.code_set()

    def test_configure_rejects_invalid_represented_nif(self, isolated_settings: Settings) -> None:
        """A malformed represented-party tax id refuses through the single identity authority.

        The refusal must not leak the raw identifier: the typed error carries
        no candidate value in its context.
        """
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(ApoderadoRepresentedNifInvalidError) as excinfo:
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="NOTANIF",
                scope_tokens=("RENT",),
            )
        assert "NOTANIF" not in str(excinfo.value)
        assert not excinfo.value.context

    def test_configure_rejects_unknown_scope(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(UnknownScopeError):
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="12345678Z",
                scope_tokens=("BOGUS",),
            )

    def test_configure_rejects_comma_separated_scope(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(UnknownScopeError, match="comma"):
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="12345678Z",
                scope_tokens=("IVA,RENT",),
            )

    def test_configure_overwrites_existing_record(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA",),
        )
        new_config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="87654321X",
            scope_tokens=("RENT",),
        )
        assert new_config.represented_nif == "87654321X"
        assert new_config.granted_scopes == ("RENT",)
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.represented_nif == "87654321X"


class TestStatusAfterConfigure:
    def test_status_reads_configured_record(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA", "CENSO"),
        )
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is True
        assert status.represented_nif == "12345678Z"
        assert status.granted_scopes == ("IVA", "CENSO")


class TestClear:
    def test_clear_retires_configuration(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA",),
        )
        cleared = svc.clear(bucket_id=_APODERADO_BUCKET_ID)
        assert cleared is True
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is False

    def test_clear_on_unconfigured_is_idempotent(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        assert svc.clear(bucket_id=_APODERADO_BUCKET_ID) is False


class TestCheck:
    def test_check_refuses_because_live_path_is_unwired(
        self,
        isolated_settings: Settings,
    ) -> None:
        """``check`` is live verification; the path is sealed, so it refuses.

        It must never silently re-read stored configuration and present it
        as a live result — that is the silent mislabelling this contract
        forbids. ``status`` is the offline read.
        """
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA",),
        )
        with pytest.raises(ApoderadoLiveCheckUnavailableError):
            svc.check(bucket_id=_APODERADO_BUCKET_ID)

    def test_check_refuses_even_when_unconfigured(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(ApoderadoLiveCheckUnavailableError):
            svc.check(bucket_id=_APODERADO_BUCKET_ID)


class TestBucketIsolation:
    def test_configurations_are_bucket_scoped(self, tmp_path: Path) -> None:
        with isolated_two_bucket_runtime(
            tmp_path=tmp_path,
            primary_bucket_id=_PROFILE_BUCKET_ID,
            secondary_bucket_id=_SECONDARY_PROFILE_BUCKET_ID,
        ) as runtime:
            primary_svc = ApoderadoService(settings=runtime.primary.settings)
            primary_svc.configure(
                bucket_id=runtime.primary.bucket_id, represented_nif="12345678Z", scope_tokens=("IVA",)
            )

            with runtime.switch_to_secondary():
                secondary_svc = ApoderadoService()
                secondary_svc.configure(
                    bucket_id=runtime.secondary.bucket_id,
                    represented_nif="87654321X",
                    scope_tokens=("RENT",),
                )
                b = secondary_svc.status(bucket_id=runtime.secondary.bucket_id)

            a = primary_svc.status(bucket_id=runtime.primary.bucket_id)

        assert a.represented_nif == "12345678Z"
        assert a.granted_scopes == ("IVA",)
        assert b.represented_nif == "87654321X"
        assert b.granted_scopes == ("RENT",)
        assert (runtime.primary.storage_root / "buckets" / runtime.primary.bucket_id / "db" / "cadrumo.db").is_file()
        assert (runtime.primary.storage_root / "buckets" / runtime.secondary.bucket_id / "db" / "cadrumo.db").is_file()


class TestApoderadoFlowDoor:
    """The paged apoderado flow walks its pages and commits through the real service."""

    def test_headless_walk_commits_through_the_service(self, isolated_settings: Settings) -> None:
        """A scripted walk of the door's pages configures the real record.

        Drives the engine headlessly through the door's own
        ``FlowDefinition`` -- the same definition the interactive frontend
        renders -- then projects and commits through the real
        ``ApoderadoService``. The read-back asserts against the service's own
        status surface, never the flow state's echo.
        """
        svc = ApoderadoService(settings=isolated_settings)
        definition = build_apoderado_flow_definition(svc.catalogue)

        state, _projection = run_scripted_flow(
            definition,
            tokens=["87654321X", "RENT,IVA"],
            mode=FlowMode.MODIFY,
        )
        represented_nif, scope_tokens = apoderado_answers_from_state(state)
        assert represented_nif == "87654321X"
        # CHECKBOX canonicalises to sorted tokens.
        assert scope_tokens == ("IVA", "RENT")

        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif=represented_nif,
            scope_tokens=scope_tokens,
        )
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is True
        assert status.represented_nif == "87654321X"
        assert status.granted_scopes == ("IVA", "RENT")

    def test_answer_pages_bind_no_profile_domain_key(self, isolated_settings: Settings) -> None:
        """Every answer page is domain_key-free: no apoderado answer is a profile fact."""
        svc = ApoderadoService(settings=isolated_settings)
        definition = build_apoderado_flow_definition(svc.catalogue)
        pages = {page.id: page for section in definition.sections for page in section.items}
        represented_page = pages[REPRESENTED_NIF_PAGE_ID]
        scopes_page = pages[SCOPES_PAGE_ID]
        assert isinstance(represented_page, FlowPage)
        assert isinstance(scopes_page, FlowPage)
        assert represented_page.domain_key is None
        assert scopes_page.domain_key is None

    def test_malformed_represented_nif_is_rejected_before_commit(self, isolated_settings: Settings) -> None:
        """A bad represented-party tax id fails the identity validator, so the scripted walk refuses."""
        from ...flows import FlowAnswerError

        svc = ApoderadoService(settings=isolated_settings)
        definition = build_apoderado_flow_definition(svc.catalogue)
        with pytest.raises(FlowAnswerError):
            run_scripted_flow(
                definition,
                tokens=["NOT-A-NIF", "RENT"],
                mode=FlowMode.MODIFY,
            )


class TestSettingsRouting:
    def test_service_explicit_settings_route_survives_context_override(
        self,
        isolated_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        svc = ApoderadoService(settings=isolated_profile.settings)
        wrong_root = tmp_path / "wrong-storage-root"

        with override_settings(
            cadrumo_local_storage_root=wrong_root, cadrumo_active_profile=isolated_profile.bucket_id
        ):
            config = svc.configure(
                bucket_id=isolated_profile.bucket_id,
                represented_nif="12345678Z",
                scope_tokens=("IVA",),
            )

        assert config.bucket_id == isolated_profile.bucket_id
        assert svc.status(bucket_id=isolated_profile.bucket_id).represented_nif == "12345678Z"
        assert not (wrong_root / "buckets" / isolated_profile.bucket_id / "db" / "cadrumo.db").exists()


class TestCanonicalBucketEquivalence:
    """One bucket has one apoderado record, whatever spelling the caller uses.

    ``ApoderadoConfiguration.bucket_id`` is the canonical ``BucketId``, so
    ``configure`` persisted under the *normalised* value while ``status`` and
    ``clear`` keyed on the caller's raw input. A whitespace-wrapped bucket
    therefore configured successfully and read back as unconfigured, and
    ``clear`` reported nothing to remove while the record was still stored.
    """

    _WRAPPED = f"  {_PROFILE_BUCKET_ID}  "

    def test_status_resolves_a_configuration_written_under_a_wrapped_id(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(bucket_id=self._WRAPPED, represented_nif="12345678Z", scope_tokens=("IVA",))

        assert svc.status(bucket_id=_PROFILE_BUCKET_ID).configured is True
        assert svc.status(bucket_id=self._WRAPPED).configured is True

    def test_status_projects_the_canonical_identity(self, isolated_settings: Settings) -> None:
        """The returned status names the stored bucket, not the caller's spelling."""
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(bucket_id=_PROFILE_BUCKET_ID, represented_nif="12345678Z", scope_tokens=("IVA",))

        assert svc.status(bucket_id=self._WRAPPED).bucket_id == _PROFILE_BUCKET_ID
        assert svc.status(bucket_id=self._WRAPPED).represented_nif == "12345678Z"

    def test_unconfigured_status_also_projects_the_canonical_identity(
        self,
        isolated_settings: Settings,
    ) -> None:
        status = ApoderadoService(settings=isolated_settings).status(bucket_id=self._WRAPPED)

        assert status.configured is False
        assert status.bucket_id == _PROFILE_BUCKET_ID

    def test_clear_removes_a_record_addressed_by_either_spelling(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(bucket_id=_PROFILE_BUCKET_ID, represented_nif="12345678Z", scope_tokens=("IVA",))

        assert svc.clear(bucket_id=self._WRAPPED) is True
        assert svc.status(bucket_id=_PROFILE_BUCKET_ID).configured is False
        assert svc.clear(bucket_id=_PROFILE_BUCKET_ID) is False

    def test_repository_cache_is_keyed_canonically(self, isolated_settings: Settings) -> None:
        """Two spellings must not open two repositories over one bucket's storage."""
        svc = ApoderadoService(settings=isolated_settings)

        first = svc._repository_for(_PROFILE_BUCKET_ID)
        second = svc._repository_for(self._WRAPPED)

        assert first is second

    @pytest.mark.parametrize("bad", ["", "   ", "x" * 129])
    def test_uncanonicalizable_bucket_input_is_refused(
        self,
        isolated_settings: Settings,
        bad: str,
    ) -> None:
        """A blank or overlength bucket cannot silently address a repository."""
        svc = ApoderadoService(settings=isolated_settings)

        with pytest.raises(ValidationError):
            svc.status(bucket_id=bad)
        with pytest.raises(ValidationError):
            svc.clear(bucket_id=bad)

    def test_distinct_buckets_stay_distinct(self) -> None:
        """Canonicalisation must not merge two genuinely different buckets.

        Trimming is only safe if it collapses spellings of ONE identity; a
        normaliser that also collapsed two identities would route bucket B's
        represented NIF into bucket A's repository.
        """
        assert _canonical_bucket_id(self._WRAPPED) == _canonical_bucket_id(_PROFILE_BUCKET_ID)
        assert _canonical_bucket_id(_SECONDARY_PROFILE_BUCKET_ID) != _canonical_bucket_id(_PROFILE_BUCKET_ID)


class TestStoredConfigurationOwnership:
    """The object key is the only durable statement of which bucket owns a record.

    ``_ApoderadoConfigRepository`` derives its key from
    ``ApoderadoConfiguration.bucket_id``, but the inherited load path validated
    only the envelope class and version. A configuration for bucket B rekeyed
    under bucket A therefore loaded cleanly, and ``status(bucket_id=A)``
    reported it as configured while projecting B's represented tax identifier.
    """

    def _foreign_configuration(self) -> ApoderadoConfiguration:
        return ApoderadoConfiguration(
            bucket_id=_SECONDARY_PROFILE_BUCKET_ID,
            represented_nif="12345678Z",
            granted_scopes=(),
            catalogue_version="v1",
            configured_at=now(),
            notes="",
        )

    def _rekey_under(self, repo: _ApoderadoConfigRepository, key: str, config: ApoderadoConfiguration) -> None:
        """Write ``config``'s genuine encrypted envelope under a foreign ``key``."""
        envelope = repo._identified_envelope(config)[1]
        repo._objects.save(
            namespace=repo.namespace,
            object_key=key,
            classification=repo.sensitivity,
            schema_version=repo.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def test_load_refuses_a_configuration_keyed_under_a_foreign_bucket(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        repo = _ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)
        self._rekey_under(repo, _PROFILE_BUCKET_ID, self._foreign_configuration())

        with pytest.raises(ApoderadoConfigurationIdentityError):
            repo.load(_PROFILE_BUCKET_ID)

    def test_status_refuses_rather_than_projecting_a_foreign_represented_identity(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        """The leak this closes is identity-bearing, so refusal must reach the service."""
        repo = _ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)
        self._rekey_under(repo, _PROFILE_BUCKET_ID, self._foreign_configuration())

        with pytest.raises(ApoderadoConfigurationIdentityError):
            ApoderadoService(settings=isolated_profile.settings).status(bucket_id=_PROFILE_BUCKET_ID)

    def test_save_refuses_a_configuration_for_another_bucket(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        """A bound repository writes only its own bucket's encrypted storage."""
        repo = _ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)

        with pytest.raises(ApoderadoConfigurationIdentityError):
            repo.save(self._foreign_configuration())

    def test_same_bucket_round_trip_still_succeeds(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        """The guard must not refuse the legitimate write-then-read path."""
        repo = _ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)
        config = ApoderadoConfiguration(
            bucket_id=_PROFILE_BUCKET_ID,
            represented_nif="12345678Z",
            granted_scopes=(),
            catalogue_version="v1",
            configured_at=now(),
            notes="own bucket",
        )

        repo.save(config)

        assert repo.load(_PROFILE_BUCKET_ID) == config

    def test_absent_record_still_reads_as_none(self, isolated_profile: TestRuntimeProfile) -> None:
        """An unconfigured bucket is not an identity violation."""
        repo = _ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)

        assert repo.load(_PROFILE_BUCKET_ID) is None
