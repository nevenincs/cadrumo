"""The navigation register loads only when every rule holds, and every label it names is translated."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n.render import lookup_translation

from ..navigation import (
    NavigationRegister,
    NavigationRegisterError,
    NavigationSurface,
    SurfaceImplementation,
    ViewLink,
    ViewOpened,
    load_navigation_register,
    parse_view_link,
    resolve_view,
    view_link,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KINDS = """
[[kind]]
name = "invoice"
alphabet = "0123456789abcdef"
length = 64
"""


def _element(view_id: str, *, parent: str | None = None, extra: str = "", surfaces: str = '["gui"]') -> str:
    parent_line = "" if parent is None else f'parent = "{parent}"\n'
    label = "nav." + view_id.replace("/", ".").replace("-", "_") + ".label"
    return (
        f'\n[[element]]\nid = "{view_id}"\n{parent_line}label = "{label}"\n'
        f'keywords = "words"\nsurfaces = {surfaces}\n{extra}'
    )


_VALID = (
    'schema = 1\nretired = ["old"]\n'
    + _KINDS
    + _element("ledger", surfaces='["gui", "tui"]')
    + _element("ledger/invoices", parent="ledger", extra='params = { select = "invoice" }\n')
)


def _load(tmp_path: Path, text: str) -> NavigationRegister:
    path = tmp_path / "navigation.toml"
    path.write_text(text, encoding="utf-8")
    return load_navigation_register(path)


def test_the_fixture_baseline_loads(tmp_path: Path) -> None:
    register = _load(tmp_path, _VALID)
    assert [element.id for element in register.elements] == ["ledger", "ledger/invoices"]
    invoices = register.element("ledger/invoices")
    assert invoices is not None
    assert invoices.params == {"select": "invoice"}
    assert register.param_names == {"select"}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        pytest.param(_VALID.replace("schema = 1", "schema = 2"), "register schema 2", id="schema"),
        pytest.param(_VALID + _element("Ledger-two"), "not one to four lowercase segments", id="uppercase-id"),
        pytest.param(_VALID + _element("ledger_two"), "not one to four lowercase segments", id="underscore-id"),
        pytest.param(_VALID + _element("two-"), "not one to four lowercase segments", id="trailing-hyphen"),
        pytest.param(
            _VALID + _element("a/b/c/d/e", parent="a/b/c/d"), "not one to four lowercase segments", id="five-segments"
        ),
        pytest.param(_VALID + _element("ledger"), "declared more than once", id="duplicate-id"),
        pytest.param(_VALID + _element("old"), "retired ids ['old'] are declared again", id="reused-retired-id"),
        pytest.param(
            _VALID.replace('retired = ["old"]', 'retired = ["Old"]'), "are not register ids", id="bad-retired"
        ),
        pytest.param(
            _VALID.replace('retired = ["old"]', 'retired = ["old", "old"]'), "listed once", id="repeated-retired"
        ),
        pytest.param(
            _VALID + _element("calendar/months", parent="calendar"),
            "name a parent the register does not declare",
            id="unknown-parent",
        ),
        pytest.param(_VALID + _element("docs/guide"), "must name its enclosing path", id="child-without-parent"),
        pytest.param(
            _VALID + _element("docs", parent="ledger"), "root element 'docs' names a parent", id="root-with-parent"
        ),
        pytest.param(
            # Each names the other as parent: a cycle can only be written by
            # breaking the enclosing-path rule, which refuses it.
            _VALID + _element("cyc", parent="cyc/a") + _element("cyc/a", parent="cyc"),
            "root element 'cyc' names a parent",
            id="cycle",
        ),
        pytest.param(
            _VALID + _element("ledger/rules", parent="ledger/invoices"),
            "must name its enclosing path 'ledger'",
            id="parent-not-enclosing",
        ),
        pytest.param(_VALID + _element("docs", surfaces="[]"), "surfaces", id="no-surface"),
        pytest.param(_VALID + _element("docs", surfaces='["web"]'), "surfaces", id="unknown-surface"),
        pytest.param(_VALID + _element("docs", surfaces='["gui", "gui"]'), "at most once", id="repeated-surface"),
        pytest.param(
            _VALID + '\n[[element]]\nid = "docs"\nkeywords = "w"\nsurfaces = ["gui"]\n', "label", id="missing-label"
        ),
        pytest.param(
            _VALID + '\n[[element]]\nid = "docs"\nlabel = "Docs"\nkeywords = "w"\nsurfaces = ["gui"]\n',
            "not a dotted locale key",
            id="label-not-a-key",
        ),
        pytest.param(_VALID + _element("docs", extra='target = "x"\n'), "target", id="unknown-field"),
        pytest.param(
            _VALID + _element("docs", extra='params = { select = "transaction" }\n'),
            "take a value kind the register does not declare",
            id="undeclared-value-kind",
        ),
        pytest.param(
            _VALID + _element("docs", extra='params = { prefer = "invoice" }\n'),
            "'prefer' is reserved",
            id="reserved-prefer",
        ),
        pytest.param(
            _VALID + _element("docs", extra='params = { Select = "invoice" }\n'),
            "are not lowercase hyphenated words",
            id="bad-param-name",
        ),
        pytest.param(_VALID + _KINDS, "value kinds ['invoice'] are declared more than once", id="duplicate-kind"),
        pytest.param(
            _VALID.replace('alphabet = "0123456789abcdef"', 'alphabet = "0123456789ABCDEF"'),
            "cannot hold unescaped",
            id="uppercase-alphabet",
        ),
        pytest.param(
            _VALID.replace('alphabet = "0123456789abcdef"', 'alphabet = "0123456789abcdef&"'),
            "cannot hold unescaped",
            id="reserved-alphabet",
        ),
        pytest.param(_VALID.replace("length = 64", "length = 0"), "length", id="empty-value"),
        pytest.param("schema = 1\nretired = []\nelement = []\n", "element", id="no-elements"),
        pytest.param(_VALID + "[[element]\n", "navigation register refused", id="not-toml"),
    ],
)
def test_a_register_breaking_a_rule_is_refused(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(NavigationRegisterError, match="navigation register refused") as refusal:
        _load(tmp_path, text)
    assert message in str(refusal.value)


def test_nearest_ancestor_wins_over_the_preferred_surface(tmp_path: Path) -> None:
    register = _load(
        tmp_path,
        _VALID
        + _element("ledger/invoices/lines", parent="ledger/invoices")
        + _element("ledger/invoices/lines/tax", parent="ledger/invoices/lines"),
    )
    outcome = resolve_view(
        ViewLink(view_id="ledger/invoices/lines/tax"),
        {
            NavigationSurface.GUI: SurfaceImplementation(views=frozenset({"ledger"})),
            NavigationSurface.TUI: SurfaceImplementation(views=frozenset({"ledger/invoices"})),
        },
        register=register,
    )
    assert outcome == ViewOpened(
        requested=ViewLink(view_id="ledger/invoices/lines/tax"),
        opened="ledger/invoices",
        surface=NavigationSurface.TUI,
        fallback="ancestor",
        params=(),
    )


def test_the_shipped_register_declares_the_initial_elements() -> None:
    register = load_navigation_register()
    gui, tui = NavigationSurface.GUI, NavigationSurface.TUI
    assert {element.id: set(element.surfaces) for element in register.elements} == {
        "home": {tui},
        "ledger": {gui, tui},
        "ledger/movements": {gui},
        "ledger/invoices": {gui},
        "ledger/documents": {gui},
        "ledger/rules": {gui},
        "ledger/registers": {gui},
        "ledger/health": {gui},
        "withholding": {tui},
        "declarations": {gui, tui},
        "aeat-sync": {tui},
        "operations": {tui},
        "installation": {tui},
        "setup": {tui},
        "reference": {tui},
        "profile": {gui, tui},
        "profile/aeat-access": {tui},
        "calendar": {gui},
        "docs": {gui},
        "agent": {gui},
        "terminal": {gui},
        "panel": {gui},
        "panel/console": {gui},
        "panel/python": {gui},
        "panel/logs": {gui},
    }
    assert {element.id: dict(element.params) for element in register.elements if element.params} == {
        "ledger": {"select": "transaction"},
        "ledger/movements": {"select": "transaction"},
        "ledger/invoices": {"select": "invoice"},
    }
    assert register.retired == ()


def test_the_shipped_value_kinds_are_content_derived_sha256_ids() -> None:
    register = load_navigation_register()
    assert {(kind.name, kind.alphabet, kind.length) for kind in register.kinds} == {
        ("transaction", "0123456789abcdef", 64),
        ("invoice", "0123456789abcdef", 64),
    }


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_label_is_translated_in_every_locale(locale: str) -> None:
    register = load_navigation_register()
    untranslated = sorted(
        element.label
        for element in register.elements
        if not (lookup_translation(element.label, locale=locale) or "").strip()
    )
    assert not untranslated, f"{locale} has no translation for {untranslated!r}"


def test_labels_are_distinct_in_the_source_locale() -> None:
    register = load_navigation_register()
    labels = [element.label for element in register.elements]
    assert len(set(labels)) == len(labels)


def test_parameters_are_spelled_in_name_order_and_read_in_any(tmp_path: Path) -> None:
    register = _load(
        tmp_path,
        _VALID.replace('params = { select = "invoice" }', 'params = { select = "invoice", focus = "invoice" }'),
    )
    invoice, other = "a" * 64, "b" * 64
    link = view_link("ledger/invoices", {"select": invoice, "focus": other}, NavigationSurface.TUI, register=register)
    assert link == f"cadrumo://view/ledger/invoices?focus={other}&select={invoice}&prefer=tui"
    expected = ViewLink(
        view_id="ledger/invoices", params=(("focus", other), ("select", invoice)), prefer=NavigationSurface.TUI
    )
    for text in (link, f"cadrumo://view/ledger/invoices?prefer=tui&select={invoice}&focus={other}"):
        assert parse_view_link(text, register=register) == expected


def test_a_surface_honouring_only_some_parameters_drops_them_all(tmp_path: Path) -> None:
    register = _load(
        tmp_path,
        _VALID.replace('params = { select = "invoice" }', 'params = { select = "invoice", focus = "invoice" }'),
    )
    request = ViewLink(view_id="ledger/invoices", params=(("focus", "a" * 64), ("select", "b" * 64)))
    gui = SurfaceImplementation(views=frozenset({"ledger/invoices"}), params={"ledger/invoices": frozenset({"select"})})
    outcome = resolve_view(request, {NavigationSurface.GUI: gui}, register=register)
    assert outcome == ViewOpened(request, "ledger/invoices", NavigationSurface.GUI, "none", ())
    assert isinstance(outcome, ViewOpened)
    assert outcome.notice_due
