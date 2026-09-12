"""Tests for the apoderado application service."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from ....core.config import Settings, override_settings
from ....core.flows import FlowMode
from ....core.identity.bucket import canonical_bucket_id
from ....domain.auth.apoderamientos.catalogue import UnknownScopeError
from ...flows.definition import FlowPage
from ...flows.errors import FlowRunAbandonedError
from ...flows.scripted import run_scripted_flow
from ..apoderado_flow import (
    REPRESENTED_NIF_PAGE_ID,
    SCOPES_PAGE_ID,
    build_apoderado_flow_definition,
    run_apoderado_flow,
)
from ..apoderado_service import (
    ApoderadoLiveCheckUnavailableError,
    ApoderadoRepresentedNifInvalidError,
    ApoderadoService,
)
from .apoderado_fakes import InMemoryApoderadoConfigurationRepositoryFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_BUCKET_ID = "26262626-2626-4262-8262-262626262626"
_APODERADO_BUCKET_ID = _PROFILE_BUCKET_ID
_SECONDARY_PROFILE_BUCKET_ID = "27272727-2727-4272-8272-272727272727"


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    """Provide explicit settings while the service uses an in-memory port fake."""
    return Settings(cadrumo_local_storage_root=tmp_path)


@pytest.fixture
def repository_factory() -> InMemoryApoderadoConfigurationRepositoryFactory:
    """Provide one explicit in-memory factory for a test's service graph."""
    return InMemoryApoderadoConfigurationRepositoryFactory()


def _service(settings: Settings) -> ApoderadoService:
    """Construct the application service with its required test capability."""
    return ApoderadoService(
        repository_factory=InMemoryApoderadoConfigurationRepositoryFactory(),
        settings=settings,
    )


class TestStatus:
    def test_status_on_unconfigured_bucket_reports_not_configured(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = _service(isolated_settings)
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is False
        assert status.represented_nif is None
        assert status.granted_scopes == ()


class TestConfigure:
    def test_configure_persists_canonical_scopes(self, isolated_settings: Settings) -> None:
        svc = _service(isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA", "RENT"),
        )
        assert config.represented_nif == "12345678Z"
        assert config.granted_scopes == ("IVA", "RENT")
        assert config.catalogue_version.startswith("2026")

    def test_configure_dedupes_repeated_scopes(self, isolated_settings: Settings) -> None:
        svc = _service(isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("IVA", "RENT", "IVA"),
        )
        assert config.granted_scopes == ("IVA", "RENT")

    def test_configure_expands_all_token(self, isolated_settings: Settings) -> None:
        svc = _service(isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="12345678Z",
            scope_tokens=("ALL",),
        )
        assert set(config.granted_scopes) == svc.catalogue.code_set()

    def test_configure_rejects_invalid_represented_nif(self, isolated_settings: Settings) -> None:
        """A malformed represented-party tax id refuses through the single identity authority.

        The refusal must not leak the raw identifier: the typed error carries
        no candidate value in its context, and it carries no machine facts at
        all, because the only fact this failure has to report IS the rejected
        identifier and that value is identity-sensitive.

        The operator-facing text resolves from the registered locale key rather
        than an authored English sentence. Asserting the key alone would stay
        green if prose were passed positionally beside it, because resolution
        prefers the key while ``str(exc)`` prefers the sentence -- which is how
        English reaches tracebacks and logs in every locale. Pinning
        ``str(exc)`` to the key is what fails a re-introduced sentence.
        """
        from ....core.errors.error_codes import get_registered_error_code, resolve_error_message

        svc = _service(isolated_settings)
        with pytest.raises(ApoderadoRepresentedNifInvalidError) as excinfo:
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="NOTANIF",
                scope_tokens=("RENT",),
            )
        error = excinfo.value
        assert "NOTANIF" not in str(error)
        assert not error.context
        assert error.translated_message == "errors.refused.refused_apoderado_invalid_represented_nif"
        assert get_registered_error_code(error).code == "REFUSED_APODERADO_INVALID_REPRESENTED_NIF"
        assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
        resolved = resolve_error_message(error)
        assert resolved and resolved != error.translated_message
        assert "NOTANIF" not in resolved

    def test_configure_rejects_unknown_scope(self, isolated_settings: Settings) -> None:
        svc = _service(isolated_settings)
        with pytest.raises(UnknownScopeError):
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="12345678Z",
                scope_tokens=("BOGUS",),
            )

    def test_configure_rejects_comma_separated_scope(self, isolated_settings: Settings) -> None:
        """A comma-joined scope token refuses, and names the rule it broke as a fact.

        The refusal used to be told apart from the other unknown-scope
        rejections by the word "comma" in an authored English sentence. It now
        shares the registered key with them and is distinguished by the
        ``validation_rule`` fact, so matching on prose here would assert a
        rendering that no longer exists rather than the contract that does.
        """
        svc = _service(isolated_settings)
        with pytest.raises(UnknownScopeError) as excinfo:
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="12345678Z",
                scope_tokens=("IVA,RENT",),
            )
        error = excinfo.value
        assert error.context == {
            "scope_token": "IVA,RENT",
            "validation_rule": "no_comma_separated_values",
        }
        assert error.translated_message == "errors.refused.refused_apoderado_unknown_scope"
        assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"

    def test_configure_overwrites_existing_record(self, isolated_settings: Settings) -> None:
        svc = _service(isolated_settings)
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
        svc = _service(isolated_settings)
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
        svc = _service(isolated_settings)
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
        svc = _service(isolated_settings)
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
        svc = _service(isolated_settings)
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
        svc = _service(isolated_settings)
        with pytest.raises(ApoderadoLiveCheckUnavailableError):
            svc.check(bucket_id=_APODERADO_BUCKET_ID)


class TestBucketIsolation:
    def test_configurations_are_bucket_scoped(
        self,
        isolated_settings: Settings,
        repository_factory: InMemoryApoderadoConfigurationRepositoryFactory,
    ) -> None:
        primary_svc = ApoderadoService(repository_factory=repository_factory, settings=isolated_settings)
        primary_svc.configure(bucket_id=_PROFILE_BUCKET_ID, represented_nif="12345678Z", scope_tokens=("IVA",))

        secondary_svc = ApoderadoService(repository_factory=repository_factory, settings=isolated_settings)
        secondary_svc.configure(
            bucket_id=_SECONDARY_PROFILE_BUCKET_ID,
            represented_nif="87654321X",
            scope_tokens=("RENT",),
        )
        b = secondary_svc.status(bucket_id=_SECONDARY_PROFILE_BUCKET_ID)
        a = primary_svc.status(bucket_id=_PROFILE_BUCKET_ID)

        assert a.represented_nif == "12345678Z"
        assert a.granted_scopes == ("IVA",)
        assert b.represented_nif == "87654321X"
        assert b.granted_scopes == ("RENT",)


class TestApoderadoFlowDoor:
    """The paged apoderado flow walks its pages and commits through the real service."""

    def test_headless_walk_commits_through_the_production_door(self, isolated_settings: Settings) -> None:
        """Real line prompts reach the production service writer and read back durably.

        The input bytes drive the same ``LineFlowFrontend`` instance the CLI
        door delegates to. The runner itself performs the service write; the
        assertion then reads through the service's status boundary rather than
        trusting the transient flow state.
        """
        svc = _service(isolated_settings)
        output = StringIO()
        # Catalogue order is GENERALNT, RENT, IVA.  Move to RENT, select it,
        # move to IVA, select it, finish the checkbox, then submit review.
        keys = "87654321X\r\x1b[B \x1b[B \r\r"
        with create_pipe_input() as pipe:
            pipe.send_text(keys)
            result = run_apoderado_flow(
                svc,
                bucket_id=_APODERADO_BUCKET_ID,
                input=pipe,
                output=PlainTextOutput(output),
            )

        assert result.represented_nif == "87654321X"
        assert result.granted_scopes == ("IVA", "RENT")
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is True
        assert status.represented_nif == "87654321X"
        assert status.granted_scopes == ("IVA", "RENT")
        assert output.getvalue(), "the production line door must render its prompts and review"

    def test_ctrl_c_refuses_before_the_production_door_writes(self, isolated_settings: Settings) -> None:
        """Cancellation is typed and cannot manufacture an apoderado record."""
        svc = _service(isolated_settings)
        output = StringIO()
        with create_pipe_input() as pipe:
            pipe.send_text("\x03")
            with pytest.raises(FlowRunAbandonedError) as excinfo:
                run_apoderado_flow(
                    svc,
                    bucket_id=_APODERADO_BUCKET_ID,
                    input=pipe,
                    output=PlainTextOutput(output),
                )

        assert excinfo.value.translated_message == "errors.refused.refused_flow_run_abandoned"
        assert svc.status(bucket_id=_APODERADO_BUCKET_ID).configured is False

    def test_answer_pages_bind_no_profile_domain_key(self, isolated_settings: Settings) -> None:
        """Every answer page is domain_key-free: no apoderado answer is a profile fact."""
        svc = _service(isolated_settings)
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
        from ...flows.errors import FlowAnswerError

        svc = _service(isolated_settings)
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
        isolated_settings: Settings,
        repository_factory: InMemoryApoderadoConfigurationRepositoryFactory,
        tmp_path: Path,
    ) -> None:
        svc = ApoderadoService(repository_factory=repository_factory, settings=isolated_settings)
        wrong_root = tmp_path / "wrong-storage-root"

        with override_settings(
            cadrumo_local_storage_root=wrong_root, cadrumo_active_profile=_PROFILE_BUCKET_ID
        ):
            config = svc.configure(
                bucket_id=_PROFILE_BUCKET_ID,
                represented_nif="12345678Z",
                scope_tokens=("IVA",),
            )

        assert config.bucket_id == _PROFILE_BUCKET_ID
        assert svc.status(bucket_id=_PROFILE_BUCKET_ID).represented_nif == "12345678Z"
        assert repository_factory.settings_by_bucket[_PROFILE_BUCKET_ID] is isolated_settings


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
        svc = _service(isolated_settings)
        svc.configure(bucket_id=self._WRAPPED, represented_nif="12345678Z", scope_tokens=("IVA",))

        assert svc.status(bucket_id=_PROFILE_BUCKET_ID).configured is True
        assert svc.status(bucket_id=self._WRAPPED).configured is True

    def test_status_projects_the_canonical_identity(self, isolated_settings: Settings) -> None:
        """The returned status names the stored bucket, not the caller's spelling."""
        svc = _service(isolated_settings)
        svc.configure(bucket_id=_PROFILE_BUCKET_ID, represented_nif="12345678Z", scope_tokens=("IVA",))

        assert svc.status(bucket_id=self._WRAPPED).bucket_id == _PROFILE_BUCKET_ID
        assert svc.status(bucket_id=self._WRAPPED).represented_nif == "12345678Z"

    def test_unconfigured_status_also_projects_the_canonical_identity(
        self,
        isolated_settings: Settings,
    ) -> None:
        status = _service(isolated_settings).status(bucket_id=self._WRAPPED)

        assert status.configured is False
        assert status.bucket_id == _PROFILE_BUCKET_ID

    def test_clear_removes_a_record_addressed_by_either_spelling(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = _service(isolated_settings)
        svc.configure(bucket_id=_PROFILE_BUCKET_ID, represented_nif="12345678Z", scope_tokens=("IVA",))

        assert svc.clear(bucket_id=self._WRAPPED) is True
        assert svc.status(bucket_id=_PROFILE_BUCKET_ID).configured is False
        assert svc.clear(bucket_id=_PROFILE_BUCKET_ID) is False

    def test_repository_cache_is_keyed_canonically(self, isolated_settings: Settings) -> None:
        """Two spellings must not open two repositories over one bucket's storage."""
        svc = _service(isolated_settings)

        first = svc._repository_for(_PROFILE_BUCKET_ID)
        second = svc._repository_for(self._WRAPPED)

        assert first is second

    @pytest.mark.parametrize("bad", ["", "   ", "x" * 129])
    def test_uncanonicalizable_bucket_input_is_refused(
        self,
        isolated_settings: Settings,
        bad: str,
    ) -> None:
        """A blank or overlength bucket cannot silently address a repository.

        The refusal is the property under test, not its exception class. This
        surface now defers to :func:`~cadrumo.core.identity.canonical_bucket_id`
        rather than re-deriving the rule, and that shared helper deliberately
        raises the plain builtin so it does not impose one consumer's error
        class on every other. ``ValidationError`` subclasses ``ValueError``, so
        this still holds whichever the boundary raises.
        """
        svc = _service(isolated_settings)

        with pytest.raises(ValueError):
            svc.status(bucket_id=bad)
        with pytest.raises(ValueError):
            svc.clear(bucket_id=bad)

    def test_distinct_buckets_stay_distinct(self) -> None:
        """Canonicalisation must not merge two genuinely different buckets.

        Trimming is only safe if it collapses spellings of ONE identity; a
        normaliser that also collapsed two identities would route bucket B's
        represented NIF into bucket A's repository.
        """
        assert canonical_bucket_id(self._WRAPPED) == canonical_bucket_id(_PROFILE_BUCKET_ID)
        assert canonical_bucket_id(_SECONDARY_PROFILE_BUCKET_ID) != canonical_bucket_id(_PROFILE_BUCKET_ID)
