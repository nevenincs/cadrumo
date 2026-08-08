---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:479f26506ba818566d34b54c5930aca471aa7ec9ea347f24437f5750aa3e9e88'
step_id: 'S07'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
# Cover the register walk end to end offline, closing the browser-shell exclusion S02 records. The chain is reachable because nothing in it must behave like the ZK app, only be present, visible and clickable: route interception fulfils the real listing URL so the post-Buscar landing assertion still sees an AEAT url, a static composite fixture carrying the Modelo and Ejercicio labels, the combobox buttons, visible comboitem texts, a Buscar button and the listbox satisfies the form-render check and both combobox drives, and the Buscar click needs no response because the same document already carries the result rows. Gate: a test drives the real walk entry point against that fixture through a real headless browser with no AEAT contact and asserts the truncation refusal surfaces from walk itself, plus a companion asserting the real no-pager capture returns its rows. The new fixture declares synthetic_generated provenance in its sidecar

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/tests/`

## Description

- Added two offline walk tests at the adapter boundary, both driving the real walk coroutine over route-intercepted synthetic documents through a real headless browser.
- Asserted the truncation refusal surfaces from the walk itself, carrying its rendered count, declared total, modelo and ejercicio, with both numbers read out of the fixture's raw markup rather than from the parser.
- Added the companion asserting a page carrying no pager returns its rows, with each row's parsed modelo, ejercicio, expediente and timezone-aware timestamp checked.
- Reused the two composite form-and-grid fixtures authored for the preceding Step rather than adding a third; both already declare synthetic_generated provenance in their sidecars.

## Outcome

The exclusion the earlier Step recorded is closed. The refusal had been proven by feeding the parse helper a fixture directly, which left out the navigation, the post-navigation landing assertion, both combobox drives, the Buscar click and the read of the resulting document. The residual risk that leaves is not that the refusal misfires; it is that the walk stops reaching the parse at all, in which case the parse-level gate stays green while every real register read quietly returns nothing. Both new tests fail if that happens, and the mutation run below demonstrates it rather than asserting it.

The whole shell genuinely runs. Route interception FULFILS the real listing url instead of redirecting away from it, so the landing-prefix assertion sees a real AEAT url; the form-render check finds its exact Modelo label; both comboboxes are opened and an option clicked in each; Buscar is clicked; and the result is read back off the same document, which is why the click needs no response. Nothing in the fixture behaves like the ZK application, and nothing has to: every element only has to be present, visible and clickable, which is exactly what the drive asserts.

What the row asks that this does not deliver, stated rather than quietly narrowed. The row names "the real walk entry point", and there are two candidates. The one covered is the register session's own walk method, which is the walk every bulk sweep and the whole-history sweep reach, and which is where the browser shell lives. The module-level walk function is NOT covered, and cannot be reached offline without either a new production seam or real encrypted-bucket setup: it refuses outright when the session carries no persisted browser state, it resolves an active bucket id, and it creates its own page and context internally, so route interception cannot be installed before its own navigation. The standing goal still asks for that second entry point; what stands in the way is recorded here rather than left as an unexplained gap, and no seam was added to it because the plan authorises a seam only on the two bulk functions.

The pass condition is the property in both tests, never a count as a gate. The truncated case asserts that a page rendering strictly fewer rows than its own pager declares is refused, having first confirmed from the markup that the fixture still has that shape. The complete case asserts rows come back and match the fixture's own rendered count. A regenerated fixture of a different size exercises the same property with nothing rewritten.

## Verification

    uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_register_walk_offline.py
    2 passed in 9.13s

    uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/aeat/sede/tests/
    747 passed, 12 deselected in 109.19s

The twelve deselected were checked rather than ignored: they carry the external-tool or keychain markers. A run of the same directory under the integration marker reported all 759 deselected, so nothing in this directory hides behind that lane.

Two mutation proofs, both from pytest plugins resident OUTSIDE the repository, so no tracked file was edited and no peer sweep could commit a mutation. Each asserted its target was present before rebinding and asserted the rebinding took, printing that the mutation was applied and the holder found.

First, a detector that can never report truncation: the pager-total reader was rebound to return no total.

    1 failed, 1 passed in 9.73s
    FAILED ...::test_the_walk_itself_refuses_a_page_declaring_more_than_it_rendered

The companion stayed green under that mutation, which is correct and is itself worth recording: the no-pager case must not depend on the detector firing, or it would be pinning the refusal twice instead of guarding against a false one.

Second, and this is the proof that the shell is really traversed: the form drive was rebound to report the ejercicio unavailable, which is a shell that never reaches the parse.

    2 failed in 1.89s
    FAILED ...::test_the_walk_itself_refuses_a_page_declaring_more_than_it_rendered
    FAILED ...::test_the_walk_returns_the_rows_of_a_page_carrying_no_pager

Both reddened, which is exactly the residual risk the parse-level gate could not see. The run also fell from roughly nine seconds to under two, corroborating that the unmutated runs spend that time driving a real browser rather than short-circuiting somewhere.

Type and lint gates: ty check reported all checks passed, ruff format left the module unchanged, ruff check clean.

## Notes

No live authenticated AEAT probe was performed or required, and the live-tests opt-in environment variable was never set, per the plan's Constraints and the standing operator directive. Whether AEAT's real grid paginates this form remains unverified and is not implicitly closed by this Step.

No new fixture was needed. The two composite documents authored for the preceding Step carry everything the shell asserts, and both already declare synthetic_generated provenance with a recorded role and the sha256 and byte size of their committed bytes, so the row's provenance requirement is satisfied without a third artefact.
