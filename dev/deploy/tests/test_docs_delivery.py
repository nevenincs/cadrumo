"""What a publish deploys and what it verifies, decided without reaching Cloudflare."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ..cloudflare_api import CloudflareAccount
from ..docs_static_site import (
    _MISSING_DOCS_PATH,
    _RELEASE_ID_RE,
    CANONICAL_DOCS_BASE_URL,
    CANONICAL_SITE_DOMAIN,
    DELIVERY_ROUTES,
    MIRROR_DOCS_BASE_URL,
    MIRROR_SITE_DOMAIN,
    RELEASE_HEADER,
    WORKER_MODULE,
    WORKER_SCRIPT,
    DeliveryCredentials,
    _delivery_credentials,
    expected_redirect,
    localized_languages,
    public_delivery_checks,
    release_id,
    worker_bindings,
)
from ..r2_objects import R2Bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Placeholder material only; nothing here is ever sent anywhere.
_PLACEHOLDER = "placeholder"
_CREDENTIALS = DeliveryCredentials(
    account=CloudflareAccount(account_id="account", api_token=_PLACEHOLDER),
    bucket=R2Bucket(account_id="account", name="docs-bucket", access_key_id="id", secret_access_key=_PLACEHOLDER),
)


def test_a_release_id_is_the_label_plus_a_utc_instant() -> None:
    instant = datetime(2026, 9, 23, 15, 4, 5, tzinfo=timezone(timedelta(hours=2)))
    assert release_id("v0.6.0", now=instant) == "v0.6.0-20260923T130405Z"
    assert _RELEASE_ID_RE.fullmatch(release_id("local-5b1c188d285f", now=datetime.now(UTC)))


@pytest.mark.parametrize("label", ["", "../x", "v1 2", "-v1", "a/b", "x" * 65])
def test_a_label_that_could_escape_its_prefix_is_refused(label: str) -> None:
    with pytest.raises(SystemExit):
        release_id(label, now=datetime.now(UTC))


def test_the_worker_serves_the_release_from_the_delivery_bucket_on_both_mounts() -> None:
    bindings = {binding["name"]: binding for binding in worker_bindings(_CREDENTIALS, "v1-20260923T000000Z")}
    assert bindings["SITE"] == {"type": "r2_bucket", "name": "SITE", "bucket_name": "docs-bucket"}
    assert bindings["RELEASE_ID"]["text"] == "v1-20260923T000000Z"
    assert (bindings["CANONICAL_HOST"]["text"], bindings["CANONICAL_MOUNT"]["text"]) == (CANONICAL_SITE_DOMAIN, "/docs")
    assert (bindings["MIRROR_HOST"]["text"], bindings["MIRROR_MOUNT"]["text"]) == (MIRROR_SITE_DOMAIN, "/cadrumo/docs")


def test_both_mounts_are_routed_to_the_worker() -> None:
    assert {(route.pattern, route.script) for route in DELIVERY_ROUTES} == {
        ("cadrumo.neve.md/docs*", WORKER_SCRIPT),
        ("neve.md/cadrumo/docs*", WORKER_SCRIPT),
    }


def test_the_live_checks_cover_every_root_404_and_mount_redirect_on_both_mounts() -> None:
    checks = dict(public_delivery_checks())
    for base_url in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
        assert checks[f"{base_url}/"] == 200
        for language in localized_languages():
            assert checks[f"{base_url}/{language}/"] == 200
        assert checks[f"{base_url}/{_MISSING_DOCS_PATH}"] == 404
        assert checks[base_url] == 301


def test_missing_credentials_are_named_together_without_their_values() -> None:
    with pytest.raises(SystemExit) as refusal:
        _delivery_credentials({"CLOUDFLARE_ACCOUNT_ID": "account", "CLOUDFLARE_API_TOKEN": "sensitive-value"})
    message = str(refusal.value)
    assert "CADRUMO_DOCS_R2_BUCKET" in message and "CADRUMO_DOCS_R2_SECRET_ACCESS_KEY" in message
    assert "sensitive-value" not in message


def test_the_publisher_and_worker_agree_on_the_release_header() -> None:
    """The publisher polls the header the Worker sets; a rename on one side would stall every deploy."""
    assert f'"{RELEASE_HEADER}"' in WORKER_MODULE.read_text(encoding="utf-8")


def test_an_apex_page_is_checked_to_redirect_to_the_source_language_root() -> None:
    checks = dict(public_delivery_checks())
    for base_url, mount in ((CANONICAL_DOCS_BASE_URL, "/docs"), (MIRROR_DOCS_BASE_URL, "/cadrumo/docs")):
        deep_link = f"{base_url}/search.html"
        assert checks[deep_link] == 301
        assert expected_redirect(deep_link) == f"{mount}/en/search.html"
        assert expected_redirect(base_url) == f"{mount}/"


def test_the_worker_knows_every_language_root_and_the_source_root() -> None:
    bindings = {binding["name"]: binding for binding in worker_bindings(_CREDENTIALS, "v1-20260923T000000Z")}
    assert bindings["LANGUAGE_ROOTS"]["text"].split(",") == list(localized_languages())
    assert bindings["SOURCE_ROOT"]["text"] == "en"
