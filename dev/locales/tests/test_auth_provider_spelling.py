"""The canonical certificate provider ID stays exact in translated prose."""

from pathlib import Path

import pytest

from cadrumo.core.auth_provider import AuthProviderKind

from ..signal_spelling import spellcheck_catalogues
from ..signal_spelling_enrollment import is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("locale", ["es", "ca", "hu"])
def test_certificate_provider_id_does_not_hide_typos(locale: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return False

    provider = AuthProviderKind.CERTIFICATE.value
    assert provider == "certificate"
    assert is_project_spelling(locale, provider)
    assert not is_project_spelling(locale, "Certificate")
    assert not is_project_spelling(locale, "certficate")
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: {locale: Dictionary()})
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"provider"}, {locale: {"provider": f"{provider} certficate misspeling"}}, Path(".")
    )
    assert set(spelling[(locale, "provider")]) == {"certficate", "misspeling"}
