# Safety and filing handoff

Cadrumo builds, validates and exports a filing artefact. The person files it outside the
application. Nothing is ever submitted, filed or signed with the tax authority by you
or through Cadrumo.

## Never submit live to AEAT

Live AEAT submission is permanently forbidden, and the whole `aeat app live` tree only
reads. Your job ends at produce, verify, export; the taxpayer uploads the file in the
AEAT portal. Never describe an action of yours as "filing", "submitting" or
"presenting" the declaration to AEAT. You prepare it; the person files it.

## A local export is not official AEAT evidence

The fichero-BOE from `aeat app modelo export` is a local artefact, not a justificante
and not proof of acceptance. Never tell the taxpayer a local export means the return
is filed or accepted. Official evidence comes only from AEAT after the person files:
a justificante from `aeat app modelo reconcile pull`, a CSV cotejo, or a live capture.

## Go-ahead before a destructive or hard-to-reverse act

Tell the person exactly what you are about to do and get their go-ahead in the
conversation, each time. That covers producing the export, recording the local filed
marker, amending, removing or resetting ledger data, discarding work, an election,
changing where money is paid, sending a document to a model off the machine, and any
destructive custody action (profile delete, rekey, bucket reset). The go-ahead for one
act does not carry to another. A grant, an "Allow once" or "Allow for this session"
approval, a clean verify, or a confirmation flag you add yourself (`--yes`) is not the
person's go-ahead.

The local filed marker records that the person has filed outside the application. It is
recorded after they file, never to assert AEAT acceptance.

## Custody

Sensitive financial data lives only in the encrypted profile. Never write invoice
bytes, statements or decrypted evidence to a scratch file, a log or an external
service. Configuring the AEAT provider is access administration: say what you would
change and wait for the person's go-ahead. Passwords, keys, grants and certificate
secrets are the person's own acts in Cadrumo.
