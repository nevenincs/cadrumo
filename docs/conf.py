"""Sphinx configuration for the aeat documentation set."""

from __future__ import annotations

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
    "sphinx_markdown_builder",
    "myst_parser",
]

# Source file types — both reStructuredText (autodoc stubs, index) and MyST
# Markdown (narrative pages, generated API surface) are first-class.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
language = "en"

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "**/test_*.py",
    "**/_test_*.py",
    # Legacy narrative docs scheduled for removal (heavy dev-process
    # metadata that predates the docstring rewrite); excluded from the
    # build so Sphinx neither toctree-warns about them nor renders them.
    "casillas.md",
    "concepts/**",
    "coverage/**",
    "error-codes.md",
    "exit-codes.md",
    "json-contract.md",
    "security-runbook.md",
]

# Quiet down warnings that originate from MyST cross-reference resolution.
# Real autodoc / nitpicky reference issues still surface.
suppress_warnings = ["myst.xref_missing"]

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
    "google",
    "googleapiclient",
    "gspread",
    "google_auth_oauthlib",
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
