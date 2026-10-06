"""Site-chrome localization gates: catalogue coverage and English-literal detection.

The documentation site is published as one root per language. Page content is
substituted by gettext; the chrome around it -- header, broadcast strip, footer,
accessible names, and every string the interaction layer writes into the DOM --
is not page content and gettext never sees it. Two gates keep that surface
honest.

The first reads the ``docs.site`` subtree of the English catalogue, so the key
set is derived rather than restated, and proves every key resolves in every
:class:`~cadrumo.core.external_constants.OutputLanguage` member through the same
strict resolver the build uses. It also holds the subtree and
:mod:`dev.docs.site_chrome` to the same key set, so neither an orphaned
translation nor an unauthored request can sit unnoticed.

The second is a detector. Resolving today's strings fixes today's site; the
regression that matters is the next control someone adds with its label written
in English at the call site. It scans the shipped templates and
``docs/_static/cadrumo-docs.js`` for exactly that shape and allows only an
explicit list of tokens that are not language. Its teeth are proven against
planted files in a temporary directory, so the detector's own failure mode is
tested without touching the working tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import lookup_translation
from dev._paths import REPO_ROOT

from .._locale_chrome import docs_chrome
from ..site_chrome import site_chrome, site_labels

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"
_TEMPLATES = _DOCS / "_templates"
_WIDGET_JS = _DOCS / "_static" / "cadrumo-docs.js"
_EN_DOCS_CATALOGUE = _REPO_ROOT / "src" / "cadrumo" / "locales" / "en" / "docs.yml"

#: Tokens a chrome surface may carry as a bare literal because they are not
#: language. Each is either a brand name the product never translates, or the
#: name printed on a physical key, which does not change with the reader's
#: language:
#:
#: * ``CADRUMO`` and ``docs`` are the two halves of the header wordmark lockup.
#: * ``Cadrumo`` is the product name.
#: * ``Ctrl K`` and ``⌘ K`` name the palette shortcut's keys as the keyboard
#:   prints them; a reader presses the same two keys in every language.
#: * ``esc`` is the same fact for the dismiss key.
#: * ``GitHub`` and ``AEAT`` are proper nouns.
_ALLOWED_NON_LANGUAGE_TOKENS = frozenset(
    {
        "AEAT",
        "CADRUMO",
        "Cadrumo",
        "Ctrl K",
        "GitHub",
        "docs",
        "esc",
        "⌘ K",
    }
)

#: Attributes whose value a reader hears or sees as prose.
_PROSE_ATTRIBUTES = ("aria-label", "title", "placeholder", "alt")

#: A run of two or more letters is the signal that a literal is language rather
#: than a class name fragment, a unit, or a version prefix.
_WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)

#: A literal that is only a substitution placeholder (``{count}``) is filled by
#: the reader's browser from the authored translation, so it carries no prose.
_PLACEHOLDER_ONLY = re.compile(r"^\{[a-z_]+\}$")


def _site_subtree_keys() -> frozenset[str]:
    """Return every dotted ``docs.site.*`` key the English catalogue authors."""
    catalogue = yaml.safe_load(_EN_DOCS_CATALOGUE.read_text(encoding="utf-8"))
    assert isinstance(catalogue, dict), "the English docs catalogue must be a mapping"
    subtree = catalogue["docs"]["site"]
    assert isinstance(subtree, dict) and subtree, "docs.site must be a non-empty subtree"

    def walk(node: dict[str, object], prefix: str) -> list[str]:
        keys: list[str] = []
        for name, value in node.items():
            path = f"{prefix}.{name}"
            if isinstance(value, dict):
                keys.extend(walk({str(k): v for k, v in value.items()}, path))
            else:
                keys.append(path)
        return keys

    return frozenset(walk({str(key): value for key, value in subtree.items()}, "docs.site"))


def _requested_keys() -> frozenset[str]:
    """Return every ``docs.site.*`` key :mod:`dev.docs.site_chrome` resolves.

    Read from the module's own source the way the catalogue authority reads it,
    so the two cannot be reconciled by editing a list in this file.
    """
    source = (Path(__file__).resolve().parents[1] / "site_chrome.py").read_text(encoding="utf-8")
    # Any of the resolvers, because which one a key is asked for through says
    # which writer puts it on the page and nothing about the key set.
    pattern = re.compile(r'(?:docs|template|toctree_title)_chrome\(\s*"(docs\.site\.[\w.]+)"')
    keys: set[str] = set()
    for match in pattern.finditer(source):
        key = match.group(1)
        assert isinstance(key, str)
        keys.add(key)
    return frozenset(keys)


def test_every_site_chrome_key_resolves_in_every_language() -> None:
    """Every authored ``docs.site.*`` key has a value in every output language.

    The strict resolver is what the build uses, so a key that raises here is a
    key that would abort a localized build -- and a key that quietly returned
    English would be the silent fallback the localization contract refuses.
    """
    keys = _site_subtree_keys()
    assert keys, "the English catalogue authors no docs.site keys"
    missing: list[str] = []
    for language in OutputLanguage:
        for key in sorted(keys):
            if lookup_translation(key, locale=language.value) is None:
                missing.append(f"{language.value}:{key}")
    assert not missing, "site chrome keys with no authored value: " + ", ".join(missing)


def test_authored_site_chrome_keys_are_exactly_the_requested_keys() -> None:
    """The catalogue subtree and the resolving module name the same key set."""
    authored = _site_subtree_keys()
    requested = _requested_keys()
    assert not authored - requested, "authored but never resolved: " + ", ".join(sorted(authored - requested))
    assert not requested - authored, "resolved but never authored: " + ", ".join(sorted(requested - authored))


@pytest.mark.parametrize("language", list(OutputLanguage), ids=lambda member: member.value)
def test_site_chrome_mappings_are_complete_and_disjoint(language: OutputLanguage) -> None:
    """Both mappings resolve for every language and together cover every key.

    Args:
        language: The output language to resolve the mappings in.
    """
    labels = site_labels(language)
    chrome = site_chrome(language, language_endonym="Endonym")
    assert not set(labels) & set(chrome), "a chrome string must have one destination, not two"
    assert len(labels) + len(chrome) == len(_site_subtree_keys())
    assert all(value.strip() for value in (*labels.values(), *chrome.values()))


def test_language_switcher_accessible_name_carries_the_endonym() -> None:
    """The switcher's accessible name is interpolated, not left as a placeholder."""
    chrome = site_chrome(OutputLanguage.HU, language_endonym="Magyar")
    assert "Magyar" in chrome["aria_language"]
    assert "{language}" not in chrome["aria_language"]
    assert docs_chrome("docs.site.aria.language", OutputLanguage.HU).count("{language}") == 1


# ── English-literal detector ────────────────────────────────────────────────


def _is_prose(literal: str) -> bool:
    """Return whether one literal reads as language a reader would be shown."""
    text = literal.strip()
    if not text or text in _ALLOWED_NON_LANGUAGE_TOKENS or _PLACEHOLDER_ONLY.match(text):
        return False
    return bool(_WORD.search(text))


def template_prose_findings(text: str) -> list[str]:
    """Return every hard-coded prose literal in one Jinja template's source.

    Two shapes are inspected: the value of an attribute a reader hears as prose,
    and a text node between two tags. A value written entirely as a Jinja
    expression is resolved chrome and passes; anything else carrying a word is
    reported.

    Args:
        text: The template source.

    Returns:
        One human-readable finding per hard-coded literal, in source order.
    """
    # Jinja comments hold authoring notes for maintainers, never rendered text.
    body = re.sub(r"\{#.*?#\}", " ", text, flags=re.DOTALL)
    findings: list[str] = []
    for attribute in _PROSE_ATTRIBUTES:
        for match in re.finditer(rf'\b{attribute}="([^"]*)"', body):
            value = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "", match.group(1), flags=re.DOTALL)
            if _is_prose(value):
                findings.append(f"{attribute}={match.group(1)!r}")
    # Text nodes: drop every Jinja construct, then read what sits between tags.
    stripped = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "", body, flags=re.DOTALL)
    for match in re.finditer(r">([^<>]*)<", stripped):
        if _is_prose(match.group(1)):
            findings.append(f"text node {match.group(1).strip()!r}")
    return findings


def script_prose_findings(text: str) -> list[str]:
    """Return every hard-coded prose literal the interaction layer would render.

    Inspected shapes: an assignment to ``textContent``, a ``setAttribute`` call
    naming a prose attribute, and an ``aria-label`` written into a markup
    string. A literal supplied as the English value of a ``chromeText`` lookup is
    the documented no-payload value and passes; a bare one does not.

    Args:
        text: The script source.

    Returns:
        One human-readable finding per hard-coded literal, in source order.
    """
    # The English value inside a chromeText lookup is the sanctioned literal.
    body = re.sub(r'chromeText\(\s*"[\w.]+"\s*,\s*"(?:[^"\\]|\\.)*"\s*\)', "CHROME", text)
    # A typeof comparison names a JavaScript type, never rendered text.
    body = re.sub(r'typeof\s+[^;]*?[=!]==\s*"[a-z]+"', "TYPEOF", body)
    # A class test or selector inside a rendered expression names markup, not text.
    body = re.sub(
        r"\.(?:classList\.\w+|getAttribute|hasAttribute|matches|closest|querySelector(?:All)?)"
        r'\(\s*"(?:[^"\\]|\\.)*"\s*\)',
        ".DOM()",
        body,
    )
    findings: list[str] = []
    expressions = [
        ("textContent", r"\.textContent\s*=([^;]*);"),
        ("setAttribute", r'setAttribute\(\s*"(?:' + "|".join(_PROSE_ATTRIBUTES) + r')"\s*,([\s\S]*?)\);'),
    ]
    for shape, pattern in expressions:
        for match in re.finditer(pattern, body):
            for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1)):
                if _is_prose(literal):
                    findings.append(f"{shape} {literal!r}")
    for match in re.finditer(r'aria-label="([^"\']*)"', body):
        if _is_prose(match.group(1)):
            findings.append(f"markup aria-label {match.group(1)!r}")
    return findings


def test_shipped_templates_hard_code_no_prose() -> None:
    """No shipped template renders a prose literal instead of resolved chrome."""
    findings: dict[str, list[str]] = {}
    for template in sorted(_TEMPLATES.rglob("*.html")):
        hits = template_prose_findings(template.read_text(encoding="utf-8"))
        if hits:
            findings[template.relative_to(_DOCS).as_posix()] = hits
    assert not findings, f"templates carry hard-coded prose: {findings}"


def test_interaction_layer_hard_codes_no_prose() -> None:
    """The interaction layer writes no prose literal the catalogue does not own."""
    findings = script_prose_findings(_WIDGET_JS.read_text(encoding="utf-8"))
    assert not findings, f"cadrumo-docs.js carries hard-coded prose: {findings}"


def test_detector_reports_a_planted_template_literal(tmp_path: Path) -> None:
    """The template detector fires on a planted literal in an isolated file.

    Args:
        tmp_path: Pytest-provided isolated directory holding the planted file.
    """
    planted = tmp_path / "planted.html"
    planted.write_text(
        '<div aria-label="Recent activity"><p>Unsaved changes</p></div>\n'
        '<span aria-label="{{ cadrumo_chrome.aria_breadcrumb }}">{{ title }}</span>\n',
        encoding="utf-8",
    )
    findings = template_prose_findings(planted.read_text(encoding="utf-8"))
    assert findings == ["aria-label='Recent activity'", "text node 'Unsaved changes'"]


def test_detector_reports_a_planted_script_literal(tmp_path: Path) -> None:
    """The script detector fires on a planted literal in an isolated file.

    Args:
        tmp_path: Pytest-provided isolated directory holding the planted file.
    """
    planted = tmp_path / "planted.js"
    planted.write_text(
        'node.textContent = "Nothing to show";\n'
        'node.setAttribute("aria-label", "Close panel");\n'
        'node.textContent = chromeText("sequence_copied", "Copied");\n'
        'node.setAttribute("aria-label", chromeText("cli_help_close", "Close help"));\n'
        "shell.innerHTML = '<button aria-label=\"Run again\"></button>';\n",
        encoding="utf-8",
    )
    findings = script_prose_findings(planted.read_text(encoding="utf-8"))
    assert findings == [
        "textContent 'Nothing to show'",
        "setAttribute 'Close panel'",
        "markup aria-label 'Run again'",
    ]
