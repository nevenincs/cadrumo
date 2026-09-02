"""Event-keyed continuity planning for the Modelo 100 anexo-A AEIP family.

The anexo-A "acontecimientos de excepcional interés público" table repacks its
casilla ids every filing year while every event row shares one
``semantic_role``, so neither the id nor the role identifies a programme. The
programme title AEAT prints in the label does, which is why this family's
continuity chains are keyed on the event:
``irpf.aeip.<event-slug>.aplicado``.

This package extracts the family from the registry authoring tree, derives
those chain ids, and plans the stamps and evolution records a grounding
campaign would author. It never writes into the registry, and it fails closed
on the shapes that need a legal-identity judgment rather than guessing them.

Run via ``python -m dev.registry.aeip inventory`` for the event matrix,
``check`` for the open adjudications (exits non-zero while any remain), or
``plan`` for the chain plan.

Major declarations:

* :func:`~dev.registry.aeip.manager.extract_occurrences` — read the family.
* :func:`~dev.registry.aeip.manager.plan_chains` — plan chains and records.
* :class:`~dev.registry.aeip.adjudications.AdjudicationSet` — the recorded
  identity judgments the planner reads instead of guessing.
"""
