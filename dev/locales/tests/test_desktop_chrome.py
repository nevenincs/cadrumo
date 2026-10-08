"""The desktop shell's chrome strings: one declaration, generated from the catalogues.

The shell is TypeScript and reads a generated JSON file, so three things must
stay aligned without a ``tr()`` call site to tie them: the keys the shell
source names, the declaration the generator and the locale key scan read, and
the four canonical catalogues. Each test below fails when one of them drifts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

from dev._paths import REPO_ROOT

from .._paths import LOCALES_DIR
from ..desktop_chrome import (
    DESKTOP_CHROME_AWAITING_CONSUMER,
    DESKTOP_CHROME_FAMILIES,
    DESKTOP_CHROME_KEYS,
    DESKTOP_LOCALES,
    desktop_chrome_strings,
    main,
    render_desktop_chrome,
)
from ..errors import LocaleError
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FRONTEND_SOURCE = REPO_ROOT / "native" / "desktop" / "frontend" / "src"
# A whole key in quotes, or the fixed head of a template literal up to `${`.
_LITERAL_KEY = re.compile(r"""["'`](desktop\.[A-Za-z0-9_.]+)["'`]""")
_TEMPLATE_HEAD = re.compile(r"`(desktop\.[A-Za-z0-9_.]*)\$\{")


def _frontend_references(source: Path) -> tuple[set[str], set[str]]:
    """Return the literal keys and template prefixes the shell source names."""
    literals: set[str] = set()
    templates: set[str] = set()
    sources = [
        path
        for pattern in ("*.ts", "*.tsx")
        for path in source.rglob(pattern)
        if "generated" not in path.relative_to(source).parts
    ]
    assert sources, f"no shell source under {source}, so nothing was checked"
    for path in sources:
        text = path.read_text(encoding="utf-8")
        literals.update(_LITERAL_KEY.findall(text))
        templates.update(_TEMPLATE_HEAD.findall(text))
    return literals, templates


def _expand(literals: set[str], templates: set[str], families: Mapping[str, tuple[str, ...]]) -> set[str]:
    """Return every key named, expanding the templates that have a declared family."""
    return literals | {f"{prefix}{member}" for prefix in templates & set(families) for member in families[prefix]}


def _used_keys(source: Path, families: Mapping[str, tuple[str, ...]]) -> set[str]:
    """Return every key the shell source names."""
    return _expand(*_frontend_references(source), families)


def _drift(source: Path, keys: frozenset[str], families: Mapping[str, tuple[str, ...]]) -> dict[str, list[str]]:
    """Compare what the shell source names with a key declaration."""
    literals, templates = _frontend_references(source)
    used = _expand(literals, templates, families)
    return {
        "undeclared_templates": sorted(templates - set(families)),
        "undeclared": sorted(used - keys),
        "unused": sorted(keys - used),
    }


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


def test_every_declared_key_is_authored_in_all_four_canonical_catalogues(tmp_path: Path) -> None:
    output = tmp_path / "chrome-strings.json"

    assert main(["--output", str(output)]) == 0

    written = json.loads(output.read_text(encoding="utf-8"))
    assert list(written) == sorted(DESKTOP_LOCALES)
    for locale in DESKTOP_LOCALES:
        assert set(written[locale]) == DESKTOP_CHROME_KEYS, locale
    assert written == desktop_chrome_strings(LOCALES_DIR)


def test_the_shell_source_names_exactly_the_declared_keys() -> None:
    drift = _drift(_FRONTEND_SOURCE, DESKTOP_CHROME_KEYS - DESKTOP_CHROME_AWAITING_CONSUMER, DESKTOP_CHROME_FAMILIES)

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

    assert _drift(source, keys, {}) == {
        "undeclared_templates": ["desktop.kind_"],
        "undeclared": ["desktop.rail.extra"],
        "unused": ["desktop.kind_a", "desktop.stale"],
    }
    assert _drift(source, keys, {"desktop.kind_": ("a", "b")}) == {
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
        "desktop.signin.open_tui",
        "desktop.signin.open_tui_hint",
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
    # An empty source tree isolates this key source from every call-site scan.
    keys = LocaleManager(tmp_path, LOCALES_DIR).get_codebase_keys()

    assert keys >= DESKTOP_CHROME_KEYS
