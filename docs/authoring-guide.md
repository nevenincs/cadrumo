# Authoring and reviewing documentation

This guide shows you how to make a documentation change and take it through review. A change might touch any of three English documentation surfaces. Two are hand-written: the repository markdown and the in-source docstrings. The third is the generated reference for the application programming interface (API) and the command-line interface (CLI).

## Choose the right surface

Where you make a change depends on what you're changing:

- **Repository markdown** is hand-written. Edit the README or a guide under `docs/` directly.
- **Docstrings** are the single source for the API reference. Edit the docstring in the source, and let Sphinx render it. Never copy a signature into prose by hand.
- **The API reference** is generated from the source modules by `aeat.apidocs`. Don't edit the stubs; regenerate them.
- **The CLI reference** is generated from the command tree. Don't edit it; regenerate it.

To regenerate the generated surfaces and check the result, run:

```bash
python -m aeat.apidocs scaffold
just docs
just docs-check
```

`just docs-check` fails on a broken cross-reference, a missing stub, or a command reference that no longer matches the commands.

## Take a narrative change through review

A change to the README or a guide under `docs/` moves through a staged review. Each stage has a distinct reviewer, and each completes before the next begins:

1. **Wireframe.** Outline the document as titles and section intents. Assign each page a Diataxis type: tutorial, how-to, reference, or explanation.
2. **Refinement.** A reviewer with no project context reads only the wireframe and confirms a newcomer would understand what each section delivers. Revise until every section passes.
3. **Context.** Researchers gather the facts, commands, paths, and source locations each section needs.
4. **Drafting.** Authors write each section from the gathered context and the prose-style rules.
5. **Technical review.** Reviewers verify every command, flag, path, and class name against the code.
6. **Editorial review.** A reviewer with no project context checks the writing against the prose-style rules.
7. **Approval.** The change lands once the technical and editorial reviews pass.

## Keep the roles separate

Keep research, drafting, and review in separate hands. When you gather context, don't write the final prose. When you author, write from the gathered context, and don't invent facts. When you review for editorial quality, work from the document alone, without the codebase. The separation keeps each judgment honest.

## Don't encode process metadata

Documentation paths, filenames, and content carry domain and topic names only. Don't put the documentation framework or the project-management process into them. That rules out wave, phase, and step identifiers, plan and decision-record identifiers, and agent or campaign labels. A reader should see the product, not the process that built it.
