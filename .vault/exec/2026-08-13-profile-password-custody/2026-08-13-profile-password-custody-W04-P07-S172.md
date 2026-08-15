---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:aa2318540979850cfcbf5417706e5ab51a65f4f4477085ad41c4fd8cbe47eba0'
step_id: 'S172'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh re-root the five production exception classes that inherit a bare builtin rather than the project error taxonomy, two in the M303 simplified-regime calculation path and three in the profile record and custody crypto paths, since the hygiene gate that forbids an unregistered builtin root is red on exactly them and an unregistered root escapes the registry that gives every refusal its code, its operator suggestion and its four-locale text

## Scope

- `src/cadrumo/application/calculations/ and src/cadrumo/application/user_profile/_capsule_record.py and src/cadrumo/application/profile_custody/`

## Description

- Census every catch site that could see the five classes, before touching any
  of them.
- Re-root each class onto the family its meaning belongs to, preserving the
  builtin ancestry wherever a live catch clause depends on it.
- Declare all five in the error-code registry against existing four-locale
  message keys.
- Prove each re-root bites by runtime patch from outside the tree.

## Notes

**THE CATCH-SITE CENSUS WAS THE ROW, AND IT FOUND ONE LIVE TRAP.** An AST walk
of every production `except` handler naming `ValueError`, `RuntimeError`,
`Exception` or a bare catch, restricted to the modules on each class's call
graph, returned one site that a blind re-root would have broken: the profile
lifecycle's restore-database arm catches `(DatabaseError, OSError,
SQLAlchemyError, ValueError)` around the authenticated staged-database
validation and converts whatever it catches into its own refusal naming the
validation stage. The integrity refusal raised inside that validation is caught
there ONLY because it is a `ValueError`. Re-root it off `ValueError` and the
inner refusal escapes the conversion silently -- the operator would get a
message about a different stage, and the shipped assertions that pin the
converted wording and its cause chain, corrected by the closed row that split
the count half from the key half, would have gone red for a reason nothing in
the diff explains. That file belongs to another owner, so the constraint was
absorbed rather than negotiated: the ancestry stays.

**THE REST OF THE CENSUS IS NEGATIVE, AND THE NEGATIVES MATTER AS MUCH.** No
production handler catches `RuntimeError` anywhere on the custody crypto path;
the only two in the tree are an asyncio guard in the inbound TUI and a PDF
backend's optional-dependency arm. The two `except ValueError` sites inside the
record module itself guard a strict JSON decode and an event-type/timestamp
parse, so they see pydantic and builtin refusals, never these classes. The
crypto port's own two handlers are `except Exception`, which no re-root can
change. The source mesh that drives the annual-summary resolver wraps no
resolver call at all, and neither calculation-action module carries a
bare-root handler, so the M303 refusals were never being converted by anyone.

**EACH PARENT WAS CHOSEN FROM WHAT THE CLASS MEANS, AND TWO WERE DELIBERATELY
NOT FLATTENED TOGETHER WITH THE OTHERS.** The two M303 refusals join
`CoreValidationError`, which is what every other refusal in the calculations
application package already roots at and what that package's error module
documents itself as using instead of a bare `ValueError`; the base already
carries `ValueError`, so the arm that converts the domain row-validation
refusal into the calculation refusal is untouched. The two record classes join
the user-profile error family, following the same package's login-throttle
refusal, and each keeps `ValueError` alongside -- the established mixed shape
that the user-profile validation refusal, the storage validation refusal and
the custody record refusal all use. The crypto refusal joins `CoreError` and
keeps `RuntimeError`, mirroring the async-cleanup refusal in core.

**THE CRYPTO REFUSAL WAS THE ONE PLACE A "BETTER" PARENT WAS REJECTED.** The
persistence layer has an AEAD failure family, and on meaning alone that is the
closest fit. It was not taken: this package exists to keep the adapter's crypto
types off the application port -- the neutral blob model beside it says so --
and adopting that family would make the port's refusal newly catchable by every
storage-family handler in the tree. That is a broadening, not a re-root, and
this row's mandate on the crypto path was behaviour preservation except for
ancestry. A probe asserts the refusal is NOT an instance of the encryption,
decryption or storage bases.

**NO LOCALE COORDINATION WAS NEEDED, WHICH WAS A DESIGN CHOICE RATHER THAN
LUCK.** Registering a class means giving it a message key, and a new key would
have reddened the four-locale parity gate until another owner landed
translations. Every one of the five was instead pointed at an existing key
whose text is true of the condition: an IVA calculation error, a periodic-to-
annual-summary reconciliation error, an encryption-or-decryption error in the
secure store, a secure-object revision conflict, and a malformed profile
custody record. All five resolve to real prose in all four locales, verified by
rendering each. Key sharing is already established -- twenty-eight keys carry
more than one code, including one shared across the application and adapter
layers. Each class still gets its own unique code, which is what the
one-code-one-class gate requires.

**THE BITE-PROOFS RUN FROM OUTSIDE THE TREE AND FORTY ASSERTIONS PASS.** For
every class the probe drives a real raise condition, builds the real envelope,
renders the real stderr text, resolves the key in four locales, then withdraws
that class's registry declaration and requires the envelope build to refuse --
so the registration is demonstrably what supplies the code rather than
something the assertions assumed. The crypto probe seals and opens real AEAD
bytes, refuses under a wrong key with the adapter's own decryption failure
preserved as the cause, and opens again under the right key so the refusal is
shown to discriminate. Two probes drive real `except` clauses in both
directions: the lifecycle restore arm converts the integrity refusal and, fed a
registry-bound refusal that is not a `ValueError` -- exactly the shape a blind
re-root would have produced -- lets it escape unconverted; the M303
row-validation arm converts a domain `ValueError` and lets a `RuntimeError`
pass through. Nothing under the source tree was edited for any of it.

**THE HYGIENE GATE WENT FROM SIX NAMED CLASSES TO ONE.** All five in scope are
gone. The sixth, an operation-declaration refusal in the operations package,
was named by the same failure before this work started and belongs to another
owner; it is reported, not taken.

**WHAT COULD NOT BE VERIFIED, STATED PLAINLY.** The registry authority does not
load in this tree: a concurrent authority-grade sweep, which advanced through
roughly twenty commits during this row, leaves registry validation refusing on
missing export layouts and unmet filing-grade claims across dozens of
revisions. Every M303 test that needs a real snapshot is red for that reason
before and after this change, with an identical failure signature and an
identical pass count on both sides. The consequence is that the full
calculate-a-simplified-result path could not be driven end to end here; what
was driven instead is every refusal in those two modules that does not require
the authority, plus the conversion arm, plus the registry binding. The record
boundary suites, the cross-process roundtrip, the error-registry gates and the
envelope enrollment gates are all green.

**A PEER'S BROAD COMMIT CONSUMED THIS WORK BEFORE IT WAS REPORTED.** The
changes were made in the working tree and never staged or committed from here.
A concurrent registry-sweep commit captured all five class declarations and all
five registry rows into its own commit under a registry-sweep subject line. The
content is intact and verified present at head; what is lost is the
attribution, which is exactly the shared-index hazard the worktree rule
describes. Only a docstring cross-reference role adjustment remained
uncommitted afterwards.

**A PRE-EXISTING VIOLATION SITS IN AN OWNED FILE AND WAS NOT ABSORBED.** The
import hygiene gate is red on seven counts, none of them introduced here; one
is a type-checking-time import of seven port protocols from a private module of
the user-profile package, made by the custody ports package. It predates this
row by two feature commits and this change only shifted its line number.
Clearing it means promoting seven protocols onto another owner's public facade,
which is a different row's decision, so it is reported rather than taken.
