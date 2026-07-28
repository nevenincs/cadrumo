---
tags:
  - '#audit'
  - '#open-decisions-and-operator-gates'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - "[[2026-07-25-open-decisions-and-operator-gates-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace open-decisions-and-operator-gates with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `open-decisions-and-operator-gates` audit: `operator gate verification: the repository is private, S09 is discharged, and the R6 marketplace supersession never shipped`

## Scope

The six open rows of the operator-gates plan, each of which declares itself
operator-only, were measured against live account state and against the tree at
HEAD rather than accepted as written. The question asked of every row was not
"has the operator done this yet" but "is the row's own premise still true, and
is any part of it dischargeable by measurement". Three rows survived that test
unchanged, one is discharged outright, one is superseded by a later accepted
record whose implementation is missing, and every row premised on the repository
having been published rests on a premise that is false today.

Measurements were taken 2026-07-28 against the `nevenincs` account with a token
carrying `repo` and `workflow` scope, and against the working tree at HEAD.

## Findings

### repository-is-private | critical | every row premised on publication rests on a false premise

The plan states in S09 that a release-time coupling "did not exist before the
repository went public", and in S10 that secret scanning was "enabled on this
repository at the moment it went public with push protection". Neither is true
today. The repository reports `visibility: private`. The secret-scanning alerts
endpoint returns HTTP 404 with "Secret scanning is disabled on this repository".
The branch-protection endpoint returns HTTP 403 with "Upgrade to GitHub Pro or
make this repository public to enable this feature", which is the response for a
private repository on a plan without protected branches.

This does not contradict the closure of S05. That row asked the operator to
decide whether to push the local commit backlog, and the closing record states
the operator instructed the push and it executed. The push did land; the
repository it landed in is private. What never became true is the *publication*
premise that S09 and S10 attach to. The two sibling distribution repositories
are genuinely public, which is the likely source of the confusion: the
marketplace and the tap are public, the product repository is not.

The consequence is that neither S09 nor S10 can be discharged the way its own
text describes, and that both are blocked on a decision nobody has recorded:
whether this repository is to be made public at all.

### s09-no-default-branch-write | medium | the conditional antecedent is false, so the row is discharged

S09 is conditional: confirm branch protection admits the publish workflow *if
any release-time write to that branch survives the final topology*. No such
write survives. The publish workflow performs exactly three pushes, at the
Scoop, Homebrew, and marketplace steps of `.github/workflows/publish-release.yml`,
and each runs as `git -C "$work" ... push` inside a clone of a *sibling*
repository, never the product repository. Release artefacts are attached with
`gh release create` and `gh release upload`, which write release objects and not
branch commits; the job's `contents: write` permission exists for exactly that.
The documentation leg in `.github/workflows/docs-publish.yml` declares
`contents: read`, and its deploy tooling refuses to run under `CI` or
`GITHUB_ACTIONS` at all. A search for `git push` across every workflow returns
nothing.

The antecedent being false, the row is discharged on its own terms. The finding
is reinforced rather than weakened by the private-repository state: branch
protection cannot presently be configured on this repository even if it were
wanted.

### r6-supersession-producer-missing | high | the accepted marketplace retirement is a silent no-op at HEAD

S07 asks the operator to delete the stale pre-rename plugin entry by hand. That
row is superseded: ruling R6 of the accepted canonical-release-pipeline record
retires the stale identity by *declared supersession*, where the cohort manifest
carries a list of plugin names the product retires and the merge tool removes
them under the unchanged ownership rule. The consumer half of that ruling
shipped. `dev/packaging/marketplace_publish.py` reads a `supersedes` key,
validates it as a list of non-empty names, refuses a manifest that both claims
and supersedes the same name, refuses superseding a plugin published by a
sibling product, and carries a preflight that refuses when a retired identity is
still live in the published index.

The producer half did not ship. `_marketplace_manifest_document()` in
`src/cadrumo/agent/_workspace.py` emits exactly `name`, `description`, `owner`,
and `plugins`. It emits no `supersedes` key and no `published_by` key. No other
site in the tree writes either. The cohort therefore never declares that it
retires the prior identity, the merge tool's sibling-protection preserves that
subtree exactly as the ruling's own problem statement describes, and the
preflight passes silently because it can only check retirements that were
declared.

The failure mode is the dangerous one: not a loud refusal but a silent no-op.
The authorising plan is marked complete, so the ruling reads as in force while
HEAD retains the pre-ruling behaviour, and the first publication would carry the
stale identity forward untouched.

### s06-secret-migration-live | medium | the rename is half-applied and one secret is now orphaned

The row is confirmed accurate and remains blocked. The workflow reads
`secrets.HOMEBREW_TAP_TOKEN` at the Scoop and Homebrew steps and
`secrets.CLAUDE_MARKETPLACE_TOKEN` at the marketplace step. The repository holds
`CADRUMO_HOMEBREW_TAP_TOKEN`, `CADRUMO_MARKETPLACE_TOKEN`, and
`CADRUMO_SCOOP_BUCKET_TOKEN`. The variable half of the same rename already
landed: `HOMEBREW_TAP_REPO` and `CLAUDE_MARKETPLACE_REPO` both exist under their
account-scoped names, so the secrets are the only un-migrated half.

Two observations sharpen the row. Only two secrets are needed, not three: the
Scoop bucket push reads `HOMEBREW_TAP_TOKEN` and `HOMEBREW_TAP_REPO`, because
the account serves both channels from one shared distribution repository. That
makes `CADRUMO_SCOOP_BUCKET_TOKEN` orphaned — no workflow reads it under either
the old or the new name. Secret values are never retrievable through the API, so
no agent can copy the existing values across; this row is genuinely
operator-only.

### s08-gate-refuses-as-designed | low | the arming variable is unset and Gate 1 correctly refuses

Confirmed as written. The repository declares only `HOMEBREW_TAP_REPO` and
`CLAUDE_MARKETPLACE_REPO`; `CADRUMO_PUBLISH_ENABLED` is absent, so the guard at
the head of the publish workflow refuses. This is the designed state and the
accepted records keep publication held. No agent may arm it.

### s04-custody-verification-unobservable-by-agents | medium | the block is structural, not a scheduling delay

Confirmed as written and confirmed unobservable from any agent session. The
custody-bound cases require an interactive desktop logon; an agent session
reaching the host over a network logon cannot supply the credential the platform
keychain demands, and the failure it produces is indistinguishable from a broken
vault. The row is correct to mark itself a recurring obligation rather than a
one-time sign-off, because it re-opens on any change to login, logout, resume,
or session-key custody.

### full-history-credential-scan-clean | medium | no credential of the scanned classes was ever committed

The substantive question behind S10 was answered locally, independently of
GitHub. Every object in the repository was streamed and matched against seven
credential families: GitHub tokens across all five prefixes and the fine-grained
form, AWS access-key ids, Anthropic keys, Slack tokens, Google API keys, Stripe
live keys, and PEM private-key headers. The result is zero matches across the
full object graph of a 512 MiB repository.

The instrument was validated before the result was trusted, because an empty
result from a scan that never ran is indistinguishable from a clean history. A
positive control carrying a synthetic GitHub token and a synthetic AWS key was
passed through the identical expression and both were caught, and the object
stream was confirmed to produce content. The empty result is therefore evidence
rather than an absence of evidence.

The limit of that evidence must be stated plainly: this instrument matches seven
structural families, while the platform scanner it stands in for carries several
hundred partner patterns with issuer-side validation. A clean local scan lowers
the risk materially but does not discharge the row as written.

### branch-protection-unavailable-on-this-plan | high | the protection directive cannot be satisfied while the repository is private

The operator's standing requirement is that the default branch be protected.
That cannot be configured today. Both mechanisms refuse: the classic
branch-protection endpoint returns HTTP 403 and the newer repository-rulesets
endpoint returns HTTP 403, each with the identical message directing the caller
to upgrade to GitHub Pro or make the repository public. This is a plan-tier
restriction on private repositories, not a permissions problem with the token,
which carries `repo` and `workflow` scope and administers the repository
successfully elsewhere in this same audit.

The requirement and the decision to remain private are therefore in direct
tension, and only three resolutions exist: raise the account tier, publish the
repository, or accept that the default branch carries no server-side protection
for now. Nothing an agent can do closes this gap.

### available-hardening-partly-already-in-force | low | the token posture is sound and one detection gap was closed

What can be configured on a private repository at this tier was measured. The
Actions token posture is already correct and needs no change: the default
workflow permission is `read` and workflows cannot approve pull requests. That
default is safe to keep because every workflow in the tree declares its own
top-level permissions block, so no job silently depends on an ambient write
token.

One genuine gap was found and closed during this audit: Dependabot vulnerability
alerts were disabled and are now enabled, verified by re-reading the endpoint.
Two further controls were deliberately left alone. Automated security fixes were
not enabled because they open pull requests autonomously, which sits awkwardly
against the operator's stated intent to be the one who opens branches, and that
intent needs clarifying first. Required SHA pinning for Actions was not enabled
because every workflow currently references actions by tag, so turning it on
would break each of them until they are pinned; it is worth doing as its own
scoped change, not as a side effect of this audit.

### r6-declaration-fails-the-strict-validator | critical | the ruled mechanism cannot be implemented where it says to implement it

Implementation of the producer half was authorised and attempted, and it does
not work as specified. The ruling puts the supersession declaration in the
cohort's marketplace manifest, and the merge tool carries that manifest into the
published index verbatim. That manifest is governed by a live external oracle:
the generator's own source comments record that every field it emits is one
`claude plugin validate --strict` accepts, and a shipped test runs that oracle
whenever the CLI is present.

The conflict was measured rather than assumed. Two real marketplace trees were
generated from the production emitter, identical except that one carried
`supersedes` listing the retired identity. Validated unpiped so the exit status
is the command's own: the control passes `--strict` with exit 0, and the variant
fails with exit 1, reporting `Unknown field 'supersedes'. Claude Code ignores it
at load time`. Without `--strict` the variant passes with that warning.

Two consequences follow. The declaration is not merely unvalidated in that file,
it is *ignored* by the consumer the file exists for, so the manifest is the wrong
home for it on its own terms. And shipping it there forces a choice between a red
validation gate and dropping `--strict`, which would retire a genuine oracle to
accommodate a field that does not belong to it.

The sound resolution is to move the declaration off the validated manifest and
onto a cohort-side artefact the publisher reads directly, leaving the published
marketplace document validator-clean. The ruling's durability rationale survives
that move intact, because it rests on the declaration shipping with every cohort
rather than on residing in that particular file, and the existing invariant check
already reads the retirement set from the cohort rather than from the published
index. This is an amendment to the ruling, not an implementation detail, so it is
named here and left for a decision record rather than settled in code.

### rag-code-index-desynchronised | high | discovery was unusable and its repair is throttled by host load

The mandatory pre-coding discovery gate could not be satisfied during this
session. The code index reported `succeeded` while holding zero searchable
sections, and its hash metadata simultaneously claimed the tree was indexed, so
incremental runs embedded only the handful of changed files and could never
repair it. Two deliberately unrelated probes both returned no results, which is
the honest failure rather than the confident-garbage one, but unusable either
way.

Automatic updates were stopped, the code index was cleared, and a genuine full
rebuild is underway across 4702 files. It is progressing at roughly ten files a
minute against a host sitting at 94 percent CPU under container load, which puts
completion hours out rather than minutes. The rebuild must not be interrupted.
This is recorded because it gates any further coding on this campaign, and
because the failure mode — a completed job reporting success over an empty index
— defeats the status signal an agent would normally trust.

### correction-the-producer-existed-and-the-gate-was-red | critical | the earlier finding named the wrong mechanism, and the truth was worse

Correcting the `r6-supersession-producer-missing` finding above rather than
rewriting it, because the conclusion it drove was right and the mechanism it
named was wrong, and the difference matters to anyone reading this later.

That finding claimed no producer existed anywhere. A producer did exist: the
checked-in scaffold carries the declaration and a gate asserts it. The claim came
from a search that returned nothing, and the search was wrong rather than the
tree: ripgrep skips dotfile directories by default, and the declaration lives
under `.claude-plugin/`. An earlier directory listing missed it the same way. The
empty result was read as absence when it was only invisibility — the exact
failure the "a clean negative is not evidence" discipline exists to prevent,
committed while writing a finding about a silent no-op.

The true state was worse than the reported one, and had three independent
defects. The generator did not emit the declaration although the scaffold carried
it, so the drift gate binding those two was RED at HEAD and had been since the
commit that introduced the feature. The gate meant to prove the producer asserted
against the checked-in scaffold rather than the emitted cohort, so it passed while
the artifact a release actually pushes declared nothing. And the preflight matched
the retired name as a bare substring of the marketplace description, which
necessarily names AEAT the tax authority, so declaring the retirement would have
refused every publication permanently — failing closed in the shape that reads as
the guard working.

The conclusion the original finding reached therefore stands and is strengthened:
the ruling was inert, and the manifest is genuinely the wrong home, which the
validator measurement proves independently of any of this.

### supersession-now-lands-end-to-end | medium | S07 is discharged by mechanism rather than by a manual edit

All three defects are fixed and the retirement now reaches publication. The
declaration moved to a sidecar beside the manifest, which the publisher reads and
the merge drops from the published document, so the served manifest keeps exactly
the shape the strict validator accepts. The producer gate now asserts against the
emitted tree, and a mutation removing the emission turns it red, so it is a real
gate rather than a restatement. The preflight distinguishes an identity field,
where a bare token is stale branding, from prose, where only identity-shaped forms
count, and a test pins the generator's own bilingual description as permitted.

Proven against a marketplace in the live shape — the stale entry present and
carrying no publisher. The preflight refuses while it is live; publishing removes
both the index entry and its tree; the published manifest stays validator-clean;
the preflight then passes; and a republish is idempotent. So S07 no longer needs
the manual marketplace edit it was written to request: the retirement happens on
the first publication and is re-verified on every later one.

### full-history-scan-with-a-real-scanner | medium | 59 findings, all false positives, no credential ever committed

The S10 review was completed with an industry scanner rather than the seven-family
expression recorded earlier. Gitleaks scanned 17,269 commits and 684 MB of history
against its full rule set and reported 59 findings, every one from the single
`generic-api-key` entropy heuristic.

All 59 triage to domain identifiers. They are variables and fields named
`*_key` or `*_token` holding ordinary strings: registry `header_key` and
`profile_key` entries in modelo TOML, a `period_token` that is a typed enum field
rather than a value at all, namespace-registry names such as `workflow_state` and
`user_profile_value`, and `object_key_hmac` values in test fixtures, which are
storage lookup HMACs and not credentials. The heuristic fires on the assignment
shape, not on anything secret.

Two independent instruments therefore agree: the structural seven-family scan
found zero, and the heuristic scanner found zero after triage. That is a stronger
answer than either alone, and it is the substantive question S10 exists to ask.
The instrument still differs from the one the row names, and that difference is
recorded rather than smoothed over: this scanner has no issuer-side validation and
no partner-pattern catalogue, so it is a strong negative and not the platform's.

## Recommendations

Re-ground S09 as discharged, citing the absence of any default-branch write
rather than a branch-protection setting, and record that the row's publication
premise was false when written.

Re-ground S10 against reality: the surface it names does not exist, because
scanning is disabled on a private repository. The substantive question behind
the row — whether any credential was ever committed to this history — is
answerable locally and independently of GitHub, and should be answered before
publication rather than after it.

Open implementation rows against the canonical-release-pipeline campaign, not
this plan, to ship the producer half of R6: emit `supersedes` and `published_by`
from the marketplace manifest builder, and add a gate that fails when the
consumer-side contract has no producer writing it. The present shape — a
validated key that nothing emits — is the class of defect that passes every test
while doing nothing.

Retire `CADRUMO_SCOOP_BUCKET_TOKEN` when the two renamed secrets are created,
since no workflow reads it under either name.

Keep S10 open rather than closing it on the local scan. The scan is recorded
here as interim evidence and materially lowers the risk, but it is a narrower
instrument than the row names, and the row's own surface only comes into
existence if the repository is published. Re-run it as written at that point.

Resolve the protection tension explicitly, because it is the only item where a
standing operator requirement is currently unsatisfiable. Raising the account to
a tier that permits rulesets on private repositories is the resolution that
preserves both the requirement and the decision to stay private; the alternatives
are publishing earlier than intended or accepting an unprotected default branch.
Whichever is chosen should be recorded, because an unrecorded gap between a
stated requirement and the live configuration is exactly the drift this audit
exists to surface.

Clarify who may open branches and pull requests before enabling automated
security fixes, and pin the Actions references as a scoped change before
requiring SHA pinning.

Amend the supersession ruling to record where the retirement is declared. The
implementation has landed and is proven end-to-end, but the ruling still names
the manifest, and the code now uses a sidecar because the manifest's external
validator rejects the field and ignores it at load. The decision the amendment
carries is that relocation, and the reason is measured rather than preferred.
Until it is written, the record and the tree disagree about a shipped mechanism.

Run gitleaks in CI over the incoming diff. The full-history pass is a one-time
answer and it came back clean, but nothing currently prevents the next commit
from introducing what the sweep just proved absent. A diff-scoped run is cheap,
and the 59 false positives should be pinned as a baseline so the signal stays
readable rather than trained-away.

Raise the cohort-build toolchain pin or the local uv, independently of this
campaign. The clean-source reproducibility test refuses with "release cohort
requires uv 0.11.29, got 0.11.31", so no cohort can be built on this host as
configured, which also means the serial marketplace oracle cannot exercise the
retirement end-to-end here. That is a release-pipeline blocker sitting outside
this plan and worth its own row.
