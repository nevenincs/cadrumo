"""Run the subordinate import checker over a planted sample package."""

from __future__ import annotations

import configparser
from pathlib import Path

from dev.quality.import_binding_inventory import read_modules
from dev.quality.import_check_models import Authority, Finding, ForbiddenContract, ImportOccurrence, RootPackage
from dev.quality.import_dynamic_checks import check_dynamic_imports
from dev.quality.import_occurrences import collect_import_occurrences
from dev.quality.import_record_provenance import RecordTargetProvenance


def check_planted_package(tmp_path: Path, root: Path) -> tuple[list[Finding], tuple[ImportOccurrence, ...]]:
    """Run the real dynamic checks and occurrence collection over ``root`` as package ``sample``."""
    authority = Authority(
        tmp_path,
        tmp_path / "authority.ini",
        configparser.ConfigParser(),
        ("sample",),
        (RootPackage("sample", root),),
        (),
        (ForbiddenContract("boundary", "boundary", ("sample.loader",), ("sample.forbidden",)),),
    )
    modules, findings = read_modules(authority)
    provenance = RecordTargetProvenance(modules)
    check_dynamic_imports(authority, modules, findings, provenance)
    return findings, collect_import_occurrences(authority, modules, provenance)
