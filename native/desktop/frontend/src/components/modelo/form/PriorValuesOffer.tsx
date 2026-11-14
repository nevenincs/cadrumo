import { useId, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import type { PublicModeloFormPriorValueAttestation } from "../../../shell/modeloContract/modeloWorkFormPart2";
import type { RefusalIntent, WindowPlace } from "../../../shell/refusal";
import { usePanePreference } from "../../../shell/panePreference";
import { useStrings } from "../../../shell/strings";
import { RefusalNotice } from "../../RefusalNotice";
import { BoxNumber } from "./BoxNumber";
import { calm } from "./FieldRow";
import {
  editKey,
  type EntryOutcome,
  type FormSession,
  type PriorWithdrawal,
} from "./session";

// The figures the filer can state for earlier returns the application does
// not hold, as the form serves them: grouped by the earlier returns they
// stand in for, each carry in the words the form served for the statement.
// A carry whose earlier return the application holds is refused with the
// served sentence and its served way out. The figures stated for one family
// of earlier returns are withdrawn together, by the served withdrawal, or not
// at all. The window names no earlier return and decides no admission.

type RefusalDoors = {
  onRefusalAction?: (intent: RefusalIntent) => void;
  opensRefusalPlace?: (place: WindowPlace) => boolean;
};

/** The served entries by family, each family in the order it is first
 * served and its carries in served order. */
function families(
  entries: readonly PublicModeloFormPriorValueAttestation[],
): PublicModeloFormPriorValueAttestation[][] {
  const byFamily = new Map<string, PublicModeloFormPriorValueAttestation[]>();
  for (const entry of entries) {
    const held = byFamily.get(entry.family_id);
    if (held) held.push(entry);
    else byFamily.set(entry.family_id, [entry]);
  }
  return [...byFamily.values()];
}

/** The name the offer's shown or hidden state is kept under in the
 * viewer's preferences. */
export const PRIOR_VALUES_PANE = "modelo.workspace.prior_values";

export function PriorValuesOffer({
  session,
  onRefusalAction,
  opensRefusalPlace,
}: { session: FormSession } & RefusalDoors) {
  const t = useStrings();
  // Shown or hidden as the viewer last left it, on every declaration.
  const kept = usePanePreference(PRIOR_VALUES_PANE);
  const open = kept.preference.open ?? true;
  const setOpen = kept.setOpen;
  const titleId = useId();
  const listId = useId();
  const { priorValues } = session;
  if (priorValues.length === 0) return null;
  return (
    <section
      aria-labelledby={titleId}
      data-prior-values=""
      className="flex flex-none flex-col gap-2 border-b border-border px-6 py-3"
    >
      <div className="flex items-center gap-2">
        <Icon name="bookmark" size="xs" className="text-muted-foreground" />
        <h2 id={titleId} className="text-sm font-medium">
          {t("desktop.modelo.prior_values.title")}
        </h2>
        <Badge variant="neutral">{priorValues.length}</Badge>
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
        <div id={listId} className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            {t("desktop.modelo.prior_values.intro")}
          </p>
          {families(priorValues).map((entries) => (
            <PriorFamily
              key={entries[0]?.family_id}
              entries={entries}
              session={session}
              onRefusalAction={onRefusalAction}
              opensRefusalPlace={opensRefusalPlace}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function PriorFamily({
  entries,
  session,
  onRefusalAction,
  opensRefusalPlace,
}: {
  entries: PublicModeloFormPriorValueAttestation[];
  session: FormSession;
} & RefusalDoors) {
  const t = useStrings();
  const headingId = useId();
  const [refused, setRefused] = useState<Extract<
    PriorWithdrawal,
    { kind: "refused" }
  > | null>(null);
  const first = entries[0];
  if (!first) return null;
  const withdrawal =
    entries.find((entry) => entry.withdrawal !== null)?.withdrawal ?? null;
  const withdrawn = session.stagesPriorWithdrawal(first.family_id);
  return (
    <div
      role="group"
      aria-labelledby={headingId}
      data-prior-family={first.family_id}
      className="flex flex-col gap-2"
    >
      <h3 id={headingId} className="text-sm font-medium">
        {first.source_words}
      </h3>
      <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
        {entries.map((entry) => (
          <PriorEntry
            key={entry.binding_id}
            entry={entry}
            session={session}
            onRefusalAction={onRefusalAction}
            opensRefusalPlace={opensRefusalPlace}
          />
        ))}
      </ul>
      {withdrawal && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="xs"
            variant="outline"
            data-withdraw-prior={withdrawal.family_id}
            disabled={withdrawn}
            onClick={() => {
              const outcome = session.withdrawPriorValues(withdrawal);
              setRefused(outcome.kind === "refused" ? outcome : null);
            }}
          >
            <Icon name="erase" size="xs" />
            {withdrawal.action_words}
          </Button>
          <span className="text-sm text-muted-foreground">
            {withdrawn
              ? t("desktop.modelo.statements.withdrawn")
              : withdrawal.effect_words}
          </span>
        </div>
      )}
      {refused && !withdrawn && (
        <p
          role="status"
          className="flex items-start gap-1 text-sm text-warning"
        >
          <Icon name="alert" size="xs" className="mt-0.5 shrink-0" />
          {refused.field
            ? t("desktop.modelo.statements.withdraw_kept", {
                box: refused.field.box ?? refused.field.label.text,
              })
            : t("desktop.modelo.statements.not_placed")}
        </p>
      )}
    </div>
  );
}

/** What the filer is told when an entry was not staged, or null when it
 * was. */
function entrySaid(
  t: ReturnType<typeof useStrings>,
  outcome: EntryOutcome,
): string | null {
  if (outcome.kind === "refused")
    return (
      outcome.entry.refusal_words ?? t("workspace.modelo.editor.unreadable")
    );
  if (outcome.kind === "failed")
    return outcome.words ?? t("workspace.modelo.editor.not_checked");
  return null;
}

function PriorEntry({
  entry,
  session,
  onRefusalAction,
  opensRefusalPlace,
}: {
  entry: PublicModeloFormPriorValueAttestation;
  session: FormSession;
} & RefusalDoors) {
  const t = useStrings();
  const describedBy = useId();
  // The box whose edit is submitted to the carry's binding, which can be a
  // box addressed by its casilla that the binding feeds.
  const key = `b:${entry.binding_id}`;
  const field =
    session.placed.find((placed) => editKey(placed.field) === key)?.field ??
    null;
  const staged = session.staged.get(key);
  const stating = staged?.intent.kind === "attest_prior_value" ? staged : null;
  const [text, setText] = useState(stating?.entry ?? "");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const takes = field !== null && session.editable(field);
  const state = async (event: FormEvent) => {
    event.preventDefault();
    if (!field || pending) return;
    setPending(true);
    setMessage(null);
    const outcome = await session.enter(field, text, {
      family: entry.family_id,
      words: entry.action_words,
      effect: entry.effect_words,
    });
    setPending(false);
    setMessage(entrySaid(t, outcome));
  };
  return (
    <li
      data-prior-entry={entry.binding_id}
      data-stated={entry.stated || undefined}
      data-admitted={entry.admitted}
      className="flex flex-col gap-2 px-3 py-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        {field && <BoxNumber box={field.box} size="sm" />}
        <span className="min-w-0 flex-1 text-base">
          {field ? calm(field.label.text) : entry.source_words}
        </span>
        {stating ? (
          <span className="inline-flex items-center gap-1 text-sm text-foreground">
            <Icon name="edit" size="xs" />
            {stating.read ?? stating.entry}
            <span className="text-muted-foreground">
              {t("workspace.modelo.attention.staged")}
            </span>
          </span>
        ) : (
          entry.stated && (
            <span className="inline-flex items-center gap-1.5 text-sm">
              <Badge variant="neutral">
                <Icon name="bookmark" size="xs" />
                {t("desktop.modelo.statements.mark")}
              </Badge>
              {field?.value_text}
            </span>
          )
        )}
      </div>
      {!entry.admitted ? (
        <RefusalNotice
          refusal={{
            refusal_words: entry.refusal_words,
            verdict: entry.refusal,
          }}
          onAction={onRefusalAction}
          opens={opensRefusalPlace}
        />
      ) : takes ? (
        <form
          onSubmit={(event) => void state(event)}
          className="flex flex-col gap-1.5"
        >
          <div className="flex items-center gap-2">
            <Input
              controlSize="sm"
              className="max-w-44 tabular-nums"
              aria-label={entry.action_words}
              aria-describedby={describedBy}
              aria-invalid={message !== null || undefined}
              value={text}
              disabled={pending}
              onChange={(event) => {
                setText(event.target.value);
                setMessage(null);
              }}
            />
            <Button
              type="submit"
              size="xs"
              variant="secondary"
              disabled={pending}
            >
              {entry.action_words}
            </Button>
          </div>
          <span
            id={describedBy}
            className="flex flex-col gap-0.5 text-sm text-muted-foreground"
          >
            <span>{entry.statement_words}</span>
            <span>{entry.effect_words}</span>
          </span>
          {message && (
            <span
              role="status"
              className="flex items-start gap-1 text-sm text-warning"
            >
              <Icon name="alert" size="xs" className="mt-0.5 shrink-0" />
              {message}
            </span>
          )}
        </form>
      ) : (
        !field && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.modelo.statements.not_placed")}
          </p>
        )
      )}
    </li>
  );
}
