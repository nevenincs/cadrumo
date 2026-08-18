"""Deterministic export-fragment generation pipeline.

Render -> validate -> publish -> check, over three authored authorities
(semantic map, render profile, parsed record design), emitting the generated
``export/`` trees under ``src/cadrumo/_data/registry/``.
"""

from ._export_tree import render_complete_export_tree
from ._tree_check import check_generated_export_tree
from ._tree_publication import publish_validated_generated_export_tree
from ._tree_validation import validate_generated_export_tree

__all__ = [
    "check_generated_export_tree",
    "publish_validated_generated_export_tree",
    "render_complete_export_tree",
    "validate_generated_export_tree",
]
