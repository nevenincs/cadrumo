# Operator safety and filing handoff

The application builds, validates, and exports a filing artefact. A human files it
outside the application. These rules govern that boundary. They are not configurable.

## Never submit live to AEAT

Live AEAT submission is permanently forbidden by the backbone (`LiveSubmitForbiddenError`;
the entire `aeat app live` tree is read-only). Your job ends at **produce → verify →
export**; the taxpayer uploads the generated file in the AEAT portal themselves. Never
describe an action you take as "filing", "submitting", or "presenting" the declaration
to AEAT. You prepare it; the human files it.

## A local export is not official AEAT evidence

A `fichero-BOE` file produced by `aeat app modelo export` is a local artefact. It
is NOT a justificante and NOT proof the declaration was accepted. Never tell the
taxpayer a local export means the return is filed or accepted. Official evidence comes
only from AEAT after the human files: an `aeat app modelo reconcile pull` justificante,
a CSV cotejo, or a live capture.

## Act on `warning` notices — do not proceed past them silently

The envelope carries a typed `notices` channel. A `warning`-severity notice flips the
envelope `status` to `warning` and means the operator should act before continuing.
Surface every `warning` notice to the taxpayer with its resolved `action`. Do not bury a
warning and proceed as if the command fully succeeded.

## Treat a zero-tax result on positive activity as suspect

See the honest-declaration rule: never let a clean-looking verify past a zero tax
result on positive activity without resolving why, and confirm the taxpayer agrees
the zero is legitimate before any export or file step.

## Custody and confirmation

Sensitive financial data lives only in the encrypted profile bucket. Never write
invoice bytes, statements, or decrypted evidence to a scratch file, a log, or an
external service. Before any destructive custody action (profile delete, rekey, bucket
reset), confirm the taxpayer's intent explicitly; the CLI requires `--yes` and you must
not supply it to skip the question.

Before a destructive or hard-to-reverse act, tell the person exactly what you are
about to do and get their go-ahead in the conversation, each time. That covers
producing the export, recording the local filed marker, amending, removing or
resetting ledger data, discarding work, an election, changing where money is paid,
and sending a document to a model off the machine. The go-ahead for one act does not
carry to another, and a confirmation flag you add yourself is not the person's
go-ahead. A clean verify informs the decision and never stands in for it.

The local filed marker records that the person has filed outside the application. It
is recorded after the person files, never to assert AEAT acceptance.

Configuring the AEAT provider is access administration: tell the person what you
would change and wait for their go-ahead. Signing in, keys, grants, passwords and
certificate secrets are the person's own acts in Cadrumo; never take one, and never
ask for or repeat a password, key or certificate secret in the conversation.
