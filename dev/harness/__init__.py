"""Outer-serial harness proofs, held out of every parallel lane.

A member here spawns a real child pytest over the whole first-party corpus, so
it must never run inside a worker pool -- nesting one pool in another is the
failure this directory exists to avoid. No lane sweeps this package by path;
``just test-harness`` names each member explicitly and runs it with ``-n0``.
"""
