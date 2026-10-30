"""The desktop shell's chrome strings: one declaration, generated from the catalogues.

The shell is TypeScript and reads a generated JSON file, so three things must
stay aligned without a ``tr()`` call site to tie them: the keys the shell
source names, the declaration the generator and the locale key scan read, and
the four canonical catalogues. Each test below fails when one of them drifts.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

from dev._paths import REPO_ROOT

from .. import desktop_chrome
from .._paths import LOCALES_DIR
from ..desktop_chrome import (
    DESKTOP_CHROME_AWAITING_CONSUMER,
    DESKTOP_CHROME_FAMILIES,
    DESKTOP_CHROME_KEYS,
    DESKTOP_LOCALES,
    desktop_chrome_strings,
    main,
    refuse_unbuilt_shell_keys,
    render_desktop_chrome,
    shell_drift,
    shell_key_references,
    shell_named_keys,
)
from ..errors import LocaleError
from ..manager import LocaleManager
from ..service_catalogues import SERVICE_FAMILIES, SERVICE_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FRONTEND_SOURCE = REPO_ROOT / "native" / "desktop" / "frontend" / "src"


def _used_keys(source: Path, families: Mapping[str, tuple[str, ...]]) -> frozenset[str]:
    """Return every key the shell source names."""
    return shell_named_keys(*shell_key_references(source), families)


def _catalogues(root: Path, values: dict[str, dict[str, str]]) -> Path:
    """Write sharded fixture catalogues the way the catalogue authority lays them out."""
    for locale, leaves in values.items():
        shard = root / locale / "common.yml"
        shard.parent.mkdir(parents=True, exist_ok=True)
        tree: dict[str, object] = {}
        for key, value in leaves.items():
            node = tree
            *parents, leaf = key.split(".")
            for part in parents:
                child = node.setdefault(part, {})
                assert isinstance(child, dict)
                node = child
            node[leaf] = value
        shard.write_text(yaml.safe_dump(tree, allow_unicode=True), encoding="utf-8")
    return root


_KEYS = frozenset({"desktop.rail.search", "desktop.logs.errors"})
_COMPLETE = {
    "en": {"desktop.rail.search": "Search", "desktop.logs.errors": "Errors: {count}"},
    "es": {"desktop.rail.search": "Buscar", "desktop.logs.errors": "Errores: {count}"},
}


def test_generation_projects_every_declared_key_in_every_locale(tmp_path: Path) -> None:
    strings = desktop_chrome_strings(_catalogues(tmp_path, _COMPLETE), keys=_KEYS, locales=("en", "es"))

    assert strings == _COMPLETE
    rendered = json.loads(render_desktop_chrome(strings))
    assert rendered == {"en": _COMPLETE["en"], "es": _COMPLETE["es"]}


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (None, "absent"),
        ("   ", "blank"),
        ("desktop.logs.errors", "key_echo"),
    ],
)
def test_a_missing_or_placeholder_translation_refuses_generation(
    tmp_path: Path, value: str | None, reason: str
) -> None:
    spanish = dict(_COMPLETE["es"])
    if value is None:
        del spanish["desktop.logs.errors"]
    else:
        spanish["desktop.logs.errors"] = value
    root = _catalogues(tmp_path, {"en": _COMPLETE["en"], "es": spanish})

    with pytest.raises(LocaleError, match=rf"es:desktop\.logs\.errors is {reason}"):
        desktop_chrome_strings(root, keys=_KEYS, locales=("en", "es"))


@pytest.mark.parametrize(
    ("spanish", "match"),
    [
        ("Errores: {total}", "different placeholders"),
        ("Errores", "different placeholders"),
        ("Errores: {count:d}", "cannot substitute"),
        ("Errores: %{count}", "cannot substitute"),
    ],
)
def test_placeholders_must_match_and_take_the_form_the_shell_substitutes(
    tmp_path: Path, spanish: str, match: str
) -> None:
    root = _catalogues(tmp_path, {"en": _COMPLETE["en"], "es": {**_COMPLETE["es"], "desktop.logs.errors": spanish}})

    with pytest.raises(LocaleError, match=match):
        desktop_chrome_strings(root, keys=_KEYS, locales=("en", "es"))


def test_a_locale_without_a_catalogue_is_refused(tmp_path: Path) -> None:
    root = _catalogues(tmp_path, {"en": _COMPLETE["en"]})

    with pytest.raises(LocaleError, match="No catalogue for desktop locale 'es'"):
        desktop_chrome_strings(root, keys=_KEYS, locales=("en", "es"))


def test_generation_composes_runtime_and_service_catalogues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tax = _catalogues(tmp_path / "tax", {"en": {"desktop.rail.search": "Search"}})
    runtime = _catalogues(tmp_path / "runtime", {"en": {"desktop.attendance.network": "Network access"}})
    service = _catalogues(tmp_path / "service", {"en": {"desktop.agent.title": "Agent"}})
    monkeypatch.setattr(desktop_chrome, "LOCALES_DIR", tax)
    monkeypatch.setattr(desktop_chrome, "RUNTIME_LOCALES_DIR", runtime)
    monkeypatch.setattr(desktop_chrome, "SERVICE_LOCALES_DIR", service)
    expected = {
        "desktop.rail.search": "Search",
        "desktop.attendance.network": "Network access",
        "desktop.agent.title": "Agent",
    }

    assert desktop_chrome_strings(tax, keys=frozenset(expected), locales=("en",)) == {"en": expected}


@pytest.mark.parametrize("colliding_owner", ["tax", "service"])
def test_runtime_catalogue_collisions_refuse_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, colliding_owner: str
) -> None:
    values = {
        "tax": {"desktop.rail.search": "Search"},
        "runtime": {"desktop.attendance.network": "Network access"},
        "service": {"desktop.agent.title": "Agent"},
    }
    values[colliding_owner]["desktop.attendance.network"] = "Conflicting network access"
    roots = {owner: _catalogues(tmp_path / owner, {"en": leaves}) for owner, leaves in values.items()}
    monkeypatch.setattr(desktop_chrome, "LOCALES_DIR", roots["tax"])
    monkeypatch.setattr(desktop_chrome, "RUNTIME_LOCALES_DIR", roots["runtime"])
    monkeypatch.setattr(desktop_chrome, "SERVICE_LOCALES_DIR", roots["service"])

    with pytest.raises(LocaleError, match="catalogue keys overlap"):
        desktop_chrome_strings(roots["tax"], keys=frozenset({"desktop.attendance.network"}), locales=("en",))


def test_missing_runtime_translation_refuses_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tax = _catalogues(tmp_path / "tax", {"en": {}, "es": {}})
    runtime = _catalogues(tmp_path / "runtime", {"en": {"desktop.attendance.network": "Network access"}, "es": {}})
    monkeypatch.setattr(desktop_chrome, "LOCALES_DIR", tax)
    monkeypatch.setattr(desktop_chrome, "RUNTIME_LOCALES_DIR", runtime)
    monkeypatch.setattr(desktop_chrome, "SERVICE_LOCALES_DIR", tmp_path / "absent-service")

    with pytest.raises(LocaleError, match=r"es:desktop\.attendance\.network is absent"):
        desktop_chrome_strings(tax, keys=frozenset({"desktop.attendance.network"}), locales=("en", "es"))


def test_every_declared_key_is_authored_in_all_four_canonical_catalogues(tmp_path: Path) -> None:
    output = tmp_path / "chrome-strings.json"

    assert main(["--output", str(output)]) == 0

    written = json.loads(output.read_text(encoding="utf-8"))
    assert list(written) == sorted(DESKTOP_LOCALES)
    for locale in DESKTOP_LOCALES:
        assert (
            set(written[locale])
            == DESKTOP_CHROME_KEYS
            | desktop_chrome.DESKTOP_NAVIGATION_LABEL_KEYS
            | desktop_chrome.DESKTOP_NAVIGATION_KEYWORD_KEYS
        ), locale
    assert written == desktop_chrome_strings(LOCALES_DIR)


def test_the_shell_source_names_exactly_the_declared_keys() -> None:
    drift = shell_drift(
        _FRONTEND_SOURCE, DESKTOP_CHROME_KEYS - DESKTOP_CHROME_AWAITING_CONSUMER, DESKTOP_CHROME_FAMILIES
    )

    assert drift == {"undeclared_templates": [], "undeclared": [], "unused": []}, (
        "the shell source and the desktop chrome declaration disagree: a template needs a declared family, "
        "an undeclared key is never generated, and an unused one is stale"
    )


def test_the_drift_check_sees_templates_undeclared_and_stale_keys(tmp_path: Path) -> None:
    source = tmp_path / "src"
    (source / "generated").mkdir(parents=True)
    (source / "generated" / "ignored.ts").write_text('t("desktop.only.generated");\n', encoding="utf-8")
    (source / "Panel.tsx").write_text(
        "t(\"desktop.rail.search\"); t('desktop.rail.extra'); t(`desktop.kind_${kind}`);\n", encoding="utf-8"
    )
    keys = frozenset({"desktop.rail.search", "desktop.kind_a", "desktop.stale"})

    assert shell_drift(source, keys, {}) == {
        "undeclared_templates": ["desktop.kind_"],
        "undeclared": ["desktop.rail.extra"],
        "unused": ["desktop.kind_a", "desktop.stale"],
    }
    assert shell_drift(source, keys, {"desktop.kind_": ("a", "b")}) == {
        "undeclared_templates": [],
        "undeclared": ["desktop.kind_b", "desktop.rail.extra"],
        "unused": ["desktop.stale"],
    }


# The sign-in and account keys were authored before the sign-in view existed.
# Keys may leave the awaiting set as their view lands; none may join it.
_AWAITING_CONSUMER_CEILING = frozenset(
    {
        "desktop.account.remaining_access",
        "desktop.account.sign_out",
        "desktop.account.sign_out_hint",
        "desktop.account.signed_in",
        "desktop.account.signed_out",
        "desktop.account.title",
        "desktop.account.unknown",
        "desktop.signin.checking",
        "desktop.signin.lead",
        "desktop.signin.password",
        "desktop.signin.refused.custody_changed",
        "desktop.signin.refused.generation_changed",
        "desktop.signin.refused.invalid",
        "desktop.signin.refused.keyring_unavailable",
        "desktop.signin.refused.login_mismatch",
        "desktop.signin.refused.other",
        "desktop.signin.refused.profile_locked",
        "desktop.signin.refused.receipt_absent",
        "desktop.signin.refused.receipt_expired",
        "desktop.signin.refused.runtime_unavailable",
        "desktop.signin.refused.throttled",
        "desktop.signin.start_services",
        "desktop.signin.submit",
        "desktop.signin.submitting",
        "desktop.signin.title",
        "desktop.signin.unsupported",
    }
)


def test_keys_awaiting_their_consumer_are_declared_and_only_ever_shrink() -> None:
    assert DESKTOP_CHROME_AWAITING_CONSUMER <= DESKTOP_CHROME_KEYS, "an awaiting key must still be declared"
    assert DESKTOP_CHROME_AWAITING_CONSUMER <= _AWAITING_CONSUMER_CEILING, (
        "a new key belongs in the regular declaration with the shell source that names it, not in the awaiting set"
    )


def test_no_key_awaiting_its_consumer_is_named_by_the_shell() -> None:
    named = sorted(_used_keys(_FRONTEND_SOURCE, DESKTOP_CHROME_FAMILIES) & DESKTOP_CHROME_AWAITING_CONSUMER)

    assert named == [], (
        "the shell now names these keys: remove them from DESKTOP_CHROME_AWAITING_CONSUMER "
        "so the exact-match drift check covers them"
    )


def test_the_awaiting_check_sees_a_named_key(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "SignIn.tsx").write_text(
        "t('desktop.signin.title'); t(`desktop.signin.refused.${reason}`);\n", encoding="utf-8"
    )
    families = {"desktop.signin.refused.": ("invalid",)}
    awaiting = frozenset({"desktop.signin.title", "desktop.signin.refused.invalid", "desktop.signin.lead"})

    assert sorted(_used_keys(source, families) & awaiting) == [
        "desktop.signin.refused.invalid",
        "desktop.signin.title",
    ]


def test_the_locale_key_scan_reads_the_declaration(tmp_path: Path) -> None:
    # The tax key source excludes independently owned service chrome; generation merges both catalogues.
    keys = LocaleManager(tmp_path, LOCALES_DIR).get_codebase_keys()

    service_prefixes = tuple(f"{namespace}.{family}." for namespace, family in SERVICE_FAMILIES)
    service_keys = {key for key in DESKTOP_CHROME_KEYS if key.startswith(service_prefixes) or key in SERVICE_KEYS}
    assert keys >= DESKTOP_CHROME_KEYS - service_keys
    assert keys.isdisjoint(service_keys)


def _planted_shell(root: Path, text: str) -> Path:
    source = root / "src"
    source.mkdir()
    (source / "Workspace.tsx").write_text(text, encoding="utf-8")
    return source


def test_generation_refuses_a_key_the_shell_names_but_does_not_carry(tmp_path: Path) -> None:
    source = _planted_shell(
        tmp_path,
        "w('workspace.modelo.filing.title'); w('workspace.example.absent'); w(`workspace.example.kind_${kind}`);\n",
    )

    with pytest.raises(LocaleError, match=r"workspace\.example\.absent") as refusal:
        refuse_unbuilt_shell_keys(source)
    assert "workspace.example.kind_" in str(refusal.value)
    assert "workspace.modelo.filing.title" not in str(refusal.value)


def test_generation_admits_a_shell_that_names_only_declared_keys(tmp_path: Path) -> None:
    source = _planted_shell(tmp_path, "w('workspace.modelo.filing.title'); w(`workspace.modelo.origin.${origin}`);\n")

    refuse_unbuilt_shell_keys(source)


def test_the_build_entry_point_stops_on_an_uncarried_shell_key(tmp_path: Path) -> None:
    source = _planted_shell(tmp_path, "t('desktop.example.absent');\n")
    output = tmp_path / "out" / "chrome-strings.json"

    with pytest.raises(SystemExit) as stopped:
        main(["--output", str(output), "--shell-source", str(source)])

    assert stopped.value.code == 1
    assert not output.exists()
