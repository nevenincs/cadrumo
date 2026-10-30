"""A foral resident's forecast refuses through the live command tree, in every language.

``aeat app ledger actividad-asset forecast`` stops for a taxpayer resident in
Araba, Bizkaia, Gipuzkoa or Navarra, where Modelos 100 and 130 of the AEAT do
not apply, and for one whose recorded residence the catalogue cannot read. The
refusal keeps its specific catalogue key through the registered operation, so
each supported language renders its own text rather than a generic refusal.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.core.errors.error_codes import ErrorCategory, get_error_exit_code
from cadrumo.core.i18n.render import tr

from .cli_runner import invoke_cached_cli
from .runtime_profile_backend import runtime_cli_profile
from .test_actividad_asset_accelerated_da18_cli import (
    _BASIS,
    _LANGUAGES,
    electric_van,
    seed_direct_normal_profile,
    van_payment,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_FORAL_KEY = "ledger.actividad_asset.errors.foral_territory"
_UNRESOLVED_KEY = "ledger.actividad_asset.errors.tax_residence_unresolved"
_IN_SERVICE = date(2024, 3, 1)
_ASSET_ID = "van-2024"


def _forecast(language: str) -> Result:
    return invoke_cached_cli(
        [
            *("--format", "json", "--language", language),
            *("app", "ledger", "actividad-asset", "forecast", _ASSET_ID),
            *("--covered-from", date(2024, 1, 1).isoformat(), "--covered-until", date(2025, 1, 1).isoformat()),
            *("--free-depreciation-amount", str(_BASIS)),
        ],
    )


def _refusals(tmp_path: Path, residence: str) -> dict[str, Result]:
    with runtime_cli_profile(tmp_path=tmp_path, label=f"register residence {residence}") as profile:
        seed_direct_normal_profile(profile.storage_root, profile.bucket_id)
        payment = van_payment(_ASSET_ID, _IN_SERVICE)
        created = invoke_cached_cli(
            [
                *("--format", "json", "app", "ledger", "actividad-asset", "create"),
                *("--name", "Furgoneta de reparto"),
                electric_van(_ASSET_ID, _IN_SERVICE, payment),
            ],
        )
        assert created.exit_code == 0, created.output
        # The ledger itself refuses to book a payment for such a residence, so it is recorded after the asset exists.
        seed_direct_normal_profile(profile.storage_root, profile.bucket_id, residence=residence)
        return {language: _forecast(language) for language in _LANGUAGES}


@pytest.mark.parametrize(
    ("residence", "key"),
    [("bizkaia", _FORAL_KEY), ("atlantis", _UNRESOLVED_KEY)],
    ids=["foral", "unreadable"],
)
def test_a_forecast_for_a_foral_or_unreadable_residence_refuses_in_every_language(
    tmp_path: Path,
    residence: str,
    key: str,
) -> None:
    refusals = _refusals(tmp_path, residence)

    messages: set[str] = set()
    for language, refused in refusals.items():
        assert refused.exit_code == get_error_exit_code(ErrorCategory.REFUSED), refused.output
        error = json.loads(refused.output)["error"]
        assert error["message"] == tr(key, locale=language), refused.output
        messages.add(error["message"])
    assert len(messages) == len(_LANGUAGES)
