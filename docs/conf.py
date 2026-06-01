"""Sphinx configuration for the aeat documentation set."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `aeat` importable for autodoc without installing the wheel.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# ── Project metadata ────────────────────────────────────────────────────────
project = "aeat"
author = "wgergely"
copyright = f"%Y, {author}"
release = "0.1.0"
version = "0.1.0"

# ── Extensions ──────────────────────────────────────────────────────────────
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

# Source file types — both reStructuredText (autodoc stubs, index) and MyST
# Markdown (narrative pages, generated API surface) are first-class.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
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
]

# No blanket warning suppression: the docs-check gate builds nitpicky (-n)
# with warnings-as-errors (-W), so unresolved cross-references must be fixed
# or added to nitpick_ignore_regex below.

# ── Autodoc / Napoleon ──────────────────────────────────────────────────────
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

autodoc_default_options = {
    "members": True,
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
python_use_unqualified_type_names = True

# ── Intersphinx ─────────────────────────────────────────────────────────────
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
    "httpx": ("https://www.python-httpx.org/", None),
    "typer": ("https://typer.tiangolo.com/", None),
}
intersphinx_disabled_reftypes = ["std:doc"]

# Offline-hermetic gate: the docs-check build sets AEAT_DOCS_OFFLINE to skip
# intersphinx inventory fetches. External references are already covered by
# nitpick_ignore_regex, so the nitpicky gate stays deterministic and network-free.
if os.environ.get("AEAT_DOCS_OFFLINE"):
    intersphinx_mapping = {}

# ── HTML theme ──────────────────────────────────────────────────────────────
html_theme = "furo"
html_title = "aeat — Spanish Tax Authority automation"
html_static_path = ["_static"]
templates_path = ["_templates"]

# ── MyST ────────────────────────────────────────────────────────────────────
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]
myst_heading_anchors = 3

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
    # pydantic constrained-type metadata and regex pattern fragments leak into
    # rendered annotations as bogus targets (min_length=1, strict=None,
    # pattern=^...$, *$, {64}$). Any target containing a non-identifier
    # character is not a real Python object reference.
    (r"py:class", r".*[^A-Za-z0-9_.].*"),
    # pydantic / typing internals and constrained-type alias names that carry
    # no autodoc cross-reference target.
    (
        r"py:.*",
        r"^(FieldInfo|MinLen|MaxLen|NoneType|EllipsisType|Annotated|"
        r"Strict[A-Za-z]*|[A-Za-z]*Constraints)$",
    ),
    # Typed-id NewType aliases (CasillaId, SourceRefId, ...) are documented at
    # their definition, not as standalone class targets.
    (r"py:.*", r".*\._ids\.[A-Za-z]\w*$"),
    # References into private (underscore) modules, which are excluded from the
    # documented API surface, have no cross-reference target.
    (r"py:.*", r".*\._[a-z]\w*\.[A-Za-z_]\w*$"),
    # External types resolved (when online) via intersphinx; ignored so the
    # gate stays hermetic offline.
    (
        r"py:.*",
        r"^(Path|Decimal|Session|TypeDecorator|PydanticUndefined|"
        r"Ge|Le|Gt|Lt|Len|Interval|MultipleOf)$",
    ),
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


def setup(app):
    """Resolve deferred pydantic forward references before autodoc runs.

    Several diagnostics report models defer ``model_rebuild()`` to a lazy
    runtime path so the ``aeat --version`` fast path stays light. Autodoc
    imports those modules directly and would crash on a not-fully-defined
    model; the docs build is not the fast path, so the rebuild is triggered
    once the builder is initialised and mock imports are active.

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
        from aeat.application import diagnostics

        diagnostics._ensure_models_rebuilt()

    app.connect("builder-inited", _resolve_deferred_models)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
