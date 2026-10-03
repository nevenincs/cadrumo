# serial: shares the process-global master-key-provider / active-profile state
# that flakes under `-n auto` worker interleaving; runs in the serial (-n0) pass.
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...config_payloads import (
    ApoderadoCheckResult,
    ApoderadoClearResult,
    ApoderadoConfigureResult,
    ApoderadoStatusResult,
)
from ...main import app as root_app
from ...tests.cli_runner import invoke_typer_app
from ...tests.diagnostics_native_support import diagnostics_native_profile, invoke_diagnostics_cli
from ...tests.runtime_profile_cli_fixture import NativeCliProfileFixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.usefixtures("authority_operation"),
]

__all__ = ["diagnostics_native_profile"]


def test_apoderado_status_fails_without_profile(tmp_path: Path) -> None:
    """Keep the root admission refusal clear when no profile exists."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        result = invoke_typer_app(root_app, ["--language", "en", "config", "auth", "apoderado", "status"])
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output, result.output
    assert "Refused" in result.output, result.output
    assert "config profile create" in result.output, result.output


def test_apoderado_scopes_list_remains_public() -> None:
    from ...tests.cli_runner import invoke_cached_cli

    result = invoke_cached_cli(["config", "auth", "apoderado", "scopes", "list"])
    assert result.exit_code == 0
    assert "GENERAL" in result.output


def test_apoderado_happy_path_uses_exact_encrypted_profile_worker(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """Every private verb stays bound to the registered profile worker."""
    status = invoke_diagnostics_cli(["config", "auth", "apoderado", "status"])
    assert status.exit_code == 0, f"apoderado status failed: {status.output}"
    assert "configured\tFalse" in status.output

    configure = invoke_diagnostics_cli(
        ["config", "auth", "apoderado", "configure", "--represented-nif", "87654321X", "--scope", "RENT"],
    )
    assert configure.exit_code == 0, f"apoderado configure failed: {configure.output}"
    assert "represented_nif\tsha256:" in configure.output
    assert "87654321X" not in configure.output, f"raw NIF leaked into CLI output: {configure.output!r}"
    assert "RENT" in configure.output

    status_after = invoke_diagnostics_cli(["config", "auth", "apoderado", "status"])
    assert status_after.exit_code == 0, status_after.output
    assert "configured\tTrue" in status_after.output

    check = invoke_diagnostics_cli(["config", "auth", "apoderado", "check"])
    assert check.exit_code != 0, f"apoderado check should refuse, got: {check.output}"
    assert "configured\tTrue" not in check.output, (
        f"check leaked a stored-config status as a live result: {check.output!r}"
    )

    clear = invoke_diagnostics_cli(["config", "auth", "apoderado", "clear"])
    assert clear.exit_code == 0, f"apoderado clear failed: {clear.output}"
    assert "cleared\tTrue" in clear.output


def test_apoderado_configure_without_nif_refuses_naming_the_flags(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """The interactive door under a non-interactive host names the recovery flags.

    Invoked without ``--represented-nif`` the verb opens the paged flow; the
    test runner is a non-interactive host, so the door refuses -- and the
    refusal must name ``--represented-nif`` (the real recovery), not the
    generic scripted-answer-file copy.
    """
    result = invoke_diagnostics_cli(["config", "auth", "apoderado", "configure", "--scope", "RENT"])
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output, result.output
    assert "--represented-nif" in result.output, result.output


def test_apoderado_configure_without_scope_lists_the_accepted_codes(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """A missing --scope refuses by enumerating the accepted catalogue codes."""
    result = invoke_diagnostics_cli(
        ["config", "auth", "apoderado", "configure", "--represented-nif", "87654321X"],
    )
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output, result.output
    # The refusal enumerates the accepted set (never a bare "value required").
    assert "RENT" in result.output, result.output
    assert "GENERALNT" in result.output, result.output


def test_apoderado_configure_rejects_invalid_nif_on_the_flags_path(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """The flags path validates the represented NIF through the same identity authority.

    A malformed ``--represented-nif`` refuses (parity with the interactive
    page validator) and never echoes the raw value.
    """
    result = invoke_diagnostics_cli(
        ["config", "auth", "apoderado", "configure", "--represented-nif", "NOTANIF", "--scope", "RENT"],
    )
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output, result.output
    assert "NOTANIF" not in result.output, f"raw represented NIF leaked: {result.output!r}"


def test_apoderado_configure_leaves_profile_facts_untouched(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """Profile facts remain stable while delegation state uses its own namespace."""
    import json

    before = invoke_diagnostics_cli(["--format", "json", "config", "profile", "view"])
    assert before.stdout
    before_document = json.loads(before.stdout)
    before_facts = before_document["result"]["facts"]

    configure = invoke_diagnostics_cli(
        ["config", "auth", "apoderado", "configure", "--represented-nif", "87654321X", "--scope", "RENT"],
    )
    assert configure.exit_code == 0, f"apoderado configure failed: {configure.output}"

    after = invoke_diagnostics_cli(["--format", "json", "config", "profile", "view"])
    assert after.stdout
    after_document = json.loads(after.stdout)
    after_facts = after_document["result"]["facts"]
    assert after_facts == before_facts, (
        f"apoderado configure changed profile facts: before={before_facts!r} after={after_facts!r}"
    )

    status = invoke_diagnostics_cli(["config", "auth", "apoderado", "status"])
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
