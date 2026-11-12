import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import type {
  HouseholdGroup,
  HouseholdGroupState,
  HouseholdPersonEdit,
  HouseholdQuestion,
  HouseholdRow,
  ProfileHousehold,
  ProfileCompanionPort,
} from "../../shell/profileHousehold";
import { useStrings } from "../../shell/strings";
import type { ProfileChange, UserProfilePort } from "../../shell/userProfile";
import {
  addition,
  answerEdit,
  atCap,
  blockedWrite,
  declaredNone,
  factWords,
  orderedRows,
  removal,
  replacement,
  rowChangeOf,
  statedChoice,
} from "./householdModel";
import {
  HouseholdPersonDialog,
  type PersonAction,
} from "./HouseholdPersonDialog";

// The household a profile states, drawn group by group exactly as the product
// serves it: what is known about each group of people, the people recorded,
// the words for "N stated, M recorded", and the limit the declaration's design
// sets. Nothing here knows what a descendant or an ascendant is owed. A group
// nobody has answered is unknown, never empty; a hidden value stays hidden.
// Adding or removing one person goes through the group's served control, in
// its words, and resends nobody else; editing a person is the product's
// whole-set replacement. Every change names the revision the household was
// read at. A question the product asks of the household is drawn apart from
// the groups: its answer is stated, or not stated, and not stated is never
// drawn as a "no".

/** How each stated state of a group is marked. A state is a stated token of
 * the product, and each keeps a mark and words of its own. */
const STATE: Record<
  HouseholdGroupState,
  { icon: IconName; tone: string; words: string; help: string | null }
> = {
  rows: {
    icon: "users",
    tone: "text-success",
    words: "desktop.profile.household.state.rows",
    help: null,
  },
  incomplete: {
    icon: "alert",
    tone: "text-warning",
    words: "desktop.profile.household.state.incomplete",
    help: null,
  },
  none_declared: {
    icon: "check",
    tone: "text-success",
    words: "desktop.profile.household.state.none_declared",
    help: "desktop.profile.household.state.none_declared_help",
  },
  unknown: {
    icon: "unknown",
    tone: "text-faint",
    words: "desktop.profile.household.state.unknown",
    help: "desktop.profile.household.state.unknown_help",
  },
  not_served: {
    icon: "unplug",
    tone: "text-faint",
    words: "desktop.profile.household.state.not_served",
    help: "desktop.profile.household.state.not_served_help",
  },
};

/** How a rejected read or write is worded, from the host's code alone. */
const FAILURE_WORDS: Record<string, string> = {
  not_signed_in: "desktop.profile.signed_out",
  refused: "desktop.profile.refused",
  conflict: "desktop.profile.conflict",
  unknown: "desktop.profile.unknown",
  saved_unread: "desktop.profile.saved_unread",
};

type Failure = {
  code: string;
  /** The finished sentence the application served for a refusal, when the
   * rejection carries one. The window shows it as served. */
  words: string | null;
};

function failureOf(error: unknown): Failure {
  const found = error as { code?: unknown; refusal_words?: unknown } | null;
  const words = found?.refusal_words;
  return {
    code: typeof found?.code === "string" ? found.code : "unavailable",
    words: typeof words === "string" && words.trim() !== "" ? words : null,
  };
}

const wordsOf = (failure: Failure, t: (key: string) => string) =>
  failure.words ??
  t(FAILURE_WORDS[failure.code] ?? "desktop.profile.unavailable");

type Read =
  | { phase: "reading" }
  | { phase: "failed"; failure: Failure }
  | { phase: "ready"; household: ProfileHousehold };

type Open = {
  group: HouseholdGroup;
  row: HouseholdRow | null;
  number: number;
  action: PersonAction;
};

/** A dialog open on the household read it was opened from: a person removed
 * is named by the index that read served, at that read's revision. */
type Opened = Open & { read: ProfileHousehold };

type Notice = { kind: "saved" } | { kind: "failed"; failure: Failure } | null;

export type HouseholdProps = {
  reads: Pick<ProfileCompanionPort, "household">;
  change: UserProfilePort["change"];
  /** Told whenever the profile changes elsewhere, where the host reports it. */
  observe?: UserProfilePort["observe"];
  language: string;
  /** Whether this window may write the profile now. */
  writable?: boolean;
  /** Whether the window asked the signed-in session to end. The host tells
   * every observer of the end, and nothing wants a household read after it. */
  sessionEnded?: () => boolean;
};

/** The facts one person states, in the order their group serves its leaves. */
function Person({
  group,
  row,
  number,
  disabled,
  editable,
  onEdit,
  onRemove,
}: {
  group: HouseholdGroup;
  row: HouseholdRow;
  number: number;
  disabled: boolean;
  /** Whether the person's facts can be stated again from here. */
  editable: boolean;
  onEdit(): void;
  onRemove(): void;
}) {
  const t = useStrings();
  const facts = group.leaves.flatMap((leaf) => {
    const fact = row.facts.find((entry) => entry.leaf === leaf.leaf);
    return fact ? [{ leaf, fact }] : [];
  });
  return (
    <li
      data-household-person={row.row_index}
      className="flex items-start gap-3 rounded-md border border-border px-3 py-2"
    >
      <span className="w-6 shrink-0 pt-0.5 text-right text-sm text-faint tabular-nums">
        {number}
      </span>
      <dl className="grid min-w-0 flex-1 grid-cols-[minmax(0,max-content)_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
        {facts.map(({ leaf, fact }) => (
          <div key={leaf.leaf} className="contents">
            <dt className="text-muted-foreground">{leaf.label}</dt>
            <dd
              data-household-fact={leaf.leaf}
              data-masked={fact.masked || undefined}
              className="min-w-0 break-words text-foreground"
            >
              {fact.masked ? (
                <>
                  <span aria-hidden="true">{fact.value}</span>
                  <span className="sr-only">
                    {t("desktop.profile.household.hidden")}
                  </span>
                </>
              ) : (
                factWords(leaf, fact.value)
              )}
            </dd>
          </div>
        ))}
      </dl>
      <span className="flex shrink-0 gap-0.5">
        <IconButton
          size="xs"
          variant="ghost"
          disabled={disabled || !editable}
          label={t("desktop.profile.household.edit_person", { number })}
          onClick={onEdit}
        >
          <Icon name="edit" size="xs" />
        </IconButton>
        {group.remove_row_action &&
          rowChangeOf(group.remove_row_action) !== null && (
            <IconButton
              size="xs"
              variant="ghost"
              disabled={disabled}
              label={group.remove_row_action.action_words}
              data-household-remove={row.row_index}
              onClick={onRemove}
            >
              <Icon name="trash" size="xs" />
            </IconButton>
          )}
      </span>
    </li>
  );
}

function Group({
  group,
  disabled,
  onOpen,
  onNone,
}: {
  group: HouseholdGroup;
  disabled: boolean;
  onOpen(open: Open): void;
  onNone(): void;
}) {
  const t = useStrings();
  const heading = useId();
  const mark = STATE[group.state];
  const people = orderedRows(group);
  const blocked = blockedWrite(group);
  const full = atCap(group);
  const locked = disabled || blocked !== null;
  const add =
    group.add_row_action && rowChangeOf(group.add_row_action) !== null
      ? group.add_row_action
      : null;
  return (
    <section
      aria-labelledby={heading}
      data-household-group={group.group_key}
      data-household-state={group.state}
      className="flex flex-col gap-2 rounded-lg border border-border bg-background p-3"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h4 id={heading} className="text-base font-medium text-foreground">
          {group.label}
        </h4>
        <span className="flex items-center gap-1.5 text-sm">
          <Icon name={mark.icon} size="xs" className={mark.tone} />
          <span data-household-mark="" className="text-foreground">
            {t(mark.words)}
          </span>
        </span>
        {people.length > 0 && (
          <span className="text-sm text-muted-foreground tabular-nums">
            {group.max_rows === null
              ? t("desktop.profile.household.people", {
                  count: people.length,
                })
              : t("desktop.profile.household.limit", {
                  count: people.length,
                  max: group.max_rows,
                })}
          </span>
        )}
        <span className="ml-auto flex items-center gap-1">
          {(group.state === "unknown" || group.state === "incomplete") &&
            people.length === 0 && (
              <Button
                size="xs"
                variant="ghost"
                disabled={locked}
                onClick={onNone}
              >
                {t("desktop.profile.household.declare_none")}
              </Button>
            )}
          {add && (
            <Button
              size="xs"
              variant="outline"
              disabled={disabled}
              data-household-add=""
              onClick={() =>
                onOpen({
                  group,
                  row: null,
                  number: people.length + 1,
                  action: "add",
                })
              }
            >
              <Icon name="userAdd" size="xs" />
              {add.action_words}
            </Button>
          )}
        </span>
      </div>
      {group.state === "incomplete" && group.incomplete_words && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          <span data-household-incomplete="">{group.incomplete_words}</span>
        </Alert>
      )}
      {mark.help && (
        <p className="text-sm text-muted-foreground">{t(mark.help)}</p>
      )}
      {full && (
        <p className="text-sm text-muted-foreground">
          {t("desktop.profile.household.cap_reached")}
        </p>
      )}
      {blocked === "hidden" && (
        <p className="text-sm text-muted-foreground">
          {t("desktop.profile.household.blocked_hidden")}
        </p>
      )}
      {people.length > 0 && (
        <ul className="flex flex-col gap-2">
          {people.map((row, index) => (
            <Person
              key={row.row_index}
              group={group}
              row={row}
              number={index + 1}
              disabled={disabled}
              editable={blocked === null}
              onEdit={() =>
                onOpen({ group, row, number: index + 1, action: "edit" })
              }
              onRemove={() =>
                onOpen({ group, row, number: index + 1, action: "remove" })
              }
            />
          ))}
        </ul>
      )}
    </section>
  );
}

/** A question the product asks of this household now, with the answer the
 * profile states. A stated answer is marked in the product's words for it;
 * nothing stated has a mark of its own and no choice selected. */
function Question({
  question,
  disabled,
  onAnswer,
}: {
  question: HouseholdQuestion;
  disabled: boolean;
  onAnswer(value: string | null): void;
}) {
  const t = useStrings();
  const heading = useId();
  const stated = statedChoice(question);
  return (
    <section
      aria-labelledby={heading}
      data-household-question={question.question_id}
      data-household-answer={stated?.value ?? "unknown"}
      className="flex flex-col gap-2 rounded-lg border border-border bg-background p-3"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h4 id={heading} className="text-base font-medium text-foreground">
          {question.prompt}
        </h4>
        <span className="flex items-center gap-1.5 text-sm">
          <Icon
            name={stated ? "check" : "unknown"}
            size="xs"
            className={stated ? "text-success" : "text-faint"}
          />
          <span data-household-mark="" className="text-foreground">
            {stated
              ? stated.label
              : t("desktop.profile.household.state.unknown")}
          </span>
        </span>
      </div>
      {question.help && (
        <p className="text-sm text-muted-foreground">{question.help}</p>
      )}
      {!stated && (
        <p className="text-sm text-muted-foreground">
          {t("desktop.profile.household.question.unknown_help")}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <SegmentedControl
          aria-labelledby={heading}
          value={stated?.value ?? ""}
          disabled={disabled}
          onValueChange={onAnswer}
        >
          {question.choices.map((choice) => (
            <SegmentedControlItem
              key={choice.value}
              value={choice.value}
              data-household-choice={choice.value}
            >
              {choice.label}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
        {stated && (
          <Button
            size="xs"
            variant="ghost"
            disabled={disabled}
            onClick={() => onAnswer(null)}
          >
            {t("desktop.profile.household.question.clear")}
          </Button>
        )}
      </div>
    </section>
  );
}

/**
 * The household element. It reads the household through the profile's
 * companion read and writes through the profile's one write door, naming the
 * revision it was read at; whatever a write comes to, the household is read
 * again. A write whose outcome is unknown blocks further writes until the
 * person refreshes, because it may have landed.
 */
export function Household({
  reads,
  change,
  observe,
  language,
  writable = true,
  sessionEnded,
}: HouseholdProps) {
  const t = useStrings();
  const heading = useId();
  const [read, setRead] = useState<Read>({ phase: "reading" });
  const [open, setOpen] = useState<Opened | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [unsettled, setUnsettled] = useState(false);
  const latest = useRef(0);
  const shown = useRef(false);
  const alive = useRef(true);
  const busy = useRef(false);
  const windowEnded = useRef(sessionEnded);
  windowEnded.current = sessionEnded;

  const load = useCallback(async (): Promise<boolean> => {
    // The read is wanted by this element, and only while its session lasts.
    const ended = () => !alive.current || windowEnded.current?.() === true;
    if (ended()) return false;
    const ticket = ++latest.current;
    try {
      const household = await reads.household(language, {
        sessionEnded: ended,
      });
      if (ticket !== latest.current) return false;
      shown.current = true;
      setRead({ phase: "ready", household });
      return true;
    } catch (error) {
      // A read that fails while a household is shown keeps it.
      if (ticket === latest.current && !shown.current)
        setRead({ phase: "failed", failure: failureOf(error) });
      return false;
    }
  }, [reads, language]);

  useEffect(() => {
    alive.current = true;
    shown.current = false;
    setRead({ phase: "reading" });
    setOpen(null);
    setNotice(null);
    setUnsettled(false);
    void load();
    return () => {
      alive.current = false;
      latest.current += 1;
    };
  }, [load]);

  useEffect(() => {
    if (!observe) return;
    let stop: (() => void) | undefined;
    let live = true;
    void observe(() => {
      // A write in flight reads the household itself when it settles.
      if (live && !busy.current) void load();
    }).then((end) => {
      if (live) stop = end;
      else end();
    });
    return () => {
      live = false;
      stop?.();
    };
  }, [observe, load]);

  const write = async (
    household: ProfileHousehold,
    edit: ProfileChange["edit"] | null,
  ) => {
    if (busy.current || edit === null) return;
    busy.current = true;
    setSaving(true);
    setNotice(null);
    let outcome: Notice;
    try {
      await change({
        profile_id: household.profile_id,
        expected_revision: household.record_revision,
        expected_content_digest: household.content_digest,
        edit,
      });
      outcome = { kind: "saved" };
    } catch (error) {
      outcome = { kind: "failed", failure: failureOf(error) };
    }
    // Whatever it came to, the household is read again.
    const reread = await load();
    busy.current = false;
    if (!alive.current) return;
    setSaving(false);
    if (outcome.kind === "saved") {
      setOpen(null);
      setNotice(
        reread
          ? { kind: "saved" }
          : {
              kind: "failed",
              failure: { code: "saved_unread", words: null },
            },
      );
      return;
    }
    const { failure } = outcome;
    // A refusal wrote nothing, so what was typed stays for another try. Any
    // other failure leaves the person's edit behind: after a conflict it was
    // made against people that are no longer the ones recorded, and after an
    // unknown outcome the write may already have landed.
    if (failure.code !== "refused") setOpen(null);
    if (failure.code === "unknown") setUnsettled(true);
    setNotice(outcome);
  };

  const refresh = async () => {
    setNotice(null);
    if (await load()) setUnsettled(false);
  };

  const body = (() => {
    if (read.phase === "reading")
      return (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          {t("desktop.profile.household.reading")}
        </div>
      );
    if (read.phase === "failed")
      return (
        <div className="flex flex-col items-start gap-2">
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {read.failure.code === "not_signed_in"
              ? t("desktop.profile.signed_out")
              : t("desktop.profile.unavailable")}
          </Alert>
          <Button size="sm" variant="outline" onClick={() => void load()}>
            {t("desktop.profile.household.retry")}
          </Button>
        </div>
      );
    const { household } = read;
    const failure = notice?.kind === "failed" ? notice.failure : null;
    const closed = saving || unsettled || !writable;
    return (
      <>
        <p className="text-sm text-muted-foreground">
          {t("desktop.profile.household.lead")}
        </p>
        {notice?.kind === "saved" && (
          <Alert tone="success" icon={<Icon name="check" />}>
            {t("desktop.profile.household.saved")}
          </Alert>
        )}
        {failure && !open && (
          <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
            <span data-household-failure="">{wordsOf(failure, t)}</span>
          </Alert>
        )}
        {unsettled && (
          <div>
            <Button size="sm" variant="outline" onClick={() => void refresh()}>
              {t("desktop.profile.refresh")}
            </Button>
          </div>
        )}
        <div className="flex flex-col gap-3">
          {household.groups.map((group) => (
            <Group
              key={group.group_key}
              group={group}
              disabled={closed}
              onOpen={(opened) => setOpen({ ...opened, read: household })}
              onNone={() => void write(household, declaredNone(group))}
            />
          ))}
        </div>
        {household.questions.map((question) => (
          <Question
            key={question.question_id}
            question={question}
            disabled={closed}
            onAnswer={(value) =>
              void write(household, answerEdit(question, value))
            }
          />
        ))}
        {open && (
          <HouseholdPersonDialog
            group={open.group}
            row={open.row}
            number={open.number}
            action={open.action}
            busy={saving}
            words={failure ? wordsOf(failure, t) : null}
            onClose={() => {
              setOpen(null);
              setNotice(null);
            }}
            onSave={(person: HouseholdPersonEdit | null) => {
              // A person is removed by the index the dialog's read served,
              // at that read's revision: if the household moved since, the
              // product refuses it as a conflict rather than removing whoever
              // holds that index now.
              if (open.action === "remove")
                return void write(
                  open.read,
                  open.row ? removal(open.group, open.row) : null,
                );
              // The group may have moved while the dialog was open.
              const current =
                household.groups.find(
                  (entry) => entry.group_key === open.group.group_key,
                ) ?? open.group;
              if (open.action === "add")
                return void write(
                  household,
                  person ? addition(current, person) : null,
                );
              // An edit names the person by the place the dialog was opened
              // at; a person no longer recorded gets nothing sent.
              const place = orderedRows(current).findIndex(
                (entry) => entry.row_index === open.row?.row_index,
              );
              if (place === -1 || !person) return setOpen(null);
              void write(household, replacement(current, place, person));
            }}
          />
        )}
      </>
    );
  })();

  return (
    <section
      aria-labelledby={heading}
      data-household=""
      className="flex flex-col gap-3 rounded-lg border bg-card p-4"
    >
      <h3 id={heading} className="text-base font-semibold text-foreground">
        {t("desktop.profile.household.title")}
      </h3>
      {body}
    </section>
  );
}
