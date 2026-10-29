"""The navigation register loads only when every rule holds, and every label it names is translated."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.toml import parse_toml

from .. import navigation
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
        "reference": {tui},
        "profile": {gui, tui},
        "profile/aeat-access": {gui, tui},
        "calendar": {gui},
        "browser": {gui},
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


_SHIPPED_VIEWS = Path(__file__).with_name("navigation_shipped_views.json")


def _shipped_ids() -> tuple[str, ...]:
    """Every view id ever shipped, read from the append-only baseline beside this module."""
    shipped = json.loads(_SHIPPED_VIEWS.read_text(encoding="utf-8"))["shipped"]
    assert isinstance(shipped, list)
    return tuple(str(item) for item in shipped)


def _retired_baseline() -> tuple[str, ...]:
    """Every id the baseline records as retired; a subset of the shipped ids."""
    retired = json.loads(_SHIPPED_VIEWS.read_text(encoding="utf-8"))["retired"]
    assert isinstance(retired, list)
    return tuple(str(item) for item in retired)


def _lifecycle_breaches(
    register: NavigationRegister, shipped: tuple[str, ...], retired_baseline: tuple[str, ...] = ()
) -> list[str]:
    """Return every way ``register`` breaks the shipped baseline; empty when it keeps it.

    A shipped id stays answerable for good: either an element declares it or
    ``retired`` lists it. So deleting an element without retiring it, or
    dropping an id from ``retired``, breaks the baseline. A declared or
    retired id the baseline lacks means the baseline was not grown with it.
    An id the baseline records as retired stays in ``retired``: taking it out
    and declaring it again would let an old link open something new.
    """
    declared = {element.id for element in register.elements}
    retired = set(register.retired)
    breaches = [
        f"shipped id {item!r} is neither declared nor retired" for item in shipped if item not in declared | retired
    ]
    breaches.extend(
        f"id {item!r} is missing from the shipped baseline" for item in sorted((declared | retired) - set(shipped))
    )
    breaches.extend(f"retired id {item!r} was taken out of retired" for item in retired_baseline if item not in retired)
    return breaches


def _shipped_register_data() -> dict[str, Any]:
    source = Path(navigation.__file__).with_name("navigation.toml").read_text(encoding="utf-8")
    return dict(parse_toml(source))


def test_the_shipped_baseline_lists_each_id_once() -> None:
    shipped = _shipped_ids()
    assert shipped
    assert len(set(shipped)) == len(shipped)


def test_every_id_ever_shipped_is_declared_or_retired() -> None:
    assert _lifecycle_breaches(load_navigation_register(), _shipped_ids(), _retired_baseline()) == []


def test_the_retired_baseline_lists_each_id_once_and_only_shipped_ids() -> None:
    retired = _retired_baseline()
    assert len(set(retired)) == len(retired)
    assert set(retired) <= set(_shipped_ids())


def test_an_element_deleted_without_retiring_its_id_breaks_the_baseline() -> None:
    data = _shipped_register_data()
    data["element"] = [element for element in data["element"] if element["id"] != "panel/logs"]
    register = NavigationRegister.model_validate(data)
    assert _lifecycle_breaches(register, _shipped_ids()) == ["shipped id 'panel/logs' is neither declared nor retired"]

    data["retired"] = [*data["retired"], "panel/logs"]
    assert _lifecycle_breaches(NavigationRegister.model_validate(data), _shipped_ids()) == []


def test_an_id_taken_out_of_retired_breaks_the_baseline() -> None:
    data = _shipped_register_data()
    shipped = (*_shipped_ids(), "statements")
    retired = data["retired"]
    data["retired"] = [*retired, "statements"]
    assert _lifecycle_breaches(NavigationRegister.model_validate(data), shipped) == []

    data["retired"] = retired
    assert _lifecycle_breaches(NavigationRegister.model_validate(data), shipped) == [
        "shipped id 'statements' is neither declared nor retired"
    ]


def test_a_retired_id_removed_from_retired_and_declared_again_breaks_the_baseline(tmp_path: Path) -> None:
    shipped = ("ledger", "ledger/invoices", "old")
    kept = _load(tmp_path, _VALID)
    assert _lifecycle_breaches(kept, shipped, ("old",)) == []

    (tmp_path / "revived").mkdir()
    revived = _load(tmp_path / "revived", _VALID.replace('retired = ["old"]', "retired = []") + _element("old"))
    assert [element.id for element in revived.elements] == ["ledger", "ledger/invoices", "old"]
    assert _lifecycle_breaches(revived, shipped, ("old",)) == ["retired id 'old' was taken out of retired"]
    # Without the retired baseline the revival is invisible: every shipped id is declared.
    assert _lifecycle_breaches(revived, shipped) == []


def test_an_element_added_without_growing_the_baseline_breaks_it() -> None:
    data = _shipped_register_data()
    data["element"] = [
        *data["element"],
        {"id": "notes", "label": "nav.notes.label", "keywords": "w", "surfaces": ["gui"]},
    ]
    assert _lifecycle_breaches(NavigationRegister.model_validate(data), _shipped_ids()) == [
        "id 'notes' is missing from the shipped baseline"
    ]


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
