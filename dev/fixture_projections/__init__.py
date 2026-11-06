"""The registry of generated fixture projections, their digest stamps and the seeding verbs.

Each family names the producer that writes a projection, the repository inputs
it reads, where its outputs land and the producer's own read-only check. A
digest stamp records what the outputs were produced from, so freshness is a
content comparison and never a modification time.
"""
