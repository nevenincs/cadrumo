"""Shared fixtures for the dev-side repo-wide ratchet suite.

The ratchets moved here from the package test tree still exercise the shipped
source surface, so the package-root session fixture they were built on is
re-imported rather than re-implemented. pytest registers fixture-marked
objects found in any conftest namespace, so the import alone makes
``source_tree_ast`` available to the tests in this directory.
"""

from __future__ import annotations

from cadrumo.conftest import source_tree_ast

__all__ = ["source_tree_ast"]
