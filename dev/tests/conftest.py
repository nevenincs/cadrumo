"""Repo-wide ratchets use ``source_tree_ast`` from the root pytest plugin.

No fixture is forwarded here: repository-root plugin discovery exposes it to
this tree alongside every other package test.
"""
