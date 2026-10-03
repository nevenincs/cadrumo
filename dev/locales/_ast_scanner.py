"""Parse and coordinate locale-key discovery over one source corpus."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.logging import get_logger
from dev._paths import UTF_8
from dev.quality.unread_inputs import report_unread

from ._ast_key_calls import _extract_error_constructor_keys
from ._ast_key_flows import _extract_locale_constant_keys
from ._ast_key_namespaces import _extract_concat_prefixes, _extract_fstring_prefixes
from ._ast_key_wrappers import (
    _extract_positional_translation_key_arguments,
    _membership_guard_keys,
    _translated_value_names,
    _translation_key_parameter_positions,
    _translation_wrapper_names,
)

_log = get_logger(__name__)


_UTF_8: Final[str] = UTF_8


_UNSCANNED_MODULE_NAMES: frozenset[str] = frozenset({"test_parity.py", "manager.py", "_ast_scanner.py"})
"""Modules whose dotted string literals describe the scan itself, not call sites."""


def declares_locale_keys(module: Path) -> bool:
    """Return True when ``module`` is a source file the key scan reads.

    Shared by the tree walk below and by the change-scoped scan, so a module the
    tree ignores can never be judged as an added or orphaned call site by the
    other. Two independent copies of this predicate would let one scanner see a
    key the other cannot.
    """
    if module.name in _UNSCANNED_MODULE_NAMES:
        return False
    return not (module.name.startswith("test_") or module.name.startswith("_test_") or "/tests/" in module.as_posix())


def _parse_module_source(source: str, filename: str) -> ast.Module | None:
    """Parse ``source``, debug-logging and swallowing a syntax failure."""
    try:
        return ast.parse(source, filename=filename)
    except SyntaxError as exc:
        _log.debug("locale ast scan: parse failure %s (%s)", filename, exc)
        return None


def scan_source_text(source: str, *, filename: str) -> set[str]:
    """Emit the concrete dotted locale keys one module's source text declares.

    The text form of :func:`scan_source_tree`, for callers holding source text
    directly rather than a working-tree file -- a synthetic specimen in a test,
    for instance. Unparseable source yields an empty set, exactly as the tree
    walk skips it.
    """
    tree = _parse_module_source(source, filename)
    if tree is None:
        return set()
    return _extract_error_constructor_keys(tree) | _extract_locale_constant_keys(tree)


def scan_namespace_markers_in_text(source: str, *, filename: str) -> set[str]:
    """Emit the dynamic-namespace markers one module's source text declares."""
    tree = _parse_module_source(source, filename)
    if tree is None:
        return set()
    return _extract_fstring_prefixes(tree) | _extract_concat_prefixes(tree)


def _iter_parseable_python_modules(root: Path) -> Iterator[tuple[Path, ast.Module]]:
    """Yield ``(path, tree)`` pairs of parseable Python ASTs under ``root``.

    Every module this cannot read is ANNOUNCED. Three silences stacked here: a
    lenient decode dropped undecodable bytes so the text scanned was not the
    file, a read failure was logged at debug level, and a parse failure was
    swallowed the same way. All three shrink the set of DECLARED keys, and a
    key that is never seen declared looks unused - which is how a cleanup sweep
    deletes a live translation.

    That is not hypothetical for this scanner: four unknown key factories once
    put seventy-seven catalogue entries on the deletion path. Measured now:
    2119 modules declare locale keys, none undecodable and none unparsable.
    """
    yield from _iter_parseable_python_modules_from_roots((root,))


def _iter_parseable_python_modules_from_roots(roots: Iterable[Path]) -> Iterator[tuple[Path, ast.Module]]:
    """Yield parseable modules from several roots and report unread files once.

    A manager may scan the package and one or more adjacent source roots as one
    logical corpus. Keeping those roots in one parse pass is both faster and
    more accurate for the cross-module wrapper/signature analysis below. The
    per-root public scanner retains its historical behaviour by delegating to
    this helper with a one-item tuple.
    """
    skipped: list[str] = []
    for root in roots:
        for module in iter_directory(root, pattern="*.py", recursive=True):
            if not declares_locale_keys(module):
                continue
            try:
                source = module.read_text(encoding=_UTF_8)
            except (OSError, UnicodeDecodeError) as exc:
                # Files can disappear between directory enumeration and this
                # read while another process edits the checkout. Treat that as
                # an unread inventory item, never as a scan crash.
                skipped.append(f"{module}: {type(exc).__name__}: {exc}")
                continue
            tree = _parse_module_source(source, str(module))
            if tree is None:
                skipped.append(f"{module}: does not parse")
                continue
            yield module, tree
    report_unread(
        "locale ast scan",
        "the keys they declare are absent from this scan and would look unused to a cleanup sweep",
        skipped,
    )


def scan_source_trees(roots: Iterable[Path]) -> set[str]:
    """Scan several source roots as one cross-module locale-key corpus.

    Parsing and indexing happen once for the combined roots. This matters for
    the CLI, whose package, documentation, and harness roots all contribute to
    one key set and therefore do not need independent scans.
    """
    modules = list(_iter_parseable_python_modules_from_roots(roots))
    key_positions = _translation_key_parameter_positions(modules)
    wrappers = _translation_wrapper_names(modules)
    translated_names = _translated_value_names(modules, wrappers)
    findings: set[str] = set()
    for _module, tree in modules:
        findings.update(_extract_error_constructor_keys(tree, wrappers))
        findings.update(_membership_guard_keys(tree, translated_names))
        findings.update(_extract_locale_constant_keys(tree, wrappers))
        findings.update(_extract_positional_translation_key_arguments(tree, key_positions))
    return findings


def scan_source_tree(root: Path) -> set[str]:
    """Walk ``root`` for `.py` files and emit concrete dotted locale keys.

    Concrete keys are literal translation keys passed to error
    constructors (positional first argument or ``message_key=`` kwarg).
    Dynamic namespaces (f-string and concatenation patterns) are
    returned by :func:`scan_namespace_markers` and routed through a
    separate parity check that asserts at least one concrete locale
    entry exists under each declared namespace prefix.
    """
    return scan_source_trees((root,))


def scan_namespace_markers(root: Path) -> set[str]:
    """Walk ``root`` for `.py` files and emit dynamic-namespace markers.

    A namespace marker is a ``<prefix>.*`` string identifying a
    family of keys whose tail is computed at runtime (f-string
    interpolation or string concatenation). Each marker passes the
    parity check when at least one concrete locale key starts with
    its prefix.
    """
    findings: set[str] = set()
    for _module, tree in _iter_parseable_python_modules(root):
        findings.update(_extract_fstring_prefixes(tree))
        findings.update(_extract_concat_prefixes(tree))
    return findings
