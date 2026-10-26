"""Repository-wide prose does not duplicate or alias the Spanish IVA stem.

Sibling of ``cadrumo.tests.test_spanish_iva_stem_conformance``, which owns the
shipped-package Python and non-Python surface. This gate walks prose files
across the development tree and documentation alongside the shipped package,
so it lives with the other repository-wide quality ratchets rather than
inside the package it does not exclusively scan.
"""

from __future__ import annotations

import re

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests.inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DUPLICATED_IVA = re.compile(r"(?<![A-Za-z0-9])iva(?:[._:/-]+|\s+(?:\(\s*)?)iva\b", re.IGNORECASE)
_MIXED_IVA_ALIAS = re.compile(
    r"(?<![A-Za-z0-9])(?:vat[._:/-]+iva|iva[._:/-]+vat)(?=$|[._:/-])",
    re.IGNORECASE,
)
_EXTERNAL_IVA_LOCATOR = re.compile(
    r"(?:https?://\S+|/Sede/\S+|(?:sede\.)?agenciatributaria\.gob\.es/\S+|IVA/IVA_\d{4}/\S+)",
    re.IGNORECASE,
)


def test_authored_repository_prose_uses_iva_without_a_mixed_alias() -> None:
    violations: list[str] = []
    # The development-record trees are deliberately out of scope: they are
    # removable scaffolding, so asserting over their prose would make this
    # shipped-package gate fail on an edit to a document the product does not
    # ship and does not read.
    for root_name in (
        "dev",
        "docs",
        "src/cadrumo",
    ):
        root = REPO_ROOT / root_name
        for path in scan_directory(root, pattern="*", recursive=True):
            if (
                not path.is_file()
                or "_data" in path.parts
                or path.suffix
                not in {
                    ".md",
                    ".po",
                    ".rst",
                    ".toml",
                    ".yaml",
                    ".yml",
                }
            ):
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1,
            ):
                authored_text = _EXTERNAL_IVA_LOCATOR.sub("", line)
                if _DUPLICATED_IVA.search(authored_text) or _MIXED_IVA_ALIAS.search(authored_text):
                    violations.append(f"{relative}:{line_number}:{line.strip()}")
    assert violations == []
