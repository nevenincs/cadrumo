import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { LedgerPort } from "../../../shell/ledger";
import type { GrammarRefusal } from "../../../shell/ledgerGrammar";
import { useStrings, type Translate } from "../../../shell/strings";
import { useWritePause, WriteHold, type LandingCheck } from "../WritePause";
import { amountText, dateText } from "../movements/movementWords";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  Reading,
  TextField,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import type { SetupCall } from "../setup/setupModel";
import { grammarText } from "../setup/setupWords";
import {
  answer,
  bajaLanding,
  CONFLICT,
  correctionLanding,
  createReused,
  descriptorLanding,
  describeRequest,
  disposeRequest,
  draftedCall,
  draftOf,
  elementLanding,
  INCOMPLETE,
  missingLabels,
  neverReused,
  optionsSignature,
  provisionalCall,
  refusalOf,
  refusalWord,
  viewOf,
  type FormDraft,
} from "./assetWrites";
import type {
  AcquisitionCandidate,
  AssetListRow,
  FormField,
  FormOptions,
  FormValues,
  ProvisionalOperationId,
  ProvisionalRequests,
  ProvisionalResults,
} from "./assetsContract";
import { ASSET_KEYS, eventWord } from "./assetsWords";

/** What every act form is given: the page's port and the account it reads
 * for, and the two things a form tells the page. */
export type ActProps = {
  port: LedgerPort;
  /** Null while the account withholds the ledger; omitted, the port's own. */
  reader?: string | null;
  locale: string;
  /** The person left the form. */
  onClose?: () => void;
  /** The form wrote: the page reads the register again. */
  onWritten?: () => void;
};

const NO_CANDIDATES: readonly AcquisitionCandidate[] = [];
const NO_CLAIMS: readonly string[] = [];

// ---- Reading --------------------------------------------------------------------

/**
 * Reads one provisional operation while the form shows, again when `key`
 * changes, on `reload` or after the page re-reads a write it held, and drops
 * what it read with the account. A null `payload` reads nothing; an omitted
 * `reader` reads the port's own ledger; a read that a later one replaced is
 * never shown.
 */
export function useProvisionalRead<D extends ProvisionalOperationId>(
  port: LedgerPort,
  reader: string | null | undefined,
  id: D,
  payload: ProvisionalRequests[D] | null,
  key: string,
): { read: SetupCall<ProvisionalResults[D]> | null; reload(): void } {
  const [read, setRead] = useState<SetupCall<ProvisionalResults[D]> | null>(
    null,
  );
  const [round, setRound] = useState(0);
  const { round: reread } = useWritePause();
  const latest = useRef(payload);
  latest.current = payload;
  useEffect(() => {
    const asked = latest.current;
    if (reader === null || asked === null) return;
    let active = true;
    void provisionalCall(port, id, asked, false).then((answer) => {
      if (active) setRead(answer);
    });
    return () => {
      active = false;
      setRead(null);
    };
  }, [port, reader, id, key, round, reread]);
  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { read, reload };
}

/** The element a form acts on, as the register lists it now. */
export function useAssetRow(
  port: LedgerPort,
  reader: string | null | undefined,
  assetId: string | null,
): { row: AssetListRow | null; reload(): void } {
  const { read, reload } = useProvisionalRead(
    port,
    reader,
    "ledger.actividad-asset.list",
    assetId === null ? null : {},
    assetId ?? "",
  );
  const row =
    assetId !== null && read?.kind === "done"
      ? (read.result.rows.find((found) => found.asset_id === assetId) ?? null)
      : null;
  return { row, reload };
}

// ---- The form's text -----------------------------------------------------------

/** The text of a form, started from what the options state as current. It
 * starts again only when what the record states changes, never when the same
 * options are read again, so what was typed is kept through a re-read. */
export function useOptionsDraft(loaded: FormOptions | null) {
  const [held, setHeld] = useState<{
    options: FormOptions;
    signature: string;
    initial: FormDraft;
  } | null>(null);
  const [draft, setDraft] = useState<FormDraft>({});
  if (loaded !== null && loaded !== held?.options) {
    const signature = optionsSignature(loaded);
    if (held === null || signature !== held.signature) {
      const initial = draftOf(loaded);
      setHeld({ options: loaded, signature, initial });
      setDraft(initial);
    } else setHeld({ ...held, options: loaded });
  }
  const initial = held?.initial ?? {};
  return {
    options: held?.options ?? loaded,
    draft,
    initial,
    /** Anything typed that is not what the record states. */
    dirty: Object.keys(draft).some(
      (key) => draft[key] !== (initial[key] ?? ""),
    ),
    set(changes: FormDraft) {
      setDraft((current) => ({ ...current, ...changes }));
    },
  };
}

const boundsText = (t: Translate, locale: string, field: FormField) => {
  const say = (bound: string) =>
    field.control === "date"
      ? dateText(locale, bound, true)
      : field.control === "amount"
        ? amountText(locale, bound)
        : bound;
  return [
    field.bounds?.min
      ? t("desktop.ledger.assets.bounds.min", { min: say(field.bounds.min) })
      : null,
    field.bounds?.max
      ? t("desktop.ledger.assets.bounds.max", { max: say(field.bounds.max) })
      : null,
  ]
    .filter(Boolean)
    .join(" · ");
};

/**
 * The fields the backend serves for an act, each drawn by its control. The
 * form decides nothing about them: their labels, choices, bounds and starting
 * values are the options'. A field the backend named as still to fill in is
 * marked until something is typed.
 */
export function OptionsFields({
  options,
  draft,
  onField,
  problems,
  missing,
  candidates,
  purchaseKnown,
  locale,
}: {
  options: FormOptions;
  draft: FormDraft;
  onField(field: FormField, value: string): void;
  problems: Record<string, GrammarRefusal>;
  missing: ReadonlySet<string>;
  candidates: readonly AcquisitionCandidate[];
  /** Fields the picked purchase does not know. */
  purchaseKnown: ReadonlySet<string>;
  locale: string;
}) {
  const t = useStrings();
  const unstated = (field: FormField) => (draft[field.key] ?? "") === "";
  return (
    <FormGrid>
      {options.fields.map((field) => {
        const raw = draft[field.key] ?? "";
        const problem = problems[field.key];
        const fillIn = missing.has(field.key) && unstated(field);
        const hint =
          [
            field.hint_key ? t(field.hint_key) : null,
            boundsText(t, locale, field) || null,
            purchaseKnown.has(field.key) && unstated(field)
              ? t("desktop.ledger.assets.field.not_known")
              : null,
            field.control === "candidate" && candidates.length === 0
              ? t("desktop.ledger.assets.field.acquisition_none")
              : null,
            fillIn ? t("desktop.ledger.assets.write.fill_in") : null,
          ]
            .filter(Boolean)
            .join(" ") || undefined;
        const label = t(field.label_key);
        const choose = (value: string) => onField(field, value);
        return (
          <div key={field.key} data-field={field.key} className="contents">
            {field.control === "text" ||
            field.control === "date" ||
            field.control === "amount" ||
            field.control === "whole" ? (
              <TextField
                label={label}
                name={field.key}
                value={raw}
                onValue={choose}
                required={field.required}
                hint={hint}
                error={
                  problem
                    ? grammarText(t, problem)
                    : fillIn
                      ? t("desktop.ledger.assets.write.fill_in")
                      : null
                }
                inputMode={
                  field.control === "amount"
                    ? "decimal"
                    : field.control === "whole"
                      ? "numeric"
                      : "text"
                }
                maxLength={field.control === "text" ? 200 : 32}
              />
            ) : (
              <ChoiceField
                label={label}
                value={raw}
                onValue={choose}
                placeholder={t("desktop.ledger.form.choose")}
                hint={hint}
                options={
                  field.control === "candidate"
                    ? candidates.map((candidate) => ({
                        value: candidate.candidate_id,
                        label: t(
                          "desktop.ledger.assets.field.acquisition_option",
                          {
                            description: candidate.description,
                            date: dateText(locale, candidate.date, true),
                            amount: candidate.amount
                              ? amountText(locale, candidate.amount.decimal)
                              : "—",
                          },
                        ),
                      }))
                    : field.control === "flag"
                      ? [
                          { value: "yes", label: t("desktop.ledger.form.yes") },
                          { value: "no", label: t("desktop.ledger.form.no") },
                        ]
                      : field.choices.map((choice) => ({
                          value: choice.token,
                          label: t(choice.label_key),
                        }))
                }
              />
            )}
          </div>
        );
      })}
    </FormGrid>
  );
}

/** What stands where an act's options are not yet drawn: the read, or why it
 * did not answer. */
export function OptionsRead({
  call,
}: {
  call: SetupCall<{ options: FormOptions | null }> | null;
}) {
  const t = useStrings();
  if (call === null)
    return <Reading label={t("desktop.ledger.form.reading")} />;
  return (
    <CallLine
      call={call}
      refusal={() =>
        call.kind === "refused" ? refusalWord(t, refusalOf(call.detail)) : null
      }
    />
  );
}

// ---- How a write ended, in the form ---------------------------------------------

/**
 * The line under a form for how its last call ended: saved or already there,
 * refused with what was kept, incomplete with what to fill in, a claim that
 * overlaps another, or a call that failed or was not seen to settle. A
 * refusal is worded by the backend's keys and never by its English.
 */
export function WriteLine({
  call,
  locale,
  options,
  saved,
  onSupersede,
}: {
  call: SetupCall<unknown> | null;
  locale: string;
  options: FormOptions | null;
  /** The words for a write that landed, new and already there; null where a
   * landing is not worth a line, as for a forecast. */
  saved: {
    done: string;
    reused: string;
    reusedOf: (result: unknown) => boolean;
  } | null;
  /** Offers to correct the claim a new one overlaps. */
  onSupersede?: (claimId: string) => void;
}) {
  const t = useStrings();
  const view = viewOf(call, saved?.reusedOf ?? neverReused);
  const kept = t("desktop.ledger.assets.write.kept");
  if (view.kind === "none") return null;
  if (view.kind === "saved")
    return saved ? (
      <Alert
        tone="success"
        icon={<Icon name="check" />}
        className="ledger-asset-saved"
      >
        {view.reused ? saved.reused : saved.done}
      </Alert>
    ) : null;
  if (view.kind === "refused") {
    if (view.code === INCOMPLETE)
      return (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-asset-incomplete"
        >
          {t(ASSET_KEYS.write.incomplete, {
            fields: missingLabels(t, options, view.missing),
          })}
        </Alert>
      );
    if (view.code === CONFLICT && view.conflict) {
      const existing = view.conflict;
      return (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-asset-conflict"
        >
          <span>
            {t(ASSET_KEYS.write.conflict, {
              from: dateText(locale, existing.from, true),
              until: dateText(locale, existing.until, true),
            })}
            {onSupersede && (
              <>
                {" "}
                <Button
                  variant="link"
                  size="xs"
                  className="ledger-asset-supersede"
                  onClick={() => onSupersede(existing.claim_id)}
                >
                  {t("desktop.ledger.assets.claim.supersede")}
                </Button>
              </>
            )}
          </span>
        </Alert>
      );
    }
    return (
      <Alert
        tone="danger"
        role="alert"
        icon={<Icon name="refused" />}
        className="ledger-asset-refused"
      >
        <span>
          {refusalWord(t, view) ??
            t("desktop.ledger.form.refused", {
              code: view.reasonKey ?? view.code ?? view.reason ?? "refused",
            })}
        </span>
        <span className="text-sm text-muted-foreground">{kept}</span>
      </Alert>
    );
  }
  return (
    <>
      <CallLine call={call} />
      {view.kind === "failed" && (
        <p className="text-sm text-muted-foreground">{kept}</p>
      )}
    </>
  );
}

// ---- The acts --------------------------------------------------------------------

export type ActKind = "element" | "descriptor" | "correction" | "baja";

type Context = {
  port: LedgerPort;
  assetId: string;
  asset: AssetListRow | null;
  options: FormOptions;
  values: FormValues;
  supersede: readonly string[];
};

type Act = {
  title: string;
  submit: string;
  /** The timeline event a landed write adds, which words it. */
  event: string;
  /** Only what changed is stated, the rest left as the record has it. */
  delta: boolean;
  send(context: Context): Promise<SetupCall<unknown>>;
  landing(context: Context): LandingCheck;
  reused: (result: unknown) => boolean;
};

/** An act the options do not number cannot be told from the register. */
const UNTOLD: LandingCheck = async () => "untold";

const ACTS: Record<ActKind, Act> = {
  element: {
    title: ASSET_KEYS.action.add,
    submit: "desktop.ledger.assets.submit.create",
    event: "element_added",
    delta: false,
    send: (c) =>
      draftedCall(
        c.port,
        "ledger.actividad-asset.create",
        { asset_id: c.assetId, values: c.values },
        true,
      ),
    landing: (c) => elementLanding(c.port, c.assetId),
    reused: createReused,
  },
  descriptor: {
    title: ASSET_KEYS.action.describe,
    submit: "desktop.ledger.form.save",
    event: "description_added",
    delta: false,
    send: (c) =>
      provisionalCall(
        c.port,
        "ledger.actividad-asset.describe",
        describeRequest(c.assetId, c.values),
        true,
      ),
    landing: (c) =>
      c.options.next_sequence == null
        ? UNTOLD
        : descriptorLanding(c.port, c.assetId, c.options.next_sequence),
    reused: neverReused,
  },
  correction: {
    title: ASSET_KEYS.action.correct,
    submit: "desktop.ledger.assets.submit.correct",
    event: "correction_added",
    delta: true,
    send: (c) =>
      draftedCall(
        c.port,
        "ledger.actividad-asset.correct",
        {
          asset_id: c.assetId,
          revision_number: c.asset?.revision_number ?? 0,
          values: c.values,
          supersede_claim_ids: [...c.supersede],
        },
        true,
      ),
    landing: (c) =>
      c.options.next_sequence == null
        ? UNTOLD
        : correctionLanding(c.port, c.assetId, c.options.next_sequence),
    reused: neverReused,
  },
  baja: {
    title: ASSET_KEYS.action.dispose,
    submit: ASSET_KEYS.action.dispose,
    event: "baja_recorded",
    delta: false,
    send: (c) =>
      provisionalCall(
        c.port,
        "ledger.actividad-asset.dispose",
        disposeRequest(c.assetId, c.values),
        true,
      ),
    landing: (c) => bajaLanding(c.port, c.assetId),
    reused: neverReused,
  },
};

/**
 * The form of an act on the register, drawn from the options the backend
 * serves for it. Adding an element mints its opaque id once, when the form
 * opens, and never shows it. A write that was not seen to settle holds the
 * page's writes and is never sent again; a refusal keeps what was typed.
 * `children` sit between the fields and the buttons.
 */
export function AssetForm({
  port,
  reader,
  locale,
  kind,
  assetId,
  supersede = NO_CLAIMS,
  onClose,
  onWritten,
  children,
}: ActProps & {
  kind: ActKind;
  /** The element acted on; null when adding one. */
  assetId: string | null;
  /** Effective claims recorded again in the same write, for a correction. */
  supersede?: readonly string[];
  children?: ReactNode;
}) {
  const t = useStrings();
  const act = ACTS[kind];
  const [minted] = useState(() =>
    kind === "element" ? crypto.randomUUID() : "",
  );
  const id = kind === "element" ? minted : (assetId ?? "");
  const asset = useAssetRow(port, reader, kind === "element" ? null : id);
  const options = useProvisionalRead(
    port,
    reader,
    "ledger.actividad-asset.form-options",
    kind === "element" ? { kind } : id === "" ? null : { kind, asset_id: id },
    `${kind}:${id}`,
  );
  const form = useOptionsDraft(
    options.read?.kind === "done" ? options.read.result.options : null,
  );
  const purchases = useProvisionalRead(
    port,
    reader,
    "ledger.actividad-asset.acquisition-candidates",
    form.options?.fields.some((field) => field.control === "candidate")
      ? {}
      : null,
    id,
  );
  const candidates =
    purchases.read?.kind === "done"
      ? purchases.read.result.candidates
      : NO_CANDIDATES;
  const write = useSetupWrite(
    [t(act.title), asset.row?.name].filter(Boolean).join(" · "),
  );
  useSetupDraft(form.dirty);

  const picked = candidates.find(
    (candidate) =>
      candidate.candidate_id ===
      form.draft[
        form.options?.fields.find((field) => field.control === "candidate")
          ?.key ?? ""
      ],
  );
  const answered = form.options
    ? answer(form.options, form.draft, act.delta ? form.initial : null)
    : null;
  const view = viewOf(write.last, act.reused);
  const missing = new Set(view.kind === "refused" ? view.missing : []);
  const ready =
    form.options !== null &&
    answered !== null &&
    Object.keys(answered.problems).length === 0 &&
    (kind === "element" || asset.row !== null);

  const onField = (field: FormField, value: string) => {
    form.set({
      [field.key]: value,
      // A purchase fills the fields it knows; what it does not know stays
      // as it is, and is never read as zero.
      ...(field.control === "candidate"
        ? Object.fromEntries(
            Object.entries(
              candidates.find((candidate) => candidate.candidate_id === value)
                ?.values ?? {},
            ).filter((entry): entry is [string, string] => entry[1] !== null),
          )
        : {}),
    });
  };

  const send = async () => {
    if (!ready || write.busy || !form.options || !answered) return;
    const context: Context = {
      port,
      assetId: id,
      asset: asset.row,
      options: form.options,
      values: answered.values,
      supersede,
    };
    const done = await write.run(() => act.send(context), act.landing(context));
    if (viewOf(done, act.reused).kind === "saved") {
      // What the record states has changed: read it again.
      options.reload();
      asset.reload();
      onWritten?.();
    }
  };

  const shown = form.options;
  return (
    <Panel
      title={t(act.title)}
      className={`ledger-asset-form ledger-asset-form-${kind}`}
    >
      {shown === null ? (
        <OptionsRead call={options.read} />
      ) : (
        <form
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <OptionsFields
            options={shown}
            draft={form.draft}
            onField={onField}
            problems={answered?.problems ?? {}}
            missing={missing}
            candidates={candidates}
            purchaseKnown={
              new Set(
                Object.entries(picked?.values ?? {})
                  .filter(([, known]) => known === null)
                  .map(([key]) => key),
              )
            }
            locale={locale}
          />
          {children}
          <div className="flex flex-wrap gap-2">
            {onClose && (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-disabled={write.busy || undefined}
                onClick={() => {
                  if (!write.busy) onClose();
                }}
              >
                {t("desktop.ledger.form.cancel")}
              </Button>
            )}
            <WriteHold>
              <Button
                type="submit"
                size="sm"
                className="ledger-asset-submit"
                aria-disabled={!ready || write.busy || undefined}
              >
                {write.busy ? t("desktop.ledger.form.saving") : t(act.submit)}
              </Button>
            </WriteHold>
          </div>
          <WriteLine
            call={write.last}
            locale={locale}
            options={shown}
            saved={{
              done: eventWord(t, act.event),
              reused: t(ASSET_KEYS.write.reused),
              reusedOf: act.reused,
            }}
          />
        </form>
      )}
    </Panel>
  );
}
