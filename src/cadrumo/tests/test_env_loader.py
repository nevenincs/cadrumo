"""Unit tests for :mod:`aeat-tests._env_loader`."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ..core.config import Settings
from .env_loader import bridge_env_file_into_environ, load_env_file, parse_env_text
from .env_scope import scoped_env_var

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestParseEnvText:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("FOO=bar", {"FOO": "bar"}, id="simple-pair"),
            pytest.param("A=1\nB=2\nC=3\n", {"A": "1", "B": "2", "C": "3"}, id="multiple-pairs"),
            pytest.param(
                "\n# this is a comment\nFOO=bar\n  # leading-space comment\nBAZ=qux\n",
                {"FOO": "bar", "BAZ": "qux"},
                id="blank-lines-and-comments",
            ),
            pytest.param("PORT=8080 # the dev server port", {"PORT": "8080"}, id="inline-comment"),
            pytest.param("COLOR=#ffaabb", {"COLOR": "#ffaabb"}, id="hash-without-leading-space"),
            pytest.param('NAME="Persona Prueba"', {"NAME": "Persona Prueba"}, id="double-quoted"),
            pytest.param("NAME='Persona Prueba'", {"NAME": "Persona Prueba"}, id="single-quoted"),
            pytest.param('TOKEN="abc#def"', {"TOKEN": "abc#def"}, id="quoted-hash"),
            pytest.param("  FOO  =   bar  ", {"FOO": "bar"}, id="trimmed-key-value"),
            pytest.param("FOO\nBAR=baz\n", {"BAR": "baz"}, id="line-without-equals"),
            pytest.param("=orphan\nA=1", {"A": "1"}, id="blank-key"),
            pytest.param("A=1\nA=2\n", {"A": "2"}, id="later-assignment-wins"),
            pytest.param("FOO=", {"FOO": ""}, id="empty-value"),
        ],
    )
    def test_parse_env_text_cases(self, text: str, expected: dict[str, str]) -> None:
        assert parse_env_text(text) == expected


class TestLoadEnvFile:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_env_file(tmp_path / "nope.env") == {}

    def test_real_file_round_trip(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        cert_path = tmp_path / "cert.p12"
        env.write_text(
            f"# header\nCADRUMO_LIVE_TESTS_ENABLED=1\nCADRUMO_CERTIFICATE_PATH={cert_path}\n",
            encoding="utf-8",
        )
        loaded = load_env_file(env)
        assert loaded["CADRUMO_LIVE_TESTS_ENABLED"] == "1"
        assert loaded["CADRUMO_CERTIFICATE_PATH"] == str(cert_path)


class TestBridgeEnvFileIntoEnviron:
    """The pytest-collection-time bridge from a dotfile into ``os.environ``.

    Production ``Settings`` carries no dotenv source of its own; these
    prove the bridge is the sole channel that makes a dotfile's values
    reach a real ``Settings`` instance, and that it never outranks a real
    ambient environment variable.
    """

    def test_missing_file_is_a_clean_no_op(self, tmp_path: Path) -> None:
        before = dict(os.environ)
        applied = bridge_env_file_into_environ(tmp_path / "does-not-exist" / ".env")
        assert applied == {}
        assert dict(os.environ) == before

    def test_dotfile_only_field_reaches_settings(self, tmp_path: Path) -> None:
        """A field with no ambient environment variable is populated purely by the dotfile."""
        env_file = tmp_path / ".env"
        env_file.write_text("CADRUMO_CLAVE_MOVIL_NIE_SOPORTE=Z9988776F\n", encoding="utf-8")
        with scoped_env_var("CADRUMO_CLAVE_MOVIL_NIE_SOPORTE", None):
            applied = bridge_env_file_into_environ(env_file)
            assert applied == {"CADRUMO_CLAVE_MOVIL_NIE_SOPORTE": "Z9988776F"}
            assert os.environ["CADRUMO_CLAVE_MOVIL_NIE_SOPORTE"] == "Z9988776F"
            settings = Settings()
            assert settings.cadrumo_clave_movil_nie_soporte is not None
            assert settings.cadrumo_clave_movil_nie_soporte.get_secret_value() == "Z9988776F"

    def test_a_real_ambient_environment_variable_wins_over_the_dotfile(self, tmp_path: Path) -> None:
        """``setdefault`` semantics: an already-set env var is never overridden."""
        env_file = tmp_path / ".env"
        env_file.write_text("CADRUMO_CLAVE_MOVIL_DNI_NIE=99999999R\n", encoding="utf-8")
        with scoped_env_var("CADRUMO_CLAVE_MOVIL_DNI_NIE", "11111111H"):
            applied = bridge_env_file_into_environ(env_file)
            assert applied == {"CADRUMO_CLAVE_MOVIL_DNI_NIE": "99999999R"}
            assert os.environ["CADRUMO_CLAVE_MOVIL_DNI_NIE"] == "11111111H"
            settings = Settings()
            assert settings.cadrumo_clave_movil_dni_nie is not None
            assert settings.cadrumo_clave_movil_dni_nie.get_secret_value() == "11111111H"

    @pytest.mark.parametrize(("opt_in", "enabled"), [("0", False), ("1", True)])
    def test_explicit_persisted_file_precedes_checkout_defaults_and_keeps_ambient_overrides(
        self, tmp_path: Path, opt_in: str, enabled: bool
    ) -> None:
        selected = tmp_path / "main" / "env" / ".env"
        checkout = tmp_path / "feature" / "env" / ".env"
        selected.parent.mkdir(parents=True)
        checkout.parent.mkdir(parents=True)
        selected.write_text(
            f"CADRUMO_LIVE_TESTS_ENABLED={opt_in}\n"
            "CADRUMO_CLAVE_MOVIL_DNI_NIE=99999999R\n"
            "CADRUMO_CLAVE_MOVIL_NIE_SOPORTE=\n"
            "CADRUMO_CLAVE_MOVIL_DNI_FECHA=2029-01-01\n",
            encoding="utf-8",
        )
        corpus = tmp_path / "corpus"
        checkout.write_text(
            "CADRUMO_LIVE_TESTS_ENABLED=1\n"
            "CADRUMO_CLAVE_MOVIL_DNI_NIE=22222222J\n"
            "CADRUMO_CLAVE_MOVIL_NIE_SOPORTE=Z9988776F\n"
            f"CADRUMO_INGEST_CORPUS_ROOT={corpus}\n",
            encoding="utf-8",
        )
        with (
            scoped_env_var("CADRUMO_LIVE_TESTS_ENABLED", None),
            scoped_env_var("CADRUMO_CLAVE_MOVIL_DNI_NIE", None),
            scoped_env_var("CADRUMO_CLAVE_MOVIL_NIE_SOPORTE", None),
            scoped_env_var("CADRUMO_CLAVE_MOVIL_DNI_FECHA", "2030-01-01"),
            scoped_env_var("CADRUMO_INGEST_CORPUS_ROOT", None),
        ):
            # An explicit pre-pytest bridge selects the persisted file. The
            # checkout's normal conftest bridge then fills only unset names.
            bridge_env_file_into_environ(selected)
            bridge_env_file_into_environ(checkout)
            settings = Settings()
            assert settings.live_tests_enabled is enabled
            assert settings.cadrumo_clave_movil_dni_nie is not None
            assert settings.cadrumo_clave_movil_dni_nie.get_secret_value() == "99999999R"
            assert settings.cadrumo_clave_movil_nie_soporte is None
            assert os.environ["CADRUMO_CLAVE_MOVIL_NIE_SOPORTE"] == ""
            assert settings.cadrumo_clave_movil_dni_fecha == "2030-01-01"
            assert os.environ["CADRUMO_INGEST_CORPUS_ROOT"] == str(corpus)
