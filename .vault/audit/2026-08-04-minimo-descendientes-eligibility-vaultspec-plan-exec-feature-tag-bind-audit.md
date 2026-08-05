---
tags:
  - '#audit'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:62d49df78bfab8b184605ccdbe44eb709f3d075e53c16c1ad96e30f2819da68c'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
  - "[[2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace minimo-descendientes-eligibility with a kebab-case feature tag, e.g. #foo-bar.
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

# `minimo-descendientes-eligibility` audit: `A topic-infixed ADR can never get its own plan with exec records`

## Scope

A limitation of the vaultspec-core CLI, found while trying to open a plan for an ADR that
carries a topic infix. Recorded as a finding for a tool owner rather than as a project
rule, because it is a property of the tooling and not a discipline this codebase can adopt
its way out of. The workaround used here is sound but narrow, and the general case has no
route at all.

Traced to source rather than inferred from error messages, and every claim below was
verified by running the verb rather than reasoning about it.

## Findings

### topic-infix-blocks-plan-and-exec | high | An ADR with a `--topic` infix cannot get its own plan carrying exec records

`vaultspec-core vault add` accepts `--topic` for adr, audit, reference and research, which
produces `{date}-{feature}-{topic}-{type}.md` and lets one feature hold several documents
of a type. Plan and exec do not accept it. A feature therefore holds at most ONE plan,
because a second scaffold resolves to the identical `{date}-{feature}-plan.md` and refuses
with a file-exists error whose only offered escape is `--force`, which would overwrite the
existing plan.

The obvious escape is to give the new plan its own feature tag. That fails at the next
step. Exec creation runs a lifecycle gate in `vaultcore/resolve.py` which collects the
document types already present for the target feature and hard-fails when `adr` is absent:
`Cannot create exec for feature '<tag>' - no ADR document exists.` The feature is resolved
by `feature_from_tags_or_meta`, which reads the `tags:` block with a bare `feature:`
frontmatter key as fallback. Both are frontmatter, and the framework's own rules forbid
hand-writing frontmatter, so an author cannot legitimately move one document to the new
tag.

No verb closes the gap. `vault rename` changes a document's file stem and re-points
incoming links but does not touch tags, confirmed by dry-run, so a renamed ADR still
resolves to its original feature and the gate still fails. `vault feature rename` operates
on a tag across every surface, so using it drags every other document sharing that tag,
including any closed plan and its exec records.

The result is a closed loop: the ADR cannot get a plan under its own topic, a plan under a
new tag cannot get exec records, and the document cannot legitimately change tags. Placing
the ADR's implementation under the parent feature's existing plan is the only fully
CLI-routed path.

### renumbering-workaround-is-narrow | medium | The available workaround depends on unused Step numbers and does not generalise

The resolution used here was to extend the parent feature's existing plan with a new Phase
whose Steps continue past the closed range, so the generated exec filenames
(`{date}-{feature}-P##-S##.md`) do not collide with the closed campaign's records. That
worked, and it is arguably the more honest artefact: the feature index now reads as one
lifecycle with a gap where the campaign closed and reopened, which is what happened.

It generalises poorly. It works only because the parent plan was complete and its Step
numbers were free, so appending could not disturb in-flight work. A feature needing two
CONCURRENT plans has no route: both would need the same filename, and the topic infix that
would separate them does not exist for plans. A feature whose single plan is being actively
executed by another agent would also be a poor place to append, since the two campaigns
would then share one document and one completion percentage.

### corrected-row-strands-its-record-heading | medium | A Step Record's heading is machine-filled at scaffold time and has no re-sync verb

A Step Record's level-one heading and its Scope block are machine-filled from the
originating Step row when the record is scaffolded. The row can legitimately change
afterwards, through the owning `vault plan step edit` verb, and nothing re-syncs the
record. There is no verb that would: the scaffold verb creates, and re-running it on an
existing record is not the shape of the need.

That leaves a stale heading on every record whose row is later corrected, and the residue
is worse than an ordinary stale string because of what a heading is. It is the first line
a reader meets, it is phrased as an instruction because Step rows are phrased as
instructions, and it sits above a closed row that now says something different. A reader
who trusts headings — which is the ordinary reader, for the same reason rows outrank prose
— takes it as live.

Encountered concretely here. The `S16` row carried a BLOCKED clause naming a per-comunidad
regional table, which was retired on measurement before the Step was executed. The row was
corrected before the row was checked, as its own closing condition required. The record's
heading still names the retired blocker, so the artefact recording that the table must not
be built opens with a line instructing a reader to build it.

The interim taken here was to leave the machine-filled fields untouched, because the
template forbids hand-filling them and a hand-written heading is exactly the value that
could later lie without anyone able to tell, and to open the Description by stating that
the heading preserves the row text as it stood at scaffold time and is not a live
instruction. That is the same shape as every other correction this campaign made well:
preserve the stale text, say what it is, rather than tidying it away and losing the record
that it changed.

It generalises past this campaign. Any plan that corrects a row after its record is
scaffolded hits it, and correcting a row after execution is not an unusual event — it is
what happens whenever a Step's stated blocker turns out not to apply, which is a normal
outcome of executing the Step rather than a planning error.

The smallest fix in the existing vocabulary would be a re-sync on the owning verb, so that
`vault plan step edit` offers to update the machine-filled fields of any record already
bound to that Step, or a `--resync` flag on the exec verb that refreshes heading and Scope
from the current row without touching authored prose. Either keeps the fields
machine-owned, which is the property that makes them trustworthy.

### per-article-excerpt-omits-its-own-clause | medium | A bundled per-article corpus file is missing a clause the full consolidated text carries

Not a tooling finding like the two above, but recorded here because this is where this
feature's findings are being carried upstream and it bites the same reader.

The bundled per-article excerpt for the LIRPF maternity-deduction article carries only
its first two apartados. It runs to about fourteen hundred characters and contains no
occurrence of acogimiento, of inscripción, or of the three-years-following phrase. The
clause it omits is the one granting the deduction for an adoption or entitling
acogimiento regardless of the child's age, for three years from the inscription date.

That clause IS bundled, in the full consolidated statute file and in the tax authority's
own annual manuals for two filing years. So the corpus holds it; one particular file
that a reader would reach for first does not.

The hazard is specific and this project's grounding discipline names it: the bundled
corpus is preferred over secondary sources and is not infallible. A corpus reference
pointed at the per-article file for this clause would fail its required-text check, or
worse, a reader consulting that file to ground the clause would conclude it does not
exist. That nearly happened during this campaign: a Step whose whole premise is the
date-scoped window was almost reported as ungrounded on the strength of the excerpt
alone, and only a wider search of the corpus found the clause.

Two follow-on notes for whoever grounds this clause. Point the reference at the
consolidated file rather than the per-article one, or refresh the excerpt. And expect
the statute and the manual to word the entitling placements differently: the statute
names acogimiento both preadoptivo and permanente, while the manual names acogimiento
permanente or delegación de guarda para la convivencia, which is the post-2015
civil-law renaming of the same arrangement. Both describe the same set. An implementer
who grounds on one and reviews against the other will think they disagree.

## Impact

Nothing is broken and no data is at risk. The cost is that an ADR authored with a topic
infix silently acquires a constraint its author had no reason to anticipate, and the
constraint only surfaces later, at exec time, after the plan has already been written.
Three exchanges were spent here discovering it, and the natural escapes an author reaches
for first are all either forbidden or destructive: hand-editing frontmatter, `--force` over
an existing plan or an existing exec record, or authoring a duplicate ADR under the new tag
purely to satisfy the gate. That last one is the most tempting and the most damaging,
because it manufactures a second decision record for a decision that already has one.

`corrected-row-strands-its-record-heading` puts no data at risk either, and its cost is
different in kind. The other finding costs an author time at authoring time, and the author
is present to absorb it. This one costs a READER accuracy at reading time, and the reader
is by definition not the person who knows the heading is stale. It is the cheaper finding
to fix and the more expensive one to leave, because a stale instruction is acted on rather
than merely stumbled over.

## Recommendations

For the tool owner, tied to `topic-infix-blocks-plan-and-exec`, in ascending order of
effort. Any ONE of them opens the loop.

Extend `--topic` to plan and exec. Plan filenames gain the same infix the other four types
already use, and exec records gain it on their directory or stem so a feature can hold more
than one plan lineage. This is the smallest change that matches the existing vocabulary,
and an author who already understands `--topic` for an ADR needs to learn nothing new.

Alternatively, add a per-document feature move, something in the shape of
`vault feature move <doc> --to <tag>`, so the CLI owns the mutation the rules forbid an
author from making by hand. That would also give `vault rename` a natural companion: today
one verb moves a stem and another moves a tag across an entire feature, with nothing in
between.

Alternatively, relax the exec lifecycle gate so that an ADR reachable through the parent
plan's `related:` chain satisfies it, rather than requiring a same-tag ADR. The plan
already names its authorizing documents, which is the linkage the framework's own
documentation says Steps inherit, so the gate is arguably asking the wrong question.

Whichever is chosen, the file-exists error on a second plan scaffold should stop offering
`--force` as its only hint. Overwriting an existing plan is almost never what the author
wants, and here the correct action was structurally elsewhere.

The re-sync recommendation for `corrected-row-strands-its-record-heading` is stated with
that finding rather than repeated here, because it is one change to one verb and has no
alternatives worth ranking. It goes upstream with the rest.

Recorded as findings rather than promoted to rules, deliberately: codification is retired
in this project, and these are tooling limitations rather than disciplines for authors to
absorb. They are worth carrying upstream to the vaultspec-core repository rather than
living only here.

A note on this document's own title, which names the first finding only and has now
outgrown it. It was left rather than renamed: the stem is cited by the feature index and by
the exec records, and renaming a document to widen its title is a larger change than the
finding it would accommodate. Whoever carries these upstream should read the title as the
originating finding rather than the full contents, which is the same reading the stale Step
Record heading asks for and the same reason it was left in place.
