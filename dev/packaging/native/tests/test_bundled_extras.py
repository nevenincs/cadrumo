"""The package carries every optional extra the application offers."""

from __future__ import annotations

import pytest

from cadrumo.application.ledger import actions_import
from cadrumo.application.ledger.actions_import import LedgerProviderID, installed_ledger_providers
from cadrumo.core.optional_extras import OFX_EXTRA, OPTIONAL_EXTRAS, OptionalExtra
from cadrumo.core.toml import parse_toml
from dev.paths import REPO_ROOT

from ..product import BUNDLE_EXCLUDED_EXTRAS, BUNDLED_EXTRAS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_every_optional_extra_is_bundled_or_excluded_by_name() -> None:
    declared = [extra.extra for extra in OPTIONAL_EXTRAS]

    assert sorted([*BUNDLED_EXTRAS, *BUNDLE_EXCLUDED_EXTRAS]) == sorted(declared)
    assert not set(BUNDLED_EXTRAS) & set(BUNDLE_EXCLUDED_EXTRAS)
    assert all(reason.strip() for reason in BUNDLE_EXCLUDED_EXTRAS.values())


def test_only_the_copyleft_ofx_parser_is_left_out() -> None:
    assert set(BUNDLE_EXCLUDED_EXTRAS) == {OFX_EXTRA.extra}
    assert {"browser", "google", "pdf"} <= set(BUNDLED_EXTRAS)


def test_each_bundled_extra_is_a_declared_project_extra() -> None:
    project = parse_toml((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    extras = project["optional-dependencies"]

    for extra in BUNDLED_EXTRAS:
        assert extras.get(extra), extra


def test_the_package_offers_no_import_format_whose_parser_it_leaves_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def packaged(extra: OptionalExtra) -> bool:
        return extra.extra in BUNDLED_EXTRAS

    monkeypatch.setattr(actions_import, "optional_extra_available", packaged)
    offered = installed_ledger_providers()

    assert LedgerProviderID.OFX not in offered
    assert LedgerProviderID.QFX not in offered
    assert set(offered) == set(LedgerProviderID) - {LedgerProviderID.OFX, LedgerProviderID.QFX}
