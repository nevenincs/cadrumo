"""Per-modelo synthetic PDF generators (EPIC #305 cluster C scaffolding).

Each concrete ``modelo_N_generator.py`` module (landed by clusters D and
F) exposes a ``generate(params) -> tuple[bytes, GroundTruth]`` function.
The shared rendering primitives live in ``_generator_shared.py``.
"""
