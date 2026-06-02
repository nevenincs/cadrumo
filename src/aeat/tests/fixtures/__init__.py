"""Test-fixture package root.

Makes the fixture subtrees proper packages so that identically-named test
modules (e.g. several ``test_generate.py``) import under unique dotted paths
under pytest's prepend import mode, rather than colliding on basename.
"""
