"""Sphinx configuration for the aeat documentation set."""

from __future__ import annotations

import os
import tomllib

# Pin the CLI output language to English BEFORE any project module is imported.
# CLI help strings are tr() values resolved at import time; the sphinx-click
# build-time CLI reference renders them, so the language must be fixed for the
# whole build process here, at the top of conf.py.
os.environ["AEAT_OUTPUT_LANGUAGE"] = "en"

import sys
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive

# Make `aeat` importable for autodoc without installing the wheel.
_PROJECT_ROOT = Path(os.environ.get("AEAT_DOCS_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


def _project_metadata() -> dict[str, object]:
    """Load project metadata from ``pyproject.toml`` for Sphinx display fields."""
    pyproject = _PROJECT_ROOT / "pyproject.toml"
    with pyproject.open("rb") as stream:
        return tomllib.load(stream)["project"]


_PYPROJECT = _project_metadata()
_PROJECT_URLS = _PYPROJECT.get("urls", {})
_DOCS_BASE_URL = os.environ.get("AEAT_DOCS_BASE_URL", "").rstrip("/")
_DOCS_FONT_STACK = '"Geist", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif'
_DOCS_HEADING_FONT_STACK = '"Geist", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
_DOCS_MONO_FONT_STACK = '"Geist Mono", "Cascadia Code", "SFMono-Regular", Consolas, monospace'
_REPOSITORY_URL = str(_PROJECT_URLS.get("Repository", ""))
_ISSUES_URL = str(_PROJECT_URLS.get("Issues", ""))
_RELEASES_URL = f"{_REPOSITORY_URL}/releases" if _REPOSITORY_URL else ""
_LATEST_RELEASE_URL = f"{_RELEASES_URL}/latest" if _RELEASES_URL else ""

# ── Project metadata ────────────────────────────────────────────────────────
project = str(_PYPROJECT["name"])
author = ", ".join(author["name"] for author in _PYPROJECT.get("authors", []))
copyright = f"2026, {author}"
release = str(_PYPROJECT["version"])
version = release

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
    "myst_parser",
]
if _DOCS_BASE_URL:
    extensions.append("sphinx_sitemap")

# Source file types — both reStructuredText (autodoc stubs, index) and MyST
# Markdown (narrative pages, generated API surface) are first-class.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = os.environ.get("AEAT_DOCS_MASTER_DOC", "index")
# English is the only documentation language. Additional languages attach
# here - set `language`, add `locale_dirs` and `gettext_compact`, and a
# gettext / sphinx-intl build matrix. Documentation translation must not
# reuse the runtime CLI translation catalogues.
language = "en"

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "**/test_*.py",
    "**/_test_*.py",
    "USERDOCS-KICKOFF-BRIEF.md",
]

_DOCS_ROOT = Path(__file__).resolve().parent
_ONLY_SOURCES = {
    Path(item).as_posix() for item in os.environ.get("AEAT_DOCS_ONLY", "").split(os.pathsep) if item.strip()
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
if os.environ.get("AEAT_DOCS_SINGLE_PAGE"):
    suppress_warnings.append("toc.excluded")
    suppress_warnings.append("toc.not_included")

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
        "__init__,model_config,model_fields,model_computed_fields,"
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
    "ofxparse",
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
    "pydantic": ("https://docs.pydantic.dev/latest", None),
    "httpx": ("https://www.python-httpx.org/", None),
    "typer": ("https://typer.tiangolo.com/", None),
}
_SELF_INVENTORY = Path(__file__).resolve().parent / "_build" / "html" / "objects.inv"
if os.environ.get("AEAT_DOCS_SELF_INVENTORY") and _SELF_INVENTORY.is_file():
    intersphinx_mapping["aeat-local"] = ((_SELF_INVENTORY.parent).as_uri() + "/", str(_SELF_INVENTORY))
intersphinx_disabled_reftypes = ["std:doc"]

# Offline-hermetic gate: the docs-check build sets AEAT_DOCS_OFFLINE to keep only
# the vendored local inventories (read from disk) and drop the network-only
# mappings, so the build resolves stdlib/SQLAlchemy targets deterministically
# without any network access. The dropped third-party namespaces are covered by
# nitpick_ignore_regex below.
if os.environ.get("AEAT_DOCS_OFFLINE"):
    intersphinx_mapping = {
        name: (uri, inv) for name, (uri, inv) in intersphinx_mapping.items() if inv and Path(inv).is_file()
    }

# ── HTML theme ──────────────────────────────────────────────────────────────
html_theme = "furo"
html_title = "aeat-cli - local Spanish tax-file automation"
html_short_title = "aeat-cli"
html_baseurl = f"{_DOCS_BASE_URL}/" if _DOCS_BASE_URL else ""
html_favicon = "_static/aeat-favicon.svg"
html_static_path = ["_static"]
templates_path = ["_templates"]
html_css_files = ["aeat-docs.css"]
html_js_files = ["aeat-docs.js"]
# The left sidebar carries the command-palette trigger and the navigation tree;
# brand and the stock search box move into the sticky site header / palette.
html_sidebars = {
    "**": [
        "sidebar/aeat-search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/scroll-end.html",
    ],
}
html_theme_options = {
    "light_logo": "aeat-mark-light.svg",
    "dark_logo": "aeat-mark-dark.svg",
    "sidebar_hide_name": True,
    "announcement": "aeat-site-broadcast",
    "light_css_variables": {
        # 2026 design-token pass: zinc neutral scale + Geist blue accent
        # mapped onto Furo's semantic variables.
        "color-brand-primary": "#18181b",
        "color-brand-content": "#0068d6",
        "color-brand-visited": "#0068d6",
        "color-foreground-primary": "#18181b",
        "color-foreground-secondary": "#52525b",
        "color-foreground-muted": "#71717a",
        "color-foreground-border": "#d4d4d8",
        "color-background-primary": "#ffffff",
        "color-background-secondary": "#fafafa",
        "color-background-hover": "#f4f4f5",
        "color-background-hover--transparent": "#f4f4f500",
        "color-background-border": "#e4e4e7",
        "color-card-border": "#e4e4e7",
        "color-card-background": "transparent",
        "color-card-marginals-background": "#fafafa",
        "color-link": "#0068d6",
        "color-link--hover": "#0054ad",
        "color-link--visited": "#0068d6",
        "color-link--visited--hover": "#0054ad",
        "color-link-underline": "transparent",
        "color-link-underline--hover": "#0068d6",
        "color-link-underline--visited": "transparent",
        "color-link-underline--visited--hover": "#0068d6",
        "color-inline-code-background": "#f4f4f5",
        "color-admonition-background": "#fafafa",
        "color-admonition-title": "#18181b",
        "color-admonition-title-background": "transparent",
        "color-admonition-title-background--important": "transparent",
        "color-admonition-title--important": "#18181b",
        "color-admonition-title-background--warning": "transparent",
        "color-admonition-title--warning": "#18181b",
        "color-sidebar-background": "transparent",
        "color-sidebar-background-border": "transparent",
        "color-sidebar-link-text": "#52525b",
        "color-sidebar-link-text--top-level": "#3f3f46",
        "color-sidebar-item-background--current": "#f4f4f5",
        "color-sidebar-item-background--hover": "#f4f4f5",
        "color-toc-background": "transparent",
        "color-toc-item-text": "#52525b",
        "color-toc-item-text--hover": "#18181b",
        "color-toc-item-text--active": "#0068d6",
        "color-toc-title-text": "#71717a",
        "font-stack": _DOCS_FONT_STACK,
        "font-stack--headings": _DOCS_HEADING_FONT_STACK,
        "font-stack--monospace": _DOCS_MONO_FONT_STACK,
    },
    "dark_css_variables": {
        "color-brand-primary": "#fafafa",
        "color-brand-content": "#52a8ff",
        "color-brand-visited": "#52a8ff",
        "color-foreground-primary": "#ededed",
        "color-foreground-secondary": "#a1a1aa",
        "color-foreground-muted": "#8f8f98",
        "color-foreground-border": "#3f3f46",
        "color-background-primary": "#0a0a0a",
        "color-background-secondary": "#121214",
        "color-background-hover": "#1d1d20",
        "color-background-hover--transparent": "#1d1d2000",
        "color-background-border": "#26262a",
        "color-card-border": "#26262a",
        "color-card-background": "transparent",
        "color-card-marginals-background": "#121214",
        "color-link": "#52a8ff",
        "color-link--hover": "#7ec0ff",
        "color-link--visited": "#52a8ff",
        "color-link--visited--hover": "#7ec0ff",
        "color-link-underline": "transparent",
        "color-link-underline--hover": "#52a8ff",
        "color-link-underline--visited": "transparent",
        "color-link-underline--visited--hover": "#52a8ff",
        "color-inline-code-background": "#1b1b1f",
        "color-admonition-background": "#121214",
        "color-admonition-title": "#ededed",
        "color-admonition-title-background": "transparent",
        "color-admonition-title-background--important": "transparent",
        "color-admonition-title--important": "#ededed",
        "color-admonition-title-background--warning": "transparent",
        "color-admonition-title--warning": "#ededed",
        "color-sidebar-background": "transparent",
        "color-sidebar-background-border": "transparent",
        "color-sidebar-link-text": "#a1a1aa",
        "color-sidebar-link-text--top-level": "#d4d4d8",
        "color-sidebar-item-background--current": "#1d1d20",
        "color-sidebar-item-background--hover": "#1d1d20",
        "color-toc-background": "transparent",
        "color-toc-item-text": "#a1a1aa",
        "color-toc-item-text--hover": "#ededed",
        "color-toc-item-text--active": "#52a8ff",
        "color-toc-title-text": "#8f8f98",
    },
    "source_repository": _REPOSITORY_URL,
    "source_branch": "main",
    "source_directory": "docs/",
    "top_of_page_buttons": ["view", "edit"],
}

html_context = {
    "aeat_repository_url": _REPOSITORY_URL,
    "aeat_nav": [
        {"label": "Guides", "doc": "how-to/index"},
        {"label": "Tutorial", "doc": "tutorials/index"},
        {"label": "CLI reference", "doc": "cli/index"},
        {"label": "How it works", "doc": "explanation/index"},
        {"label": "API", "doc": "api/aeat"},
    ],
    "aeat_broadcasts": [
        {
            "label": "Pre-alpha",
            "message": "Breaking changes are expected. Verify official AEAT deadlines before filing.",
            "links": [
                {"label": "Updates", "doc": "updates"},
                {"label": "Latest download", "url": _LATEST_RELEASE_URL},
                {"label": "Report an issue", "url": _ISSUES_URL},
            ],
        }
    ],
    "aeat_footer_groups": [
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
    "aeat_footer_note": (
        "aeat is pre-alpha, local-first software. It is not tax advice, is not affiliated with AEAT, "
        "and never replaces official AEAT tools or professional review."
    ),
}

# ── Publishing metadata ─────────────────────────────────────────────────────
ogp_site_name = "aeat documentation"
ogp_site_url = html_baseurl
ogp_description_length = 180
ogp_type = "website"
ogp_image = "_static/aeat-mark-light.svg"

# ── Syntax highlighting ─────────────────────────────────────────────────────
# Bare code fences are overwhelmingly operator command transcripts; lexing them
# as ``console`` colours the ``$``/``PS>`` prompts and keeps plain output calm.
# Explicit ```bash fences keep their bash lexer.
highlight_language = "console"
pygments_style = "friendly"
pygments_dark_style = "github-dark"

# ── Mermaid diagrams ────────────────────────────────────────────────────────
# ```mermaid fences render as client-side mermaid.js diagrams. The theme is
# chosen once at page load from the Furo light/dark state.
mermaid_init_js = (
    'const aeatDocsDark = document.body.dataset.theme === "dark" || '
    '(document.body.dataset.theme !== "light" && '
    'window.matchMedia("(prefers-color-scheme: dark)").matches);\n'
    "mermaid.initialize({ startOnLoad: true, theme: aeatDocsDark ? "
    '"dark" : "neutral", fontFamily: \'"Geist", "Segoe UI", sans-serif\' });'
)

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
        r"playwright_stealth|pikepdf|pdfplumber|ofxparse|openpyxl|reportlab|"
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
    # Bare ``TypeVar`` parameters (``TPayload``, ``PayloadT``, ``T_co``) and the
    # single-letter PEP 695 type parameters used in ``class Foo[T, K: Hashable]``
    # generic syntax (``K``, ``V``) are not documentable objects; they appear in
    # generic signatures only. Listed explicitly so the pattern cannot mask a
    # real CamelCase class.
    (
        r"py:.*",
        r"^(T|K|V|KT|VT|RT|_T|T_co|T_contra|TPayload|PayloadT|PayloadT_co|ResultT|RecordT|PayloadType|CheckerObservation|ObservationT)$",
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
        r"rich|yaml|tomllib|tomli|cryptography|jinja2|markupsafe|"
        r"prompt_toolkit|google|typing_extensions|asyncio|contextvars|"
        r"_pytest|playwright|_schema|_orm|annotated_types)(\..*)?$",
    ),
    # Test modules are excluded from the documented API surface (see
    # ApiStubManager exclusions), so references into them have no stub target.
    (r"py:.*", r".*\btest_[A-Za-z0-9_]*$"),
    (r"py:.*", r"^aeat\.tests(\..*)?$"),
    # Dunder and numeric-literal targets that leak out of docstrings as bogus
    # cross-references (a ``:class:`1``` or ``:data:`__all__```), never real
    # documentable objects.
    (r"py:.*", r"^([0-9]+|__all__|__repr__|__init__|__init_subclass__)$"),
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
    (r"py:.*", r"^aeat\.entrypoints\.cli(\..*)?$"),
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
    if os.environ.get("AEAT_DOCS_FORCE_CLI_REFERENCE"):
        return True
    if os.environ.get("AEAT_DOCS_SKIP_CLI_REFERENCE"):
        return False
    specific_sources = _specific_build_sources()
    if specific_sources is None:
        return True
    cli_root = (Path(__file__).resolve().parent / "cli").resolve()
    return any(source == cli_root or cli_root in source.parents for source in specific_sources)


def _should_resolve_deferred_models() -> bool:
    """Return whether this Sphinx invocation needs diagnostics model rebuilding."""
    if os.environ.get("AEAT_DOCS_FORCE_DEFERRED_MODELS"):
        return True
    if os.environ.get("AEAT_DOCS_SKIP_DEFERRED_MODELS"):
        return False
    specific_sources = _specific_build_sources()
    if specific_sources is None:
        return True
    docs_root = Path(__file__).resolve().parent
    diagnostic_pages = {
        (docs_root / "api" / "aeat.application.diagnostics.rst").resolve(),
        (docs_root / "api" / "aeat.application.auth._diagnostics.rst").resolve(),
        (docs_root / "api" / "aeat.application.transactions._diagnostics.rst").resolve(),
    }
    return any(source in diagnostic_pages for source in specific_sources)


_PY_SUFFIX_INDEX: dict[str, list[str]] = {}


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
        end in it (for example ``BorradorObservation`` ->
        ``["aeat.adapters.inbound.borrador._schema.BorradorObservation"]``).
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
    is re-exported under (``:class:`aeat.domain.filing.ModeloDraft```), neither
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

    if not _PY_SUFFIX_INDEX:
        _PY_SUFFIX_INDEX.update(_build_py_suffix_index(env))
    candidates = _PY_SUFFIX_INDEX.get(short)
    if not candidates:
        return None

    # A public re-export path (``aeat.domain.iva.verify_catalogue``) maps onto a
    # defining-module path that carries extra private segments
    # (``aeat.domain.iva._catalogue.verify_catalogue``). The public components
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

    def run(self):
        """Build a generic ``Legacy`` admonition from the directive body.

        Returns:
            A single-element list holding the admonition node.
        """
        admonition = nodes.admonition()
        admonition += nodes.title(text="Legacy")
        self.state.nested_parse(self.content, self.content_offset, admonition)
        return [admonition]


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

    def _resolve_deferred_models(app):
        """Import the diagnostics module and run its idempotent model rebuild.

        Args:
            app: The Sphinx application instance (unused).
        """
        if not _should_resolve_deferred_models():
            return
        from aeat.application import diagnostics

        diagnostics._ensure_models_rebuilt()

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

    app.connect("builder-inited", _resolve_deferred_models)
    app.connect("builder-inited", _generate_cli_reference)
    # Priority 700 runs after intersphinx (which resolves external targets at the
    # default priority) so the short-name bridge only fires for genuinely
    # unresolved in-tree references.
    app.connect("missing-reference", _resolve_short_reference, priority=700)
    app.add_role("paramref", _paramref_role)
    app.add_directive("legacy", _LegacyDirective)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
