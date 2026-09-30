# Fill in and file a declaration in the workbench

The full-screen interface gives each declaration one workbench: its official
pages, every box with its value and where that value comes from, the one thing
to do next, and the help for the box under the cursor. This guide shows how to
open a declaration, fill it in, calculate, review, file and export it.

Cadrumo records a filing in your own records. It never submits a return to the
AEAT; [File at AEAT](file-at-aeat.md) explains that step.

## Before you start

- Your taxpayer profile is complete: see [Set up your taxpayer profile](profile-setup.md).
- The declaration exists. In **Declarations**, use *Create or reopen a
  declaration* with the modelo, the filing year and the period.

## Open a declaration

1. Start the full-screen interface with `aeat app tui` and sign in.
2. Open **Declarations**, select the declaration in the list and press Enter.

The workbench opens on the first box that needs you.

## Read the workbench

- **The header** names the modelo, the period in words and, when the modelo
  declares one, the calculated result.
- **The journey line** shows the four steps: Fill in, Calculate, Review and
  File. A step marked ✓ is done, ● is the current step, ▲ is blocked and ○ is
  still to come.
- **The next line** says the one thing to do next and the key that does it. It
  also counts the default values you have not confirmed.
- **The navigator** on the left lists the official pages and their sections. A
  section marked ! with a number still has boxes that need you; ✓ marks a
  finished one. On a narrow terminal the navigator folds away: use `[` and `]`
  to change page.
- **The list** shows each box: its number in brackets, its label, its value, a
  state mark and the state in words.
- **The help band** explains the box under the cursor: what it asks for, where
  its value comes from, what you can do about it and, once loaded, its formula,
  the official text and its legal basis. Press `?` or F1 to enlarge it; the
  enlarged band also lists every key.

A value that is missing is always said in words, never shown as a zero.

### State marks

| Mark | Meaning |
| ---- | ------- |
| - | Not applicable |
| ≠ | Your value replaces the source |
| = | Calculated |
| ◌ | Not calculated yet |
| × | Could not be calculated |
| ◇ | For information |
| ! | Needs your input |
| ↓ | Imported |
| ⇣ | Not imported yet |
| ○ | Optional, empty |
| □ | Cleared by you |
| ◐ | Default, please confirm |
| ● | Entered by you |
| Δ | Changed, not applied |
| ▲ | Blocks filing |

### Keys

| Key | What it does |
| --- | ------------ |
| Enter | Edit the box under the cursor |
| `n` and `N` | Go to the next or the previous box that needs you |
| `[` and `]` | Go to the previous or the next page |
| `f` | Show every box, only those that need you, or only your own values |
| `d` | Show each box on one line or on two |
| `s` | See where the values come from |
| `x` or Delete | Clear a value you entered |
| `u` | Undo the change you made to the box |
| `R` | Review your changes |
| F8 | Run the next step |
| `i` | List what verification found |
| `c` | Calculate |
| `e` | Export |
| `?` or F1 | Enlarge the help and list every key |
| Esc | Go back |
| F3 | Switch between the light and the dark appearance |

The footer shows as many keys as fit the width of the terminal.

## Fill in boxes

1. Move to a box with the arrow keys or with `n`, then press Enter.
2. Type the value the way you write numbers in your language, for example
   `1.234,56` in Spanish or `1,234.56` in English. The editor shows how it
   will read the value, or says why it cannot read it.
3. Choose **Add to changes**. The box shows Δ with the value it replaces.

Nothing is saved yet. When a box cannot be typed into, the help band says
why: a value that follows your records, for example, is corrected in the
ledger and then recalculated.

## Review and apply your changes

Press `R`. Cadrumo first checks your changes against the declaration as it
stands. The review then lists each change with its box, how it read before,
how it will read after, and what the change does. It warns you when your value
replaces an imported or a calculated one: your value keeps winning until you
restore the source.

Under the changes, the review lists what the check found. An item marked ▲
would stop the changes from being applied, so **Apply and recalculate** stays
unavailable until you resolve it.

The review asks you to tick **I have checked what applying does** before you
apply in two cases:

- The declaration was last calculated outside the workbench. Cadrumo cannot
  tell which of its values you typed, so the review names the boxes whose
  values go back to what their source says. To keep one, enter its value
  first.
- The declaration changed after you staged your changes. Your changes are
  kept, a change that no longer applies is removed, and the lines whose box
  now reads differently are marked.

Choose **Apply and recalculate** to save the changes and recalculate the
declaration, or **Discard all** to drop them. If you leave the workbench with
changes you have not applied, it asks you first.

After an apply or a recalculation, the workbench lists every box that changed
and why: your change, recalculated, from your sources, or another change.
Press Enter on a line to go to its box.

## See where the values come from

Press `s` on any box. The sources view groups every source by family: your
records, the registers you keep, your profile, earlier filings, the AEAT draft,
the values you enter and the values the official design fixes. Each source
says what you can do about its values and whether it has produced data, and
lists the boxes it feeds.

Press Enter to go to a box, or `o` to open the area that owns the source, such
as the ledger or your profile.

## Calculate, verify, file and export

- Press F8 to run the step the journey line offers, or `c` to recalculate at
  any time once your changes are applied. The values you entered are kept.
- If the declaration was last calculated outside the workbench, recalculating
  asks first, and names the boxes whose values go back to their source.
- The first Modelo 303 calculation asks the filing answers its period needs:
  whether you file a joint return and, in the last period of the year, whether
  you are exempt from Modelo 390.
- Verification checks the declaration. A box that stops you from filing shows
  ▲, and the navigator counts it on its section. When verification finds
  something, the next line says so: press `i` or F8 to list the findings,
  those that block filing first, and Enter to go to the box a finding names.
- Filing asks you to confirm, then records the filing in Cadrumo.
- Once the declaration is verified, `e` exports it: choose where to save it,
  which file to write and, for Modelo 303, the refund, payment and direct
  debit choices. The export result then states what the file is worth.

## When something looks unexpected

- **Default, please confirm.** For a declaration calculated outside the
  workbench, Cadrumo cannot tell which values you typed. Enter the value to
  confirm it; otherwise the next apply or recalculation returns it to its
  source.
- **fixed.** The official design prints the value of the box; you cannot
  change it.
- **pages arranged automatically.** The pages were arranged from the official
  design by Cadrumo and have not been reviewed by hand. Every box still appears
  exactly once.
- A declaration whose modelo has no arrangement opens with every box in box
  number order, for viewing only.
