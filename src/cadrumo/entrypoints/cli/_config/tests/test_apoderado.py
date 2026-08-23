# serial: shares the process-global master-key-provider / active-profile state
# that flakes under `-n auto` worker interleaving; runs in the serial (-n0) pass.
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....tests.cli_runner import invoke_typer_app
from .....tests.profile_storage_root_fixture import profile_storage_root_fixture

__all__ = ["profile_storage_root_fixture"]

from .....tests.secure_sql import isolated_profile_storage_root
from .....tests.user_profile import register_cli_profile
from ... import app as root_app
from ..._config_payloads import (
    ApoderadoCheckResult,
    ApoderadoClearResult,
    ApoderadoConfigureResult,
    ApoderadoStatusResult,
)
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]


def test_apoderado_status_fails_without_profile(tmp_path: Path) -> None:
    # Pin an isolated storage root with no active profile so an ambient
    # active-profile pointer left by a peer test cannot mask the
    # no-active-profile refusal this test asserts.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        # Invoke through the ROOT app (the production path). The config
        # sub-app is never reached directly in production, and invoking it
        # directly breaks under test ordering once another test has lazily
        # materialised the config subtree on the full app (see #211). Through
        # the root app the error boundary RENDERS the no-active-profile
        # refusal, so assert the rendered refusal rather than the leaked
        # exception.
        result = invoke_typer_app(root_app, ["config", "auth", "apoderado", "status"])
        # Must refuse — any non-zero exit code is acceptable (the boundary
        # maps refusals to its own exit category) — and it must be a clean
        # refusal, not a crash.
        assert result.exit_code != 0, result.output
        assert "Traceback" not in result.output, result.output
        assert "Refused" in result.output, result.output
        # The rendered copy is the no-active-profile refusal specifically: it
        # is the refusal that directs the operator to create a profile. The
        # `config profile create` guidance is locale-independent (the prose
        # around it localises, this command token does not).
        assert "config profile create" in result.output, result.output


def test_apoderado_scopes_list() -> None:
    result = invoke_typer_app(app, ["auth", "apoderado", "scopes", "list"])
    assert result.exit_code == 0
    assert "GENERAL" in result.output


def test_apoderado_service_importable_and_has_cli_callers() -> None:
    from .....application.auth import ApoderadoService
    from .._apoderado import apoderado_scopes_list

    service = ApoderadoService()
    scope_codes = service.catalogue.code_set()

    assert callable(apoderado_scopes_list)
    assert "GENERALNT" in scope_codes


def test_apoderado_happy_path_against_active_profile(profile_storage_root: Path) -> None:
    """status/configure/clear succeed against the active profile.

    The active-profile pointer carries the immutable UUID identity; the
    apoderado verbs must resolve that UUID directly, not feed it to the
    label-based ``read_profile_bucket`` resolver. This exercises the
    normal active-profile path the no-active-profile test cannot reach.
    """
    from .....adapters.persistence.storage.sql.engine import dispose_engine

    register_cli_profile(
        label="myco",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "MyCo",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )

    # status: exit 0 on the active profile (previously crashed with
    # AttributeError because the UUID never matched a label).
    dispose_engine()
    status = invoke_typer_app(root_app, ["config", "auth", "apoderado", "status"])
    assert status.exit_code == 0, f"apoderado status failed: {status.output}"
    assert "configured\tFalse" in status.output

    # configure: exit 0, persists the apoderado config.
    dispose_engine()
    configure = invoke_typer_app(
        root_app,
        [
            "config",
            "auth",
            "apoderado",
            "configure",
            "--represented-nif",
            "87654321X",
            "--scope",
            "RENT",
        ],
    )
    assert configure.exit_code == 0, f"apoderado configure failed: {configure.output}"
    # NIF is identity-class data: the CLI success-output redactor rewrites
    # any 8-digits+letter NIF span via SHA256_PREFIX, so the rendered line
    # carries the fingerprint, not the raw NIF. Pin both the field label
    # and the fingerprint shape so an unintended raw leak would still fail.
    assert "represented_nif\tsha256:" in configure.output
    assert "87654321X" not in configure.output, f"raw NIF leaked into CLI output: {configure.output!r}"
    assert "RENT" in configure.output

    # status now reflects the configured state.
    dispose_engine()
    status_after = invoke_typer_app(root_app, ["config", "auth", "apoderado", "status"])
    assert status_after.exit_code == 0, status_after.output
    assert "configured\tTrue" in status_after.output

    # check: refuses. It is the live-verification verb and the live AEAT-read
    # path is sealed, so it must NOT silently re-read the stored config and
    # present it as a live result — it refuses with the registered REFUSED
    # copy instead. Any non-zero exit is acceptable; the refusal carries the
    # operator-facing message.
    dispose_engine()
    check = invoke_typer_app(root_app, ["config", "auth", "apoderado", "check"])
    assert check.exit_code != 0, f"apoderado check should refuse, got: {check.output}"
    assert "configured\tTrue" not in check.output, (
        f"check leaked a stored-config status as a live result: {check.output!r}"
    )

    # clear: exit 0, retires the apoderado config.
    dispose_engine()
    clear = invoke_typer_app(root_app, ["config", "auth", "apoderado", "clear"])
    assert clear.exit_code == 0, f"apoderado clear failed: {clear.output}"
    assert "cleared\tTrue" in clear.output


def _create_active_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="myco",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "MyCo",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )


def test_apoderado_configure_without_nif_refuses_naming_the_flags(profile_storage_root: Path) -> None:
    """The interactive door under a non-interactive host names the recovery flags.

    Invoked without ``--represented-nif`` the verb opens the paged flow; the
    test runner is a non-interactive host, so the door refuses -- and the
    refusal must name ``--represented-nif`` (the real recovery), not the
    generic scripted-answer-file copy.
    """
    from .....adapters.persistence.storage.sql.engine import dispose_engine

    _create_active_profile()
    dispose_engine()

    result = invoke_typer_app(root_app, ["config", "auth", "apoderado", "configure", "--scope", "RENT"])
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output, result.output
    assert "--represented-nif" in result.output, result.output


def test_apoderado_configure_without_scope_lists_the_accepted_codes(profile_storage_root: Path) -> None:
    """A missing --scope refuses by enumerating the accepted catalogue codes."""
    from .....adapters.persistence.storage.sql.engine import dispose_engine

    _create_active_profile()
    dispose_engine()

    result = invoke_typer_app(
        root_app,
        ["config", "auth", "apoderado", "configure", "--represented-nif", "87654321X"],
    )
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output, result.output
    # The refusal enumerates the accepted set (never a bare "value required").
    assert "RENT" in result.output, result.output
    assert "GENERALNT" in result.output, result.output


def test_apoderado_configure_rejects_invalid_nif_on_the_flags_path(profile_storage_root: Path) -> None:
    """The flags path validates the represented NIF through the same identity authority.

    A malformed ``--represented-nif`` refuses (parity with the interactive
    page validator) and never echoes the raw value.
    """
    from .....adapters.persistence.storage.sql.engine import dispose_engine

    _create_active_profile()
    dispose_engine()

    result = invoke_typer_app(
        root_app,
        ["config", "auth", "apoderado", "configure", "--represented-nif", "NOTANIF", "--scope", "RENT"],
    )
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output, result.output
    assert "NOTANIF" not in result.output, f"raw represented NIF leaked: {result.output!r}"


def test_apoderado_configure_leaves_profile_facts_untouched(profile_storage_root: Path) -> None:
    """Configuring apoderado writes only to the ApoderadoService namespace.

    Representation is NOT a profile fact: the door routes writes to the
    apoderado encrypted namespace, never the taxpayer profile record. This
    snapshots the active profile's facts before and after a configure and
    asserts the fact set is byte-identical, so no ``renta_family.*`` /
    profile fact was minted by the apoderado walk.
    """
    from .....adapters.persistence.storage.sql.engine import dispose_engine
    from .._profile_readiness import _read_profile_record

    register_cli_profile(
        label="myco",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "MyCo",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )

    from .....application.workflow import read_profile_bucket

    pointer = read_profile_bucket("myco")
    assert pointer is not None
    before = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    before_facts = {fact.path: fact.value for fact in before.facts}

    dispose_engine()
    configure = invoke_typer_app(
        root_app,
        [
            "config",
            "auth",
            "apoderado",
            "configure",
            "--represented-nif",
            "87654321X",
            "--scope",
            "RENT",
        ],
    )
    assert configure.exit_code == 0, f"apoderado configure failed: {configure.output}"

    dispose_engine()
    after = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    after_facts = {fact.path: fact.value for fact in after.facts}
    assert after_facts == before_facts, (
        f"apoderado configure mutated profile facts: "
        f"added={set(after_facts) - set(before_facts)} removed={set(before_facts) - set(after_facts)}"
    )

    # The representation landed in the apoderado namespace: the status verb
    # (which opens the active-profile storage span) reads it back configured.
    dispose_engine()
    status = invoke_typer_app(root_app, ["config", "auth", "apoderado", "status"])
    assert status.exit_code == 0, status.output
    assert "configured\tTrue" in status.output
    assert "RENT" in status.output


class TestApoderadoEnvelopeContractParity:
    """The wire envelopes carry the canonical models' own constraints.

    ``ApoderadoConfiguration`` and ``ApoderadoStatus`` enforce a canonical
    ``BucketId``, a bounded represented identity, a non-empty catalogue
    version, bounded notes, and real ``datetime`` instants. The four CLI
    envelopes redeclared those fields as bare strings, so a blank,
    whitespace-only, or 129-character bucket, a ``configured_at`` of
    ``"not-time"``, an empty catalogue version, and a 501-character notes
    value all passed the wire boundary the canonical models refuse.
    """

    _CANONICAL_BUCKET = "26262626-2626-4262-8262-262626262626"
    _INSTANT = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)

    def _status(self, **overrides: object) -> ApoderadoStatusResult:
        fields: dict[str, object] = {"bucket_id": self._CANONICAL_BUCKET, "configured": False}
        fields.update(overrides)
        return ApoderadoStatusResult.model_validate(fields)

    def _configure(self, **overrides: object) -> ApoderadoConfigureResult:
        fields: dict[str, object] = {
            "bucket_id": self._CANONICAL_BUCKET,
            "represented_nif": "12345678Z",
            "catalogue_version": "v1",
            "configured_at": self._INSTANT,
        }
        fields.update(overrides)
        return ApoderadoConfigureResult.model_validate(fields)

    @pytest.mark.parametrize("bad", ["", "   ", "x" * 129])
    def test_every_envelope_refuses_a_non_canonical_bucket(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            self._status(bucket_id=bad)
        with pytest.raises(ValidationError):
            self._configure(bucket_id=bad)
        with pytest.raises(ValidationError):
            ApoderadoClearResult(bucket_id=bad, cleared=True)
        with pytest.raises(ValidationError):
            ApoderadoCheckResult(bucket_id=bad, configured=False)

    def test_configured_at_must_be_a_real_instant(self) -> None:
        with pytest.raises(ValidationError):
            self._configure(configured_at="not-time")
        with pytest.raises(ValidationError):
            self._status(configured_at="not-time")

    def test_catalogue_version_must_be_populated(self) -> None:
        with pytest.raises(ValidationError):
            self._configure(catalogue_version="")
        with pytest.raises(ValidationError):
            self._status(catalogue_version="")

    def test_notes_and_represented_identity_stay_bounded(self) -> None:
        with pytest.raises(ValidationError):
            self._configure(notes="x" * 501)
        with pytest.raises(ValidationError):
            self._configure(represented_nif="x" * 17)
        with pytest.raises(ValidationError):
            self._configure(represented_nif="")

    def test_a_canonical_projection_round_trips(self) -> None:
        """Anti-tautology: the refusals discriminate rather than always-refusing."""
        configure = self._configure(notes="within bounds")

        assert configure.bucket_id == self._CANONICAL_BUCKET
        assert configure.configured_at == self._INSTANT
        assert ApoderadoConfigureResult.model_validate_json(configure.model_dump_json()) == configure

    def test_a_padded_bucket_is_canonicalized_like_the_domain_model(self) -> None:
        assert self._status(bucket_id=f"  {self._CANONICAL_BUCKET}  ").bucket_id == self._CANONICAL_BUCKET
