"""Synthetic task kinds, shaped as cadrumo-agent serves them in its declared and served provider catalogs.

The ids are the agent's own vocabulary, because the served schema closes a kind's id to it; each
name and sentence is invented.
"""

from __future__ import annotations


def synthetic_task_kinds() -> list[dict[str, str]]:
    """Return a fresh list of every task kind, in the agent's served order."""
    return [
        {
            "id": "classification",
            "display_name": "Synthetic classification",
            "description": "A synthetic sentence about labelling a record.",
        },
        {
            "id": "extraction",
            "display_name": "Synthetic extraction",
            "description": "A synthetic sentence about reading fields out of a document.",
        },
    ]
