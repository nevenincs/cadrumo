"""Structural gate: the submitted-file capture never READS bytes from disk.

``capture_submitted_file_artefact`` (``_declarations_fetch.py``) used to pull
a click-triggered Playwright download's bytes off the filesystem
(``Path(path).read_bytes()`` on the path ``download.path()`` exposed) --
reading that file was a breach of
``sensitive-financial-data-secure-storage-only``.

This is one of TWO layers closing that breach, and this module proves only
the narrower one:

1. **This function never reads a download via a filesystem path.** It reads
   ``download.url``, best-effort cancels the browser-side transfer, and
   re-fetches the SAME URL in-memory through the authenticated
   ``context.request`` API -- the identical shape ``capture_row_pdf_artefact``
   already uses for the cotejo PDF. Neither byte-for-byte output nor
   exception behaviour distinguishes "read from the canceled download's temp
   path" from "re-fetched via context.request": both mechanisms return the
   same bytes for a successful download, so THIS property is a MECHANISM
   property, not an I/O-observable behavioural one, and can only be pinned by
   inspecting the mechanism -- i.e. structurally. This module is therefore a
   structural (AST/source) gate, not a behavioural test.

2. **Chromium never persists the download's bytes to disk in the first
   place** -- the stronger, disk-write-side property this module does NOT
   cover. ``BrowserSession._build_context_kwargs`` pins
   ``accept_downloads=False`` on every context this adapter creates, closing
   the browser-engine-level write this function's own careful read-avoidance
   cannot reach (measured: Chromium starts writing an attachment's bytes to
   its own temp folder the instant a download begins, and ``.cancel()`` only
   stops an in-flight transfer -- it does not un-write bytes already
   streamed). That property IS behaviourally observable (Playwright's own
   ``download.path()`` raises when a context refuses downloads) and is
   verified by a REAL, non-structural test:
   ``browser/tests/test_accept_downloads_disabled.py``.

Read both files to see the full closed picture; neither alone proves "no
taxpayer bytes ever touch disk" -- together they do.

See Also:
    :func:`~adapters.outbound.aeat.sede.declarations_fetch.capture_submitted_file_artefact`
        The guarded function.
    :func:`~adapters.outbound.aeat.sede.declarations_fetch.capture_row_pdf_artefact`
        The sibling function whose in-memory fetch shape this gate expects
        ``capture_submitted_file_artefact`` to mirror.
    :meth:`~adapters.outbound.aeat.browser.BrowserSession._build_context_kwargs`
        Where ``accept_downloads=False`` closes the disk-write-side property
        this module does not cover.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TARGET_FUNCTION = "capture_submitted_file_artefact"


def _module_path() -> Path:
    """Returns the guarded module's path, resolved relative to this file."""
    # .../sede/tests/test_declarations_submitted_file_no_disk_read.py -> .../sede/_declarations_fetch.py
    return Path(__file__).resolve().parents[1] / "_declarations_fetch.py"


def _module_tree() -> ast.Module:
    path = _module_path()
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name!r} was not found in {_module_path()}")


def _call_attr_names(node: ast.AST) -> list[str]:
    """Returns every attribute name invoked as a call within ``node``.

    Collects the ``attr`` of every ``ast.Attribute`` used as the ``func`` of
    an ``ast.Call`` anywhere in ``node``'s subtree, e.g. ``download.path()``
    yields ``"path"`` and ``context.request.get(...)`` yields ``"get"``.
    """
    names: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            names.append(sub.func.attr)
    return names


class TestModuleImportsNoFilesystemPathType:
    """The module no longer needs ``pathlib.Path`` for artefact bytes.

    A ``Path``-based disk read is the exact defect this gate closes; the
    module dropped the import as part of the fix. A future re-introduction
    of ``Path(...).read_bytes()`` almost certainly needs to re-import
    ``Path``, so this whole-module check is a cheap, low-maintenance
    tripwire that complements the function-scoped checks below.
    """

    def test_pathlib_path_is_not_imported(self) -> None:
        tree = _module_tree()
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "pathlib":
                imported_names.extend(alias.name for alias in node.names)
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names if alias.name in {"pathlib", "pathlib.Path"})
        assert imported_names == [], (
            f"{_module_path().name} imports {imported_names} from pathlib; "
            f"{_TARGET_FUNCTION} must not read taxpayer bytes from a filesystem path "
            "(sensitive-financial-data-secure-storage-only)"
        )


class TestSubmittedFileCaptureNeverReadsTheDownloadedPath:
    """``capture_submitted_file_artefact`` fetches bytes in-memory, never from disk."""

    def test_no_download_path_call(self) -> None:
        """The function must never call ``download.path()`` (or ``.save_as()``)."""
        function = _find_function(_module_tree(), _TARGET_FUNCTION)
        offending = {"path", "save_as"} & set(_call_attr_names(function))
        assert offending == set(), (
            f"{_TARGET_FUNCTION} calls {sorted(offending)}; either materialises the "
            "downloaded file's path or explicitly saves it to disk, both of which "
            "reintroduce a taxpayer-bytes-to-disk breach"
        )

    def test_no_read_bytes_call(self) -> None:
        """The function must never call ``.read_bytes()`` (the disk-read primitive)."""
        function = _find_function(_module_tree(), _TARGET_FUNCTION)
        assert "read_bytes" not in _call_attr_names(function), (
            f"{_TARGET_FUNCTION} calls .read_bytes(); this is the exact disk-read primitive the fix removes"
        )

    def test_download_is_cancelled(self) -> None:
        """Positive control: the browser-side transfer is proactively cancelled.

        Without this assertion the two tests above would be satisfiable by
        simply deleting the fetch logic entirely -- a vacuous pass. Pinning
        that ``.cancel()`` is actually called proves the mechanism this gate
        expects is present, not merely that the forbidden one is absent.
        """
        function = _find_function(_module_tree(), _TARGET_FUNCTION)
        assert "cancel" in _call_attr_names(function), (
            f"{_TARGET_FUNCTION} never calls .cancel(); the browser-triggered "
            "download must be proactively cancelled once its URL is known"
        )

    def test_bytes_are_fetched_through_the_request_context(self) -> None:
        """Positive control: bytes come from an authenticated in-memory GET.

        Mirrors the shape ``capture_row_pdf_artefact`` already uses for the
        cotejo PDF fetch (``context.request.get(...)`` then ``.body()``).
        """
        function = _find_function(_module_tree(), _TARGET_FUNCTION)
        attr_calls = _call_attr_names(function)
        assert "get" in attr_calls, (
            f"{_TARGET_FUNCTION} never calls .get(...); it must re-fetch the "
            "download's URL through the authenticated request context instead of "
            "reading Playwright's own temp download file"
        )
        assert "body" in attr_calls, (
            f"{_TARGET_FUNCTION} never calls .body(); the fetched response bytes "
            "must be read from the in-memory HTTP response, not a filesystem path"
        )

    def test_receives_a_browser_context_parameter(self) -> None:
        """The function must accept a ``context`` parameter to reach ``context.request``.

        A regression that silently drops the parameter (e.g. an edit that
        reverts the call site back to ``page``-only) would leave the
        function unable to construct the in-memory fetch at all.
        """
        function = _find_function(_module_tree(), _TARGET_FUNCTION)
        parameter_names = {arg.arg for arg in function.args.kwonlyargs}
        assert "context" in parameter_names, (
            f"{_TARGET_FUNCTION} no longer accepts a `context` keyword parameter; "
            "the in-memory fetch requires `context.request`"
        )
