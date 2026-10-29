import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { aeatSyncDay } from "../../shell/aeatSync";
import type { NotificationRow } from "../../shell/aeatSyncResults";
import { useStrings } from "../../shell/strings";

function Row({ row, language }: { row: NotificationRow; language: string }) {
  const t = useStrings();
  const received = aeatSyncDay(language, row.received_on) ?? row.received_on;
  const readOn = row.read_on ? aeatSyncDay(language, row.read_on) : null;
  return (
    <li
      data-read={row.read}
      className="flex items-start gap-2 border-t py-2 first:border-t-0"
    >
      <Icon
        name={row.read ? "eye" : "mail"}
        size="sm"
        className="mt-0.5 shrink-0 text-muted-foreground"
      />
      <span className="min-w-0 flex-1">
        <span
          className={
            row.read
              ? "block text-base text-foreground"
              : "block text-base font-semibold text-foreground"
          }
        >
          {row.subject}
        </span>
        <span className="block text-sm text-muted-foreground">
          {t("desktop.aeat_sync.results.notifications.from", {
            sender: row.sender,
            date: received,
          })}
        </span>
        {readOn && (
          <span className="block text-sm text-muted-foreground">
            {t("desktop.aeat_sync.results.notifications.read_on", {
              date: readOn,
            })}
          </span>
        )}
      </span>
    </li>
  );
}

/**
 * The notifications AEAT lists, unread first. An unread one is only listed:
 * its document can be opened once it has been read at AEAT, and opening it
 * there can count as receiving it, so the person goes to AEAT to decide.
 */
export function NotificationResults({
  rows,
  language,
  onOpenAeat,
}: {
  rows: readonly NotificationRow[];
  language: string;
  onOpenAeat(): void;
}) {
  const t = useStrings();
  const unread = rows.filter((row) => !row.read);
  const read = rows.filter((row) => row.read);
  if (rows.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        {t("desktop.aeat_sync.results.notifications.empty")}
      </p>
    );
  return (
    <div className="flex flex-col gap-3">
      {unread.length > 0 && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("desktop.aeat_sync.results.notifications.warning")}
          <span>
            <Button size="xs" variant="outline" onClick={onOpenAeat}>
              <Icon name="external" size="xs" />
              {t("desktop.aeat_sync.results.notifications.open")}
            </Button>
          </span>
        </Alert>
      )}
      {[
        { id: "unread", list: unread },
        { id: "read", list: read },
      ].map(({ id, list }) =>
        list.length === 0 ? null : (
          <section
            key={id}
            data-group={id}
            aria-label={t(
              `desktop.aeat_sync.results.notifications.group.${id}`,
              {
                count: list.length,
              },
            )}
          >
            <h4 className="text-base font-medium text-foreground">
              {t(`desktop.aeat_sync.results.notifications.group.${id}`, {
                count: list.length,
              })}
            </h4>
            <ul>
              {list.map((row) => (
                <Row
                  key={`${row.received_on}:${row.subject}`}
                  row={row}
                  language={language}
                />
              ))}
            </ul>
          </section>
        ),
      )}
    </div>
  );
}
