import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";
import type { DisagreementsRead } from "./disagreementRead";

/**
 * The answers the person gave to this declaration's source disagreements, as
 * the application lists them: its state, what it covers, whether the current
 * calculation still has it, all in its words, and the reason the person gave.
 * Nothing is drawn while no answer was given.
 */
export function DisagreementAnswers({ read }: { read: DisagreementsRead }) {
  const t = useStrings();
  if (read.phase === "idle" || read.phase === "reading") return null;
  const title = t("desktop.modelo.disagreement.list_title");
  if (read.phase === "failed")
    return (
      <section aria-label={title} className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Icon name="alert" size="xs" />
          {t("desktop.modelo.disagreement.list_failed")}
        </p>
      </section>
    );
  if (read.rows.length === 0) return null;
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
        {read.rows.map((row) => (
          <li
            key={`${row.finding_id}-${row.revision_id}`}
            data-answer-state={row.state}
            data-answer-current={row.current}
            className="flex flex-col gap-1 px-4 py-3"
          >
            <span className="text-xs text-faint" data-answer-state-words="">
              {row.state_words}
            </span>
            <span className="text-base text-foreground">
              {row.answer_words}
            </span>
            <span
              className="text-sm text-muted-foreground"
              data-answer-current-words=""
            >
              {row.current_words}
            </span>
            <span className="text-sm text-muted-foreground">
              {t("desktop.modelo.disagreement.your_reason", {
                reason: row.reason,
              })}
            </span>
            {!row.revocable && row.revoke_refusal_words && (
              <span
                className="text-sm text-muted-foreground"
                data-answer-unrevocable=""
              >
                {row.revoke_refusal_words}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
