"""Opt-in local-inference document reading, gated behind the ``llm`` extra.

This subpackage holds the probabilistic half of document ingestion: reading a
document that carries **no** structured record, by rasterising it on-host and
handing the pages to a local model. Everything exact -- the EN16931 and
Facturae readers -- stays in the deterministic core under
``adapters/inbound/einvoice``, because parsing a document that already carries
a machine-readable record is not inference and must not be gated behind an
optional extra.

**Why a subpackage rather than a sibling top-level package.** Every AST gate
enforcing secure-storage-only persistence derives its corpus from
``src/cadrumo``, and ``.importlinter`` sets ``root_package = cadrumo``. Code in
a sibling package is invisible to all of them -- which would move the code that
handles decrypted invoice bytes to the one place in the repository where the
gates forbidding temp files and plaintext side stores do not look. That inverts
the goal: the most sensitive code would become the least supervised. Staying
inside the scanned root does not grant that supervision automatically; it makes
it *reachable*, which is why this package is explicitly enumerated in the
sensitive-surface list and explicitly enrolled in the layering contract rather
than assumed to inherit either.

**The encryption ruling, and the line it does not cross.** In-memory reading,
rasterising and local inference need no encryption and no consent gate: a user
who points a local tool at a file has by that action accepted the file will be
processed, and the secure-storage rule binds persistence rather than
processing. The exemption covers PROCESSING ONLY. Anything durable -- an
extracted-document cache, a rasterised page, a debug dump, a temp file, an
extracted field draft -- returns to the core's encrypted secure storage. This
package therefore holds no repository handle, constructs no ``AttachmentStore``
and imports nothing from ``adapters.persistence``.

**Layer position.** Adapter tier: it receives already-resolved bytes and
returns a typed payload, so application code may call it while it may not reach
inward past its own tier.

Consumers import from the owning module -- :mod:`client`, :mod:`models`,
:mod:`suggestions`, :mod:`column_role_mapping`, :mod:`supply_nature_proposal`,
:mod:`consent`, :mod:`evidence_draft_text`, :mod:`evidence_draft_vision`,
:mod:`invoice_field_grounding`, :mod:`retention`, :mod:`providers`,
:mod:`errors` -- rather than from this package root, which is inert.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
"""Inert namespace: every contract is reached at the module that defines it."""
