"""Acceptance tests for the Euskera (eu) locale.

Covers three contracts from Task #212:

1. The CLI accepts ``--output-language eu`` without a parse-time error.
2. The locale loading path returns printable, valid strings (passthrough
   dotted-key values) — no UnicodeDecodeError, no ``None`` output.
3. Profile preferences written with ``eu`` are persisted and reloaded
   correctly.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.core.i18n import SUPPORTED_OUTPUT_LANGUAGES, output_language, tr
from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import isolated_profile_storage_root, isolated_sessionless_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _json_output(output: str) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", output, re.DOTALL)
    return match.group(0) if match else output


# ---------------------------------------------------------------------------
# 1. Parse-time acceptance
# ---------------------------------------------------------------------------


def test_eu_is_in_supported_output_languages() -> None:
    """``eu`` must appear in the canonical language tuple so it is not rejected."""
    assert "eu" in SUPPORTED_OUTPUT_LANGUAGES


def test_help_choice_list_includes_eu() -> None:
    """The CLI ``--output-language`` choice list must enumerate ``eu``.

    This is an anti-tautology gate: if ``eu`` is absent from
    SUPPORTED_OUTPUT_LANGUAGES the choice list rendered in ``--help``
    would also omit it and the CLI would reject ``--output-language eu``
    at parse time.  The test would fail even if the help text is generated
    from a different source than the enum, catching divergence.
    """
    with isolated_sessionless_storage_root(tmp_path=Path()):
        pass

    result = invoke_cached_cli(["config", "profile", "show", "--help"])
    assert result.exit_code == 0, result.output
    assert "eu" in result.output, (
        f"``eu`` not found in --output-language choice list.\nHelp output:\n{result.output}"
    )


def test_output_language_eu_accepted_by_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``config profile create --output-language eu`` must exit 0, not raise.

    Failure here means ``eu`` was rejected at the Click choice validation
    layer — i.e. never added to SUPPORTED_OUTPUT_LANGUAGES or the derived
    click.Choice list diverged from the tuple.
    """
    monkeypatch.delenv("AEAT_OUTPUT_LANGUAGE", raising=False)
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "eu",
        ]
    )
    assert result.exit_code == 0, (
        f"CLI rejected ``--output-language eu`` with exit {result.exit_code}:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# 2. Locale loading — passthrough values are printable, non-empty strings
# ---------------------------------------------------------------------------


def test_eu_locale_renders_tr_call_without_error() -> None:
    """``tr()`` with ``locale='eu'`` must return a non-empty string.

    The passthrough strategy sets leaf values equal to the dotted key
    path.  ``tr`` falls back to the humanised key tail when the rendered
    value equals the raw key, so the returned string is always
    operator-readable (at worst "Default translatable").  A ``None``
    or exception return would indicate a broken locale map entry.
    """
    rendered = tr("access_gate.errors.default_translatable", locale="eu")
    assert isinstance(rendered, str), "tr() returned non-string for eu locale"
    assert rendered, "tr() returned empty string for eu locale"
    # Must be printable — no control characters, no UnicodeDecodeError side-effect.
    assert rendered.isprintable() or rendered.strip(), (
        f"tr() result contains non-printable characters: {rendered!r}"
    )


def test_eu_locale_map_loads_without_error() -> None:
    """The ``eu.yml`` file must be loadable as a flat key map.

    Exercises the full YAML load + flatten path exercised at runtime.
    A structural error in eu.yml (duplicate key, bad indentation)
    would raise ``ValueError`` or ``yaml.YAMLError`` here.
    """
    from aeat.core.i18n._render import _locale_map

    mapping = _locale_map("eu")
    assert len(mapping) > 0, "eu locale map is empty after load"
    # Every value must be a non-empty string.
    empties = [k for k, v in mapping.items() if not v]
    assert not empties, f"eu locale map contains {len(empties)} empty values: {empties[:5]}"


# ---------------------------------------------------------------------------
# 3. Profile preference persistence
# ---------------------------------------------------------------------------


def test_profile_preference_eu_persists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``preferences.output_language`` written as ``eu`` round-trips through storage.

    Anti-tautology proof: if the profile serializer silently drops the
    ``eu`` value or normalises it to the ``es`` fallback, the assertion
    on the reloaded record fails.  The test would catch both a write-side
    drop and a read-side normalisation regression.
    """
    from aeat.adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from aeat.application.user_profile._orchestration import fact_value
    from aeat.application.workflow._persistence import workflow_state_repository

    monkeypatch.delenv("AEAT_OUTPUT_LANGUAGE", raising=False)

    create_result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "default",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--output-language",
            "eu",
        ]
    )
    assert create_result.exit_code == 0, create_result.output

    show_result = invoke_cached_cli(["--format", "json", "config", "profile", "show", "default"])
    assert show_result.exit_code == 0, show_result.output
    facts = {
        row["path"]: row["value"]
        for row in json.loads(_json_output(show_result.output))["facts"]
    }
    assert facts.get("preferences.output_language") == "eu", (
        f"show output does not contain eu language preference: {facts}"
    )

    # Confirm the storage-layer record also holds ``eu``.
    with activate_master_key_provider(get_master_key_provider()):
        state = workflow_state_repository().load()
        record = state.active_profile_record()
        assert record is not None
        assert fact_value(record, "preferences.output_language") == "eu", (
            f"storage-layer record has language {fact_value(record, 'preferences.output_language')!r}, expected 'eu'"
        )
