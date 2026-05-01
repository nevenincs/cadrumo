"""Tests for the ``aeat secrets`` CLI namespace."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from .secrets import app as secrets_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.fixture
def secret_store(tmp_path: Path) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(store)
    try:
        yield store
    finally:
        override_secret_store(None)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestList:
    def test_empty_store_emits_dim_message(self, secret_store: SecretStore, runner: CliRunner) -> None:
        result = runner.invoke(secrets_app, ["list"])
        assert result.exit_code == 0
        assert "no secrets persisted" in result.stdout

    def test_lists_digests_after_put(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        value_file = tmp_path / "v.txt"
        value_file.write_bytes(b"my-secret-value-payload")
        put_result = runner.invoke(
            secrets_app,
            ["put", "aeat:test:k1", "--from-file", str(value_file)],
        )
        assert put_result.exit_code == 0
        list_result = runner.invoke(secrets_app, ["list"])
        assert list_result.exit_code == 0
        # The digest is 64 hex chars; can't predict its value without
        # the master key, but it must be present and non-empty.
        digest_line = next(
            (line for line in list_result.stdout.splitlines() if len(line.strip()) == 64),
            None,
        )
        assert digest_line is not None


class TestPut:
    def test_round_trip_via_file(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        value_file = tmp_path / "v.txt"
        value_file.write_bytes(b"round-trip-payload")
        result = runner.invoke(
            secrets_app,
            ["put", "aeat:test:rt", "--from-file", str(value_file)],
        )
        assert result.exit_code == 0
        loaded = secret_store.get("aeat:test:rt")
        assert loaded.value == b"round-trip-payload"

    def test_collision_without_overwrite_exits_2(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        value_file = tmp_path / "v.txt"
        value_file.write_bytes(b"first")
        first = runner.invoke(
            secrets_app,
            ["put", "aeat:test:dup", "--from-file", str(value_file)],
        )
        assert first.exit_code == 0
        second = runner.invoke(
            secrets_app,
            ["put", "aeat:test:dup", "--from-file", str(value_file)],
        )
        assert second.exit_code == 2

    def test_overwrite_replaces_value(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        a = tmp_path / "a.txt"
        a.write_bytes(b"first")
        b = tmp_path / "b.txt"
        b.write_bytes(b"second")
        runner.invoke(secrets_app, ["put", "aeat:test:upd", "--from-file", str(a)])
        result = runner.invoke(
            secrets_app,
            ["put", "aeat:test:upd", "--from-file", str(b), "--overwrite"],
        )
        assert result.exit_code == 0
        assert secret_store.get("aeat:test:upd").value == b"second"

    def test_invalid_expires_in_rejected(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        value_file = tmp_path / "v.txt"
        value_file.write_bytes(b"x")
        result = runner.invoke(
            secrets_app,
            ["put", "aeat:test:k", "--from-file", str(value_file), "--expires-in", "two-days"],
        )
        assert result.exit_code != 0


class TestRm:
    def test_delete_existing(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        value_file = tmp_path / "v.txt"
        value_file.write_bytes(b"goodbye")
        runner.invoke(secrets_app, ["put", "aeat:test:bye", "--from-file", str(value_file)])
        result = runner.invoke(secrets_app, ["rm", "aeat:test:bye"])
        assert result.exit_code == 0

    def test_delete_missing_exits_1(self, secret_store: SecretStore, runner: CliRunner) -> None:
        result = runner.invoke(secrets_app, ["rm", "never-stored"])
        assert result.exit_code == 1


class TestRotate:
    def test_rotate_replaces_value(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        a = tmp_path / "a.txt"
        a.write_bytes(b"v1")
        b = tmp_path / "b.txt"
        b.write_bytes(b"v2")
        runner.invoke(secrets_app, ["put", "aeat:test:rot", "--from-file", str(a)])
        result = runner.invoke(
            secrets_app,
            ["rotate", "aeat:test:rot", "--from-file", str(b)],
        )
        assert result.exit_code == 0
        assert secret_store.get("aeat:test:rot").value == b"v2"

    def test_rotate_missing_exits_1(
        self,
        secret_store: SecretStore,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        value_file = tmp_path / "v.txt"
        value_file.write_bytes(b"x")
        result = runner.invoke(
            secrets_app,
            ["rotate", "never-stored", "--from-file", str(value_file)],
        )
        assert result.exit_code == 1
