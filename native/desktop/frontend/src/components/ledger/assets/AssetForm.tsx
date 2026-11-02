import { useEffect, useRef, useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { formatDay } from "../../../shared/dateFormats";
import { formatPercent } from "../../../shared/numbers";
import { facts, listed } from "../../../shell/compose";
import type { LedgerPort } from "../../../shell/ledger";
import type {
  AcquisitionCandidate,
  FormOptions,
} from "../../../shell/ledgerSetup";
import { tokensOf, useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { Panel, useSetupDraft, useSetupWrite } from "../setup/SetupParts";
import { FieldsGrid } from "./AssetFieldsGrid";
import { OptionsRead, WriteLine } from "./AssetFormStatus";
import {
  fieldsFor,
  formKeyOf,
  FURTHER_PURCHASE,
  initialOf,
} from "./assetFields";
import {
  ASSET_ACTS,
  type ActKind,
  type AssetActContext,
} from "./assetFormActs";
import {
  useLedgerRead,
  useAssetRow,
  useFieldsDraft,
  useFocusOnOpen,
} from "./assetFormState";
import { answer, type FormField, type FormValues } from "./assetFormValues";
import {
  correctRequest,
  createRequest,
  type RevisionBase,
} from "./assetRevision";
import { usePurchasePrefill, useAssetSuggestions } from "./assetSuggestions";
import {
  currentDescriptor,
  disposalOf,
  neverReused,
  purchaseOf,
  purchaseValues,
  viewOf,
} from "./assetWrites";
import {
  ASSET_FAMILY,
  ASSET_KEYS,
  keyedText,
  type AssetFamily,
} from "./assetsWords";

/** What every act form is given: the page's port and the account it reads
 * for, and the two things a form tells the page. */
export type ActProps = {
  port: LedgerPort;
  /** Null while the account withholds the ledger; omitted, the port's own. */
  reader?: string | null;
  locale: string;
  /** The tax year the page stands on, which the registry's options are read
   * for where the form states no date of its own. */
  taxYear?: number | null;
  /** The person left the form. */
  onClose?: () => void;
  /** The form wrote: the page reads the register again. */
  onWritten?: () => void;
  /** An element was added: the page shows it. */
  onAdded?: (assetId: string) => void;
};

const NO_CANDIDATES: readonly AcquisitionCandidate[] = [];
const NO_CLAIMS: readonly string[] = [];

/** The tokens of a family, from the generated words that the backend's enum
 * produced. */
const familyTokens = (family: AssetFamily) => tokensOf(ASSET_FAMILY[family]);

/** The year of an ISO date, or null while the text is not one. */
const yearOfDate = (text: string): number | null =>
  /^\d{4}-\d{2}-\d{2}$/.test(text) ? Number(text.slice(0, 4)) : null;

/** What a form asks the person to confirm before it sends, if it does. */
type Confirming = "save" | "remove" | null;

/**
 * The form of an act on the register, drawn from what the backend serves for
 * it. Adding an element mints its opaque id once, when the form opens, and
 * never shows it. The send is always available: with something missing it
 * marks what to fill in and sends nothing. A write that was not seen to
 * settle holds the page's writes and is never sent again; a refusal keeps
 * what was typed. `children` sit between the fields and the buttons.
 */
export function AssetForm({
  port,
  reader,
  locale,
  taxYear = null,
  kind,
  assetId,
  supersede = NO_CLAIMS,
  onClose,
  onWritten,
  onAdded,
  children,
}: ActProps & {
  kind: ActKind;
  /** The element acted on; null when adding one. */
  assetId: string | null;
  /** Effective claims recorded again in the same write, for a correction. */
  supersede?: readonly string[];
  /** Drawn between the fields and the buttons; given a function, it is told
   * what the form states now and whether that could be sent. */
  children?:
    ReactNode | ((form: { values: FormValues; ready: boolean }) => ReactNode);
}) {
  const t = useStrings();
  const act = ASSET_ACTS[kind];
  const [minted] = useState(() =>
    kind === "element" ? crypto.randomUUID() : "",
  );
  const id = kind === "element" ? minted : (assetId ?? "");
  const asset = useAssetRow(port, reader, kind === "element" ? null : id);
  const history = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.timeline",
    kind === "descriptor" && id !== "" ? { asset_id: id } : null,
    id,
  );
  const events =
    history.read?.kind === "done" ? (history.read.result.events ?? []) : null;
  // A correction supersedes the revision the register holds now.
  const changesRevision = kind === "correction" || kind === "baja_change";
  const inspected = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.inspect",
    (changesRevision || kind === "descriptor") && id !== ""
      ? { asset_id: id }
      : null,
    id,
  );
  const base: RevisionBase | null =
    inspected.read?.kind === "done" && inspected.read.result.revisions
      ? (inspected.read.result.revisions.at(-1) ?? null)
      : null;

  // The options the registry admits depend on the element's kind and year,
  // which a new element states in its own form.
  const [typed, setTyped] = useState({ asset_kind: "", in_service_date: "" });
  const optionsKind =
    kind === "element" ? typed.asset_kind : (asset.row?.asset_kind ?? "");
  // A baja is read for the year the page stands on: the reasons it offers do
  // not depend on the year the element came into service.
  const optionsYear =
    kind === "element"
      ? yearOfDate(typed.in_service_date)
      : kind === "baja" || kind === "baja_change"
        ? (taxYear ?? yearOfDate(asset.row?.in_service_date ?? ""))
        : (yearOfDate(
            typed.in_service_date || asset.row?.in_service_date || "",
          ) ?? taxYear);
  const wantsOptions =
    (kind === "element" ||
      kind === "correction" ||
      kind === "baja" ||
      kind === "baja_change") &&
    optionsKind !== "" &&
    optionsYear !== null &&
    optionsYear !== undefined;
  const options = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.form-options",
    wantsOptions ? { asset_kind: optionsKind, tax_year: optionsYear } : null,
    `${kind}:${optionsKind}:${optionsYear}`,
  );
  const loaded: FormOptions | null =
    options.read?.kind === "done" ? options.read.result.options : null;

  const context = {
    kind,
    row: asset.row,
    descriptor: events === null ? null : currentDescriptor(events),
    revision: base?.revision ?? null,
    tokens: familyTokens,
    options: loaded,
  };
  // The form starts from the record; the fields it draws follow what is typed.
  const form = useFieldsDraft(initialOf(context, fieldsFor(context, {})));
  const fields = fieldsFor(context, form.draft);
  const formRef = useRef<HTMLFormElement>(null);
  useFocusOnOpen(formRef, true);
  const purchases = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.acquisition-candidates",
    fields.some((field) => field.control === "candidate") ? {} : null,
    id,
  );
  const candidates =
    purchases.read?.kind === "done"
      ? (purchases.read.result.candidates ?? NO_CANDIDATES)
      : NO_CANDIDATES;
  const write = useSetupWrite(facts(t, [t(act.title), asset.row?.name]));
  useSetupDraft(form.dirty);

  // A new element starts on the first way of acquiring one the backend offers.
  const { set: setDraft } = form;
  const shape = form.draft.acquisition_shape ?? "";
  const firstShape = loaded?.acquisition_shapes?.[0] ?? "";
  useEffect(() => {
    if (kind === "element" && shape === "" && firstShape !== "")
      setDraft({ acquisition_shape: firstShape });
  }, [kind, shape, firstShape, setDraft]);

  const picked = candidates.find(
    (candidate) => candidate.transaction_id === form.draft.acquisition,
  );
  const further = candidates.find(
    (candidate) => candidate.transaction_id === form.draft[FURTHER_PURCHASE],
  );
  const ownedPurchase = base === null ? null : purchaseOf(base.revision);
  // The element owns its purchase, so it is no longer a candidate: the ledger
  // says how that one movement is described.
  const ownedRead = useLedgerRead(
    port,
    reader,
    "ledger.view",
    kind === "descriptor" && ownedPurchase !== null
      ? { transaction_prefix: ownedPurchase }
      : null,
    `purchase:${ownedPurchase ?? ""}`,
  );
  usePurchasePrefill({
    active: kind === "descriptor",
    purchase: ownedPurchase,
    stated: context.descriptor,
    draft: form.draft,
    set: setDraft,
  });
  const offered = useAssetSuggestions({
    kind,
    fields,
    draft: form.draft,
    set: setDraft,
    purchase: picked,
    purchaseDescription:
      ownedRead.read?.kind === "done"
        ? ownedRead.read.result.transaction.description
        : null,
  });
  const answered = answer(fields, form.draft, act.delta ? form.initial : null);
  const view = viewOf(write.last, neverReused);
  const [tried, setTried] = useState(false);
  const [confirming, setConfirming] = useState<Confirming>(null);
  // A fact every request of the act states, and the form still lacks.
  const lacking = act.delta
    ? []
    : fields.filter(
        (field) =>
          field.required && (answered.values[field.key] ?? null) === null,
      );
  const toFill = [...lacking.map((field) => field.key), ...answered.cleared];
  const missing = new Set([
    ...(view.kind === "refused" ? view.missing.map(formKeyOf) : []),
    ...(tried ? toFill : []),
  ]);
  const needsRow = changesRevision || kind === "baja";
  const stating = {
    assetId: id,
    regime: loaded?.regime ?? null,
    candidate: picked ?? null,
    further: further ?? null,
    base,
    options: loaded,
  };
  const create =
    kind === "element" ? createRequest(answered.values, stating) : null;
  const correct =
    kind === "correction"
      ? correctRequest(answered.values, stating, supersede)
      : null;
  const changed =
    Object.keys(answered.values).length > 0 || answered.cleared.length > 0;
  const ready =
    Object.keys(answered.problems).length === 0 &&
    toFill.length === 0 &&
    (!needsRow || asset.row !== null) &&
    (kind !== "element" || create !== null) &&
    (kind !== "correction" || (correct !== null && changed)) &&
    (kind !== "baja" || disposalOf(answered.values) !== null) &&
    (kind !== "baja_change" ||
      (base !== null && disposalOf(answered.values) !== null));

  const onField = (field: FormField, value: string) => {
    if (field.key === "asset_kind" || field.key === "in_service_date")
      setTyped((current) => ({ ...current, [field.key]: value }));
    form.set({
      [field.key]: value,
      // A purchase fills the figures it knows; what it does not know stays
      // as it is, and is never read as zero.
      ...(field.control === "candidate" && field.key === "acquisition"
        ? Object.fromEntries(
            Object.entries(
              purchaseValues(
                candidates.find(
                  (candidate) => candidate.transaction_id === value,
                ),
              ),
            ).filter((entry): entry is [string, string] => entry[1] !== null),
          )
        : {}),
    });
  };

  const send = async (removing = false) => {
    if (write.busy) return;
    const sending: AssetActContext = {
      port,
      assetId: id,
      asset: asset.row,
      values: answered.values,
      create,
      correct,
      base,
      removing,
      descriptions:
        (events ?? []).filter((event) => event.kind === "descriptor").length +
        1,
    };
    const done = await write.run(() => act.send(sending), act.landing(sending));
    setConfirming(null);
    if (viewOf(done, neverReused).kind === "saved") {
      setTried(false);
      // What the record states has changed: read it again.
      history.reload();
      inspected.reload();
      options.reload();
      asset.reload();
      onWritten?.();
      if (kind === "element") onAdded?.(id);
    }
  };

  const submit = () => {
    if (write.busy) return;
    if (!ready) {
      setTried(true);
      return;
    }
    if (act.confirms) setConfirming("save");
    else void send();
  };

  const waiting =
    kind === "element" &&
    (typed.asset_kind === "" || typed.in_service_date === "")
      ? t("desktop.ledger.assets.write.options_wait")
      : null;
  const whollyShare = loaded?.basis_stages
    .flatMap((stage) => stage.wholly_business_facts)
    .find((found) => found.fact === "business_use_share");
  const whollyBusiness = whollyShare
    ? t("desktop.ledger.assets.field.wholly_business_hint", {
        share: formatPercent(locale, whollyShare.value.decimal, {
          unit: "fraction",
        }),
      })
    : null;
  const name = asset.row?.name ?? t(ASSET_KEYS.list.no_name);
  const bajaDate = disposalOf(answered.values)?.disposal_date ?? "";
  const stillToFill = listed(
    t,
    toFill.map((key) => {
      const found = fields.find((field) => field.key === key);
      return found ? t(found.label_key) : key;
    }),
  );

  return (
    <Panel
      title={
        kind === "element"
          ? t(act.title)
          : facts(t, [t(act.title), asset.row?.name])
      }
      className={`ledger-asset-form ledger-asset-form-${kind}`}
    >
      <form
        ref={formRef}
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <FieldsGrid
          fields={offered}
          options={loaded}
          draft={form.draft}
          onField={onField}
          problems={answered.problems}
          missing={missing}
          cleared={new Set(answered.cleared)}
          candidates={candidates}
          purchaseKnown={
            new Set(
              picked === undefined
                ? []
                : Object.entries(purchaseValues(picked))
                    .filter(([, known]) => known === null)
                    .map(([key]) => key),
            )
          }
          notes={{
            opening_status: t(
              "desktop.ledger.assets.field.opening_status_hint",
            ),
            business_use_share: whollyBusiness,
            method: waiting,
            acquisition_shape: waiting,
            non_deductible_iva:
              picked === undefined
                ? null
                : keyedText(t, picked.non_deductible_iva_state_key, "") || null,
            acquisition:
              picked !== undefined &&
              (picked.invoice_evidence_id === null ||
                picked.evidence_fingerprint === null)
                ? t("desktop.ledger.assets.field.acquisition_no_evidence", {
                    documents: t("desktop.ledger.section.documents"),
                  })
                : null,
          }}
          locale={locale}
        />
        {options.read !== null && options.read.kind !== "done" && (
          <OptionsRead call={options.read} />
        )}
        {options.read?.kind === "done" &&
          options.read.result.outcome === "refused" && (
            <OptionsRead call={options.read} />
          )}
        {typeof children === "function"
          ? children({ values: answered.values, ready })
          : children}
        {confirming !== null ? (
          <Alert
            tone="warning"
            role="alertdialog"
            icon={<Icon name="alert" />}
            className="ledger-asset-confirm"
          >
            <span>
              {confirming === "remove"
                ? t("desktop.ledger.assets.baja.remove_confirm", { name })
                : t(
                    kind === "baja_change"
                      ? "desktop.ledger.assets.baja.change_confirm"
                      : "desktop.ledger.assets.baja.confirm",
                    {
                      name,
                      date: formatDay(locale, bajaDate),
                    },
                  )}
            </span>
            <span className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="ledger-asset-confirm-back"
                aria-disabled={write.busy || undefined}
                onClick={() => {
                  if (!write.busy) setConfirming(null);
                }}
              >
                {t("desktop.ledger.assets.baja.confirm_back")}
              </Button>
              <WriteHold>
                <Button
                  type="button"
                  size="sm"
                  className="ledger-asset-confirm-yes"
                  aria-disabled={write.busy || undefined}
                  onClick={() => void send(confirming === "remove")}
                >
                  {write.busy
                    ? t("desktop.ledger.form.saving")
                    : t(
                        confirming === "remove"
                          ? "desktop.ledger.assets.baja.remove_yes"
                          : "desktop.ledger.assets.baja.confirm_yes",
                      )}
                </Button>
              </WriteHold>
            </span>
          </Alert>
        ) : (
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
            {kind === "baja_change" && (
              <WriteHold>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="ledger-asset-remove"
                  aria-disabled={write.busy || base === null || undefined}
                  onClick={() => {
                    if (!write.busy && base !== null) setConfirming("remove");
                  }}
                >
                  {t("desktop.ledger.assets.baja.remove")}
                </Button>
              </WriteHold>
            )}
            {!(kind === "baja" && view.kind === "saved") && (
              <WriteHold>
                <Button
                  type="submit"
                  size="sm"
                  className="ledger-asset-submit"
                  aria-disabled={write.busy || undefined}
                >
                  {write.busy ? t("desktop.ledger.form.saving") : t(act.submit)}
                </Button>
              </WriteHold>
            )}
          </div>
        )}
        {tried &&
          !ready &&
          confirming === null &&
          (toFill.length > 0 ||
            Object.keys(answered.problems).length > 0 ||
            (kind === "correction" && !changed)) && (
            <p
              role="alert"
              className="ledger-asset-missing flex items-start gap-1.5 text-sm text-destructive"
            >
              <Icon name="alert" size="xs" className="mt-0.5" />
              <span>
                {toFill.length > 0
                  ? t("desktop.ledger.assets.write.missing", {
                      fields: stillToFill,
                    })
                  : Object.keys(answered.problems).length > 0
                    ? t("desktop.ledger.assets.write.fix_marked")
                    : t("desktop.ledger.assets.write.nothing_changed")}
              </span>
            </p>
          )}
        <WriteLine
          call={write.last}
          fields={fields}
          saved={{
            done: t(act.done),
            reused: t(ASSET_KEYS.write.reused),
            reusedOf: neverReused,
          }}
        />
      </form>
    </Panel>
  );
}
