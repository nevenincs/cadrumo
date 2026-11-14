import { useId, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import { usePanePreference } from "../../../shell/panePreference";
import { useStrings } from "../../../shell/strings";
import { rowOfStatement } from "./rowStatements";
import type { FormSession } from "./session";

// The statements a declaration serves, offered together: each in the words
// the form served for it (what the filer states, what that says and what it
// does), in the order served, with a tick. Ticking several and staging puts
// them all in the one review with the filer's other changes; leaving one
// staged earlier unticked takes it back. The window names no statement and
// chooses none: it lists what the form serves and stages what was ticked,
// each on every box the form says it covers. A statement the form serves for
// one row of a repeating group is a row of its own, named in the words served
// for the row, and is staged on the row it names.

export function StatementsOffer({ session }: { session: FormSession }) {
  const t = useStrings();
  const { statements } = session;
  const staged = statements.map((statement) =>
    session.stagesStatement(statement),
  );
  // The ticks follow what is staged until the filer changes one.
  const [ticked, setTicked] = useState<boolean[] | null>(null);
  // Shown or hidden as the viewer last left it, on every declaration.
  const kept = usePanePreference("modelo.workspace.statements");
  const open = kept.preference.open ?? true;
  const setOpen = kept.setOpen;
  const [unplaced, setUnplaced] = useState(false);
  const titleId = useId();
  const listId = useId();
  if (statements.length === 0) return null;
  const now = ticked ?? staged;
  const changed = now.some((tick, at) => tick !== staged[at]);
  const stageTicked = () => {
    const missed = session.stageStatements(
      statements.filter((_, at) => now[at]),
    );
    setUnplaced(missed.length > 0);
    setTicked(null);
  };
  return (
    <section
      aria-labelledby={titleId}
      data-statements=""
      className="flex flex-none flex-col gap-2 border-b border-border px-6 py-3"
    >
      <div className="flex items-center gap-2">
        <Icon name="bookmark" size="xs" className="text-muted-foreground" />
        <h2 id={titleId} className="text-sm font-medium">
          {t("desktop.modelo.statements.title")}
        </h2>
        <Badge variant="neutral">{statements.length}</Badge>
        <span className="ml-auto" />
        <Button
          size="xs"
          variant="ghost"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen(!open)}
        >
          {t(
            open
              ? "desktop.modelo.statements.hide"
              : "desktop.modelo.statements.show",
          )}
        </Button>
      </div>
      {open && (
        <div id={listId} className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            {t("desktop.modelo.statements.intro")}
          </p>
          <ul className="flex flex-col gap-3">
            {statements.map((statement, at) => (
              <li
                key={`${statement.family}:${rowOfStatement(statement) ?? ""}`}
                data-statement={statement.family}
                data-statement-row={rowOfStatement(statement) ?? undefined}
              >
                <label className="flex cursor-pointer items-start gap-2.5">
                  <Checkbox
                    className="mt-1"
                    checked={now[at] ?? false}
                    aria-describedby={`${listId}-${at}`}
                    onChange={(event) => {
                      const next = [...now];
                      next[at] = event.target.checked;
                      setTicked(next);
                      setUnplaced(false);
                    }}
                  />
                  <span className="flex min-w-0 flex-col gap-0.5">
                    {statement.row_words && (
                      <span className="text-sm font-medium text-foreground">
                        {statement.row_words}
                      </span>
                    )}
                    <span className="text-base font-medium">
                      {statement.action_words}
                    </span>
                    <span
                      id={`${listId}-${at}`}
                      className="flex flex-col gap-0.5 text-sm text-muted-foreground"
                    >
                      <span>{statement.statement_words}</span>
                      <span>{statement.effect_words}</span>
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {unplaced && (
            <p
              role="status"
              className="flex items-start gap-1.5 text-sm text-warning"
            >
              <Icon name="alert" size="xs" className="mt-0.5 shrink-0" />
              {t("desktop.modelo.statements.not_placed")}
            </p>
          )}
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="secondary"
              disabled={!changed}
              onClick={stageTicked}
            >
              {t("desktop.modelo.statements.stage")}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
