"""What a publish deploys and what it verifies, decided without reaching Cloudflare."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ..docs_static_site import (
    _MISSING_DOCS_PATH,
    _RELEASE_ID_RE,
    CANONICAL_DOCS_BASE_URL,
    DELIVERY_ROUTES,
    MIRROR_DOCS_BASE_URL,
    _delivery_credentials,
    expected_redirect,
    localized_languages,
    public_delivery_checks,
    release_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_release_id_is_the_label_plus_a_utc_instant() -> None:
    instant = datetime(2026, 9, 23, 15, 4, 5, tzinfo=timezone(timedelta(hours=2)))
    assert release_id("v0.6.0", now=instant) == "v0.6.0-20260923T130405Z"
    assert _RELEASE_ID_RE.fullmatch(release_id("local-5b1c188d285f", now=datetime.now(UTC)))


@pytest.mark.parametrize("label", ["", "../x", "v1 2", "-v1", "a/b", "x" * 65])
def test_a_label_that_could_escape_its_prefix_is_refused(label: str) -> None:
    with pytest.raises(SystemExit):
        release_id(label, now=datetime.now(UTC))


def test_both_mounts_are_routed_to_the_worker() -> None:
    assert {(route.pattern, route.script) for route in DELIVERY_ROUTES} == {
        ("cadrumo.neve.md/docs", "cadrumo-docs-static"),
        ("cadrumo.neve.md/docs/*", "cadrumo-docs-static"),
        ("neve.md/cadrumo/docs", "cadrumo-docs-static"),
        ("neve.md/cadrumo/docs/*", "cadrumo-docs-static"),
    }


def test_the_live_checks_cover_every_root_404_and_mount_redirect_on_both_mounts() -> None:
    checks = dict(public_delivery_checks())
    for base_url in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
        assert checks[f"{base_url}/"] == 200
        for language in localized_languages():
            assert checks[f"{base_url}/{language}/"] == 200
        assert checks[f"{base_url}/{_MISSING_DOCS_PATH}"] == 404
        assert checks[base_url] == 301
        assert checks[f"{base_url}?cadrumo_delivery_check=1"] == 301


def test_missing_credentials_are_named_together_without_their_values() -> None:
    with pytest.raises(SystemExit) as refusal:
        _delivery_credentials({"CLOUDFLARE_ACCOUNT_ID": "account", "CLOUDFLARE_API_TOKEN": "sensitive-value"})
    message = str(refusal.value)
    assert "CADRUMO_DOCS_R2_BUCKET" in message and "CADRUMO_DOCS_R2_SECRET_ACCESS_KEY" in message
    assert "sensitive-value" not in message


def test_an_apex_page_is_checked_to_redirect_to_the_source_language_root() -> None:
    checks = dict(public_delivery_checks())
    for base_url, mount in ((CANONICAL_DOCS_BASE_URL, "/docs"), (MIRROR_DOCS_BASE_URL, "/cadrumo/docs")):
        deep_link = f"{base_url}/search.html"
        assert checks[deep_link] == 301
        assert expected_redirect(deep_link) == f"{mount}/en/search.html"
        assert expected_redirect(base_url) == f"{mount}/"
        assert expected_redirect(base_url + "?q=invoice") == f"{mount}/?q=invoice"
