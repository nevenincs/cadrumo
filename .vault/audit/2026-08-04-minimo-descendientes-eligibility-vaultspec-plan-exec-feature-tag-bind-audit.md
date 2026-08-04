---
tags:
  - '#audit'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:4c7a0e6c55a85d212cce485a668c1b51a227311650598b5a59c032f31cdd27e6'
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

## Impact

Nothing is broken and no data is at risk. The cost is that an ADR authored with a topic
infix silently acquires a constraint its author had no reason to anticipate, and the
constraint only surfaces later, at exec time, after the plan has already been written.
Three exchanges were spent here discovering it, and the natural escapes an author reaches
for first are all either forbidden or destructive: hand-editing frontmatter, `--force` over
an existing plan or an existing exec record, or authoring a duplicate ADR under the new tag
purely to satisfy the gate. That last one is the most tempting and the most damaging,
because it manufactures a second decision record for a decision that already has one.

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

Recorded as a finding rather than promoted to a rule, deliberately: codification is retired
in this project, and this is a tooling limitation rather than a discipline for authors to
absorb. It is worth carrying upstream to the vaultspec-core repository rather than living
only here.
