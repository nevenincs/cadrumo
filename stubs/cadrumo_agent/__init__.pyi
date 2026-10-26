"""Hand-written mirror of the external, unpublished ``cadrumo_agent`` package.

``native/desktop/frontend/scripts/agent_catalog_dump.py`` runs under that
package's own interpreter, so its imports cannot resolve here. This tree
declares only the names that script imports and uses, with the signatures,
fields and members of the agent checkout it was written against; it must be
updated together with that package, and anything the script does not touch is
deliberately absent.
"""

__file__: str
