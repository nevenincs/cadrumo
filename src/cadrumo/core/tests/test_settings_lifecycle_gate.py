"""Growth lifecycle and location provenance for every path-valued setting.

This gate used to carry the classification itself: five hand-maintained
frozensets naming which settings directory rotated, expired, was pruned, grew
by design, or was not an application output at all. A curated list inside a
test module is a poor home for a domain fact -- it drifts from the code it
describes, and it was invisible to anything but this file.

The classification now lives on the taxonomy, where each member declares its
own :class:`~core.storage_taxonomy.StorageLifecycle`, and each path setting
outside the taxonomy declares an
:class:`~core.storage_taxonomy.ExternalPathRole` saying why. Two of the old
assertions therefore hold **by construction** rather than by checking: a path
field cannot be unclassified when classification is a required field on its
declaration, and it cannot be double-classified when it has exactly one
declaration. Re-asserting either here would be asserting that the taxonomy
equals itself. Totality over the settings model -- that every path field *has*
a declaration to read -- is a real property and is owned by
:mod:`~core.tests.test_storage_binding_gate`.

What is left is what the taxonomy cannot tell you, and both remain:

- **Derivation.** A non-exempt output directory must derive its default from
  the storage root, or be an opt-in override with no default at all. The
  eliminated defect is a concrete ``PROJECT_ROOT``-anchored default, which
  resolves inside site-packages on an installed run and puts operator data
  somewhere no override can reach.
- **Provenance by literal.** A shipped module must not build a path out of the
  taxonomy's own vocabulary. Five CLI options once defaulted to
  ``Path("var/cadrumo/filed-declarations")`` and similar; because those
  defaults were not settings, no storage-root override could reach them, and
  regulated filing evidence landed outside the taxonomy *and* outside operator
  control. Its sibling in :mod:`~tests.test_storage_provenance_gate` catches
  the paths built by joining onto the root, which no literal scan can see.

Discovery still enumerates ``Path``-typed **settings fields**, which is the
strictly larger set -- there are more path settings than taxonomy members,
because escapes are settings too. Folding discovery onto taxonomy members
would leave every escape uncovered while the suite stayed green.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ..config import Settings
from ..directory_scan import scan_directory
from ..storage_taxonomy import (
    EXTERNAL_PATH_SETTINGS_FIELDS,
    ROOT_DERIVED_STORAGE_FIELDS,
    STORAGE_ROOT_SETTINGS_FIELD,
    STORAGE_TAXONOMY,
)
from ._settings_path_fields import path_typed_settings_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _exempt_fields() -> frozenset[str]:
    """Path settings that are not application-chosen generated output.

    The declared escapes -- bundled read-only corpora, an operator-supplied
    credential, an external executable, an operator-directed dump -- plus the
    storage root itself, whose categorised children carry the lifecycles.
    """
    return frozenset(EXTERNAL_PATH_SETTINGS_FIELDS) | {STORAGE_ROOT_SETTINGS_FIELD}


def test_every_non_exempt_output_dir_derives_from_the_state_root() -> None:
    """Derived from the root, or an opt-in override -- never a concrete default.

    A concrete ``PROJECT_ROOT``-anchored default resolves inside site-packages
    on an installed run, so durable state lands where no operator override can
    reach it and no uninstall will find it.
    """
    discovered = path_typed_settings_fields(Settings)
    assert discovered, "path-field discovery found nothing, so this asserts nothing"

    offenders: list[str] = []
    for name in sorted(discovered - _exempt_fields()):
        field_info = Settings.model_fields[name]
        if name in ROOT_DERIVED_STORAGE_FIELDS or field_info.default is None:
            continue
        offenders.append(f"{name} (default {field_info.default!r})")
    assert not offenders, (
        f"non-exempt output setting(s) with a concrete default that does not derive from the "
        f"storage root: {offenders}. Declare the field's taxonomy member so settings validation "
        "computes its default from the root, or give it a None default and make it an opt-in "
        "override -- a concrete anchored default is the eliminated defect"
    )


def test_the_exempt_set_is_exactly_the_declared_escapes_and_the_root() -> None:
    """Exemption is a declaration, never a frozenset a test module curates.

    The five hand-maintained classes this gate used to carry are gone. The
    assertion that replaced them is that exemption has one source: a field is
    exempt because it declared an ``ExternalPathRole`` with a reason, or
    because it is the anchor. A field cannot become exempt by being added to a
    list here.
    """
    exempt = _exempt_fields()
    assert STORAGE_ROOT_SETTINGS_FIELD in exempt
    assert exempt - {STORAGE_ROOT_SETTINGS_FIELD} == frozenset(EXTERNAL_PATH_SETTINGS_FIELDS)
    assert not exempt & set(field for field in ROOT_DERIVED_STORAGE_FIELDS), (
        "a field cannot be both exempt from generated-output lifecycle and derived as one"
    )


# --------------------------------------------------------------------- #
# Operator-data locations come from the taxonomy, never from a literal   #
# --------------------------------------------------------------------- #

_TAXONOMY_VOCABULARY = frozenset(
    # Every segment the declared taxonomy owns, plus the retired `var` prefix
    # and the product's own directory name. A path literal built from this
    # vocabulary is naming an operator-data location, which only the taxonomy
    # may do. Read from the declaration rather than a parallel table, so a new
    # member's leaf name is protected the moment it is declared.
    {segment for location in STORAGE_TAXONOMY.values() for segment in location.subpath.split("/")} | {"var", "cadrumo"},
)

_PRODUCTION_ROOT = Path(__file__).resolve().parents[2]

_LITERAL_OWNERS = frozenset(
    {
        # The taxonomy itself and the settings modules that declare its fields:
        # these MUST carry the literals, because they are what every other
        # module resolves through.
        "core/_storage_taxonomy.py",
        "core/config.py",
        "core/_config_llm_fields.py",
        "core/_config_integration_fields.py",
        "core/_config_state_root.py",
    },
)


def _production_modules() -> list[Path]:
    """Every shipped module, excluding test trees and the taxonomy owners."""
    modules = []
    for path in scan_directory(_PRODUCTION_ROOT, pattern="*.py", recursive=True):
        rel = path.relative_to(_PRODUCTION_ROOT).as_posix()
        if "/tests/" in f"/{rel}" or rel.startswith("tests/") or rel in _LITERAL_OWNERS:
            continue
        modules.append(path)
    return modules


def test_the_vocabulary_covers_the_declared_leaf_names() -> None:
    """The vocabulary is derived, so it must actually contain what it protects.

    Without this the scan below could silently degrade to an empty vocabulary
    and pass on every module while protecting nothing.
    """
    assert {"filed-declarations", "justificantes", "keystore", "buckets"} <= _TAXONOMY_VOCABULARY


def test_no_production_module_names_an_operator_data_location_by_literal() -> None:
    """Operator-data paths resolve through the taxonomy, never a hardcoded literal.

    The sibling assertions above only see fields that ARE settings, so they are
    blind to the failure this one exists for: a path that was never enrolled at
    all. Naming ``filed-declarations`` or ``var`` in a multi-segment literal
    means a module is deciding where operator data lives, which is the
    taxonomy's job.
    """
    offenders: list[str] = []
    pattern = re.compile(r'Path\(\s*"([^"]*/[^"]*)"')
    for module in _production_modules():
        rel = module.relative_to(_PRODUCTION_ROOT).as_posix()
        for literal in pattern.findall(module.read_text(encoding="utf-8")):
            segments = {segment for segment in literal.split("/") if segment}
            if segments & _TAXONOMY_VOCABULARY:
                offenders.append(f"{rel}: Path({literal!r})")
    assert not offenders, (
        "shipped modules naming an operator-data location by literal instead of resolving it "
        "through the storage taxonomy (declare a StorageCategory and resolve it with "
        f"storage_path): {offenders}"
    )
