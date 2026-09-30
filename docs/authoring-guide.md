# Authoring and reviewing documentation

Cadrumo is a Spanish tax-filing application. AEAT is the external Spanish tax authority. This guide shows you how to make a documentation change and take it through review. Four documentation surfaces exist: repository markdown, in-source docstrings, and two generated references — one for the application programming interface (API) and one for the command-line interface (CLI).

## Choose the right surface

Where you make a change depends on what you're changing:

- **Repository markdown** is hand-written. Edit the README or a guide under `docs/` directly.
- **Docstrings** are the single source for the API reference. Edit the docstring in the source, and let Sphinx (the documentation build tool) render it. Never copy a signature into prose by hand.
- **The API reference** is generated from the source modules at the start of every full documentation build. Only its overview page, `docs/api/index.md`, is hand-written; the module pages are build output and are never committed.
- **The CLI reference** is generated from the command tree (the full set of CLI commands and subcommands). Don't edit it; regenerate it with the commands that follow.

### Definitions of generation terms

When working with generated documentation, understand the following terminology:

- **stub**: A reference stub page is a generated reStructuredText (`.rst`) file under `docs/api/`. Each stub corresponds to a Python module or package and contains the `automodule` directive that makes Sphinx pull the live docstrings from the code. A full build writes the stubs fresh from the module tree, so adding or removing a module needs no extra step.
- **sequence golden**: The committed, recorded output of a documented CLI sequence. Only `just docs-generate-sequences` writes goldens.

## Preview and verify a change

Choose the narrowest preview that shows your change:

- **One page:** `just docs-page authoring-guide` renders a single page. The path is relative to the repository or to `docs/`, and the suffix is optional. Use it while you write. A repeat preview reuses its build cache and takes about 20 seconds.
- **A directory:** `just docs-page how-to` renders every page under that directory. Use it when a change spans several related pages.
- **Live preview:** `just docs-serve` rebuilds and refreshes the browser whenever a page under `docs/` changes. It serves the taxpayer-facing pages on port 8788, and running it again attaches to the preview that is already running. To watch docstrings and API pages as well, run `uv run --no-sync python -m dev.docs.serve --scope full --open-browser`.
- **Full build:** `just docs-build` builds the whole site, including the API reference. Run it before you hand a change over for review.

Previews render CLI sequences from their committed goldens and don't execute them, so a preview never proves a sequence still matches the product. Verify the sequences and the rest of the documentation with:

```bash
just docs-sequences-check  # re-runs the documented CLI sequences against their goldens
just check-docs-api        # confirms the API reference covers every documented module
just docs-check            # validates cross-references and command references
```

`just docs-sequences-check` and `just docs-generate-sequences` refuse to run while the local registry authority is stale. Refresh it with `uv run --no-sync python -m dev.registry.pipeline publish-authority --if-stale`, then run the command again.

`just docs-check` fails on a broken cross-reference or a command reference that no longer matches the commands.

## Take a narrative change through review

A change to the README or a guide under `docs/` moves through a staged review. Each stage has a distinct reviewer, and each completes before the next begins:

1. **Wireframe.** Outline the document as titles and section intents. Assign each page a Diataxis type — Diataxis is a documentation framework that sorts pages into four kinds: tutorial, how-to, reference, or explanation.
2. **Refinement.** A reviewer with no project context reads only the wireframe and confirms a newcomer would understand what each section delivers. Revise until every section passes.
3. **Context.** Researchers gather the facts, commands, paths, and source locations each section needs.
4. **Drafting.** Authors write each section from the gathered context and the project's prose-style rules.
5. **Technical review.** Reviewers verify every command, flag, path, and class name against the code.
6. **Editorial review.** A reviewer with no project context checks the writing against the same prose-style rules.
7. **Approval.** The change lands once the technical and editorial reviews pass.

## Keep the roles separate

Keep research, drafting, and review in separate hands. When you gather context, don't write the final prose. When you author, write from the gathered context, and don't invent facts. When you review for editorial quality, work from the document alone, without the codebase. The separation keeps each judgment honest.

## Don't encode process metadata

Documentation paths, filenames, and content carry domain and topic names only. Don't put the documentation framework or the project-management process into them. That rules out wave, phase, and step identifiers, plan and decision-record identifiers, and agent or campaign labels. A reader should see the product, not the process that built it.
