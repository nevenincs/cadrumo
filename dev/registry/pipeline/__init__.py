"""Deterministic export-fragment generation pipeline.

Render -> validate -> publish -> check, over three authored authorities
(semantic map, render profile, parsed record design), emitting the generated
``export/`` trees under ``src/cadrumo/_data/registry/``.
"""
