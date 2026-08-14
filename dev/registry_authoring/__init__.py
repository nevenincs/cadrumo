"""One-shot registry authoring-tree migration tooling.

Each module here is a one-shot data migrator: it transcribes a Python-resident
regulatory literal into registry authoring-tree TOML, proves the hydrated
authoring-tree data compares equal to the literal it replaces, and is deleted
once its migration lands. Distinct from ``dev/registry/``, which houses
standing (non-one-shot) registry tooling.
"""
