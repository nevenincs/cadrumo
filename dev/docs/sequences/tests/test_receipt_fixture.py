"""Synthetic receipt custody stays inside its explicitly selected docs sandbox."""

import sys
from pathlib import Path

import keyring
import pytest
from keyring.errors import PasswordDeleteError

from cadrumo.tests.audited_process import run_audited_process

from ..receipt_fixture import (
    RECEIPT_FIXTURE_DIRECTORY,
    SequenceReceiptKeyring,
    requires_persistent_sign_in,
    sequence_receipt_store,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("sequence_ids", "enabled"),
    [
        (("profile-setup-inspect", "profile-setup-logout"), True),
        (("profile-setup-delete",), True),
        (("protect-data-access-inspect", "protect-data-access-logout"), True),
        (("profile-setup-inspect", "protect-data-access-inspect"), False),
        (("how-to/profile-setup",), False),
        ((), False),
    ],
)
def test_page_selection_uses_enrolled_scenarios_and_cleans_up(
    tmp_path: Path, sequence_ids: tuple[str, ...], enabled: bool
) -> None:
    previous = keyring.get_keyring()
    with sequence_receipt_store(tmp_path, enabled=requires_persistent_sign_in(sequence_ids)):
        assert (tmp_path / RECEIPT_FIXTURE_DIRECTORY).exists() is enabled
        if enabled:
            keyring.set_password("page-test", "account", "synthetic-proof")
        else:
            assert keyring.get_keyring() is previous
    assert keyring.get_keyring() is previous
    assert not (tmp_path / RECEIPT_FIXTURE_DIRECTORY).exists()


def test_shared_receipt_store_is_isolated_and_reaped_on_failure(tmp_path: Path) -> None:
    previous = keyring.get_keyring()
    with pytest.raises(RuntimeError, match="fixture failed"), sequence_receipt_store(tmp_path, enabled=True):
        keyring.set_password("synthetic-service", "synthetic-account", "synthetic-proof")
        reader = SequenceReceiptKeyring(tmp_path / RECEIPT_FIXTURE_DIRECTORY)
        assert reader.get_password("synthetic-service", "synthetic-account") == "synthetic-proof"
        assert reader.get_password("other-service", "synthetic-account") is None
        reader.delete_password("synthetic-service", "synthetic-account")
        assert keyring.get_password("synthetic-service", "synthetic-account") is None
        with pytest.raises(PasswordDeleteError):
            reader.delete_password("synthetic-service", "synthetic-account")
        keyring.set_password("synthetic-service", "synthetic-account", "synthetic-proof")
        raise RuntimeError("fixture failed")
    assert keyring.get_keyring() is previous
    assert not (tmp_path / RECEIPT_FIXTURE_DIRECTORY).exists()


def test_default_scenario_does_not_replace_the_selected_backend(tmp_path: Path) -> None:
    previous = keyring.get_keyring()
    with sequence_receipt_store(tmp_path, enabled=False):
        assert keyring.get_keyring() is previous
        assert not (tmp_path / RECEIPT_FIXTURE_DIRECTORY).exists()


def test_child_receipt_is_readable_and_revocable_by_parent(tmp_path: Path) -> None:
    with sequence_receipt_store(tmp_path, enabled=True):
        child = run_audited_process(
            [
                sys.executable,
                "-c",
                "import sys; from pathlib import Path; "
                "from dev.docs.sequences.receipt_fixture import SequenceReceiptKeyring; "
                "SequenceReceiptKeyring(Path(sys.argv[1])).set_password('test', 'account', 'synthetic-proof')",
                str(tmp_path / RECEIPT_FIXTURE_DIRECTORY),
            ],
            capture_output=True,
            text=True,
            timeout=None,
        )
        assert child.returncode == 0, child.stderr
        assert keyring.get_password("test", "account") == "synthetic-proof"
        keyring.delete_password("test", "account")
        assert keyring.get_password("test", "account") is None
