# Current source delta from the S07 baseline

The accepted S07 evidence is an immutable pre-optimization snapshot, not a
claim about the later shared worktree.

- Baseline source digest: `14b80a63fd368c9bfbf5ba2854326f5cf6559395538f0e59b34806df6308ce71`
- Current source digest when this delta was recorded: `060f30831857f960bd1cc4e0279a5fd27f5483e0a16236be2612855f14296ecc`
- Baseline census: 361 dynamically enrolled root/group/leaf nodes
- Current additions observed after the freeze:
  - `aeat app ledger evidence attachment-queue`
  - `aeat app ledger evidence attachment-view`

Accordingly, `--check` passes the source-bound evidence while `--check-fresh`
fails. Every post-optimization capture and regression gate must run a new
dynamic census and cover these two nodes plus every other node live at that time.
