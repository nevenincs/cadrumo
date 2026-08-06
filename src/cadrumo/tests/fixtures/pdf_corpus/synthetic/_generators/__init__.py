"""Per-modelo synthetic PDF generators.

Each concrete ``modelo_N_generator.py`` module exposes a
``generate(params) -> tuple[bytes, GroundTruth]`` function. The shared
rendering primitives live in ``_generator_shared.py``.
"""
