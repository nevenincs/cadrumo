# Authoring and reviewing documentation

This guide describes how documentation changes flow through review before they land. It applies to the three English documentation surfaces: the repository markdown (the README and the guides under `docs/`), the in-source docstrings, and the generated API and CLI references.

## The surfaces and how they stay true

Documentation is generated or verified from the codebase, not maintained in isolation:

- **Repository markdown** is hand-written, but every technical claim is verified against the code before it lands (see the review pipeline below).
- **Docstrings** are the single source for the API reference. Sphinx renders them through autodoc; you never copy a signature into prose by hand.
- **The API reference** is scaffolded from the source modules by `aeat.apidocs`. A correspondence test fails if a module lacks a stub or a stub outlives its module.
- **The CLI reference** is generated from the command tree by `aeat.entrypoints.cli` tooling. A drift test fails if the committed reference no longer matches the commands.

Regenerate the generated surfaces rather than editing them:

```bash
python -m aeat.apidocs scaffold
just docs
just docs-check
```

## The review pipeline for narrative docs

Narrative documentation - the README and the guides under `docs/` - moves through a staged pipeline with a distinct reviewer at each gate. Each stage completes before the next begins.

1. **Wireframe.** Outline the document as titles and section intents, with a Diataxis type (tutorial, how-to, reference, or explanation) for each page.
2. **Refinement.** A reviewer with no project context reads only the wireframe and confirms a newcomer would understand what each section delivers. Revise until no section fails that test.
3. **Context gathering.** Researchers gather the facts, commands, paths, and source locations each section needs, working from the codebase.
4. **Drafting.** Authors write each section from the gathered context and the prose-style rules, not from memory.
5. **Technical review.** Reviewers verify every command, flag, path, and class name against the code. Corrections land before the next gate.
6. **Editorial review.** A reviewer with no project context checks the writing against the prose-style rules.
7. **Approval.** The change lands once the technical and editorial gates pass.

## Separation of concerns

Keep research, drafting, and review separate. A researcher gathers context and does not write the final prose. An author writes from that context and does not invent facts. An editor checks the writing without access to the codebase, so writing quality is judged on its own merit. This separation is what keeps the documentation both accurate and readable.

## What documentation must never contain

Documentation paths, filenames, and content carry domain and topic names only. They never encode the documentation framework or the project-management process: no wave, phase, or step identifiers, no plan or decision-record identifiers, and no agent or campaign labels. A reader sees the product, not the process that built it.
