"""Gate output-absence assertions across the Spanish and English locale axis."""

from __future__ import annotations

import ast
import locale
import os
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..locale_bound_assertions import (
    LanguagePinning,
    declared_language_pinning,
    load_catalogue_strings,
    scan_locale_bound_assertions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
pytest_plugins = ("pytester",)

_LANGUAGE_ARGV = REPO_ROOT / "src/cadrumo/entrypoints/cli/language_argv.py"
_EXTERNAL_CONSTANTS = REPO_ROOT / "src/cadrumo/core/external_constants.py"
_LOCALES_ROOT = REPO_ROOT / "src/cadrumo/locales"
_LOCALES = ("en", "es", "ca", "hu")
_PINNING = declared_language_pinning(
    _LANGUAGE_ARGV.read_text(encoding="utf-8"),
    _EXTERNAL_CONSTANTS.read_text(encoding="utf-8"),
)
_CATALOGUES = load_catalogue_strings(
    {locale: tuple(sorted((_LOCALES_ROOT / locale).glob("*.yml"))) for locale in _LOCALES},
)
_FIXTURE = Path("fixture.py")
_FIXTURE_CORPUS = Path(__file__).with_name("fixtures") / "locale_bound_assertions.fixture"
_BLIND_AXIS_FIXTURE = Path(__file__).with_name("fixtures") / "locale_axis_blind.py.fixture"
_TEST_ROOTS = (REPO_ROOT / "src" / "cadrumo", REPO_ROOT / "dev")
_INTEGRATION_AXIS_NODE = REPO_ROOT / "src/cadrumo/application/auth/tests/test_operation_definitions.py"


def _source_fixture(name: str) -> str:
    corpus = _FIXTURE_CORPUS.read_text(encoding="utf-8")
    marker = f"# === {name} ===\n"
    assert marker in corpus, f"source fixture {name!r} is absent"
    return corpus.partition(marker)[2].partition("# === ")[0].strip() + "\n"


def _test_modules() -> tuple[Path, ...]:
    by_root = {root: tuple(root.rglob("test_*.py")) for root in _TEST_ROOTS}
    starved = {root: len(paths) for root, paths in by_root.items() if len(paths) < 500}
    assert not starved, (
        "the locale-bound sweep reached fewer than 500 test modules in a declared root; "
        f"modules found per starved root: {starved}"
    )
    return tuple(path for paths in by_root.values() for path in paths)


def _scan_fixture(name: str, *, ambient_locale: str = "es"):
    return scan_locale_bound_assertions(
        _FIXTURE,
        _source_fixture(name),
        _CATALOGUES,
        _PINNING,
        ambient_locale=ambient_locale,
    )


def _pytest_node_id(path: Path, lineno: int) -> str:
    """Resolve one detector locator to its containing pytest test node."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for top_level in tree.body:
        if (
            isinstance(top_level, (ast.FunctionDef, ast.AsyncFunctionDef))
            and top_level.name.startswith("test_")
            and top_level.lineno <= lineno <= (top_level.end_lineno or 0)
        ):
            return f"{path}::{top_level.name}"
        if isinstance(top_level, ast.ClassDef) and top_level.lineno <= lineno <= (top_level.end_lineno or 0):
            for member in top_level.body:
                if (
                    isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and member.name.startswith("test_")
                    and member.lineno <= lineno <= (member.end_lineno or 0)
                ):
                    return f"{path}::{top_level.name}::{member.name}"
    msg = f"{path}:{lineno} is not inside a pytest test node"
    raise ValueError(msg)


def _run_node_under_locale(
    pytester: pytest.Pytester,
    node_id: str,
    output_locale: str,
    *,
    isolated_config: bool = False,
) -> tuple[int, str]:
    """Execute one real pytest node with the declared output-language environment pin."""
    language_variable = _PINNING.environment_variable
    previous_language = os.environ.get(language_variable)
    previous_autoload = os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
    os.environ[language_variable] = output_locale
    arguments = ["-q"]
    if isolated_config:
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        arguments.extend(("--rootdir=.", "-p", "no:cacheprovider"))
    else:
        arguments.extend(("-n", "0", "-m", "", f"--rootdir={REPO_ROOT}"))
    try:
        result = pytester.runpytest_subprocess(*arguments, node_id)
    finally:
        if previous_language is None:
            os.environ.pop(language_variable, None)
        else:
            os.environ[language_variable] = previous_language
        if previous_autoload is None:
            os.environ.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
        else:
            os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = previous_autoload
    return int(result.ret), str(result.stdout.str()) + str(result.stderr.str())


def test_pinning_spellings_come_from_the_production_declarations() -> None:
    assert _PINNING.flags == ("--language", "--lang", "--output-language")
    assert _PINNING.prefixes == ("--language=", "--lang=", "--output-language=")
    assert _PINNING.environment_variable == "CADRUMO_OUTPUT_LANGUAGE"


def test_declaration_reader_accepts_annotated_literal_assignments() -> None:
    pinning = declared_language_pinning(
        _source_fixture("language_argv_valid"),
        _source_fixture("output_env_valid"),
    )

    assert pinning == LanguagePinning(
        flags=("--language",),
        prefixes=("--language=",),
        environment_variable="CADRUMO_OUTPUT_LANGUAGE",
    )


def test_declaration_reader_skips_module_preambles() -> None:
    pinning = declared_language_pinning(
        _source_fixture("language_argv_preamble"),
        _source_fixture("output_env_preamble"),
    )

    assert pinning == LanguagePinning(
        flags=("--language",),
        prefixes=("--language=",),
        environment_variable="CADRUMO_OUTPUT_LANGUAGE",
    )


def test_declaration_reader_rejects_missing_or_non_string_values() -> None:
    with pytest.raises(ValueError, match="declaration '_LANGUAGE_FLAGS' is absent"):
        declared_language_pinning(
            _source_fixture("language_argv_missing"),
            _source_fixture("output_env_valid"),
        )
    with pytest.raises(ValueError, match="language pinning declarations must contain only strings"):
        declared_language_pinning(
            _source_fixture("language_argv_nonstring"),
            _source_fixture("output_env_valid"),
        )
    with pytest.raises(ValueError, match="language pinning declarations must contain only strings"):
        declared_language_pinning(
            _source_fixture("language_argv_valid"),
            _source_fixture("output_env_nonstring"),
        )


def test_declaration_reader_preserves_the_exact_non_string_diagnostic() -> None:
    with pytest.raises(ValueError) as error:
        declared_language_pinning(
            _source_fixture("language_argv_nonstring"),
            _source_fixture("output_env_valid"),
        )

    assert str(error.value) == "language pinning declarations must contain only strings"


def test_catalogue_loader_flattens_nested_scalars_in_file_order(tmp_path: Path) -> None:
    first = tmp_path / "first.yml"
    second = tmp_path / "second.yml"
    first.write_text("root:\n  - first\n  - nested: {item: second}\n  - 7\n  - false\nempty: null\n", encoding="utf-8")
    second.write_text("- third\n- [fourth, {fifth: fifth}]\n", encoding="utf-8")

    assert load_catalogue_strings({"en": (first, second), "es": ()}) == {
        "en": ("first", "second", "third", "fourth", "fifth"),
        "es": (),
    }


def test_catalogue_loader_reads_real_utf8_content(tmp_path: Path) -> None:
    catalogue = tmp_path / "catalogue.yml"
    catalogue.write_text(_source_fixture("catalogue_utf8"), encoding="utf-8")

    previous_locale = locale.setlocale(locale.LC_CTYPE)
    try:
        locale.setlocale(locale.LC_CTYPE, "C")
        assert load_catalogue_strings({"es": (catalogue,)}) == {"es": ("Aviso: á",)}
    finally:
        locale.setlocale(locale.LC_CTYPE, previous_locale)


def test_the_real_join_includes_non_cli_catalogues() -> None:
    findings = scan_locale_bound_assertions(
        _FIXTURE,
        _source_fixture("non_cli_catalogue_join"),
        _CATALOGUES,
        _PINNING,
        ambient_locale="es",
    )

    assert len(findings) == 1
    assert findings[0].locales == frozenset({"en"})


def test_unpinned_english_absence_is_exposed_by_the_spanish_axis() -> None:
    findings = _scan_fixture("unpinned", ambient_locale="es")

    assert len(findings) == 1, f"the planted locale-bound absence produced {findings!r}"
    assert findings[0].literal == "ADVISORY:"
    assert findings[0].locales == frozenset({"en"})
    assert _scan_fixture("unpinned", ambient_locale="en") == ()


def test_the_planted_absence_really_changes_verdict_across_locales() -> None:
    rendered = {"es": "AVISO: detail", "en": "ADVISORY: detail"}
    verdicts = {locale: "ADVISORY:" not in output for locale, output in rendered.items()}

    assert verdicts == {"es": True, "en": False}


def test_runtime_axis_executes_a_planted_blind_assertion_under_both_locales(pytester: pytest.Pytester) -> None:
    planted = pytester.path / "test_locale_axis_blind.py"
    planted.write_text(_BLIND_AXIS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename=str(planted))
    assertion = next(node for node in ast.walk(tree) if isinstance(node, ast.Assert))
    absolute_node_id = _pytest_node_id(planted, assertion.lineno)
    node_id = absolute_node_id.replace(str(planted), planted.name, 1)

    outcomes = {
        locale_name: _run_node_under_locale(
            pytester,
            node_id,
            locale_name,
            isolated_config=True,
        )
        for locale_name in ("es", "en")
    }

    assert outcomes["es"][0] == 0, outcomes["es"][1]
    assert outcomes["en"][0] != 0
    assert "AssertionError" in outcomes["en"][1]


def test_runtime_axis_resolves_a_test_class_method(tmp_path: Path) -> None:
    module = tmp_path / "test_class_axis.py"
    module.write_text(_source_fixture("class_method_axis"), encoding="utf-8")

    assert _pytest_node_id(module, 4) == f"{module}::TestAxis::test_output"


def test_runtime_axis_overrides_the_repository_default_marker(pytester: pytest.Pytester) -> None:
    node_id = f"{_INTEGRATION_AXIS_NODE}::test_auth_families_have_one_canonical_registered_operation_each"

    return_code, output = _run_node_under_locale(pytester, node_id, "en")

    assert return_code == 0, output
    assert "1 passed" in output
    assert "deselected" not in output


def test_every_declared_direct_pinning_form_closes_its_own_output() -> None:
    assert _scan_fixture("pinned_forms") == ()


def test_pinning_helpers_propagate_only_through_their_output_data_flow() -> None:
    assert _scan_fixture("pinning_helpers") == ()


def test_a_helper_pin_does_not_hide_an_unpinned_return_value() -> None:
    findings = _scan_fixture("helper_with_unrelated_pin")

    assert len(findings) == 1
    assert findings[0].haystack == "result.output"


def test_environment_and_output_helper_kinds_cannot_be_confused() -> None:
    findings = _scan_fixture("helper_kind_confusion")

    assert [finding.haystack for finding in findings] == ["result.output", "result.output"]


def test_a_future_pin_does_not_retroactively_hide_an_assertion() -> None:
    findings = _scan_fixture("future_pin")

    assert len(findings) == 1
    assert findings[0].lineno == 3


def test_a_pin_on_one_invocation_does_not_hide_an_unpinned_output() -> None:
    findings = _scan_fixture("mixed_invocations")

    assert len(findings) == 1
    assert findings[0].haystack == "unpinned.output"


def test_non_output_and_presence_shapes_are_filtered() -> None:
    findings = _scan_fixture("non_output_and_presence")

    assert len(findings) == 1
    assert findings[0].haystack == "result.cli_output"


def test_literals_shared_by_multiple_locales_are_not_findings() -> None:
    catalogues = {"en": ("ADVISORY:",), "es": ("ADVISORY:",), "ca": ("other",)}

    assert (
        scan_locale_bound_assertions(
            _FIXTURE,
            _source_fixture("unpinned"),
            catalogues,
            _PINNING,
            ambient_locale="ca",
        )
        == ()
    )


def test_unknown_ambient_locale_is_rejected() -> None:
    with pytest.raises(ValueError, match="ambient locale 'fr' has no catalogue"):
        scan_locale_bound_assertions(_FIXTURE, "", _CATALOGUES, _PINNING, ambient_locale="fr")


def test_findings_preserve_path_line_and_haystack_metadata() -> None:
    finding = _scan_fixture("unpinned")[0]

    assert finding.path == _FIXTURE
    assert finding.lineno == 3
    assert finding.literal == "ADVISORY:"
    assert finding.polarity == "absence"
    assert finding.locales == frozenset({"en"})
    assert finding.haystack == "result.output"
    assert str(finding) == "fixture.py:3 absence 'ADVISORY:' in result.output is bound to locales [en] without a pin"


def test_clicks_untranslated_messages_are_not_locale_findings() -> None:
    assert _scan_fixture("click_message") == ()


def test_multipart_f_strings_with_unknown_parts_are_not_assumed_pinned() -> None:
    assert len(_scan_fixture("multipart_spliced_language")) == 1


def test_locale_value_without_a_language_flag_is_not_a_pin() -> None:
    assert len(_scan_fixture("locale_without_flag")) == 1


def test_trailing_language_flag_is_not_a_pin() -> None:
    assert len(_scan_fixture("trailing_language_flag")) == 1


def test_unrelated_joined_argv_is_not_a_pin() -> None:
    assert len(_scan_fixture("unrelated_joined_argument")) == 1


def test_environment_pin_is_found_after_other_keywords() -> None:
    assert _scan_fixture("env_keyword_after_other_keyword") == ()


def test_environment_value_under_the_wrong_key_is_not_a_pin() -> None:
    assert len(_scan_fixture("wrong_environment_key")) == 1


def test_unknown_direct_environment_names_are_not_pins() -> None:
    assert len(_scan_fixture("unknown_direct_environment")) == 1


def test_nested_scopes_do_not_hide_a_helper_return() -> None:
    assert _scan_fixture("return_before_nested_scope") == ()


def test_all_helper_return_paths_are_considered() -> None:
    assert len(_scan_fixture("multiple_helper_returns")) == 1


def test_an_earlier_unpinned_helper_return_cannot_be_skipped() -> None:
    assert len(_scan_fixture("earlier_unpinned_helper_return")) == 1


def test_forwarded_environment_helpers_are_pins() -> None:
    assert _scan_fixture("forwarded_environment_helper") == ()


def test_environment_helper_chains_reach_a_fixed_point() -> None:
    assert _scan_fixture("ordered_environment_helper_chain") == ()


def test_late_environment_helpers_are_not_skipped_after_a_pinned_helper() -> None:
    assert _scan_fixture("pinned_before_dependent_environment") == ()


def test_output_helper_chains_reach_a_fixed_point() -> None:
    assert _scan_fixture("ordered_output_helper_chain") == ()


def test_late_output_helpers_are_not_skipped_after_a_pinned_helper() -> None:
    assert _scan_fixture("pinned_before_dependent_output") == ()


def test_future_assignments_do_not_pin_helper_returns() -> None:
    findings = _scan_fixture("future_output_helper_pin")

    assert len(findings) == 1
    assert findings[0].haystack == "result.output"


def test_same_line_pin_assignment_precedes_the_assertion() -> None:
    assert _scan_fixture("same_line_pin_assignment") == ()


def test_multi_target_assignment_does_not_stop_state_analysis() -> None:
    assert _scan_fixture("assignment_after_multi_target") == ()


def test_annotation_without_a_value_does_not_stop_state_analysis() -> None:
    assert _scan_fixture("assignment_after_annotation") == ()


def test_unknown_output_sources_are_not_pins() -> None:
    assert len(_scan_fixture("unknown_output_source")) == 1


def test_pinned_named_helper_returns_propagate_to_callers() -> None:
    assert _scan_fixture("pinned_named_helper_return") == ()


def test_unknown_named_helper_returns_do_not_propagate_to_callers() -> None:
    assert len(_scan_fixture("unknown_named_helper_return")) == 1


def test_direct_environment_mappings_are_pins() -> None:
    assert _scan_fixture("direct_environment_mapping") == ()


def test_nested_environment_mappings_keep_their_pin_state() -> None:
    assert len(_scan_fixture("forwarded_environment_mapping")) == 1


def test_an_unrelated_pinned_argument_does_not_pin_a_call_result() -> None:
    assert len(_scan_fixture("unrelated_pinned_argument")) == 1


def test_a_dynamic_spliced_locale_is_not_assumed_supported() -> None:
    assert len(_scan_fixture("dynamic_spliced_locale")) == 1


def test_unknown_environment_mappings_are_not_pins() -> None:
    assert len(_scan_fixture("unknown_environment_mapping")) == 1


def test_output_named_captures_are_haystacks() -> None:
    assert len(_scan_fixture("output_named_capture")) == 1


def test_unknown_output_names_are_haystacks() -> None:
    assert len(_scan_fixture("unknown_output_name")) == 1


def test_non_membership_assertions_do_not_stop_later_findings() -> None:
    assert len(_scan_fixture("non_membership_before_finding")) == 1


def test_click_literals_do_not_stop_later_findings() -> None:
    assert len(_scan_fixture("click_before_finding")) == 1


def test_presence_assertions_do_not_stop_later_findings() -> None:
    assert len(_scan_fixture("presence_before_finding")) == 1


def test_direct_call_haystacks_are_checked() -> None:
    assert len(_scan_fixture("direct_call_haystack")) == 1


def test_direct_calls_with_environment_helpers_are_checked() -> None:
    assert _scan_fixture("direct_call_with_environment_helper") == ()


def test_a_pinned_direct_call_does_not_hide_a_later_unpinned_call() -> None:
    assert len(_scan_fixture("pinned_then_direct_unpinned")) == 1


def test_only_a_pinned_method_receiver_propagates_output_state() -> None:
    assert len(_scan_fixture("unpinned_receiver_transformation")) == 1
    assert len(_scan_fixture("unknown_receiver_transformation")) == 1


def test_only_a_proven_environment_alias_propagates_pin_state() -> None:
    assert _scan_fixture("forwarded_direct_environment") == ()
    assert len(_scan_fixture("forwarded_unknown_environment")) == 1


@pytest.mark.parametrize("ambient_locale", ("es", "en"))
def test_no_locale_bound_absence_survives_the_two_locale_axis(ambient_locale: str, pytester: pytest.Pytester) -> None:
    findings = tuple(
        finding
        for path in _test_modules()
        for finding in scan_locale_bound_assertions(
            path,
            path.read_text(encoding="utf-8"),
            _CATALOGUES,
            _PINNING,
            ambient_locale=ambient_locale,
        )
    )

    runtime_failures = tuple(
        (node_id, output_locale, outcome)
        for node_id in sorted({_pytest_node_id(finding.path, finding.lineno) for finding in findings})
        for output_locale in ("en", "es")
        if (outcome := _run_node_under_locale(pytester, node_id, output_locale))[0] != 0
    )
    assert not runtime_failures, "locale-bound pytest nodes fail the runtime locale axis:\n" + "\n".join(
        f"  {node_id} under {output_locale}: {outcome[1]}" for node_id, output_locale, outcome in runtime_failures
    )
    assert not findings, f"locale-bound absences under ambient {ambient_locale!r}:\n" + "\n".join(
        f"  {finding}" for finding in findings
    )
