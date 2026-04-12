"""Unit tests for the trilingual i18n support."""

from __future__ import annotations

import pytest

from aeat.i18n import (
    Language,
    Translatable,
    TranslationError,
    TranslationFallback,
    get_translation,
    require_authoritative,
    with_translation,
)


@pytest.mark.unit
class TestLanguage:
    def test_language_values(self) -> None:
        """Test the trilingual contract language values."""
        assert Language.ES == "es"
        assert Language.EN == "en"
        assert Language.HU == "hu"


@pytest.mark.unit
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

    def test_default_fallback(self) -> None:
        """Test default fallback when no specific policy is matched."""
        translatable: Translatable = {"en": "Hello"}
        assert get_translation(translatable, Language.HU) == "Hello"

        translatable2: Translatable = {"es": "Hola"}
        assert get_translation(translatable2, Language.HU) == "Hola"

    def test_no_translation_available(self) -> None:
        """Test exception when dictionary is empty."""
        translatable: Translatable = {}
        with pytest.raises(TranslationError, match="No translation available in any language"):
            get_translation(translatable, Language.HU)


@pytest.mark.unit
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


@pytest.mark.unit
class TestWithTranslation:
    def test_injects_translation(self) -> None:
        """Test injection of Translatable."""
        obj = {"id": 1}
        translatable: Translatable = {"es": "Uno", "en": "One"}
        new_obj = with_translation(obj, translatable)

        assert new_obj["id"] == 1
        assert new_obj["translation"] == translatable
        # Original object shouldn't be mutated
        assert "translation" not in obj
