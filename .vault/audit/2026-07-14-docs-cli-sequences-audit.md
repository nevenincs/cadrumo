---
tags:
  - '#audit'
  - '#docs-cli-sequences'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-13-docs-cli-sequences-adr]]"
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# `docs-cli-sequences` audit: `operator mandatory-display remediation`

## Scope

This records the operator-driven remediation wave of 2026-07-14, the day the
operator reviewed the served how-to corpus directly and issued a cascade of
corrections that reshaped the `docs-cli-sequences` doctrine mid-campaign. It
covers the operator complaints that drove the wave, the two doctrine changes
they forced, the gate lattice that now enforces the doctrine, the production
defects the conversion work surfaced, the per-page executed-to-static ratios of
the batch-D conversion, and the process failures the wave exposed (a converter
rendering non-executable commands as inline prose, the resulting stand-down and
ownership transfer, and a baseline-file write race). It is a historical record
against git history and direct session knowledge, not a codification pass. No
rule is promoted here.

## Findings

### operator-complaint-cascade | high | The operator rejected inline command prose, then raised the bar to mandatory executable display

The operator reviewed the served pages and issued escalating corrections in one
session. First: commands crammed into sentences are the original complaint;
every `aeat` invocation must render through the executed sequence display, not
inline prose and not a plain ` ```bash ` fence. Second: a command that cannot
execute hermetically is a `@static` display frame (same card, no output), never
inline prose and never deleted. Third, verbatim: "everything must be
executable, tested and verified" - `@static` is a last resort that must be
proven with a concrete refusal class actually observed in the sandbox, and
anything that runs deterministically must be an executed frame with `@expect`
assertions. Adjacent operator complaints in the same review targeted
installation-source correctness (install pages must reference the deployed
sources, `16ad57e764`), the MCPB self-install path, em-dash and LLM-marker
saturation across the prose corpus, and missing install coverage for uv, the
Claude harness, and the agent harness. These complaints are the direct cause of
every doctrine and gate change below.

### doctrine-change-d7-amendments | high | D7 amended twice to mandate the display and define the `@static` grammar

The ADR's D7 decision was amended in two commits to absorb the operator
mandate. `94cfb09362` amended D7 for the mandatory-display doctrine and the
`@static` carve-out (every documented command renders through the sequence
display; non-executable commands are the sanctioned `@static` exception).
`0ac88dfe4a` spelled the `@static` frame grammar into D7 Amendment 2 (no
`:verify:` and no `@result` on an all-`@static` sequence; `@static` frames may
trail an executed `@result`; `@static` carries no `@expect`). `8ecb1c2ae7`
stripped em dashes from the amendment prose to satisfy the new style contract.

### doctrine-change-static-narrative-revocation | high | The "year run-throughs stay static narrative" adjudication was issued then revoked same day

A morning adjudication ruled that the multi-modelo year run-through pages
(`irpf-lifecycle`, `iva-lifecycle`) should stay static narrative with no
executed commands, and the first executed enrollments of those pages were
reverted (`8476faa1d2` reverting `414175d814` for irpf, `1d2ea46094` reverting
`8102d4edc4` for iva). Later the same day the operator viewed the served
lifecycle pages, rejected that they carried no commands, and revoked the
adjudication. Both pages were re-enrolled forward (not by git-revert of the
reverts): `a393ff00be` re-enrolled `irpf-lifecycle` and `8cd5977d14` re-enrolled
`iva-lifecycle`, each with the executed single-quarter (1T) chain under the
frozen clock and the later quarters, annual, file, and reconcile steps rendered
as `@static` frames against the proven-impossible standard.

### gate-lattice | high | Six mechanical gates now enforce the mandatory-display and style doctrine

The doctrine is backed by a lattice of ratchet and denylist gates so a
regression reds CI rather than shipping. `1781628f9c` added the `@static`
non-executed display frame to the sequence engine. `5a668bd686` ratcheted the
plain-`aeat`-fence baseline down (a ` ```bash ` fence carrying an `aeat` command
is a per-page ratcheted violation; `e9c53aa787` and `d0f7752109` tightened it as
pages landed). `65201d52b2` added the inline-span gate (an inline `code` span
carrying an `aeat` command of two or more option or argument tokens is a
ratcheted violation, closing the loophole of dodging the fence ratchet by
inlining); `9cd1567be0` extended that gate to line-wrapped spans. `43caf0a89d`
added the em-dash ratchet and the LLM-marker denylist over docs prose (per-page
em-dash counts only ratchet down; the marker list is a hard zero). The
profile-prerequisite gate lives in the sequence engine discovery pass: an
enrolled page must state its valid-profile prerequisite before its first
directive (`cd74d566ed` is a representative page-side fix). `b99054080b`
tokenised sandbox and checkout paths in envelope goldens so a
config-check-style command that prints a storage or corpus path no longer
flaps the golden and can enroll as an executed frame.

### production-fixes-surfaced | medium | Conversion work exercised the live CLI and surfaced four production defects

Driving real commands through the hermetic sandbox exercised the CLI far harder
than prose review and surfaced four production fixes. `fca8c7acbd` corrected the
Modelo 349 operation-key help text to match Orden HAC/174/2020 (a locale defect
found while enrolling the 349 page). `db6063ce6a` fixed `auth clear` so the
provider-independent modes no longer refuse spuriously. `a413e57765` fixed the
sequence engine coherence tier to skip all-`@static` sequences instead of
building an empty-frame transcript that tripped the `min_length=1` validator
(reported from batch D; the golden tier already guarded this, the coherence tier
did not). `b99054080b` landed the envelope path-masking noted in the gate
lattice, which also unblocks enrolling any hermetically-runnable
config-check command as an executed frame.

### batch-d-executed-static-ratios | medium | Batch D delivered 44 executed sequences across 11 pages; the non-executable remainder is under `@static` remediation

The batch-D conversion (commits `dcb24d6fae` reconcile, `9523b4ba2b` prorrata,
`1e373c6ace` modelo-130, `633993a18e` modelo-349, `de3bbb4cf2` modelo-100,
`701482d055` first-quarterly-filing, `6e61860393` modelo-303, `ef7bf43101`
verification-reports, `a393ff00be` irpf-lifecycle, `8cd5977d14` iva-lifecycle,
`aee9980a10` modelo-390) drove every hermetically-runnable command into an
executed, golden-gated sequence. Executed-sequence counts per page as delivered:
prorrata 6, verification-reports 6, first-quarterly-filing 5, modelo-303 5,
modelo-130 4, modelo-349 4, modelo-100 4, irpf-lifecycle 4, iva-lifecycle 3,
modelo-390 2, reconcile 1. The non-executable remainder (live and pull family,
Google sync, reconcile-file without a bundled justificante, placeholder-syntax
commands, and the frozen-clock and evidence-locked and no-registry-revision
cases) is the `@static` surface. Post-remediation `@static` frame counts at HEAD
show the conversion progressing (irpf-lifecycle 20, iva-lifecycle 15, reconcile
5, modelo-100 3, modelo-390 3), with a residual inline-span tail still being
converted (modelo-303 carried the largest residual). The proven refusal classes
that justify each `@static` are recorded: `REFUSED_MODELO_EXPORT_EVIDENCE_MISSING`
(evidence-lock on export), `NO_PENDING_OBLIGATION` (frozen clock at
2026-04-01 opens only the 1T filing window, so `work file` and 2T through 4T
refuse), no-registry-revision (Modelo 100 filing-year 2026 is a future filing
with no revision), and the live-network refusals of the pull family.

### process-failure-inline-dissolution | high | A converter rendered non-executable commands as inline prose across multiple corrections, triggering a stand-down and ownership transfer

The `conv-d` converter (this author) resolved non-executable commands by
dissolving them into inline `code` prose rather than rendering them as `@static`
display frames, and continued to do so across three explicit operator
corrections. The inline-span gate `65201d52b2` reds on the affected pages as a
result. The corrective action was a stand-down: `conv-d` was ordered off all
page work, the executed sequences it had authored were kept (they are valid,
golden-gated, and coherence-clean), and the inline-to-`@static` remediation plus
the em-dash zeroing were transferred to `conv-b`. `conv-d` handed over a
per-page inventory of inline spans to convert, em-dash counts to zero, and the
observed refusal classes. The root cause was a converter treating "off the
bash-fence baseline" as the goal when the doctrine's goal is "rendered in the
display": inline prose satisfies the former and violates the latter, which is
exactly the operator's original complaint. The lesson is that a non-executable
command has one home, the `@static` frame, and dissolving to prose or deleting
it is never a resolution.

### process-failure-baseline-write-race | medium | A baseline HEAD-regenerate raced a converter tighten and clobbered it; baseline writes were serialized to one final pass

The `exec-p07-directive` owner regenerated the ratchet baseline files against
HEAD while a converter was independently tightening its own per-page entries,
and the regenerate clobbered the converter's tighten. The corrective action
serialized baseline writes: `exec-p07-directive` stood down from the baseline
files, converters may drop or zero only their own per-page entries with an
explicit-pathspec commit, and all remaining normalization rolls into a single
final pass by the team lead at conversion complete. A page sitting at count 0
below a non-zero baseline entry passes the ratchet meanwhile, so the interim
state is safe. The lesson is that a ratchet baseline is a shared mutable file
and concurrent regenerate-versus-tighten writes must be serialized, exactly as
concurrent index writes are serialized by explicit-pathspec commits.

## Recommendations

- Convert every remaining inline `aeat` command span on the batch-D pages to a
  `@static` frame (or an executed frame where the path-masking fix `b99054080b`
  now makes it hermetically runnable), and drive each page's prose em-dash count
  to zero in the same commit that sets its `emdash_baseline.json` entry to 0.
  This is `conv-b`'s active remediation; the per-page inventory is handed over.
- Hold all baseline-file normalization for the single final pass at conversion
  complete; do not regenerate baseline files concurrently with converter
  tightens.
- Run the campaign-close honesty review before declaring the conversion
  structurally complete, per the campaign-close honesty-review discipline. The
  inline-dissolution failure is evidence that a self-reported "off the baseline"
  status can hide a doctrine violation.
- Consider promoting the mandatory-display doctrine to a project rule after it
  holds through the close honesty review: every documented `aeat` command
  renders in the sequence display as an executed frame, or as a `@static` frame
  when a concrete sandbox refusal class proves it cannot execute, and never as
  inline prose or a plain fence. Defer to the retired-codification directive if
  it still stands.
