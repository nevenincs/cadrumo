"""Unit tests for the trilingual i18n support."""

from __future__ import annotations

import unicodedata

import pytest

from . import (
    Language,
    Translatable,
    TranslatableObject,
    TranslationError,
    TranslationFallback,
    get_translation,
    normalize_language_code,
    require_authoritative,
    with_translation,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_mediation]


class TestLanguage:
    def test_language_values(self) -> None:
        """Test the trilingual contract language values."""
        assert Language.ES == "es"
        assert Language.EN == "en"
        assert Language.HU == "hu"


class TestNormalization:
    def test_language_codes_are_normalized(self) -> None:
        """Language code normalization lowercases and trims valid inputs."""
        assert normalize_language_code(" ES ") == "es"
        assert normalize_language_code(Language.HU) == "hu"

    def test_invalid_language_codes_raise(self) -> None:
        """Non-ISO-639-1 values must be rejected."""
        with pytest.raises(TranslationError, match="two-letter ISO 639-1 code"):
            normalize_language_code("spanish")

    def test_nfc_normalization_applied(self) -> None:
        """Test that NFC normalization is applied to translations."""
        # 'a' + combining acute accent (decomposed)
        decomposed = "a\u0301"
        normalized = unicodedata.normalize("NFC", decomposed)

        translatable: Translatable = {"es": decomposed}
        # get_translation should return normalized
        assert get_translation(translatable, Language.ES) == normalized
        assert get_translation(translatable, Language.ES) != decomposed

        # require_authoritative should return normalized
        assert require_authoritative(translatable, domain="aeat") == normalized

        # with_translation should normalize the dict
        obj = {}
        new_obj = with_translation(obj, translatable)
        assert new_obj["translation"]["es"] == normalized


class TestGetTranslation:
    def test_exact_match(self) -> None:
        """Test getting exact translation."""
        translatable: Translatable = {"es": "Hola", "en": "Hello", "hu": "Szia"}
        assert get_translation(translatable, Language.ES) == "Hola"
        assert get_translation(translatable, Language.EN) == "Hello"
        assert get_translation(translatable, Language.HU) == "Szia"

    def test_strict_fallback_policy(self) -> None:
        """Test strict fallback policy raises error when missing."""
        translatable: Translatable = {"es": "Hola"}
        with pytest.raises(TranslationError, match="Missing strictly required translation for hu"):
            get_translation(translatable, Language.HU, fallback_policy=TranslationFallback.STRICT)

    def test_fallback_to_en(self) -> None:
        """Test fallback to english."""
        translatable: Translatable = {"es": "Hola", "en": "Hello"}
        assert get_translation(translatable, Language.HU, fallback_policy=TranslationFallback.FALLBACK_TO_EN) == "Hello"

    def test_fallback_to_es(self) -> None:
        """Test fallback to spanish."""
        translatable: Translatable = {"es": "Hola"}
        assert get_translation(translatable, Language.HU, fallback_policy=TranslationFallback.FALLBACK_TO_ES) == "Hola"

    def test_config_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fallback using the configuration list."""
        # Mock settings to prioritize Hungarian then Spanish
        monkeypatch.setenv("AEAT_FALLBACK_LANGUAGES", "hu,es")

        translatable: Translatable = {"es": "Hola", "en": "Hello"}
        # Target EN is missing, should fall back to ES as per config
        assert get_translation(translatable, Language.HU) == "Hola"

    def test_no_translation_available(self) -> None:
        """Test exception when dictionary is empty."""
        translatable: Translatable = {}
        with pytest.raises(TranslationError, match="No translation available in any language"):
            get_translation(translatable, Language.HU)


class TestRequireAuthoritative:
    def test_aeat_domain(self) -> None:
        """Test aeat domain authoritative logic."""
        translatable: Translatable = {"es": "Impuesto", "en": "Tax"}
        assert require_authoritative(translatable, domain="aeat") == "Impuesto"

    def test_aeat_domain_missing(self) -> None:
        """Test aeat domain misses authoritative."""
        translatable: Translatable = {"en": "Tax"}
        with pytest.raises(TranslationError, match="Missing authoritative language 'es' for 'aeat' domain"):
            require_authoritative(translatable, domain="aeat")

    def test_docs_domain(self) -> None:
        """Test docs domain authoritative logic."""
        translatable: Translatable = {"es": "Configuración", "en": "Configuration"}
        assert require_authoritative(translatable, domain="docs") == "Configuration"

    def test_docs_domain_missing(self) -> None:
        """Test docs domain misses authoritative."""
        translatable: Translatable = {"es": "Configuración"}
        with pytest.raises(TranslationError, match="Missing authoritative language 'en' for 'docs' domain"):
            require_authoritative(translatable, domain="docs")

    def test_unknown_domain(self) -> None:
        """Test unknown domain raises error."""
        translatable: Translatable = {"es": "Hola"}
        with pytest.raises(TranslationError, match="Unknown domain: unknown"):
            require_authoritative(translatable, domain="unknown")


class TestWithTranslation:
    def test_injects_translation(self) -> None:
        """Test injection of Translatable."""
        obj = {"id": 1}
        translatable: Translatable = {"es": "Uno", "en": "One"}
        new_obj = with_translation(obj, translatable)

        assert new_obj["id"] == 1
        assert new_obj["translation"]["es"] == "Uno"
        # Original object shouldn't be mutated
        assert "translation" not in obj


class TestTranslatableObject:
    def test_protocol_implementation(self) -> None:
        """Test that objects matching the TranslatableObject protocol are recognized."""

        class MyObj:
            def __init__(self) -> None:
                self.translation: Translatable = {"es": "Test"}

        obj = MyObj()
        assert isinstance(obj, TranslatableObject)

        class NotTranslatable:
            pass

        assert not isinstance(NotTranslatable(), TranslatableObject)
