"""Sphinx configuration for the Cadrumo documentation set."""

from __future__ import annotations

import ast
import os
import tomllib
import warnings

# Pin the CLI output language to English BEFORE any project module is imported.
# CLI help strings are tr() values resolved at import time; the sphinx-click
# build-time CLI reference renders them, so the language must be fixed for the
# whole build process here, at the top of conf.py.
os.environ["CADRUMO_OUTPUT_LANGUAGE"] = "en"

import sys
from pathlib import Path
from typing import Annotated, get_origin, override

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.deprecation import RemovedInSphinx90Warning

# Make `cadrumo` importable for autodoc without installing the wheel.
_PROJECT_ROOT = Path(os.environ.get("CADRUMO_DOCS_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from cadrumo.core.directory_scan import scan_directory  # noqa: E402
from cadrumo.core.external_constants import OutputLanguage  # noqa: E402
from cadrumo.core.product_identity import PRODUCT_IDENTITY  # noqa: E402

warnings.filterwarnings("ignore", category=RemovedInSphinx90Warning, module=r"hoverxref\.extension")


def _project_metadata() -> dict[str, object]:
    """Load project metadata from ``pyproject.toml`` for Sphinx display fields."""
    pyproject = _PROJECT_ROOT / "pyproject.toml"
    with pyproject.open("rb") as stream:
        project_metadata = tomllib.load(stream).get("project")
    if not isinstance(project_metadata, dict) or not all(isinstance(key, str) for key in project_metadata):
        raise ValueError("pyproject.toml must declare a string-keyed [project] table")
    return {key: value for key, value in project_metadata.items()}


_PYPROJECT = _project_metadata()
_PROJECT_URLS = _PYPROJECT.get("urls", {})
if not isinstance(_PROJECT_URLS, dict):
    raise ValueError("pyproject.toml [project.urls] must be a table")
_DOCS_BASE_URL = os.environ.get("CADRUMO_DOCS_BASE_URL", "").rstrip("/")
# Cadrumo documentation type ramp: Newsreader for display headings,
# Hanken Grotesk for text, JetBrains Mono for code. The display face matches
# the product site so headings read as one brand across both surfaces.
_DOCS_FONT_STACK = (
    '"Hanken Grotesk", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif'
)
_DOCS_HEADING_FONT_STACK = '"Newsreader", ui-serif, Georgia, "Times New Roman", serif'
_DOCS_MONO_FONT_STACK = '"JetBrains Mono", ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace'
_REPOSITORY_URL = str(_PROJECT_URLS.get("Repository", ""))
_ISSUES_URL = str(_PROJECT_URLS.get("Issues", ""))
_RELEASES_URL = f"{_REPOSITORY_URL}/releases" if _REPOSITORY_URL else ""
_LATEST_RELEASE_URL = f"{_RELEASES_URL}/latest" if _RELEASES_URL else ""

# ── Project metadata ────────────────────────────────────────────────────────
project = PRODUCT_IDENTITY.display_name
_PROJECT_AUTHORS = _PYPROJECT.get("authors", [])
if not isinstance(_PROJECT_AUTHORS, list) or not all(
    isinstance(item, dict) and isinstance(item.get("name"), str) for item in _PROJECT_AUTHORS
):
    raise ValueError("pyproject.toml project authors must be named tables")
author = ", ".join(item["name"] for item in _PROJECT_AUTHORS)
# Human-facing footer credit; the packaging author handle stays in pyproject.
copyright = f"2026, the {PRODUCT_IDENTITY.prose_name} authors"
release = str(_PYPROJECT["version"])
version = release

# ── Build scope ──────────────────────────────────────────────────────────────
# ``CADRUMO_DOCS_SCOPE`` selects how much of the set this invocation builds:
#   * ``full`` (default, CI + deploy): the whole handbook including the API
#     autodoc tree (``docs/api/**`` — ~1,150 ``automodule`` stubs that import the
#     entire application) and the viewcode ``_modules`` source tree.
#   * ``user``: ONLY the operator-facing surface (index / how-to / explanation /
#     reference / architecture / cli / glossary / the executed cli-sequences).
#     The API autodoc tree and the ``_modules`` tree are excluded and the
#     autodoc / viewcode / typehints extensions are never loaded, so the
#     application is never imported for *rendering* — cutting the ~60 user pages
#     free of the ~1,150 app-importing API pages so user-docs iteration builds in
#     minutes instead of an hour.
_DOCS_SCOPE = os.environ.get("CADRUMO_DOCS_SCOPE", "full")
if _DOCS_SCOPE not in {"full", "user"}:
    raise ValueError(f"CADRUMO_DOCS_SCOPE must be 'full' or 'user'; got {_DOCS_SCOPE!r}")
_USER_SCOPE = _DOCS_SCOPE == "user"

# ── Extensions ──────────────────────────────────────────────────────────────
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxext.opengraph",
    "notfound.extension",
    "sphinxcontrib.mermaid",
    "hoverxref.extension",
    "myst_parser",
]
if _USER_SCOPE:
    # Drop ONLY the app-importing autodoc machinery; every narrative/rendering
    # extension (myst, design, mermaid, copybutton, hoverxref, opengraph,
    # notfound, intersphinx, napoleon) stays so the user surface renders
    # identically. napoleon is left loaded but inert (its docstring transform
    # never fires without autodoc).
    _AUTODOC_ONLY_EXTENSIONS = {"sphinx.ext.autodoc", "sphinx.ext.viewcode", "sphinx_autodoc_typehints"}
    extensions = [name for name in extensions if name not in _AUTODOC_ONLY_EXTENSIONS]

# Hover tooltip cards on :term: cross-references to the generated glossary.
# One term per glossary entry (the shared-entry rendering bug); aliases ride as
# additional term lines on the same entry, so every declared surface resolves.
hoverxref_roles = ["term"]
hoverxref_role_types = {"term": "tooltip"}

# Source file types — both reStructuredText (autodoc stubs, index) and MyST
# Markdown (narrative pages, generated API surface) are first-class.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = os.environ.get("CADRUMO_DOCS_MASTER_DOC", "index")
# The build language is read from CADRUMO_DOCS_LANGUAGE and validated against the
# OutputLanguage closed set (es/en/ca/hu) - the single language authority shared
# with the runtime CLI catalogues, never a second hand-listed set. English is the
# msgid source (the default) and carries no catalogue; es/ca/hu substitute
# translated paragraphs from docs/locales/<lang>/LC_MESSAGES. The CLI OUTPUT
# language stays pinned to English at the top of this module (executed sequences
# render live CLI output as evidence, not translatable prose). gettext_compact is
# disabled so each source page owns one catalogue, which the all-languages
# completeness gate reads per page. Documentation translation must not reuse the
# runtime CLI translation catalogues.
_VALID_DOCS_LANGUAGES = {member.value for member in OutputLanguage}
language = os.environ.get("CADRUMO_DOCS_LANGUAGE", "en")
if language not in _VALID_DOCS_LANGUAGES:
    raise ValueError(
        f"CADRUMO_DOCS_LANGUAGE must be one of {sorted(_VALID_DOCS_LANGUAGES)}; got {language!r}",
    )
locale_dirs = ["locales"]
gettext_compact = False

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "**/test_*.py",
    "**/_test_*.py",
    "USERDOCS-KICKOFF-BRIEF.md",
]
if _USER_SCOPE:
    # User scope excludes the generated API autodoc tree and the viewcode
    # ``_modules`` source pages from the read set entirely, so no app module is
    # imported to render them.
    exclude_patterns += ["api/**", "_modules/**"]

_DOCS_ROOT = Path(__file__).resolve().parent
_ONLY_SOURCES = {
    Path(item).as_posix() for item in os.environ.get("CADRUMO_DOCS_ONLY", "").split(os.pathsep) if item.strip()
}
if _ONLY_SOURCES:
    for _source in _DOCS_ROOT.rglob("*"):
        if _source.suffix not in {".md", ".rst"}:
            continue
        _relative = _source.relative_to(_DOCS_ROOT).as_posix()
        if _relative not in _ONLY_SOURCES:
            exclude_patterns.append(_relative)

# The docs-check gate builds nitpicky (-n) with warnings-as-errors (-W), so
# unresolved cross-references must be fixed or added to nitpick_ignore_regex
# below. Two categories are suppressed at the source because they are not
# fixable broken references:
#   * ``ref.python`` — the "more than one target found for cross-reference"
#     ambiguity raised when a builtin type name (``bytes``, ``date``) collides
#     with project fields of the same name. The genuine "target not found"
#     nitpicks use distinct subtypes (``ref.class``/``ref.data``/...), so this
#     does not mask any real missing reference.
#   * the sphinx_autodoc_typehints extension's pydantic forward-reference and
#     guarded-import notices (Field's JsonValue, the optional email_validator).
suppress_warnings = [
    "ref.python",
    "sphinx_autodoc_typehints.forward_reference",
    "sphinx_autodoc_typehints.guarded_import",
]
if os.environ.get("CADRUMO_DOCS_SINGLE_PAGE"):
    suppress_warnings.append("toc.excluded")
    suppress_warnings.append("toc.not_included")
if _USER_SCOPE:
    # The root toctree carries one ``API <api/index>`` entry (docs/index.md);
    # under user scope that target is excluded, so the toctree reference to it is
    # a benign ``toc.excluded`` — the entry simply drops from the nav. This is the
    # only excluded toctree target in the user set, so the suppression is scoped
    # to exactly the pruned API entry, and the ``-n -W`` gate stays on for every
    # other reference class.
    suppress_warnings.append("toc.excluded")

# ── Autodoc / Napoleon ──────────────────────────────────────────────────────
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
# Emit Attributes: sections as ``:ivar:`` (instance variable entries) rather
# than ``:py:attribute:`` entries.  This prevents autodoc member enumeration
# from colliding with Napoleon's Attributes-section output for pydantic and
# StrEnum classes, which would otherwise produce duplicate-object-description
# warnings when the two mechanisms register the same qualified name twice.
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

autodoc_default_options = {
    "members": True,
    # Keep undocumented members out of the rendered surface. Enabling them
    # roughly triples the documented object count (every constant, alias, and
    # helper), which makes the nitpicky gate build minutes-to-tens-of-minutes
    # slower without improving the public API reference. Undocumented module
    # constants and type aliases that are referenced by other docstrings are
    # instead covered by nitpick_ignore_regex below.
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
    # Hide concretised module-level values (e.g. PROJECT_ROOT resolves to
    # the build host's absolute path, which is environment-specific noise).
    # The accompanying docstring carries the relevant meaning.
    "no-value": True,
    # Suppress dunder/private noise so pydantic-settings BaseSettings
    # subclasses do not leak their full underscore-prefixed constructor
    # signature into the rendered Settings page.
    "exclude-members": (
        "__init__,__pydantic_serializer__,__pydantic_validator__,"
        "model_config,model_fields,model_computed_fields,"
        "Config,model_post_init,settings_customise_sources,model_validate,"
        "model_validate_json,model_validate_strings,model_dump,model_dump_json,"
        "model_copy,model_construct,model_extra,model_fields_set,"
        "model_json_schema,model_parametrized_name,model_rebuild,"
        "_abc_impl,_check_frozen,_iter,_calculate_keys,_get_value,"
        "_copy_and_set_values"
    ),
}

# Use the class docstring only (avoid duplicating __init__ docstring after the
# class summary, which causes the visible "duplicate enum member emission").
autoclass_content = "class"

autodoc_typehints = "description"
autodoc_typehints_format = "short"

_PUBLIC_TYPE_ALIAS_TARGETS = {
    "CasillaId": "cadrumo.core.CasillaId",
    "SubjectTaxId": "cadrumo.core.identity.SubjectTaxId",
    "TaxIdIdentityToken": "cadrumo.core.identity.TaxIdIdentityToken",
}

# Be tolerant of the wider AEAT dep tree at autodoc-import time. These are
# either heavy native deps that pull a lot of platform-specific shared
# libraries, or optional vault tooling that isn't installed in every env.
# Listing them here lets autodoc render module pages even when the underlying
# import would raise.
autodoc_mock_imports = [
    "tree_sitter",
    "tree_sitter_language_pack",
    "qdrant_client",
    "playwright",
    "playwright_stealth",
    "pikepdf",
    "pdfplumber",
    "pikepdf._core",
    "ofxtools",
    "openpyxl",
    "reportlab",
    "argon2",
    "argon2.low_level",
    "keyring",
    "anthropic",
]

add_module_names = False
# Keep cross-reference resolution exact (the default). Enabling unqualified type
# names makes every annotation xref "refspecific" (a fuzzy suffix search), which
# resolves a builtin like ``bytes`` against project fields that happen to be
# named ``bytes`` and raises spurious "more than one target" ambiguities; the
# autodoc_typehints_format="short" setting already shortens the displayed type.
python_use_unqualified_type_names = False

# ── Intersphinx ─────────────────────────────────────────────────────────────
# Inventories vendored under docs/_inventories/ are read from disk, so the
# nitpicky gate resolves stdlib/builtin and SQLAlchemy targets exactly (an exact
# ``bytes`` builtin target short-circuits the fuzzy resolver that would otherwise
# flag every project field named ``bytes`` as an ambiguous cross-reference)
# without any network fetch. Inventories with no vendored copy (pydantic, httpx,
# typer) resolve online when available and are covered by nitpick_ignore_regex
# when the gate runs offline.
_INVENTORIES = Path(__file__).resolve().parent / "_inventories"
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", str(_INVENTORIES / "python.inv")),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", str(_INVENTORIES / "sqlalchemy.inv")),
    # textual is vendored rather than left to nitpick_ignore because the TUI
    # screens subclass it, so autodoc documents the inherited members and every
    # base class is a real cross-reference a reader will follow. Suppressing
    # them would silence the warning while leaving the link dead.
    "textual": ("https://textual.textualize.io/", str(_INVENTORIES / "textual.inv")),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
    "typer": ("https://typer.tiangolo.com/", None),
}
_SELF_INVENTORY = Path(__file__).resolve().parent / "_build" / "html" / "objects.inv"
if os.environ.get("CADRUMO_DOCS_SELF_INVENTORY") and _SELF_INVENTORY.is_file():
    intersphinx_mapping["cadrumo-local"] = ((_SELF_INVENTORY.parent).as_uri() + "/", str(_SELF_INVENTORY))
intersphinx_disabled_reftypes = ["std:doc"]

# Offline-hermetic gate: the docs-check build sets CADRUMO_DOCS_OFFLINE to keep only
# the vendored local inventories (read from disk) and drop the network-only
# mappings, so the build resolves stdlib/SQLAlchemy targets deterministically
# without any network access. The dropped third-party namespaces are covered by
# nitpick_ignore_regex below.
if os.environ.get("CADRUMO_DOCS_OFFLINE"):
    intersphinx_mapping = {
        name: (uri, inv) for name, (uri, inv) in intersphinx_mapping.items() if inv and Path(inv).is_file()
    }

# ── HTML theme ──────────────────────────────────────────────────────────────
html_theme = "furo"
html_title = f"{PRODUCT_IDENTITY.prose_name} documentation - local Spanish tax preparation"
html_short_title = f"{PRODUCT_IDENTITY.prose_name} documentation"
html_baseurl = f"{_DOCS_BASE_URL}/" if _DOCS_BASE_URL else ""
html_meta = {
    "description": (
        "Cadrumo helps you prepare, check, and export Spanish tax files locally. "
        "Cadrumo never files or submits them for you."
    ),
}
html_favicon = "_static/cadrumo-favicon.svg"
html_static_path = ["_static"]
templates_path = ["_templates"]
html_css_files = [
    "cadrumo-docs.css",
    # The generated reference surfaces carry their own stylesheets so the
    # taxpayer-facing presentation of a casilla, a provision and a glossary
    # term can evolve without editing the site-wide sheet.
    "cadrumo-casilla-reference.css",
    "cadrumo-legal-reference.css",
]
html_js_files = ["cadrumo-docs.js"]
# The left sidebar carries the command-palette trigger and the navigation tree;
# brand and the stock search box move into the sticky site header / palette.
html_sidebars = {
    "**": [
        "sidebar/cadrumo-search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/scroll-end.html",
    ],
}
html_theme_options = {
    "light_logo": "cadrumo-mark-light.svg",
    "dark_logo": "cadrumo-mark-dark.svg",
    "sidebar_hide_name": True,
    "announcement": "cadrumo-site-broadcast",
    "light_css_variables": {
        # Cadrumo documentation theme tokens: warm paper neutrals — page
        # #faf8f4, surface #f1eee7, border #e4ded4, ink #1c1a17 — with the
        # rust accent mapped onto Furo's semantic variables.
        #
        # THE ACCENT HAS TWO ROLES AND THIS PALETTE NOW HONOURS BOTH.
        # #c4553b is the canonical brand accent and it measures 4.20:1
        # against the page ground, 3.85:1 against the secondary surface and
        # 4.46:1 against a card. Every one of those is under the 4.5 that
        # body-size text needs, and these variables colour LINKS — the most
        # common piece of coloured text in a documentation site. So every
        # link on every page failed WCAG 1.4.3, on all three grounds.
        #
        # The product site hit this exact wall and resolved it by splitting
        # the accent rather than moving it: the brand value stays canonical
        # for fills, rules and display italics, and a darker sibling carries
        # the accent wherever it is INK AT READING SIZE. #9e4029 is that
        # sibling, and it measures 6.15 / 5.63 / 6.52 on the three grounds.
        # These variables are the ink role, so they take the ink value; the
        # brand value survives as --cadrumo-accent in cadrumo-docs.css for
        # the decorative uses.
        "color-brand-primary": "#1c1a17",
        "color-brand-content": "#9e4029",
        "color-brand-visited": "#9e4029",
        "color-foreground-primary": "#1c1a17",
        "color-foreground-secondary": "#5f594f",
        "color-foreground-muted": "#6b655c",
        "color-foreground-border": "#d5cec1",
        "color-background-primary": "#faf8f4",
        "color-background-secondary": "#f1eee7",
        "color-background-hover": "#ece8df",
        "color-background-hover--transparent": "#ece8df00",
        "color-background-border": "#e4ded4",
        "color-card-border": "#e4ded4",
        "color-card-background": "#ffffff",
        "color-card-marginals-background": "#f1eee7",
        "color-link": "#9e4029",
        "color-link--hover": "#7f3320",
        "color-link--visited": "#9e4029",
        "color-link--visited--hover": "#7f3320",
        "color-link-underline": "transparent",
        "color-link-underline--hover": "#c4553b",
        "color-link-underline--visited": "transparent",
        "color-link-underline--visited--hover": "#c4553b",
        "color-inline-code-background": "#f1eee7",
        "color-admonition-background": "#f1eee7",
        "color-admonition-title": "#1c1a17",
        "color-admonition-title-background": "transparent",
        "color-admonition-title-background--important": "transparent",
        "color-admonition-title--important": "#1c1a17",
        "color-admonition-title-background--warning": "transparent",
        "color-admonition-title--warning": "#1c1a17",
        "color-sidebar-background": "transparent",
        "color-sidebar-background-border": "transparent",
        "color-sidebar-link-text": "#5f594f",
        "color-sidebar-link-text--top-level": "#4d483f",
        "color-sidebar-item-background--current": "#ece8df",
        "color-sidebar-item-background--hover": "#ece8df",
        "color-toc-background": "transparent",
        "color-toc-item-text": "#5f594f",
        "color-toc-item-text--hover": "#1c1a17",
        "color-toc-item-text--active": "#9e4029",
        "color-toc-title-text": "#6b655c",
        "font-stack": _DOCS_FONT_STACK,
        "font-stack--headings": _DOCS_HEADING_FONT_STACK,
        "font-stack--monospace": _DOCS_MONO_FONT_STACK,
    },
    "dark_css_variables": {
        # Dark companion to the brand palette: the same warm hue family
        # inverted onto the ink #1c1a17, with the rust accent lifted for
        # contrast on dark surfaces.
        "color-brand-primary": "#f1eee7",
        "color-brand-content": "#e0785c",
        "color-brand-visited": "#e0785c",
        "color-foreground-primary": "#f1eee7",
        "color-foreground-secondary": "#b3ab9d",
        "color-foreground-muted": "#8f887b",
        "color-foreground-border": "#4a453c",
        "color-background-primary": "#1c1a17",
        "color-background-secondary": "#24211c",
        "color-background-hover": "#2c2822",
        "color-background-hover--transparent": "#2c282200",
        "color-background-border": "#38342c",
        "color-card-border": "#38342c",
        "color-card-background": "#24211c",
        "color-card-marginals-background": "#24211c",
        "color-link": "#e0785c",
        "color-link--hover": "#ec8a68",
        "color-link--visited": "#e0785c",
        "color-link--visited--hover": "#ec8a68",
        "color-link-underline": "transparent",
        "color-link-underline--hover": "#dd7a5f",
        "color-link-underline--visited": "transparent",
        "color-link-underline--visited--hover": "#dd7a5f",
        "color-inline-code-background": "#26231d",
        "color-admonition-background": "#24211c",
        "color-admonition-title": "#f1eee7",
        "color-admonition-title-background": "transparent",
        "color-admonition-title-background--important": "transparent",
        "color-admonition-title--important": "#f1eee7",
        "color-admonition-title-background--warning": "transparent",
        "color-admonition-title--warning": "#f1eee7",
        "color-sidebar-background": "transparent",
        "color-sidebar-background-border": "transparent",
        "color-sidebar-link-text": "#b3ab9d",
        "color-sidebar-link-text--top-level": "#d5cec1",
        "color-sidebar-item-background--current": "#2c2822",
        "color-sidebar-item-background--hover": "#2c2822",
        "color-toc-background": "transparent",
        "color-toc-item-text": "#b3ab9d",
        "color-toc-item-text--hover": "#f1eee7",
        "color-toc-item-text--active": "#dd7a5f",
        "color-toc-title-text": "#8f887b",
    },
    "source_repository": _REPOSITORY_URL,
    "source_branch": "main",
    "source_directory": "docs/",
    "top_of_page_buttons": ["view", "edit"],
}

html_context = {
    "cadrumo_repository_url": _REPOSITORY_URL,
    "cadrumo_nav": [
        {"label": "Getting started", "doc": "how-to/index"},
        {"label": "CLI reference", "doc": "cli/index"},
        {"label": "How it works", "doc": "explanation/index"},
        {"label": "API", "doc": "api/index"},
    ],
    "cadrumo_broadcasts": [
        {
            "label": "Pre-alpha",
            "message": (
                "Breaking changes are expected. Verify Agencia Estatal de Administración "
                "Tributaria (AEAT) deadlines before filing."
            ),
            "links": [
                {"label": "Updates", "doc": "updates"},
                {"label": "Latest download", "url": _LATEST_RELEASE_URL},
                {"label": "Report an issue", "url": _ISSUES_URL},
            ],
        }
    ],
    "cadrumo_footer_groups": [
        {
            "title": "Stay current",
            "links": [
                {"label": "Critical updates", "doc": "updates", "fragment": "critical-updates"},
                {"label": "Latest download", "url": _LATEST_RELEASE_URL},
                {"label": "Release notes", "url": _RELEASES_URL},
            ],
        },
        {
            "title": "Get help",
            "links": [
                {"label": "Report an issue", "url": _ISSUES_URL},
                {"label": "CLI reference", "doc": "cli/index"},
                {"label": "How it works", "doc": "explanation/index"},
            ],
        },
        {
            "title": "Trust and responsibility",
            "links": [
                {"label": "Disclaimer", "doc": "disclaimer"},
                {"label": "Events and deadlines", "doc": "updates", "fragment": "events-and-deadlines"},
                {"label": "Repository", "url": _REPOSITORY_URL},
            ],
        },
    ],
    "cadrumo_footer_note": (
        "Cadrumo is pre-alpha, local-first software. It is not tax advice, is not affiliated with the "
        "Agencia Estatal de Administración Tributaria (AEAT), "
        "and never replaces official AEAT tools or advice from a qualified professional."
    ),
}
if _USER_SCOPE:
    # The header nav carries an "API" entry pointing at the excluded api/index
    # overview; drop it so the user-scope preview nav has no dead API link.
    html_context["cadrumo_nav"] = [entry for entry in html_context["cadrumo_nav"] if entry.get("doc") != "api/index"]

# ── Language switcher ────────────────────────────────────────────────────────
# The deploy publisher emits per-language site roots (``/`` = en, ``/es/``,
# ``/ca/``, ``/hu/``). The header language switcher (docs/_templates) links the
# current page to its counterpart under each language root. The set derives from
# OutputLanguage (English first as the authoring source, then the translation
# targets in enum order) - never a second hand-listed set - and each entry
# carries its endonym, the language's own name, which is the same in every build.
_DOCS_LANGUAGE_ENDONYMS = {
    OutputLanguage.EN: "English",
    OutputLanguage.ES: "Español",
    OutputLanguage.CA: "Català",
    OutputLanguage.HU: "Magyar",
}
_DOCS_LANGUAGE_ORDER = (OutputLanguage.EN, *(member for member in OutputLanguage if member is not OutputLanguage.EN))
html_context["cadrumo_docs_language"] = language
html_context["cadrumo_docs_default_language"] = OutputLanguage.EN.value
html_context["cadrumo_docs_language_is_default"] = language == OutputLanguage.EN.value
html_context["cadrumo_docs_languages"] = [
    {"code": member.value, "label": _DOCS_LANGUAGE_ENDONYMS[member]} for member in _DOCS_LANGUAGE_ORDER
]

# ── Publishing metadata ─────────────────────────────────────────────────────
ogp_site_name = f"{PRODUCT_IDENTITY.prose_name} documentation"
ogp_site_url = html_baseurl
ogp_description_length = 180
ogp_type = "website"
ogp_image = "_static/cadrumo-mark-light.svg"

# ── Syntax highlighting ─────────────────────────────────────────────────────
# Bare code fences are overwhelmingly operator command transcripts; lexing them
# as ``console`` colours the ``$``/``PS>`` prompts and keeps plain output calm.
# Explicit ```bash fences keep their bash lexer.
highlight_language = "console"
pygments_style = "friendly"
pygments_dark_style = "github-dark"

# ── Mermaid diagrams ────────────────────────────────────────────────────────
# ```mermaid fences render as client-side mermaid.js diagrams. The extension
# observes the Furo light/dark state and re-renders on toggle; the grayscale
# "neutral" theme matches the documentation's neutral palette in light mode.
# The renderer is vendored locally so the site is offline-first and pins one
# auditable version. ``mermaid.min.mjs`` is the self-contained 11.12.1 UMD
# build (every diagram type inlined, no lazy chunk imports) with its trailing
# classic-script global assignment swapped for an ESM ``export default`` so the
# extension's ``import mermaid from`` resolves it. The file keeps a ``.js``
# extension (not ``.mjs``) so every static host — and the local dev server —
# serves it with a JavaScript MIME type; browsers enforce strict MIME on module
# scripts and reject the ``text/plain`` that ``.mjs`` gets by default. The
# extension also emits a d3 dependency in raw mode (only exercised by
# zoom/fullscreen, both off here); it is vendored too so no page reaches the
# CDN. Sphinx resolves the bare filenames per-page relative to ``_static``.
mermaid_version = "11.12.1"
mermaid_use_local = "mermaid.min.js"
d3_version = "7.9.0"
d3_use_local = "d3.min.js"
mermaid_light_theme = "neutral"
mermaid_dark_theme = "dark"
# The extension serialises this dict into a JS template literal via
# JSON.parse, so values must stay free of double quotes — CSS accepts the
# unquoted multi-word family names.
mermaid_init_config = {
    "startOnLoad": False,
    "fontFamily": "Hanken Grotesk, Segoe UI, system-ui, sans-serif",
}

# ── Copy buttons ────────────────────────────────────────────────────────────
copybutton_prompt_text = r">>> |\.\.\. |\$ |PS> "
copybutton_prompt_is_regexp = True
copybutton_only_copy_prompt_lines = False
copybutton_remove_prompts = True

# ── MyST ────────────────────────────────────────────────────────────────────
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]
myst_heading_anchors = 3
# Route ```mermaid fences to the mermaid directive instead of a literal block.
myst_fence_as_directive = ["mermaid"]

# ── Nitpicky cross-reference baseline ─────────────────────────────────────────
# docs-check builds with -n -W. The autodoc_mock_imports above replace heavy
# native deps with mocks whose types cannot resolve as cross-reference targets;
# those are ignored here so the gate flags only real, fixable broken refs. This
# baseline is curated alongside autodoc_mock_imports - adding a mock import
# without its ignore entry is incomplete.
nitpick_ignore_regex = [
    # Heavy native deps are replaced by autodoc mocks; their types have no
    # cross-reference target.
    (
        r"py:.*",
        r"^(tree_sitter|tree_sitter_language_pack|qdrant_client|playwright|"
        r"playwright_stealth|pikepdf|pdfplumber|ofxtools|openpyxl|reportlab|"
        r"argon2|keyring|anthropic)(\..*)?$",
    ),
    # pydantic constrained-type aliases render as a whole
    # ``typing.Annotated[str, StringConstraints(...)]`` expression target across
    # py:class and py:obj references; any target containing a non-identifier
    # character (brackets, parentheses, ``=``, regex fragments) is not a real
    # Python object reference.
    (r"py:.*", r".*[^A-Za-z0-9_.].*"),
    # pydantic / typing internals and constrained-type alias names that carry
    # no autodoc cross-reference target.
    (
        r"py:.*",
        r"^(FieldInfo|MinLen|MaxLen|NoneType|EllipsisType|Annotated|"
        r"Strict[A-Za-z]*|[A-Za-z]*Constraints|_PydanticGeneralMetadata)$",
    ),
    # Autodoc's ``show-inheritance`` renders a base class by its BARE name, so a
    # TUI class deriving from Textual emits ``Widget`` rather than
    # ``textual.widget.Widget``. The vendored inventory carries the qualified
    # target as ``py:class`` — verified by reading the entry — so the link is not
    # dead, merely unreachable from the short form autodoc emits. The short-name
    # bridge above resolves bare names only against IN-TREE objects by design,
    # and widening it to intersphinx would risk binding a bare project name to a
    # same-named third-party target.
    (r"py:class", r"^Widget$"),
    # ``Buffer`` is the real stdlib ``collections.abc.Buffer`` (PEP 688, 3.12+),
    # used as an annotation across the master-key recovery surface. autodoc
    # renders an annotation by its BARE name, so the reference emitted is
    # ``Buffer`` rather than ``collections.abc.Buffer``, and this gate builds
    # with ``CADRUMO_DOCS_OFFLINE`` set, so no stdlib inventory is loaded to
    # resolve either spelling. Same category as ``NoneType`` above: a genuine
    # type with no reachable target here, not a typo.
    #
    # This surfaced only once the sequence-golden hook stopped aborting the
    # nitpicky build at ``builder-inited``. Cross-reference resolution had never
    # run to completion before, so this was the first cross-reference finding the
    # gate had ever produced.
    (r"py:class", r"^Buffer$"),
    # Bare ``TypeVar`` parameters (``TPayload``, ``PayloadT``, ``T_co``) and the
    # single-letter PEP 695 type parameters used in ``class Foo[T, K: Hashable]``
    # generic syntax (``K``, ``V``) are not documentable objects; they appear in
    # generic signatures only. Listed explicitly so the pattern cannot mask a
    # real CamelCase class.
    (
        r"py:.*",
        r"^(T|K|V|Key|KT|VT|RT|_T|T_co|T_contra|TPayload|PayloadT|PayloadT_co|ResultT|RecordT|PayloadType|CasillaKey|CasillaValue|BindingKey|ExpectedKey|CheckerObservation|ObservationT|DocumentT|CalendarMoment)$",
    ),
    # SQLAlchemy column/type vocabulary referenced from the encrypted-column
    # adapters; resolved online via the vendored sqlalchemy inventory under its
    # fully-qualified name, but written short (or under SQLAlchemy's private
    # ``_types`` path) in the inherited docstrings.
    (
        r"py:.*",
        r"^(_types(\..*)?|TypeDecorator|UserDefinedType|ExternalType|Dialect|"
        r"TypeEngine)$",
    ),
    # Typed-id NewType aliases (CasillaId, SourceRefId, ...) are documented at
    # their definition, not as standalone class targets.
    (r"py:.*", r".*\._ids\.[A-Za-z]\w*$"),
    # PEP 695 ``type`` aliases are ``TypeAliasType`` instances, not classes, so a
    # bare cross-reference to one has no autodoc target. The typed-id family
    # (``type CasillaId = Annotated[...]``, ``RelationId``, ``ModeloId``, ... — 24
    # ``*Id`` aliases declared across the ``_ids.py`` modules) is matched by the
    # ``*Id`` suffix, with the two genuine ``*Id`` StrEnum classes (``ManualId``,
    # ``RegistryManualId``) excluded by negative lookahead so the suppression
    # cannot mask a real class.
    (r"py:.*", r"^(?!ManualId$)(?!RegistryManualId$)[A-Z][A-Za-z0-9]*Id$"),
    # The non-``Id`` PEP 695 ``type`` aliases (every ``type X = ...`` alias whose
    # name does not end in ``Id``), enumerated by exact name so the suppression
    # is confined to confirmed aliases and cannot match a real class.
    (
        r"py:.*",
        r"^(CasillaDelta|CasillaInputs|CounterpartSourceKind|FiledCaptureReport|"
        r"FiledDeclaracionArtefactSink|IvaCompensationAuthority|JsonObject|"
        r"IvaCompensationAuthorityKind|IvaCompensationDivergence|LlmReviewResult|"
        r"LocaleNode|ModeloAmendment|ModeloCalculationRevisionDefault|ModeloCode|"
        r"ModeloInputScalar|ModeloInputValue|ModeloInputs|ModeloWorkTarget|"
        r"PlaywrightStorageState|ProviderSessionMetadata|RegisteredSchema|"
        r"ReviewedSuggestion|SourceEvidenceFingerprint|UserProfileFactValue)$",
    ),
    # References into private (single-underscore) modules or to private classes
    # (``pkg._mod.Thing``, ``pkg.mod._Private``), which are implementation
    # internals excluded from the documented cross-reference surface.
    (r"py:.*", r".*\._[a-z]\w*\.[A-Za-z_]\w*$"),
    (r"py:.*", r".*\._[A-Z]\w*$"),
    # Private functions or methods referenced by a dotted path ending in the
    # private name (``pkg.mod._default_policy_for``, ``Engine._drive``), and
    # members reached through a private class (``mod._SensitivityClass.MEMBER``).
    (r"py:.*", r".*\._[a-z]\w*$"),
    (r"py:.*", r".*\._[A-Z]\w*\.[A-Za-z_]\w*$"),
    # ``TypeAliasType`` re-imported from typing_extensions into a project module
    # and referenced through that module's path; it is an external alias type.
    (r"py:.*", r".*\.TypeAliasType$"),
    # Bare references to private (single-underscore) helpers — ``_now``,
    # ``_coerce_utc_aware``, ``_BorradorParseError`` — written without a module
    # path. Private members are not part of the documented surface, so a literal
    # would be more correct, but the reference itself carries no public target.
    (r"py:.*", r"^_[A-Za-z]\w*$"),
    # Module-level ``ALL_CAPS`` constants (registry tables, key tuples) are data,
    # not part of the class/function cross-reference surface; references to them
    # by name (``PORTAL_REGISTRY``, ``IVA_RATE_TABLE``) have no autodoc target.
    (r"py:.*", r"(^|.*\.)[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$"),
    # Third-party namespaces with no vendored inventory (python.inv and
    # sqlalchemy.inv are vendored under docs/_inventories/ and resolve stdlib,
    # builtin, and SQLAlchemy targets exactly). pydantic / httpx / typer / click
    # and the other rendering-tooling namespaces below resolve online when
    # available; offline they have no inventory, so their fully-qualified targets
    # are ignored here to keep the gate hermetic.
    (
        r"py:.*",
        r"^(pydantic|pydantic_core|pydantic_settings|httpx|typer|click|"
        r"rich|yaml|tomllib|tomli|cryptography|jinja2|markupsafe|numpy|"
        r"prompt_toolkit|google|typing_extensions|asyncio|anyio|contextvars|"
        r"_pytest|playwright|_schema|_orm|annotated_types)(\..*)?$",
    ),
    # Test modules are excluded from the documented API surface (see
    # ApiStubManager exclusions), so references into them have no stub target.
    (r"py:.*", r".*\btest_[A-Za-z0-9_]*$"),
    (r"py:.*", r"^cadrumo\.tests(\..*)?$"),
    # Dunder, numeric-literal, and hex-like HTML-id targets that leak out of
    # docstrings as bogus cross-references (``:class:`1``` or AEAT source
    # anchors such as ``89ab``), never real documentable objects.
    (r"py:.*", r"^([0-9][0-9a-fA-F]*|__all__|__repr__|__str__|__init__|__init_subclass__)$"),
    # Playwright SDK classes referenced bare (``:class:`Page```, ``BrowserContext``,
    # ``Locator``, ``Response``, ``Playwright``) from the browser/sede adapters.
    # Playwright is in ``autodoc_mock_imports`` (offline, no inventory), so the
    # dotted ignore above does not cover these short forms; the names are
    # playwright-owned in this codebase (no project class shares them).
    (r"py:.*", r"^(Playwright|Page|BrowserContext|Locator|Response)$"),
    # Project anchors referenced by bare short name (per the docstring-anchor
    # convention; qualifying a bare anchor is barred by
    # aeat-documentation) whose short name the auto short-reference
    # resolver cannot uniquely map: ``CCAA`` (documented under more than one
    # public package).
    (r"py:.*", r"^CCAA$"),
    # Bare project-package ``:mod:`` short references (``:mod:`domain.iva```,
    # ``:mod:`application.ledger```, bare ``:mod:`application```, ...) used
    # project-wide in module docstrings per the docstring-anchor convention. The
    # short-reference resolver maps py:class / func / obj short names but not the
    # py:mod reftype, and a single-segment module name (``application``) or a
    # docs-excluded module (``entrypoints.cli``) cannot be uniquely mapped
    # anyway; until a py:mod-aware resolver lands these bare project-module short
    # forms are ignored rather than reded. Scoped to the first-segment project
    # package names so an external / stdlib ``:mod:`` reference is unaffected.
    # Any ``:mod:`` short reference that is NOT already ``cadrumo.``-qualified: the
    # short-reference resolver maps py:class/func/obj short names but not the
    # py:mod reftype, so a bare project-module reference (``:mod:`domain.iva```,
    # ``:mod:`registry```, ...) has no target. External / stdlib ``:mod:`` refs
    # are covered by the third-party namespace patterns above; a genuine
    # ``cadrumo.``-qualified module reference still resolves and is unaffected here.
    (r"py:mod", r"^(?!cadrumo\.)[a-z].*"),
    # External library types written bare (no vendored inventory offline, so the
    # dotted third-party namespace patterns above do not cover the short forms):
    # the ``cryptography`` elliptic-curve / Edwards key classes
    # (``Ed25519PrivateKey``, ``X25519PublicKey``, ...) referenced from the
    # secure-storage key adapters, the ``_typeshed`` ``SupportsAllComparisons``
    # protocol used in sort-key signatures, and the pydantic ``BaseModel``
    # serialisation methods (``model_dump_json`` / ``model_validate_json``)
    # referenced bare in roundtrip docstrings. All are external-owned; no project
    # symbol shares these names.
    (
        r"py:.*",
        r"^(Ed25519PrivateKey|Ed25519PublicKey|X25519PrivateKey|X25519PublicKey|"
        r"SupportsAllComparisons|model_dump_json|model_validate_json)$",
    ),
    # Project short references the bare/unrooted resolver cannot uniquely map.
    # Two shapes: (1) an AMBIGUOUS bare helper name with two or more documented
    # definitions across modules (``write_manifest`` x4; ``project_answers`` /
    # ``sha256_file`` / ``save_envelope`` / ``extract_pages_text`` /
    # ``extract_pages_text_from_bytes`` / ``LLMProvider`` x2), which the
    # last-segment suffix resolver cannot disambiguate by design; and (2) a
    # project object written by a path that omits the ``cadrumo.`` root
    # (``core.telemetry.workspace_hash``,
    # ``application.modelo.emit_collab_workspace_opened_event``,
    # ``adapters.persistence.storage.SensitivityClass.SECRET``). ``core-struct-
    # docstring-links`` bars adding a dotted path to a bare project anchor, so
    # these are ignored rather than qualified; a py:func / py:attr short-reference
    # resolver enhancement that disambiguates ambiguous and unrooted project
    # targets is a future follow-up.
    (
        r"py:.*",
        r"^(utc_now|project_answers|write_manifest|sha256_file|save_envelope|"
        r"reset_workflow_state|output_language|extract_pages_text|"
        r"extract_pages_text_from_bytes|emit_collab_workspace_opened_event|"
        r"LLMProvider|PersonaAction)$",
    ),
    (
        r"py:.*",
        r"^(core\.telemetry\.workspace_hash|"
        r"application\.modelo\.emit_collab_workspace_opened_event|"
        r"adapters\.persistence\.storage\.SensitivityClass\.SECRET)$",
    ),
    # Registry typed-id aliases (``CasillaId``, ``RelationId``, ``OracleId``,
    # ``BindingId``, ... ) are PEP 695 aliases, not documentable classes, so a
    # ``:class:`` reference to their registry path has no py:class target. List
    # the aliases explicitly so a future real ``*Id`` class cannot be hidden.
    # ``ModeloDetailRow`` is a re-exported alias referenced bare.
    (
        r"py:.*",
        r"^(?:cadrumo\.)?domain\.calculations\.registry\.(?:"
        r"ApplicationLinkId|BindingId|CasillaId|ConstructId|CrossReferenceId|"
        r"DeadlineWindowId|DependencyClassificationId|ExportFieldId|ExportLayoutId|"
        r"ExtractionProfileId|FormulaId|LegalRefId|ModeloId|OracleId|ParameterId|"
        r"RecordId|RelationId|RevisionId|SourceRefId|"
        r"VerificationExpectationId|WorkbookFixtureId|WorkbookOutputId|WorkbookParityRefId)$",
    ),
    # ``OneBasedExportOffset`` is the same category as the registry typed-id
    # aliases above -- a PEP 695 ``type`` alias
    # (``type OneBasedExportOffset = Annotated[int, Field(ge=1)]``), not a
    # documentable class -- but it is declared in ``_schema_surfaces`` and reaches
    # the gate through its BARE short-form render, which the qualified
    # ``domain.calculations.registry.*`` pattern above cannot match. Named on its
    # own rather than folded into a broader alias pattern so it cannot mask a
    # future real class of the same name.
    (r"py:.*", r"^OneBasedExportOffset$"),
    (r"py:.*", r"^ModeloDetailRow$"),
    # Bound-method references on external (pydantic / SQLAlchemy / asyncio /
    # google) types written ``Owner.method`` or ``obj.method``; the owning type
    # resolves via inventory but the short method target does not.
    (
        r"py:.*",
        r"^(model_copy|process_bind_param|process_result_value|run_in_executor|"
        r"from_service_account_file|create_pipe_input|normalise|reconfigure)$",
    ),
    # Bare sentinel / alias names that survive short-name rendering and carry no
    # in-tree and no inventory target (Ellipsis from ``tuple[X, ...]``
    # annotations, NoneType/EllipsisType, the short pydantic-constraint alias
    # names, and the unqualified renders of common stdlib/SQLAlchemy types whose
    # canonical fully-qualified target resolves via the vendored inventory but
    # whose ``autodoc_typehints_format = "short"`` display form is a bare name).
    (
        r"py:.*",
        r"^(Ellipsis|NoneType|EllipsisType|PydanticUndefined|TypeDecorator|"
        r"Session|Ge|Le|Gt|Lt|Len|Interval|MultipleOf|BaseModel|Decimal|Path|"
        r"Mapping|MutableMapping|Sequence|Iterable|Iterator|Mapped|StrEnum|"
        r"datetime|date|time|timedelta|UUID|"
        # Short pydantic / pydantic-settings / SQLAlchemy / stdlib public names
        # referenced without a module path.
        r"ValidationError|SecretStr|BaseSettings|AnyUrl|AnyHttpUrl|EmailStr|"
        r"Field|TypeAliasType|SkipValidation|PrivateAttr|PydanticBaseSettingsSource|"
        r"CliSettingsSource|PathType|DotenvType|EnvPrefixTarget|Engine|sessionmaker|"
        r"MappingProxyType|ContextVar|deque|InvalidOperation|APIRequestContext|"
        r"MonkeyPatch|Credentials|"
        # prompt_toolkit Input/Output rendered short-form from a wizard prompter
        # signature, and the private Callable protocol aliases used as workflow
        # source types - neither is a documentable cross-reference target.
        r"Input|Output|ExpedientesSource|NotificationsSource|"
        # Period-token regex fragments (``Q``, ``annual`` from a
        # StringConstraints ``^(Q[1-4]|...|annual)$`` pattern) that autodoc
        # mis-renders as bare class targets.
        r"Q|annual)$",
    ),
    # Bound-method references on external (stdlib / pydantic) types, written
    # ``datetime.now`` / ``date.today``; the owning type resolves via inventory
    # but the bare method name has no cross-reference target.
    (
        r"py:.*",
        r"^(datetime|date|time|Decimal|Path|UUID|dict|list|set|str|bytes)\.[a-z]\w*$",
    ),
    # The CLI entrypoint subtree is intentionally excluded from the API stub set
    # (its commands are documented in the generated CLI reference under
    # docs/cli/), so module references into it have no autodoc target.
    (r"py:.*", r"^cadrumo\.entrypoints\.cli(\..*)?$"),
]

# ── Linkcheck (advisory, never a blocking local gate) ─────────────────────────
# `sphinx-build -b linkcheck` is CI-scheduled and advisory: several AEAT/BOE
# endpoints rate-limit or block automated clients, so their failures must never
# red the local docs-check gate.
linkcheck_ignore = [
    r"https?://(www\.|sede\.)?agenciatributaria\.(es|gob\.es).*",
    r"https?://(www\.)?boe\.es.*",
]
linkcheck_timeout = 30


def _specific_build_sources() -> list[Path] | None:
    """Return Sphinx command-line source filenames for a specific-file build.

    Returns:
        ``None`` for the normal update/full build mode, otherwise the filenames
        passed after ``sourcedir`` and ``outputdir``.
    """
    docs_root = Path(__file__).resolve().parent
    args = sys.argv[1:]
    for index, arg in enumerate(args):
        try:
            if Path(arg).resolve() != docs_root:
                continue
        except OSError:
            continue
        first_filename = index + 2
        if first_filename >= len(args):
            return None
        return [Path(item).resolve() for item in args[first_filename:] if not item.startswith("-")]
    return None


def _should_generate_cli_reference() -> bool:
    """Return whether this Sphinx invocation needs generated ``docs/cli`` pages."""
    if os.environ.get("CADRUMO_DOCS_FORCE_CLI_REFERENCE"):
        return True
    if os.environ.get("CADRUMO_DOCS_SKIP_CLI_REFERENCE"):
        return False
    specific_sources = _specific_build_sources()
    if specific_sources is None:
        return True
    cli_root = (Path(__file__).resolve().parent / "cli").resolve()
    return any(source == cli_root or cli_root in source.parents for source in specific_sources)


def _should_resolve_deferred_models() -> bool:
    """Return whether this Sphinx invocation needs diagnostics model rebuilding."""
    if _USER_SCOPE:
        # The deferred-model rebuild only exists so autodoc can import the
        # diagnostics report models; user scope loads no autodoc, so importing
        # the application here would defeat the whole point of the scope.
        return False
    if os.environ.get("CADRUMO_DOCS_FORCE_DEFERRED_MODELS"):
        return True
    if os.environ.get("CADRUMO_DOCS_SKIP_DEFERRED_MODELS"):
        return False
    specific_sources = _specific_build_sources()
    if specific_sources is None:
        return True
    docs_root = Path(__file__).resolve().parent
    diagnostic_pages = {
        (docs_root / "api" / "cadrumo.application.diagnostics.rst").resolve(),
        (docs_root / "api" / "cadrumo.application.auth.diagnostics.rst").resolve(),
        (docs_root / "api" / "cadrumo.application.transactions._diagnostics.rst").resolve(),
    }
    return any(source in diagnostic_pages for source in specific_sources)


_PY_SUFFIX_INDEX: dict[str, list[str]] = {}

_TYPING_ALIAS_FACTORIES = frozenset(
    {
        "Annotated",
        "AsyncIterator",
        "Awaitable",
        "Callable",
        "Collection",
        "Iterable",
        "Iterator",
        "Literal",
        "Mapping",
        "MutableMapping",
        "Protocol",
        "Sequence",
    }
)
_ALIAS_NAME_SUFFIXES = (
    "Builder",
    "Collector",
    "Cursor",
    "Facts",
    "Fetcher",
    "Guard",
    "Kind",
    "Policy",
    "Port",
    "Predicate",
    "Projection",
    "Reference",
    "Resolver",
    "Scalar",
    "Store",
    "Token",
    "Type",
    "Value",
)


def _subscript_root_name(node: ast.expr) -> str | None:
    """Return the root identifier of a subscription expression."""
    value = node.value if isinstance(node, ast.Subscript) else None
    while isinstance(value, ast.Attribute):
        value = value.value
    return value.id if isinstance(value, ast.Name) else None


def _declared_type_hint_names() -> frozenset[str]:
    """Return source-declared aliases and TypeVars that are not API objects."""
    names: set[str] = set()
    source_root = _PROJECT_ROOT / "src" / "cadrumo"
    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
                names.add(node.name.id)
            elif isinstance(node, ast.TypeVar):
                names.add(node.name)
            elif (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "TypeVar"
            ):
                names.update(target.id for target in node.targets if isinstance(target, ast.Name))
            elif isinstance(node, ast.Assign):
                target_names = tuple(target.id for target in node.targets if isinstance(target, ast.Name))
                alias_like = (
                    _subscript_root_name(node.value) in _TYPING_ALIAS_FACTORIES
                    or (isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.BitOr))
                    or (
                        isinstance(node.value, ast.Name)
                        and node.value.id[:1].isupper()
                        and any(name.endswith(_ALIAS_NAME_SUFFIXES) for name in target_names)
                    )
                )
                if alias_like:
                    names.update(target_names)
    return frozenset(names - _PUBLIC_TYPE_ALIAS_TARGETS.keys())


_LITERAL_TYPE_HINT_NAMES = _declared_type_hint_names()


def _is_ordered_subsequence(needle: list[str], haystack: list[str]) -> bool:
    """Return whether every item of *needle* appears in *haystack*, in order.

    Used to match a public dotted reference path against a defining-module
    qualified name that interleaves extra private segments.

    Args:
        needle: The reference's dotted components.
        haystack: A candidate object's dotted components.

    Returns:
        ``True`` when *needle* is an ordered (not necessarily contiguous)
        subsequence of *haystack*.
    """
    it = iter(haystack)
    return all(part in it for part in needle)


def _build_py_suffix_index(env):
    """Index every documented Python object by its bare (final-segment) name.

    Args:
        env: The Sphinx build environment after the read phase.

    Returns:
        A mapping of bare object name to the list of fully-qualified names that
        end in it (for example ``InboundBorradorObservation`` ->
        ``["cadrumo.adapters.inbound.borrador._schema.InboundBorradorObservation"]``).
    """
    index: dict[str, list[str]] = {}
    for fullname in env.get_domain("py").objects:
        index.setdefault(fullname.rsplit(".", 1)[-1], []).append(fullname)
    return index


def _resolve_short_reference(app, env, node, contnode):
    """Bridge a short cross-reference to its single canonical defining-module target.

    Stubs document every symbol exactly once, at its defining ``__module__``
    (``:ignore-module-all:``). Docstrings, however, reference re-exported public
    API either by bare name (``:class:`Name```) or by the public package path it
    is re-exported under (``:class:`cadrumo.domain.filing.ModeloDraft```), neither
    of which autodoc can resolve to the qualified defining-module target. This
    resolver keys on the reference's final segment: when that bare name maps to
    exactly one documented object it returns a reference to it. Ambiguous names
    (several definitions) and unknown names are left untouched so they still
    surface as nitpicky warnings.

    Args:
        app: The Sphinx application.
        env: The build environment.
        node: The pending cross-reference node.
        contnode: The node holding the reference's display text.

    Returns:
        A resolved reference node, or ``None`` to defer to other resolvers.
    """
    from sphinx.util.nodes import make_refnode

    if node.get("refdomain") not in ("py", ""):
        return None
    target = node.get("reftarget", "")
    parts = target.split(".") if target else []
    short = parts[-1] if parts else ""
    if not short or not short.isidentifier():
        return None
    # ``country`` is an upstream locale-library annotation, not the unrelated
    # in-tree callable that happens to share its final component.
    if target == "country":
        return contnode

    if not _PY_SUFFIX_INDEX:
        _PY_SUFFIX_INDEX.update(_build_py_suffix_index(env))
    candidates = _PY_SUFFIX_INDEX.get(short)
    if not candidates:
        # Postponed annotations reach the extension as unresolved strings, so
        # ``typehints_formatter`` cannot inspect their runtime TypeAliasType or
        # TypeVar identity.  A source-declared alias with no documented object
        # is implementation vocabulary, not a missing public class.  Preserve
        # it as inline code; a real documented candidate always takes priority.
        if short in _LITERAL_TYPE_HINT_NAMES:
            return contnode
        if target.startswith(("bs4.", "textual.")) or target in {
            "Coordinate",
            "CursorType",
            "PlaywrightError",
            "Shape",
            "TC",
            "calc_sheets_export",
            "country",
            "textual.geometry.Size",
            "typing.Union",
        }:
            return contnode
        return None

    # A public re-export path (``cadrumo.domain.iva.verify_catalogue``) maps onto a
    # defining-module path that carries extra private segments
    # (``cadrumo.domain.iva._catalogue.verify_catalogue``). The public components
    # still appear, in order, within the defining path, so disambiguate by
    # keeping the candidates whose dotted components contain the reference's
    # components as an ordered subsequence. This separates same-named symbols
    # that live under different public packages (``iva`` vs ``normatives``).
    if len(candidates) > 1 and len(parts) > 1:
        subseq = [name for name in candidates if _is_ordered_subsequence(parts, name.split("."))]
        if len(subseq) == 1:
            candidates = subseq
    if len(candidates) != 1:
        return None

    fullname = candidates[0]
    entry = env.get_domain("py").objects[fullname]
    return make_refnode(app.builder, node.get("refdoc", env.docname), entry.docname, entry.node_id, contnode, fullname)


def _paramref_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    """Render SQLAlchemy's ``:paramref:`` cross-references as plain literals.

    SQLAlchemy documents its mapped-attribute and engine constructs with the
    ``:paramref:`` role supplied by its own ``zzzeeksphinx`` Sphinx extension.
    Autodoc pulls those inherited docstrings into the ORM module pages, so the
    role appears in our build without the extension that defines it. Rendering
    the trailing ``ClassName.param`` segment as inline literal text keeps the
    inherited prose readable without erroring the nitpicky gate.

    Args:
        name: The role name as invoked.
        rawtext: The entire role markup including the target.
        text: The interpreted target (a dotted parameter reference).
        lineno: The line number of the role in the source.
        inliner: The docutils inliner driving the parse.
        options: Role options (unused).
        content: Role content (unused).

    Returns:
        A docutils node list and an (always empty) system-message list.
    """
    label = text.split(".")[-1].strip("`") or text
    return [nodes.literal(rawtext, label)], []


def _convert_markdown_fences_in_inherited_docstrings(app, what, name, obj, options, lines):
    """Rewrite Markdown code fences in inherited docstrings as RST literal blocks.

    Same remedy as the ``:paramref:`` role and ``.. legacy::`` directive shims
    above, for a different upstream: keep inherited third-party prose readable
    instead of erroring the nitpicky gate.

    Textual documents ``Widget.compose`` — which every screen in
    ``entrypoints.tui`` inherits — with a Markdown fenced block::

        ```python
        def compose(self) -> ComposeResult:
            yield Label("Press the button below:")
        ```

    Sphinx parses reStructuredText, where ```` ``` ```` opens an inline literal
    that never closes and the indented body reads as a stray block quote. That
    single upstream docstring produced 18 of the 22 warnings this gate reported
    the first time it ever completed: "Inline literal start-string without
    end-string", "Inline interpreted text ... without end-string", and "Block
    quote ends without a blank line", once per inheriting screen.

    Rewriting rather than suppressing is deliberate. Suppressing the ``docutils``
    category would hide the identical warnings in OUR OWN docstrings, where they
    are real markup defects worth failing on; dropping
    ``autodoc_inherit_docstrings`` would silently delete inherited prose the API
    pages legitimately carry. This converts the fence to an RST literal block and
    leaves the body verbatim, so the reader sees the example the upstream author
    wrote.

    Args:
        app: The Sphinx application (unused).
        what: The kind of object being documented (unused).
        name: The fully-qualified object name (unused).
        obj: The object being documented (unused).
        options: The autodoc options in force (unused).
        lines: The docstring lines, mutated IN PLACE as autodoc requires.
    """
    if not any(line.lstrip().startswith("```") for line in lines):
        return
    converted: list[str] = []
    inside = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if inside:
                inside = False
                converted.append("")
            else:
                inside = True
                converted.append("::")
                converted.append("")
            continue
        converted.append(f"   {line}" if inside else line)
    lines[:] = converted


class _LegacyDirective(Directive):
    """Render SQLAlchemy's ``.. legacy::`` admonition as a generic note.

    SQLAlchemy's ``zzzeeksphinx`` extension defines a ``.. legacy::`` admonition
    that surfaces through autodoc'd inherited docstrings. Without the extension
    the directive is unknown and errors the gate; emitting an ``admonition``
    node with the parsed body preserves the inherited guidance.
    """

    has_content = True
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = True

    @override
    def run(self):
        """Build a generic ``Legacy`` admonition from the directive body.

        Returns:
            A single-element list holding the admonition node.
        """
        admonition = nodes.admonition()
        admonition += nodes.title(text="Legacy")
        self.state.nested_parse(self.content, self.content_offset, admonition)
        return [admonition]


def _suppress_api_scope_reference(app, env, node, contnode):
    """Resolve references into the excluded API surface inertly under user scope.

    The user-scope build (``CADRUMO_DOCS_SCOPE=user``) excludes ``docs/api/**``
    and loads no autodoc, so the py domain is intentionally empty and the API
    reference doc is absent. Two reference classes then have no target and would
    red the ``-n -W`` gate even though they resolve in the full/deployed build:

    * every py-domain cross-reference (``:class:`` / ``:func:`` / ... — chiefly
      the generated CLI reference pages, which point at the application symbols
      autodoc documents in full scope); and
    * the ``std:doc`` links into ``api/`` from the reference / architecture pages.

    This handler — connected ONLY under user scope — resolves exactly those to
    their plain display text (dropping the hyperlink), so the preview builds
    clean while every OTHER missing reference still reds the gate. It is the
    documented, scope-aware suppression of just the API-domain missing-reference
    class (never a blanket ``-W`` off); full-scope builds never connect it.
    """
    if node.get("refdomain") == "py":
        return contnode
    if (
        node.get("refdomain") == "std"
        and node.get("reftype") == "doc"
        and node.get("reftarget", "").lstrip("/").startswith("api/")
    ):
        return contnode
    return None


class _UserScopeApiWarningFilter:
    """Drop the user-scope MyST 'Unknown source document api/...' warnings.

    MyST emits ``myst.xref_missing`` for the markdown links into the excluded API
    tree directly (not via the ``missing-reference`` event that
    :func:`_suppress_api_scope_reference` intercepts), so this logging filter
    drops exactly those API-targeted records under user scope, leaving every
    other broken-link warning intact so the gate stays meaningful.
    """

    def filter(self, record) -> bool:
        message = record.getMessage()
        return not ("Unknown source document" in message and "api/" in message)


def setup(app):
    """Resolve deferred pydantic forward references before autodoc runs.

    Several diagnostics report models defer ``model_rebuild()`` to a lazy
    runtime path so the ``aeat --version`` fast path stays light. Autodoc
    imports those modules directly and would crash on a not-fully-defined
    model; the docs build is not the fast path, so the rebuild is triggered
    once the builder is initialised and mock imports are active.

    The ``:paramref:`` role and ``.. legacy::`` directive belong to
    SQLAlchemy's documentation toolchain; they reach our build only through
    autodoc'd inherited docstrings, so tolerant shims are registered rather
    than vendoring the upstream extension.

    Args:
        app: The Sphinx application instance.

    Returns:
        The extension metadata declaring parallel-read/write safety.
    """

    def _skip_non_owner_autodoc_member(app, what, name, obj, skip, options):
        """Keep private/generated typing objects out of public object indexing."""
        if name in {"__pydantic_serializer__", "__pydantic_validator__"}:
            return True
        generic_metadata = getattr(obj, "__pydantic_generic_metadata__", None)
        if isinstance(generic_metadata, dict) and generic_metadata.get("origin") is not None:
            return True
        if get_origin(obj) is Annotated:
            return True
        return None

    # Napoleon's optional private/special-member listener probes ``__doc__``
    # on every candidate before deciding to skip it.  A deferred Pydantic
    # serializer deliberately raises on that probe, even though autodoc's own
    # exclude-members contract has already made the descriptor non-public.
    # None of Napoleon's inclusion switches are enabled here, so disconnecting
    # that redundant selector preserves member selection and prevents an
    # excluded implementation descriptor from aborting public API discovery.
    for listener in tuple(app.events.listeners.get("autodoc-skip-member", ())):
        handler = listener.handler
        if handler.__module__ == "sphinx.ext.napoleon" and handler.__name__ == "_skip_member":
            if any(
                (
                    app.config.napoleon_include_init_with_doc,
                    app.config.napoleon_include_private_with_doc,
                    app.config.napoleon_include_special_with_doc,
                )
            ):
                raise RuntimeError("Napoleon member inclusion is incompatible with the Pydantic API boundary")
            app.disconnect(listener.id)

    def _resolve_deferred_models(app):
        """Import the diagnostics module and run its idempotent model rebuild.

        Args:
            app: The Sphinx application instance (unused).
        """
        if not _should_resolve_deferred_models():
            return
        from cadrumo.application import diagnostics
        from cadrumo.core.errors.error_codes import ErrorEnvelope

        diagnostics._ensure_models_rebuilt()
        if not ErrorEnvelope.__pydantic_complete__:
            raise RuntimeError("the canonical ErrorEnvelope model did not resolve for API documentation")

    def _generate_cli_reference(app):
        """Render the CLI reference fresh from the live command tree.

        The ``docs/cli/`` pages are a build-time projection of the materialised
        command tree and its English ``tr()`` help: they are regenerated on every
        build and are gitignored, never committed, so they cannot drift from the
        code. The output language is pinned to English at the top of this module
        before any project import. Generating in ``builder-inited`` writes the
        pages before Sphinx reads the source tree.

        Args:
            app: The Sphinx application instance (unused).
        """
        if not _should_generate_cli_reference():
            return
        from dev.docs.cli_reference import generate_cli_reference

        generate_cli_reference(Path(__file__).resolve().parent)

    def _generate_glossary_reference(app):
        """Render the glossary fresh from the approved Handbook concepts.

        The ``docs/_generated/glossary.rst`` page is a build-time projection of
        the Terminology Handbook: regenerated on every build and gitignored,
        never committed, so it cannot drift from the curated concepts. Only
        approved concepts render; drafts are search-only. Generating in
        ``builder-inited`` writes the page before Sphinx reads the source tree,
        so its ``:term:`` anchors resolve and the nitpicky ``-n -W`` gate
        enforces enrolment and single declaration.

        Args:
            app: The Sphinx application instance (unused).
        """
        from dev.docs.glossary_reference import generate_glossary_reference

        generate_glossary_reference(Path(__file__).resolve().parent)

    def _generate_casilla_reference(app):
        """Render the per-modelo casilla reference pages fresh from the registry.

        The ``docs/_generated/casillas/<modelo>.rst`` pages are a build-time
        projection of the registry casilla set (the same projection the injected
        search records use): regenerated on every build and gitignored, never
        committed, so they cannot drift from the registry. Generating in
        ``builder-inited`` writes the pages before Sphinx reads the source tree,
        so their anchors resolve and the nitpicky ``-n -W`` gate holds. These
        pages are the destination the search palette's casilla results deep-link
        to (they carry each casilla's full legal/source grounding).

        Args:
            app: The Sphinx application instance (unused).
        """
        from dev.docs.casilla_reference import generate_casilla_reference

        generate_casilla_reference(Path(__file__).resolve().parent, repo_root=_PROJECT_ROOT)

    def _generate_legal_reference(app):
        """Render the per-document legal reference pages fresh from the catalogue.

        The ``docs/_generated/legal/`` pages are a build-time projection of
        the authored registry legal tables.  They are regenerated before
        Sphinx reads the source tree and are never committed.  The generator
        also owns the page/anchor target inventory consumed by the later legal
        search-record projection.

        Args:
            app: The Sphinx application instance (unused).
        """
        from dev.docs.legal_reference import generate_legal_reference

        generate_legal_reference(Path(__file__).resolve().parent, repo_root=_PROJECT_ROOT)

    def _emit_cli_tree(app):
        """Write a fresh ``_static/cli-tree.json`` help projection for the widget.

        The projection is a build-time asset the ``cli-sequence`` browser widget
        fetches for hover help. It is gitignored and regenerated, never
        committed. Guarded like the sibling
        CLI-reference hook: an incremental changed-page build whose artifact
        already exists skips the projection's subprocess cost (the CLI tree
        cannot change on a docs-only page build).

        Args:
            app: The Sphinx application instance.
        """
        from dev.docs.sequence_build_gate import emit_cli_tree

        emit_cli_tree(app, specific_sources=_specific_build_sources())

    def _check_cli_sequences(app):
        """Fail the build on any cli-sequence golden divergence.

        The docs-build half of the two-surfaces-one-engine gate: runs the engine
        check mode so a divergence or a failed ``@expect`` reds the build. Scoped
        to the changed-page set on an incremental changed-page build (the same
        specific-source detection the CLI reference and deferred-model hooks use),
        unscoped on a full build.

        Args:
            app: The Sphinx application instance.
        """
        from dev.docs.sequence_build_gate import check_sequence_goldens

        specific_sources = _specific_build_sources()
        pages: list[str] | None
        if specific_sources is None:
            pages = None
        else:
            docs_root = Path(app.srcdir)
            pages = []
            for source in specific_sources:
                if source.suffix != ".md":
                    continue
                try:
                    pages.append(source.relative_to(docs_root).with_suffix("").as_posix())
                except ValueError:
                    continue
        check_sequence_goldens(app, pages=pages)

    app.connect("autodoc-process-docstring", _convert_markdown_fences_in_inherited_docstrings)
    app.connect("autodoc-skip-member", _skip_non_owner_autodoc_member, priority=100)
    app.connect("builder-inited", _resolve_deferred_models)
    app.connect("builder-inited", _generate_cli_reference)
    app.connect("builder-inited", _generate_glossary_reference)
    app.connect("builder-inited", _generate_casilla_reference)
    app.connect("builder-inited", _generate_legal_reference)
    app.connect("builder-inited", _emit_cli_tree)
    app.connect("builder-inited", _check_cli_sequences)
    # Priority 700 runs after intersphinx (which resolves external targets at the
    # default priority) so the short-name bridge only fires for genuinely
    # unresolved in-tree references.
    app.connect("missing-reference", _resolve_short_reference, priority=700)
    if _USER_SCOPE:
        # Scope-aware API-reference suppression (see the two helpers above): the
        # missing-reference handler runs LAST (priority 900, after the short-name
        # bridge) so it only inerts references the full build would resolve
        # against the excluded autodoc surface; the logging filter drops the
        # MyST markdown-link warnings into api/ that never reach that event.
        import logging as _stdlib_logging

        app.connect("missing-reference", _suppress_api_scope_reference, priority=900)
        _stdlib_logging.getLogger("sphinx").addFilter(_UserScopeApiWarningFilter())
    app.add_role("paramref", _paramref_role)
    app.add_directive("legacy", _LegacyDirective)

    # Register the cli-sequence directive: server-rendered executed-CLI frames
    # plus one inline JSON payload per sequence.
    from dev.docs.sequence_directive import register as _register_cli_sequence

    _register_cli_sequence(app)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
