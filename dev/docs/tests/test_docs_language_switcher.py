"""Language-switcher rendering and configuration contracts.

The header language switcher (``docs/_templates/cadrumo-language-switcher.html``)
links every page to its counterpart under each per-language deploy root. These
gates prove, with a real Furo build (no mocks), that the switcher computes the
correct relative hrefs from both a localized subdir build and the default English
root build, and that ``docs/conf.py`` populates the switcher context from the
single ``OutputLanguage`` authority.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"
_TEMPLATES = _DOCS / "_templates"

_LANGUAGE_LABELS = {"en": "English", "es": "Español", "ca": "Català", "hu": "Magyar"}


def _switcher_context(language: str) -> dict[str, object]:
    """Return the switcher html_context for one build language."""
    order = ["en", *[member.value for member in OutputLanguage if member is not OutputLanguage.EN]]
    return {
        "cadrumo_docs_language": language,
        "cadrumo_docs_default_language": "en",
        "cadrumo_docs_language_is_default": language == "en",
        "cadrumo_docs_languages": [{"code": code, "label": _LANGUAGE_LABELS[code]} for code in order],
    }


def _build_switcher_site(tmp_path: Path, language: str) -> str:
    """Build a two-page Furo site with the real switcher template; return the nested page HTML."""
    site = tmp_path / "site"
    (site / "how-to").mkdir(parents=True)
    context = _switcher_context(language)
    conf = (
        'extensions = ["myst_parser"]\n'
        'html_theme = "furo"\n'
        f"templates_path = [r'{_TEMPLATES}']\n"
        # The custom cadrumo header (which hosts the switcher) lives in Furo's
        # announcement block, which Furo only emits when an announcement is set -
        # exactly as the production docs config sets it.
        'html_theme_options = {"announcement": "x"}\n'
        f'language = "{language}"\n'
        f"html_context = {context!r}\n"
    )
    (site / "conf.py").write_text(conf, encoding="utf-8")
    (site / "index.md").write_text("# Home\n\n```{toctree}\nhow-to/quickstart\n```\n", encoding="utf-8")
    (site / "how-to" / "quickstart.md").write_text("# Quickstart\n\nBody text.\n", encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "html", "-j", "1", str(site), str(out)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return (out / "how-to" / "quickstart.html").read_text(encoding="utf-8")


def _switcher_hrefs(html: str) -> dict[str, str]:
    """Extract the switcher's per-language hrefs keyed by BCP-47 code from the nav block."""
    nav = re.search(r'<nav class="cadrumo-header-lang".*?</nav>', html, re.DOTALL)
    assert nav is not None, "language switcher nav is absent from the rendered header"
    hrefs: dict[str, str] = {}
    for match in re.finditer(r'<a class="cadrumo-header-nav-link" href="([^"]+)"[^>]*lang="([a-z]+)"', nav.group(0)):
        hrefs[match.group(2)] = match.group(1)
    return hrefs


def test_localized_build_links_up_to_sibling_language_roots(tmp_path: Path) -> None:
    """From a localized (es) subdir build, a nested page links up to en and across to ca/hu.

    The es root is served at ``<base>/es/``; from ``<base>/es/how-to/quickstart.html``
    the English counterpart is two levels up (``../../how-to/quickstart.html``) and each
    sibling language is under its own segment at that shared base.
    """
    html = _build_switcher_site(tmp_path, "es")
    hrefs = _switcher_hrefs(html)
    assert hrefs == {
        "en": "../../how-to/quickstart.html",
        "ca": "../../ca/how-to/quickstart.html",
        "hu": "../../hu/how-to/quickstart.html",
    }
    # The current language renders as a non-link current marker, not an anchor.
    assert 'aria-current="true" lang="es"' in html


def test_default_build_links_down_into_language_roots(tmp_path: Path) -> None:
    """From the default English root build, a nested page links down into each language subdir.

    The English site is served at the base; from ``<base>/how-to/quickstart.html`` each
    localized counterpart is one level up then into its language segment.
    """
    html = _build_switcher_site(tmp_path, "en")
    hrefs = _switcher_hrefs(html)
    assert hrefs == {
        "es": "../es/how-to/quickstart.html",
        "ca": "../ca/how-to/quickstart.html",
        "hu": "../hu/how-to/quickstart.html",
    }
    assert 'aria-current="true" lang="en"' in html


def _conf_switcher_context(language: str) -> dict[str, object]:
    """Evaluate docs/conf.py under one build language and return its switcher context."""
    conf = _DOCS / "conf.py"
    script = (
        "import json, runpy;"
        f"ns = runpy.run_path(r'{conf}');"
        "ctx = ns['html_context'];"
        "print('SWITCHER=' + json.dumps({"
        "'language': ctx['cadrumo_docs_language'],"
        "'default': ctx['cadrumo_docs_default_language'],"
        "'is_default': ctx['cadrumo_docs_language_is_default'],"
        "'languages': ctx['cadrumo_docs_languages']}))"
    )
    env = {
        **os.environ,
        "CADRUMO_DOCS_PROJECT_ROOT": str(_REPO_ROOT),
        "CADRUMO_DOCS_LANGUAGE": language,
        "CADRUMO_LOCAL_STORAGE_ROOT": tempfile.mkdtemp(prefix="cadrumo-switcher-ctx-"),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(row for row in result.stdout.splitlines() if row.startswith("SWITCHER="))
    return json.loads(line[len("SWITCHER=") :])


def test_conf_populates_switcher_context_from_output_language() -> None:
    """conf.py builds the switcher context from OutputLanguage: English first, then targets, with endonyms."""
    context = _conf_switcher_context("ca")
    assert context["language"] == "ca"
    assert context["default"] == "en"
    assert context["is_default"] is False
    codes = [entry["code"] for entry in context["languages"]]
    assert codes[0] == "en"
    assert set(codes) == {member.value for member in OutputLanguage}
    labels = {entry["code"]: entry["label"] for entry in context["languages"]}
    assert labels == _LANGUAGE_LABELS
