import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { formatTime } from "../../shared/dateFormats";
import type {
  HomeZoneState,
  PublicHomeProjectionV1,
} from "../../shell/homeContract";
import { useStrings, type Translate } from "../../shell/strings";

/** The views a Home row can take the person to: both are pages the window
 * already draws, so a row grants nothing a link does not. */
export type HomeDestination = "declarations" | "calendar";

/** What a zone that is not showing its data says of itself: the product's
 * own reason where it served one, otherwise the standing in the window's
 * generic words. Null for a zone that is showing its data. */
export function zoneNote(
  t: Translate,
  locale: string,
  zone: HomeZoneState,
): string | null {
  if (zone.availability === "available") return null;
  if (zone.reason_words) return zone.reason_words;
  switch (zone.availability) {
    case "locked":
      return t("desktop.home.availability_locked");
    case "stale":
      return zone.observed_at
        ? t("desktop.home.availability_stale_observed", {
            date: formatTime(locale, zone.observed_at),
          })
        : t("desktop.home.availability_stale");
    case "never_captured":
      return t("desktop.home.availability_never_captured");
    case "unavailable":
      return t("desktop.home.availability_unavailable");
  }
}

function Zone({
  zone,
  heading,
  note,
  children,
}: {
  /** Which zone of Home this is, for whoever looks for it. */
  zone: "actions" | "declarations" | "agenda" | "ledger" | "messages";
  heading: string;
  /** Why the zone shows no data; given, the zone shows none. */
  note: string | null;
  children?: ReactNode;
}) {
  return (
    <section
      aria-label={heading}
      data-zone={zone}
      className="flex flex-col gap-2 rounded-lg border bg-card p-3"
    >
      <h3 className="text-base font-semibold text-foreground">{heading}</h3>
      {note !== null ? (
        <p
          data-unavailable
          className="flex items-start gap-2 text-sm text-muted-foreground"
        >
          <Icon name="unknown" size="sm" className="mt-0.5 shrink-0" />
          <span className="min-w-0">{note}</span>
        </p>
      ) : (
        children
      )}
    </section>
  );
}

const rowClass =
  "h-auto w-full min-w-0 justify-start gap-2 py-1.5 text-left font-normal whitespace-normal text-foreground";

function Row({
  icon,
  onOpen,
  children,
}: {
  icon: IconName;
  onOpen?: () => void;
  children: ReactNode;
}) {
  const body = (
    <>
      <Icon name={icon} size="sm" className="shrink-0 text-muted-foreground" />
      <span className="min-w-0 [overflow-wrap:anywhere]">{children}</span>
    </>
  );
  return (
    <li>
      {onOpen ? (
        <Button variant="ghost" className={rowClass} onClick={onOpen}>
          {body}
        </Button>
      ) : (
        <p className="flex items-start gap-2 px-2.5 py-1.5 text-base text-foreground">
          {body}
        </p>
      )}
    </li>
  );
}

/** The words a row's parts were served as, joined; a part the product served
 * no words for is left out, and a row with none says so. */
function said(t: Translate, parts: (string | null)[]): string {
  const given = parts.filter((part): part is string => !!part);
  return given.length > 0 ? given.join(" · ") : t("desktop.home.unworded");
}

/**
 * The zones of Home as the product served them: next actions, declarations to
 * resume, the filing dates ahead, the ledger's readiness and the messages. A
 * zone that is not showing its data says why and shows no row and no count,
 * so an unread zone is never drawn as an empty one.
 */
export function HomeZones({
  projection,
  locale,
  onOpen,
}: {
  projection: PublicHomeProjectionV1;
  locale: string;
  onOpen: (destination: HomeDestination) => void;
}) {
  const t = useStrings();
  const empty = (
    <p className="px-2.5 text-sm text-muted-foreground">
      {t("desktop.home.empty")}
    </p>
  );
  const actions = zoneNote(t, locale, projection.actions_state);
  const declarations = zoneNote(t, locale, projection.declarations_state);
  const agenda = zoneNote(t, locale, projection.agenda_state);
  const ledger = zoneNote(t, locale, projection.ledger_state);
  const messages = zoneNote(t, locale, projection.messages_state);
  const evidence = zoneNote(t, locale, projection.agenda_evidence_state);
  return (
    <div className="grid gap-3 @2xl/home:grid-cols-2">
      <Zone
        zone="actions"
        heading={t("desktop.home.heading_actions")}
        note={actions}
      >
        {projection.actions.length === 0 ? (
          empty
        ) : (
          <ul className="flex flex-col">
            {projection.actions.map((item) => (
              <Row key={`${item.rank}`} icon="pending">
                {said(t, [
                  item.action_words,
                  item.reason_words,
                  item.period_words,
                ])}
              </Row>
            ))}
          </ul>
        )}
      </Zone>
      <Zone
        zone="declarations"
        heading={t("desktop.home.heading_declarations")}
        note={declarations}
      >
        {projection.declarations.length === 0 ? (
          empty
        ) : (
          <ul className="flex flex-col">
            {projection.declarations.map((item) => (
              <Row
                key={item.work_unit_id}
                icon="page"
                onOpen={() => onOpen("declarations")}
              >
                {said(t, [item.period_words, item.name, item.state_words])}
              </Row>
            ))}
          </ul>
        )}
      </Zone>
      <Zone
        zone="agenda"
        heading={t("desktop.home.heading_agenda")}
        note={agenda}
      >
        {evidence !== null && (
          <p data-unavailable className="px-2.5 text-sm text-muted-foreground">
            {t("desktop.home.aeat_evidence", { state: evidence })}
          </p>
        )}
        {projection.agenda.length === 0 ? (
          empty
        ) : (
          <ul className="flex flex-col">
            {projection.agenda.map((item) => (
              <Row
                key={`${item.modelo}/${item.period.filing_year}/${item.period.code}`}
                icon="calendar"
                onOpen={() => onOpen("calendar")}
              >
                {said(t, [
                  item.due_on_text,
                  t("desktop.home.modelo", { modelo: item.modelo }),
                  item.period_words,
                  item.filing_status_words,
                ])}
              </Row>
            ))}
          </ul>
        )}
      </Zone>
      <Zone
        zone="ledger"
        heading={t("desktop.home.heading_ledger")}
        note={ledger}
      >
        <p className="px-2.5 text-base text-foreground">
          {projection.ledger?.summary_words ?? t("desktop.home.unworded")}
        </p>
      </Zone>
      <Zone
        zone="messages"
        heading={t("desktop.home.heading_messages")}
        note={messages}
      >
        <p className="px-2.5 text-base text-foreground">
          {projection.messages_requiring_attention === null
            ? t("desktop.home.unworded")
            : t("desktop.home.messages_attention", {
                count: projection.messages_requiring_attention,
              })}
        </p>
      </Zone>
    </div>
  );
}
