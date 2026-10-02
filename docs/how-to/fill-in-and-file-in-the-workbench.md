# Fill in and record a filing on the declaration screen

The full-screen interface gives each declaration one screen: its official
pages, every box with its value and where that value comes from, the one thing
to do next, and the help for the box under the cursor. This guide shows how to
see what you owe, fill in the boxes that need you, understand where a value
comes from, check and fix issues, and record the filing.

Cadrumo never submits a return to the AEAT. "Record filing" tells Cadrumo that
you filed; you file with the AEAT yourself. [File at AEAT](file-at-aeat.md)
explains that step.

## Before you start

- Your taxpayer profile is complete: see [Set up your taxpayer profile](profile-setup.md).
- Know which modelo, filing year and period you want to work on.

## Open a declaration

1. Start the full-screen interface with `aeat app tui` and sign in.
2. Open **Declarations**. Press Enter on a group to open or close it.
3. Select a local declaration and press Enter to open it. For a period marked
   **Not started**, Enter asks you to confirm that you want to start it.

To choose another declaration, press `+`. Choose the Modelo first. In the
period picker, press Enter to select a period, then select **Create and open**.
Esc on the period picker returns to the Modelo picker; Esc there cancels.

The list shows the state, result direction, deadline and next action. Use `/`
to search by modelo number, name or period in words; accents do not affect the
search. Press `f` to cycle through **All**, **Needs attention**, **This year**,
**Recorded** and **Not started**. Press `s` to sort by deadline, modelo, result
or state. Press `t` when you need the technical details.

Some modelos appear as possible obligations or have limited local support.
Read their coverage and next action before starting. A completed filing found
at the AEAT can appear separately from a local draft. Seeing it does not mean
the draft is linked to that filing or that its receipt is saved; the draft is
kept separately.

The declaration opens on the first box that needs you.

## See what you owe

The header names your declaration, its deadline and its calculated result.
It stays visible while you use the docked box panel. A dialog repeats the
result and the counts of things that need you.

- **Line 1** names the Modelo and the period in words. On the right it shows
  the deadline, the last day to file, and the days left. The deadline turns
  amber at 7 days or fewer and red at 3 or fewer. After the deadline it says so
  in red. When no deadline is on record, it says that instead of guessing a
  date.
- **Line 2** shows the result with its direction: **TO PAY**, **TO BE
  REFUNDED**, **TO CARRY FORWARD** or **RESULT ZERO**, with the amount in euros
  and the box it comes from. Next to it are the counts of things that need you,
  one per level (see [Check and fix issues](#check-and-fix-issues)).
- **Line 3** shows the four steps: Fill in, Calculate, Check and Record
  filing, and the next thing to do with its key. A step marked ✓ is done, ▲ is
  blocked, and the step you are on shows ▸. Steps still to come have no mark.

Before the first calculation the result reads "not calculated yet" with the key
to calculate. After a change, or when your records changed, the result carries
◷ and says "out of date". Do not rely on an amount marked ◷: apply your
changes with `R` or calculate with `c` first.

On Modelo 130, a negative result reads "Negative result: {amount} to deduct in
later quarters" in the first three quarters and "Negative result: nothing to
pay" in the fourth.

The figures are Cadrumo's calculation. The AEAT has not seen them.

## Read the screen

- **The navigator** on the left lists the official pages and their sections.
  Each shows the most serious thing inside it (▲, then !, then ◐) with a
  count. A finished section shows ✓. A section that does not apply this period
  is dimmed and says so. Press Space, or ← and →, to close or open a page.
  On a narrow terminal the navigator becomes one line above the list; use `[`
  and `]` to change page.
- **The list** shows each box: its number in brackets, its label, its value
  with its unit, and where the value comes from, in a glyph and one or two
  words.
- **The help band** at the bottom explains the box under the cursor: what it
  asks for, where its value comes from, what you can do about it, and its
  formula, the official text and its legal basis.
- **Tables.** A grid on the official form, such as the rates in Modelo 303,
  appears as a table. Press ← and → (or `h` and `l`) to move between cells and
  ↑ and ↓ to move between rows. On a narrow terminal the table is stacked
  instead.
- **Records that repeat**, such as the intra-community traders in Modelo 349,
  appear as a numbered table. Use ↑ and ↓ or Page Up and Page Down to scroll
  through the rows. These values are read-only here; change them where they
  come from, for example in your records.

A missing value is always said in words, never shown as a zero. "Optional, empty",
"Needs your input", "Assumed, please confirm" and "Not applicable" are
different things and read differently.

### Find your way around

| Key | What it does |
| --- | --- |
| `/` | Search by box number or by words, across all pages. Enter jumps to the box |
| `g` | Go to a box by its number |
| `f` | Show every box, only those that need you, or only your own values |
| `o` | Sort by form order, box number, amount or needs attention |
| `n` and `N` | Go to the next or the previous thing to do, across pages |
| `[` and `]` | Go to the previous or the next page |
| Space | Open or close the page under the cursor |
| `d` | Show each box on one line or on two |

## Fill in the boxes that need you

1. Press `n` to go to the next thing to do, or use `/` or `g` to reach a box.
2. Press Enter. The box opens in a panel with what it asks, its current value,
   where it comes from, what it affects and a field for your value. The
   header and the neighbouring rows stay visible. On a screen under 30 rows
   high, the panel opens as a dialog instead.

3. Type the value the way you write numbers in your language, for example
   `1.234,56` in Spanish or `1,234.56` in English. The panel shows how it will
   read the value. If a number could be read two ways, it names both and asks
   you to retype it.

4. Press Enter to keep it and go to the next box that needs you, or Ctrl+Enter
   to keep it and stay.

Nothing is applied yet. The box shows Δ, and the header says "changes not
applied yet". When a box cannot be typed into, the panel says why and what to
do: a value that follows your records, for example, is corrected in Records and
then recalculated.

Press `x` or Delete to clear a value you entered, and `u` to go back to the
value before your change.

### Confirm an assumed value

An assumed value ◐ is a value Cadrumo holds but nobody entered: a required
box, or a box with a non-zero value. An optional box that is empty or zero is
not assumed.

Assumed values keep "Fill in" open, and Cadrumo refuses to export or record the
filing until you confirm them.

To confirm one:

1. Open the box. Its value is already filled in and selected.
2. Press Enter to accept it as it is, or type the right value.

The confirmation is a change waiting for review. Press `R`, review it and
choose **Apply and recalculate**. The saved box then reads "Entered by you".

To confirm many at once, press `b` with the cursor in their section or page.
Cadrumo lists the values it can confirm, each with its box number and label.
Read the list, tick "I have checked these values and they are right for me",
and confirm. Values that need a source change are listed separately by reason.
Review and apply the changes with `R`. You cannot confirm the whole
declaration in one go.

## Review and apply your changes

Press `R`. Cadrumo first checks your changes against the declaration as it
stands. The review lists each change with its box, how it read before, how it
will read after, and what the change does. It warns you when your value
replaces one from your records or from a calculation: your value keeps winning
until you go back to the source.

Under the changes, the review lists what the check found. An item marked ▲
would stop the changes from being applied, so **Apply and recalculate** stays
unavailable until you resolve it.

The review asks you to tick **I have checked what applying does** before you
apply in two cases:

- The declaration was last calculated without saved input history. Cadrumo cannot
  tell which of its values you typed, so the review names the boxes whose
  values go back to what their source says. To keep one, enter its value
  first.
- The declaration changed after you made your changes. Your changes are kept,
  a change that no longer applies is removed, and the lines whose box now reads
  differently are marked.

Choose **Apply and recalculate** to apply the changes and recalculate, or
**Discard all** to drop them. After applying, the declaration screen lists every box
that changed and why: your change, recalculated, from your records, or another
change. Press Enter on a line to go to its box. If you leave with changes not
applied yet, it asks you first.

## Understand where a value comes from

Every row shows where its value comes from:

| Mark | Words on the row | Meaning |
| ---- | ---------------- | ------- |
| ● | Entered by you | You typed it, or you confirmed an assumed value |
| ≠ | Yours, replaces your records | Your value replaces the value from another source, in this declaration only |
| = | Calculated | Cadrumo worked it out from other boxes |
| ↓ | From your records, From your profile, From AEAT data | Read from your data |
| « | From an earlier declaration | Carried from a declaration you recorded before |
| ◇ | Reference value | The official form fixes it |
| ◐ | Assumed, please confirm | Nobody entered it |
| ! | Needs your input | Required, and nobody has given it |

Press Enter on a box and read the panel: for a calculated box it shows the
formula with the numbers in it, for a box from your records it says what was
added up. Where a box can be replaced, the panel says so and explains that your
records do not change.

**Override a value.** Type your own value over one that comes from your
records. The row then reads "Yours, replaces your records". The panel says your
value replaces the amount from your records in this declaration only, and
lets you go back to the source.

**Go back to the source.** Open the box and choose **Go back to the source's value**
when its panel offers it. Review and apply this change with `R`. The `u` key
only undoes a change you have not applied.

**Open the source area.** If the panel offers an action such as **Open Records**,
choose it to correct the source there, then return and recalculate.

**See every source at once.** Press `s` for the sources map. It counts boxes,
not sources: how many come from your records, earlier declarations and AEAT
data, how many you entered, confirmed or replaced, what is assumed and what is
calculated. "None found" means Cadrumo looked in that source and found
nothing, which is different from zero. Press Enter on a line to see its boxes,
and Enter on a box to go to it.

## Calculate

Press F8 to run the step the header offers, or `c` to calculate at any time
once your changes are applied. The values you entered are kept. Press `c`
whenever the header says ◷ "out of date: recalculate", for example after your
records changed.

If the declaration was last calculated without saved input history, calculating asks
first and names the boxes whose values go back to their source.

The first Modelo 303 calculation asks the filing answers its period needs:
whether you file a joint return and, in the last period of the year, whether
you are exempt from Modelo 390.

## Check and fix issues

Press `i` to open **Issues to look at**. The header shows the same counts, one
per level:

| Mark | Level | What it means |
| ---- | ----- | ------------- |
| ▲ | Blocks filing | Fix it before you can export or record the filing |
| ! | Needs your input | A required value nobody has given |
| ◐ | Assumed, please confirm | A value nobody entered; confirm it or type the right one |
| ◆ | Worth checking | Does not stop you |
| `i` | For your information | An explanation |

Each issue says what is wrong, what to do and where. Press Enter on an issue
to go to its box, or to open its details or the area that owns the problem.
Press `t` for technical details.

Problems found while calculating appear in the same list. An amount from your
records that lands in no box, or any other problem that could make you
under-declare, is marked ▲ and blocks export and recording. A problem that
would only make you pay more is marked ◆. After a change, problems from the
last calculation are labelled as such until you calculate again.

Press F8 at the Check step to check the declaration. A box that stops you from
filing shows ▲, and the navigator counts it on its section.

## Create the file and record the filing

1. Resolve every ▲ and confirm every ◐.
2. Press `e`, choose where to save the file, which file to write and, for
   Modelo 303, the refund, payment and direct debit choices. The result says
   that the file has not been sent to the AEAT.
3. File with the AEAT yourself: [File at AEAT](file-at-aeat.md).
4. Press F8 to record the filing. Cadrumo asks you to confirm.

The header then reads "Recorded as filed" with the date.

A recorded declaration opens read-only: attention marks are hidden and editing
is refused. To change it, {ref}`start a correction <correct-an-already-filed-local-record>`
(complementaria or rectificativa).

## Look up a symbol

- Press `?` once. The help band opens and its first line lists the symbols on
  this screen, with counts.
- Press `?` a second time to open **Symbols and keys**: every symbol with its
  meaning, grouped, and the keys. Press Esc or `?` to close it.
- The first time you open a declaration, a notice says "New here? Press ? to
  see what each symbol means."

| Mark | Meaning |
| ---- | ------- |
| - | Not applicable |
| ○ | Optional, empty |
| □ | Cleared by you |
| ◌ | Not calculated yet |
| × | Could not be calculated |
| … | Not imported yet |
| `Δ` | Changed, not applied |
| ◷ | Out of date |
| ✓ | Done |
| ▸ | You are here |
| ▹ ▿ | Closed, open section |

## Keys

| Key | What it does |
| --- | ------------ |
| `Enter` | Open the box under the cursor |
| `n` and `N` | Next or previous thing to do |
| `/` and `g` | Search; go to a box |
| `f`, `o`, `d` | Filter, sort, density |
| `[` and `]` | Previous or next page |
| ← and → or `h` and `l` | Move between cells in a table |
| Space | Open or close a page |
| `b` | Confirm assumed values of a section or page |
| `x` or Delete | Clear a value you entered |
| `u` | Undo a change you have not applied |
| `s` | The sources map |
| `i` | Issues |
| `R` | Review changes |
| `c` | Calculate |
| `e` | Export |
| F8 | Run the next step |
| `?` | Symbols on this screen; twice for Symbols and keys |
| `Esc` | Go back |
| F3 | Switch between the light and the dark appearance |

The footer shows as many keys as fit the width of the terminal.

## When something looks unexpected

- **Assumed, please confirm** on a declaration calculated without saved input history: Cadrumo cannot tell which values you typed. Open the box and press
  Enter to confirm it; otherwise the next apply or calculation returns it to
  its source.
- **Reference value.** The official form fixes the box; you cannot change it.
- **Pages arranged automatically.** Cadrumo arranged the pages from the official
  design and nobody has reviewed them by hand. Every box still appears exactly
  once.
- A modelo with no arrangement opens with every box in box number order, for
  viewing only.
