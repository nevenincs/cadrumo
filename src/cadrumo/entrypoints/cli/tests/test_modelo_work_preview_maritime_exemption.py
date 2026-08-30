"""CLI surface tests for `aeat app modelo work preview-maritime-exemption`.

Exercises the verb that surfaces the maritime worker IRPF exemption
(Art. 7.p) LIRPF / REBECA 50% / DA 41 inactive / RETMAR mandatory-filing)
to operators. Verifies the four observable contracts the verb must hold:

1. Help text renders in the operator's locale (no raw ``tr()`` keys leak).
2. The JSON envelope passes :meth:`OutputSchema.model_validate` and carries
   typed CasillaObservation rows with canonical ``legal_refs`` ids.
3. The DA 41 inactive guard refuses with the registered error code when
   the active profile carries the tuna-fleet selector facts, driven
   end-to-end through the CLI verb body.
4. The RETMAR completeness gate surfaces the translated warning when the
   active profile carries ``retmar_registered=True`` while still emitting
   the observation payload (non-blocking).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.modelo._maritime_preview import maritime_facts_from_active_profile
from ....core.config import override_settings
from ....core.errors.error_codes import ErrorCategory, get_error_exit_code
from ....tests.cli_envelope import unwrap_schema_envelope as _unwrap
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .._modelo_payloads import (
    WorkPreviewMaritimeExemptionResult,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_BUCKET_ID = "70707070-7070-4507-8507-070707070707"


@pytest.fixture
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(cadrumo_live_state_dir=tmp_path / "probe-live-state"),
        open_test_profile_session(_BUCKET_ID),
    ):
        yield


def _register_maritime_profile(*, overrides: dict[str, str]) -> None:
    """Seed an active profile carrying ``maritime_worker.*`` facts."""
    register_minimal_profile(profile_id=_BUCKET_ID, overrides=overrides)


class TestHelpSurfaceLocalisation:
    """Verb help renders in the active output language, not the tr() key."""

    def test_spanish_help_renders_spanish_translation(self) -> None:
        result = invoke_cached_cli(
            [
                "--language", "es",
                "app", "modelo", "work", "preview-maritime-exemption", "--help",
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        # The Spanish help text mentions the legal pathway. The raw tr()
        # key would surface as the literal "preview_maritime_exemption_help"
        # token; the translation does not contain that literal.
        assert "preview_maritime_exemption_help" not in result.output
        assert "trabajador del mar" in result.output.lower() or "REBECA" in result.output

    def test_english_help_renders_english_translation(self) -> None:
        result = invoke_cached_cli(
            [
                "--language", "en",
                "app", "modelo", "work", "preview-maritime-exemption", "--help",
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        assert "preview_maritime_exemption_help" not in result.output
        assert "Art. 7.p" in result.output or "REBECA" in result.output


class TestArt7pEnvelopeContract:
    """JSON envelope carries CasillaObservation with the Art. 7.p) BOE anchor."""

    def test_art_7p_envelope_validates_against_output_schema(self, isolated_backend: None) -> None:
        _register_maritime_profile(
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_flag": "foreign",
                "maritime_worker.waters_type": "international",
            },
        )
        result = invoke_cached_cli(
            [
                "--format", "json",
                "app", "modelo", "work", "preview-maritime-exemption",
                "--annual-salary", "36500",
                "--qualifying-days", "100",
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        payload = _unwrap(result.output)
        # Strict pydantic round-trip: the envelope MUST satisfy
        # OutputSchema.model_validate or the schema-conformance gate
        # would catch the regression.
        validated = WorkPreviewMaritimeExemptionResult.model_validate(payload)
        assert validated.worker_class == "trabajador_del_mar"
        assert len(validated.observations) == 1
        observation = validated.observations[0]
        assert observation.legal_refs == ["ley-35-2006:art-7"]
        # Flat projection mirrors the typed observation.
        assert validated.casilla_values[observation.casilla_id] == observation.value


class TestRetmarMandatoryFilingWarningSurface:
    """RETMAR completeness gate surfaces as a translated non-blocking warning."""

    def test_retmar_registered_profile_emits_warning_alongside_observation(self, isolated_backend: None) -> None:
        _register_maritime_profile(
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_registry": "REBECA",
                "maritime_worker.retmar_registered": "true",
            },
        )
        result = invoke_cached_cli(
            [
                "--language", "es",
                "--format", "json",
                "app", "modelo", "work", "preview-maritime-exemption",
                "--gross-navigation-income", "30000",
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        payload = _unwrap(result.output)
        validated = WorkPreviewMaritimeExemptionResult.model_validate(payload)
        assert validated.retmar_mandatory_filing is True
        # The RETMAR warning rides the registered ProfileCompletenessError
        # translated through the error registry; the Spanish anchor must
        # name RETMAR and the LIRPF art. 96 BOE id.
        assert validated.retmar_warning is not None
        assert "RETMAR" in validated.retmar_warning
        assert "BOE-A-2006-20764" in validated.retmar_warning
        # The observation payload is still produced (the warning is
        # non-blocking per service contract).
        assert len(validated.observations) == 1
        assert validated.observations[0].legal_refs == ["ley-19-1994:art-75"]


class TestDa41InactiveGuard:
    """DA 41 inactive guard refuses through the CLI verb body end-to-end.

    The active profile carries ``maritime_worker.tuna_fleet=true`` and
    ``maritime_worker.pending_eu_clearance=true`` schema facts; the verb
    body resolves them via :func:`_maritime_facts_from_active_profile`
    and dispatches the maritime exemption service, which raises
    :class:`MaritimeExemptionInactiveError`. The CLI error boundary maps
    that exception to the registered ``REFUSED`` exit category and
    renders the translated message in the operator's active locale.
    """

    def test_da41_refusal_propagates_through_cli_verb(self, isolated_backend: None) -> None:
        _register_maritime_profile(
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.tuna_fleet": "true",
                "maritime_worker.pending_eu_clearance": "true",
            },
        )
        result = invoke_cached_cli(
            [
                "--language", "es",
                "app", "modelo", "work", "preview-maritime-exemption",
                "--annual-salary", "36500",
                "--qualifying-days", "100",
            ],
        )  # fmt: skip
        refused_exit = get_error_exit_code(ErrorCategory.REFUSED)
        assert result.exit_code == refused_exit, result.output
        # The Spanish-locale error envelope must name the DA 41 anchor
        # and the Ley 35/2006 BOE id; the boundary renders the message
        # registered for ``REFUSED_RENTA_MARITIME_EXEMPTION_INACTIVE``.
        assert "DA 41" in result.output
        assert "BOE-A-2006-20764" in result.output


class TestAmountGrammarRefusal:
    """Non-canonical amount text refuses at the CLI boundary, not silently coerced.

    Both amount options previously ran a bare ``Decimal(value)``, so every form
    the constructor happens to accept became a real figure: ``1e3`` became
    ``1000``, ``+36500`` became ``36500``, and the Spanish thousands shape
    ``36.500`` became ``Decimal("36.5")`` — a thirty-six-euro salary where the
    operator meant thirty-six thousand five hundred. Each case below drives the
    real CLI verb and asserts a usage refusal, so a regression that re-widens
    the grammar fails here rather than filing a wrong figure.
    """

    @pytest.mark.parametrize(
        "raw_amount",
        ["1e3", "+36500", "36.500", "36.500,00", "36500,00", "3 6500", "NaN", "Infinity"],
    )
    def test_non_canonical_annual_salary_refuses(self, isolated_backend: None, raw_amount: str) -> None:
        _register_maritime_profile(
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_flag": "foreign",
            },
        )
        result = invoke_cached_cli(
            [
                "app", "modelo", "work", "preview-maritime-exemption",
                "--annual-salary", raw_amount,
                "--qualifying-days", "100",
            ],
        )  # fmt: skip
        # Typer renders a BadParameter as a usage error (exit 2); the run must
        # not reach the exemption service with a coerced figure.
        assert result.exit_code != 0, result.output
        assert "--annual-salary" in result.output

    @pytest.mark.parametrize("raw_amount", ["1e3", "+36500", "36.500", "36500,00"])
    def test_non_canonical_gross_navigation_income_refuses(
        self,
        isolated_backend: None,
        raw_amount: str,
    ) -> None:
        _register_maritime_profile(
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_registry": "REBECA",
            },
        )
        result = invoke_cached_cli(
            [
                "app", "modelo", "work", "preview-maritime-exemption",
                "--gross-navigation-income", raw_amount,
            ],
        )  # fmt: skip
        assert result.exit_code != 0, result.output
        assert "--gross-navigation-income" in result.output

    @pytest.mark.parametrize("raw_amount", ["36500", "36500.00", "36500.5", "0.99"])
    def test_canonical_annual_salary_still_accepted(self, isolated_backend: None, raw_amount: str) -> None:
        """The tightening refuses only non-canonical text; euro forms still pass."""
        _register_maritime_profile(
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_flag": "foreign",
            },
        )
        result = invoke_cached_cli(
            [
                "--format", "json",
                "app", "modelo", "work", "preview-maritime-exemption",
                "--annual-salary", raw_amount,
                "--qualifying-days", "100",
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output


class TestVerbWiringIntegration:
    """The verb reads the active profile and dispatches the service correctly."""

    def test_no_eligibility_yields_empty_observations(self, isolated_backend: None) -> None:
        # An active profile without any maritime_worker facts produces no
        # pathway match — the envelope is well-formed and the observation
        # list is empty.
        _register_maritime_profile(overrides={})
        result = invoke_cached_cli(
            [
                "--format", "json",
                "app", "modelo", "work", "preview-maritime-exemption",
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        payload = _unwrap(result.output)
        validated = WorkPreviewMaritimeExemptionResult.model_validate(payload)
        assert validated.worker_class is None
        assert validated.observations == []
        assert validated.retmar_mandatory_filing is False
        assert validated.retmar_warning is None

    def test_facts_reader_round_trips_through_profile(self, isolated_backend: None) -> None:
        _register_maritime_profile(
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_registry": "rebeca_eu_eea",
            },
        )
        facts = maritime_facts_from_active_profile()
        assert facts.worker_class == "trabajador_del_mar"
        assert facts.vessel_registry == "rebeca_eu_eea"
