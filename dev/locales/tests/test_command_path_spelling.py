"""Only exact executable paths are syntax; prose and command typos stay visible."""

import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.core.i18n.render import tr
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.shared_contracts import LazyBinding, TranslationKey

from ..signal_command_paths import _compile_command_paths, command_path_pattern, executable_command_paths
from ..signal_spelling import spellcheck_catalogues
from ..signal_tokens import filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(autouse=True)
def _fresh_command_path_cache() -> Iterator[None]:
    executable_command_paths.cache_clear()
    _compile_command_paths.cache_clear()
    yield
    executable_command_paths.cache_clear()
    _compile_command_paths.cache_clear()


@pytest.mark.parametrize(
    "text",
    [
        "The login profile config is misspeling.",
        "Natural prose 'config profile' remains misspeling.",
        'Natural prose "config profile" remains misspeling.',
        "Please say 'aeat config logni' and keep misspeling.",
        "aeat config profile",
        "aeat config loginx",
        "prefixaeat config login",
        "aeat config login-ish",
        "AEAT config login",
        "cadrumo-runtime config auth logni",
        "aeat\nconfig login",
        "aeat config\r\nlogin",
        "cadrumo-runtime config\nauth test",
        "aeat\vconfig login",
        "aeat config\flogin",
        "aeat config\u2028login",
    ],
)
def test_prose_partial_paths_and_near_miss_commands_are_not_classified(text: str) -> None:
    assert not command_path_pattern().search(text)


@pytest.mark.parametrize("quote", ["", "'", '"'])
def test_exact_paths_preserve_neighboring_prose_and_arguments(quote: str) -> None:
    text = f"Run {quote}aeat config login{quote} NAME then misspeling."
    filtered, excluded = filtered_translation_text(text)
    assert "aeat" not in filtered
    assert "config" not in filtered
    assert "login" not in filtered
    assert "misspeling" in filtered
    assert excluded == 2  # One exact command path and the NAME metavariable.


def test_horizontal_whitespace_matches_but_separate_prose_lines_remain_checked() -> None:
    assert command_path_pattern().fullmatch("aeat\tconfig  login")
    filtered, excluded = filtered_translation_text("Read aeat\nconfig login then misspeling.")
    assert filtered == "Read aeat config login then misspeling."
    assert excluded == 0


def test_both_graphs_and_numeric_paths_are_recognized_before_identifier_masking() -> None:
    text = "Use cadrumo-runtime config auth test; aeat app live borrador 100 list."
    filtered, excluded = filtered_translation_text(text)
    assert filtered == "Use ."
    assert excluded == 2


def test_longest_path_is_one_span_and_distinct_mentions_remain_distinct() -> None:
    pattern = _compile_command_paths(frozenset({("tool", "run"), ("tool", "run", "detail")}))
    assert pattern.subn(" ", "tool run detail then tool run") == ("  then  ", 2)
    assert _compile_command_paths(frozenset()).subn(" ", "Natural prose") == ("Natural prose", 0)


def test_inline_literals_and_urls_are_not_counted_again_as_commands() -> None:
    filtered, excluded = filtered_translation_text(
        "Use `aeat config login` and https://example.test/aeat/config/login."
    )
    assert filtered == "Use and"
    assert excluded == 2


def test_unavailable_handler_is_not_an_executable_path(monkeypatch: pytest.MonkeyPatch) -> None:
    root = COMMAND_GRAPH.root()
    unavailable = replace(
        COMMAND_GRAPH.resolve_path(("aeat", "config", "login")),
        key="unavailable",
        parent_key=root.key,
        handler=LazyBinding.unavailable(TranslationKey("errors.command.unavailable")),
    )
    graph = CommandSpecGraph((root, unavailable), resolver=COMMAND_GRAPH.resolver)
    monkeypatch.setattr("dev.locales.signal_command_paths._command_graphs", lambda: (graph,))
    assert executable_command_paths() == frozenset()
    assert not command_path_pattern().search("aeat login")


def test_graph_failure_does_not_fall_back_to_an_unchecked_vocabulary(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_graphs() -> tuple[CommandSpecGraph, ...]:
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr("dev.locales.signal_command_paths._command_graphs", broken_graphs)
    with pytest.raises(RuntimeError, match="graph unavailable"):
        command_path_pattern()


def test_real_locale_error_preserves_adjacent_and_command_typos(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word not in {"aeat", "config", "logni", "misspeling"}

    value = tr("application.auth.operator.errors.requires_custody_session", locale="en")
    assert "aeat config login" in value
    leaves: dict[str, object] = {"valid": value + " misspeling", "invalid": "Run aeat config logni then misspeling."}
    filtered, excluded = filtered_translation_text(str(leaves["invalid"]))
    assert filtered == leaves["invalid"]
    assert excluded == 0
    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries", lambda repository: {"en": Dictionary(), "es": Dictionary()}
    )
    spelling, _inventory, _findings = spellcheck_catalogues(set(leaves), {"en": leaves}, Path("."))
    assert spelling[("en", "valid")] == ("misspeling",)
    # The exact spellings aeat/config are enrolled technical vocabulary even
    # outside a valid command; its misspelled verb must still reach the audit.
    assert set(spelling[("en", "invalid")]) == {"logni", "misspeling"}


def test_lazy_graph_loading_has_no_docs_cycle_and_reuses_only_process_local_cache() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from dev.locales.signal_command_paths import executable_command_paths
assert 'cadrumo.entrypoints.cli.command_specs' not in sys.modules
assert 'cadrumo_runtime.commands.command_specs' not in sys.modules
from dev.locales.signal_tokens import filtered_translation_text
first = executable_command_paths()
assert ('aeat', 'config', 'login') in first
assert ('cadrumo-runtime', 'config', 'auth', 'test') in first
assert executable_command_paths() is first
assert executable_command_paths.cache_info().hits == 1
assert not any(name.startswith('dev.docs') for name in sys.modules)
assert 'dev.locales.signal_document_prose' not in sys.modules
assert 'misspeling' in filtered_translation_text('Run aeat config login then misspeling.')[0]
""",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_tokenizer_also_imports_after_loading_the_command_graphs() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from dev.locales.signal_command_paths import command_path_pattern
assert command_path_pattern().search('aeat config login')
from dev.locales.signal_tokens import filtered_translation_text
assert not any(name.startswith('dev.docs') for name in sys.modules)
assert 'misspeling' in filtered_translation_text('Run aeat config login then misspeling.')[0]
""",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
