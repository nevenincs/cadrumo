"""``aeat app modelo work calculate`` decrypts the profile once for the whole command.

The command runs the readiness gate twice, the IVA-wallet and ledger gates,
the profile binding tier, the source mesh (relation prefill, previous-filing
carry, Renta expenses, the Modelo 303 annual-summary scope) and the
post-calculation advisories. Each of those used to decrypt the profile capsule
on its own; the command now loads it once and every consumer reads that
record. The count is taken at the capsule store behind the real CLI, so a
consumer that bypasses the record repository is counted too.

The Modelo 100 scenario is counted up to whatever outcome the command reaches:
the count holds for every step the command runs.
"""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....application.modelo.profile_readiness_gate import load_modelo_work_profile, require_profile_ready_for_work_unit
from ....application.user_profile.capsule_record import LoadedProfileRecord, ProfileRecordStore
from ....core.bucket_pointer import resolve_active_bucket_id
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....tests.cli_envelope import unwrap_schema_envelope
from .._modelo_behavior_support import resolve_work_unit_for_cli
from ._modelo_work_ux_support import (
    _capture_m115_invoice_withholding,
    _create_calculable_work_unit,
    operator_profile_facts,
)
from .cli_runner import invoke_cached_cli
from .modelo_cli import create_modelo_work_unit_via_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["_isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture
def profile_decrypts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every profile-record decrypt in the process, still performing it."""
    decrypts: list[str] = []
    real_load = ProfileRecordStore.load

    def counting_load(self: ProfileRecordStore) -> LoadedProfileRecord:
        decrypts.append(str(self.session.profile_id))
        return real_load(self)

    monkeypatch.setattr(ProfileRecordStore, "load", counting_load)
    return decrypts


def _create_work_unit(*, modelo: str, year: int, period: str) -> str:
    """Create a work unit on the revision the law selects for its target."""
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", modelo, "--year", str(year), "--period", period,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    work_unit_id = unwrap_schema_envelope(result.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _calculate(decrypts: list[str], *arguments: str) -> tuple[int, str]:
    """Run one real ``work calculate`` and keep only the decrypts it performed."""
    decrypts.clear()
    result = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "calculate", *arguments])
    return result.exit_code, result.output


def test_m111_calculate_decrypts_the_profile_once(seed_profile: ProfileSeeder, profile_decrypts: list[str]) -> None:
    seed_profile(label="operator", facts=operator_profile_facts())
    work_unit_id = _create_calculable_work_unit()

    exit_code, output = _calculate(profile_decrypts, work_unit_id)

    assert exit_code == 0, output
    assert len(profile_decrypts) == 1, profile_decrypts


def test_m115_calculate_decrypts_the_profile_once(seed_profile: ProfileSeeder, profile_decrypts: list[str]) -> None:
    seed_profile(label="operator", facts=operator_profile_facts())
    work_unit_id = _create_work_unit(modelo="115", year=2025, period="1T")
    _capture_m115_invoice_withholding()

    exit_code, output = _calculate(profile_decrypts, work_unit_id, "--casilla", "04=0")

    assert exit_code == 0, output
    assert len(profile_decrypts) == 1, profile_decrypts


def test_m100_calculate_decrypts_the_profile_once(seed_profile: ProfileSeeder, profile_decrypts: list[str]) -> None:
    seed_profile(label="operator", facts=operator_profile_facts())
    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")

    _, output = _calculate(
        profile_decrypts,
        work_unit_id,
        "--binding",
        "renta-modelo-100-estimacion-directa-es-normal=1",
    )

    assert len(profile_decrypts) == 1, (profile_decrypts, output)


def test_m303_attestation_cli_admits_only_a_sanitized_secure_reference_once(
    seed_profile: ProfileSeeder, profile_decrypts: list[str]
) -> None:
    seed_profile(label="operator", facts=operator_profile_facts())

    profile_decrypts.clear()
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "attest-m303-exonerado-390",
            "--year",
            "2025",
            "--period",
            "1T",
            "--observed-at",
            "2025-03-31T12:00:00+00:00",
        ]
    )

    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    attachment_id = payload["attachment_id"]
    sha256 = payload["sha256"]
    assert isinstance(attachment_id, str) and len(attachment_id) == 64
    assert attachment_id == sha256
    assert payload["filing_year"] == 2025
    assert payload["period"] == {"filing_year": 2025, "code": "1T"}
    assert "profile_witness" not in result.output
    assert "attachment:" not in result.output
    assert "filing_evidence_reference" not in result.output
    assert len(profile_decrypts) == 1, profile_decrypts


def test_the_readiness_gate_hands_back_the_profile_it_checked(seed_profile: ProfileSeeder) -> None:
    """Consumers downstream of the gate read the very record the gate refused or admitted."""
    seed_profile(label="operator", facts=operator_profile_facts())
    work_unit_id = _create_calculable_work_unit()
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    work_unit = resolve_work_unit_for_cli(work_unit_id=work_unit_id)

    with bundled_indexed_authority().operation() as operation:
        loaded = load_modelo_work_profile(
            bucket_id=bucket_id, profile_decode_context=operation.profile_decode_context()
        )
        assert loaded is not None
        checked = require_profile_ready_for_work_unit(
            work_unit,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
            profile=loaded,
        )
        loaded_by_gate = require_profile_ready_for_work_unit(
            work_unit,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
        )

    assert checked is loaded
    assert loaded_by_gate.record == loaded.record
