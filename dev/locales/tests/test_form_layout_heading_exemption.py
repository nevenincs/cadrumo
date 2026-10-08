"""Form layout headings are exempt from key-set parity only when a layout declares them.

Layout headings are optional registry-declared translations with a fallback
chain, so they are neither required nor extra. The exemption must not become a
shape-based pass: a heading-shaped key no layout declares is still extra.
"""

import pytest

from .._paths import DOCS_SRC_DIR, HARNESS_SRC_DIR, LOCALES_DIR, SRC_DIR
from .._registry_scanner import is_form_layout_heading_candidate, scan_form_layout_heading_keys
from ..locale_audit import _audit_locale_file
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_declared_headings_and_the_shared_vocabulary_are_exempt() -> None:
    declared = scan_form_layout_heading_keys()
    assert "modelo.schema.303.form.authored.page-1.heading" in declared
    assert "modelo.form.column.territorio_navarra" in declared
    assert all(is_form_layout_heading_candidate(key) for key in declared)
    # A physical layout may reuse required application copy as its heading.
    # Such copy retains ordinary catalogue parity rather than becoming an
    # optional form translation merely because the layout references it.
    assert "application.modelo.calculation_summary.value_true" not in declared
    assert "application.modelo.calculation_summary.value_false" not in declared


def test_an_undeclared_heading_shaped_key_is_still_extra() -> None:
    stray = "modelo.schema.303.form.page.not-a-page.heading"
    assert is_form_layout_heading_candidate(stray)
    assert stray not in scan_form_layout_heading_keys()


def test_inter_locale_parity_exempts_only_exact_declared_optional_headings() -> None:
    declared = "modelo.schema.303.form.authored.page-1.heading"
    stray = "modelo.schema.303.form.page.not-a-page.heading"
    result = _audit_locale_file(
        "en.yml",
        {},
        set(),
        codebase_keys=set(),
        all_locale_keys={declared, stray},
        namespace_prefixes=(),
    )
    assert result.inter_locale_missing == (stray,)


def test_the_committed_catalogues_carry_no_extra_heading_keys() -> None:
    manager = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR, extra_src_dirs=(DOCS_SRC_DIR, HARNESS_SRC_DIR))
    result = manager.audit()
    extra = {key for file_result in result.files for key in file_result.codebase_extra if ".form." in key}
    assert extra == set()
