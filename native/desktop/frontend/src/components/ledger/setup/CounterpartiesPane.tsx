import { useId, useLayoutEffect, useRef, useState } from "react";
import { CountryEditor } from "@/components/editors/CountryEditor";
import { NotesEditor } from "@/components/editors/NotesEditor";
import { TaxIdEditor } from "@/components/editors/TaxIdEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts, labelled } from "@/shell/compose";
import { useFieldSuggestions } from "../suggestions/SuggestionsProvider";
import type { LedgerCounterpartyResult } from "../../../shell/ledgerClassificationSetup";
import { useTextLimit } from "../../../shell/ledgerLimits";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing } from "../WritePause";
import { formatTime } from "../../../shared/dateFormats";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  useSetupDraft,
  useSetupWrite,
} from "./SetupParts";
import { CounterpartyFilingName } from "./CounterpartyFilingName";
import { CounterpartyProvincia } from "./CounterpartyProvincia";
import { EditorField } from "./EditorField";
import type { SetupProps } from "./setupProps";
import { setupCall, type SetupCall } from "./setupModel";
import { tokenText } from "./setupWords";

/** Where a counterparty can be established, as the registry names it. */
export const TERRITORIAL_SCOPES = [
  "es_mainland",
  "es_canarias",
  "es_ceuta_melilla",
  "eu_member",
  "third_country",
] as const;

const TWO_LETTERS = /^[A-Za-z]{2}$/;
type Draft = {
  scope: string;
  state: string;
  note: string;
  actor: string;
  withdrawing: boolean;
};
const EMPTY_DRAFT: Draft = {
  scope: "",
  state: "",
  note: "",
  actor: "",
  withdrawing: false,
};
const identityOf = (taxId: string, country: string) =>
  JSON.stringify([taxId.trim(), country || null]);

/**
 * What the ledger answers for one counterparty, by its tax id: where it is
 * established and which State identifies it for VAT, and where each answer
 * comes from. The person confirms the facts or withdraws an earlier
 * confirmation; each is its own write.
 */
export function CounterpartiesPane({ port, locale }: SetupProps) {
  const t = useStrings();
  const taxIdLimit = useTextLimit("counterparty_tax_id");
  const noteLimit = useTextLimit("counterparty_note");
  const actorLimit = useTextLimit("counterparty_asserted_by");
  const [taxId, setTaxId] = useState("");
  const [viewed, setViewed] = useState<{
    identity: string;
    call: SetupCall<LedgerCounterpartyResult>;
  } | null>(null);
  const [country, setCountry] = useState("");
  const identity = identityOf(taxId, country);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const draft = drafts[identity] ?? EMPTY_DRAFT;
  const { scope, state, note, actor, withdrawing } = draft;
  const [conflict, setConflict] = useState<{
    identity: string;
    context: [string, string][];
  } | null>(null);
  const [writeIdentity, setWriteIdentity] = useState<string | null>(null);
  const [notApplied, setNotApplied] = useState<string | null>(null);
  const [attribution, setAttribution] = useState<{
    identity: string;
    name: string;
  } | null>(null);
  const setDraft = (patch: Partial<Draft>) =>
    setDrafts((held) => ({
      ...held,
      [identity]: { ...(held[identity] ?? EMPTY_DRAFT), ...patch },
    }));
  const setScope = (scope: string) => setDraft({ scope });
  const setState = (state: string) => setDraft({ state });
  const setNote = (note: string) => setDraft({ note });
  const setWithdrawing = (withdrawing: boolean) => setDraft({ withdrawing });
  const generation = useRef(0);
  const answerId = useId();
  useLayoutEffect(
    () => () => {
      generation.current += 1;
    },
    [port],
  );
  const invalidateAnswer = () => {
    generation.current += 1;
    setViewed(null);
    setAttribution(null);
  };
  const changeIdentity = (id: string, hint: string) => {
    invalidateAnswer();
    setTaxId(id);
    setCountry(hint);
  };
  // A form with anything typed into it that is not yet written.
  useSetupDraft(
    Object.values(drafts).some((draft) =>
      [draft.scope, draft.state, draft.note, draft.actor].some(Boolean),
    ),
  );
  const write = useSetupWrite(t("desktop.ledger.counterparty.title"));
  const taxIds = useFieldSuggestions("party_tax_id");
  const countries = useFieldSuggestions("country");
  const states = useFieldSuggestions("state");

  const view = async (id = taxId) => {
    if (!id.trim() || (country !== "" && !TWO_LETTERS.test(country))) return;
    if (id !== taxId) changeIdentity(id, country);
    setConflict(null);
    setNotApplied(null);
    const mine = ++generation.current;
    const requested = identityOf(id, country);
    setViewed(null);
    const call = await setupCall(
      port,
      "ledger.counterparty",
      {
        action: "view",
        tax_identifier: id.trim(),
        country_code: country || null,
      },
      false,
    );
    if (mine === generation.current) setViewed({ identity: requested, call });
  };
  const call = viewed?.identity === identity ? viewed.call : null;
  const result = call?.kind === "done" ? call.result : null;
  // VIEW serves a resolution, not exact stored facts. An absent fact cannot
  // establish whether an uncertain confirmation or withdrawal took effect.
  const unknownLanding = async (): Promise<Landing> => "untold";
  const countryWrong = country !== "" && !TWO_LETTERS.test(country);
  const stateWrong = state !== "" && !TWO_LETTERS.test(state);
  const canConfirm =
    result !== null &&
    !countryWrong &&
    !stateWrong &&
    (scope !== "" || state !== "") &&
    actor.trim() !== "" &&
    actorLimit !== null &&
    actor.trim().length <= actorLimit;

  const confirm = async () => {
    if (!result || !canConfirm || write.busy) return;
    const mine = generation.current;
    setWriteIdentity(identity);
    setConflict(null);
    setNotApplied(null);
    setAttribution(null);
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.counterparty",
          {
            action: "confirm",
            tax_identifier: result.tax_identifier,
            country_code: country || null,
            territorial_scope: scope || null,
            identification_state: state ? state.toUpperCase() : null,
            note: note.trim(),
            asserted_by: actor.trim(),
          },
          true,
        ),
      unknownLanding,
    );
    if (done.kind !== "done") return;
    if (done.result.conflict_context != null) {
      setConflict({ identity, context: done.result.conflict_context });
      return;
    }
    const saved = done.result.facts;
    if (
      !saved ||
      (scope !== "" && saved.territorial_scope !== scope) ||
      (state !== "" && saved.identification_state !== state.toUpperCase()) ||
      saved.note !== note.trim()
    ) {
      setNotApplied(identity);
      return;
    }
    setDrafts((held) => {
      const current = held[identity];
      // Typing while the write is pending belongs to the next draft.
      if (
        !current ||
        current.scope !== scope ||
        current.state !== state ||
        current.note !== note ||
        current.actor !== actor
      )
        return held;
      const next = { ...held };
      delete next[identity];
      return next;
    });
    if (mine === generation.current) {
      setAttribution(
        saved.asserted_by !== actor.trim()
          ? { identity, name: saved.asserted_by }
          : null,
      );
      await view();
    }
  };
  const withdraw = async () => {
    if (!result || write.busy) return;
    const mine = generation.current;
    setWriteIdentity(identity);
    setAttribution(null);
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.counterparty",
          {
            action: "withdraw",
            tax_identifier: result.tax_identifier,
            country_code: country || null,
          },
          true,
        ),
      unknownLanding,
    );
    setWithdrawing(false);
    if (done.kind === "done" && mine === generation.current) await view();
  };
  const answer = result?.resolution;
  const confirmed =
    (result?.facts !== null && result?.facts !== undefined) ||
    answer?.territorial_source === "operator_assertion" ||
    answer?.identification_source === "operator_assertion";
  const targetWords =
    result &&
    facts(t, [
      labelled(
        t,
        t("desktop.ledger.counterparty.tax_id"),
        result.tax_identifier,
      ),
      result.country_code
        ? labelled(
            t,
            t("desktop.ledger.counterparty.country"),
            result.country_code,
          )
        : null,
    ]);
  const sourced = (
    value: string | null | undefined,
    source: string | null | undefined,
  ) =>
    value
      ? facts(t, [
          tokenText(t, "counterparty.scope", value),
          tokenText(t, "counterparty.source", source ?? null),
        ])
      : t("desktop.ledger.counterparty.undetermined");

  return (
    <Panel title={t("desktop.ledger.counterparty.title")}>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (taxId.trim() && !countryWrong) void view();
        }}
      >
        <EditorField
          label={t("desktop.ledger.counterparty.tax_id")}
          className="w-64"
        >
          {(control) => (
            <TaxIdEditor
              id={control.id}
              value={taxId}
              onChange={(next) => changeIdentity(next, country)}
              invalid={control.invalid}
              describedBy={control.describedBy}
              maxLength={taxIdLimit ?? undefined}
              {...taxIds}
              onPick={(picked) => void view(picked.value)}
            />
          )}
        </EditorField>
        <EditorField
          label={t("desktop.ledger.counterparty.country")}
          error={countryWrong ? t("desktop.ledger.form.two_letters") : null}
          className="w-64"
        >
          {(control) => (
            <CountryEditor
              id={control.id}
              value={country}
              onChange={(next) => changeIdentity(taxId, next)}
              invalid={control.invalid}
              describedBy={control.describedBy}
              maxLength={2}
              {...countries}
            />
          )}
        </EditorField>
        <Button
          type="submit"
          size="sm"
          variant="outline"
          className="ledger-counterparty-view"
          aria-disabled={!taxId.trim() || countryWrong || undefined}
        >
          {t("desktop.ledger.counterparty.view")}
        </Button>
      </form>
      <CallLine call={call} />
      {attribution?.identity === identity && (
        <p
          role="status"
          className="text-sm text-muted-foreground wrap-anywhere"
        >
          {t("desktop.ledger.counterparty.attribution_kept", {
            name: attribution.name,
          })}
        </p>
      )}
      {result && (
        <div className="ledger-counterparty-answer flex flex-col gap-3">
          <Alert icon={<Icon name="info" />}>
            <span id={answerId} className="font-medium wrap-anywhere">
              {facts(t, [t("desktop.ledger.counterparty.answer"), targetWords])}
            </span>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.established")}
              </dt>
              <dd>
                {sourced(answer?.territorial_scope, answer?.territorial_source)}
              </dd>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.counterparty.vat_state")}
              </dt>
              <dd>
                {answer?.identification_state
                  ? facts(t, [
                      answer.identification_state,
                      tokenText(
                        t,
                        "counterparty.source",
                        answer.identification_source,
                      ),
                    ])
                  : t("desktop.ledger.counterparty.undetermined")}
              </dd>
              {result.facts && (
                <>
                  <dt className="text-muted-foreground">
                    {t("desktop.ledger.counterparty.confirmed")}
                  </dt>
                  <dd>{formatTime(locale, result.facts.asserted_at)}</dd>
                </>
              )}
            </dl>
            {answer?.contradiction_detail && (
              <span className="text-sm">{answer.contradiction_detail}</span>
            )}
          </Alert>
          <FormGrid>
            <ChoiceField
              label={t("desktop.ledger.counterparty.scope_label")}
              value={scope}
              onValue={setScope}
              placeholder={t("desktop.ledger.form.choose")}
              options={TERRITORIAL_SCOPES.map((value) => ({
                value,
                label: tokenText(t, "counterparty.scope", value),
              }))}
            />
            <EditorField
              label={t("desktop.ledger.counterparty.state")}
              error={stateWrong ? t("desktop.ledger.form.two_letters") : null}
            >
              {(control) => (
                <CountryEditor
                  id={control.id}
                  value={state}
                  onChange={setState}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  maxLength={2}
                  {...states}
                />
              )}
            </EditorField>
            <EditorField
              label={t("desktop.ledger.counterparty.asserted_by")}
              hint={t("desktop.ledger.counterparty.asserted_by_hint")}
            >
              {(control) => (
                <TextEditor
                  id={control.id}
                  value={actor}
                  onChange={(actor) => setDraft({ actor })}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  maxLength={actorLimit ?? undefined}
                  required
                />
              )}
            </EditorField>
            <EditorField label={t("desktop.ledger.counterparty.note")}>
              {(control) => (
                <NotesEditor
                  id={control.id}
                  value={note}
                  onChange={setNote}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  maxLength={noteLimit ?? undefined}
                />
              )}
            </EditorField>
          </FormGrid>
          <div className="flex flex-wrap gap-2">
            <WriteHold>
              <Button
                size="sm"
                className="ledger-counterparty-confirm"
                aria-describedby={answerId}
                aria-disabled={!canConfirm || write.busy || undefined}
                onClick={() => canConfirm && !write.busy && void confirm()}
              >
                {t("desktop.ledger.counterparty.confirm")}
              </Button>
            </WriteHold>
            {confirmed && (
              <Button
                size="sm"
                variant="outline"
                aria-expanded={withdrawing}
                aria-describedby={answerId}
                onClick={() => setWithdrawing(!withdrawing)}
              >
                {t("desktop.ledger.counterparty.withdraw")}
              </Button>
            )}
          </div>
          {withdrawing && (
            <Alert tone="warning" icon={<Icon name="alert" />}>
              <span>
                {facts(t, [
                  targetWords,
                  t("desktop.ledger.counterparty.withdraw_what"),
                ])}
              </span>
              <span className="flex gap-2">
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setWithdrawing(false)}
                >
                  {t("desktop.ledger.form.cancel")}
                </Button>
                <WriteHold>
                  <Button
                    size="xs"
                    variant="destructive"
                    className="ledger-counterparty-withdraw"
                    aria-describedby={answerId}
                    disabled={write.busy}
                    onClick={() => void withdraw()}
                  >
                    {t("desktop.ledger.counterparty.withdraw_confirm")}
                  </Button>
                </WriteHold>
              </span>
            </Alert>
          )}
          <CallLine
            call={writeIdentity === identity ? write.last : null}
            onReread={() => void view(result.tax_identifier)}
          />
          <CounterpartyProvincia
            key={`${identity}:${result.provincia_code ?? ""}`}
            port={port}
            result={result}
            country={country}
            actor={actor}
            onSaved={() => view(result.tax_identifier)}
          />
          <CounterpartyFilingName
            key={`${identity}:${JSON.stringify(result.filing_name ?? null)}`}
            port={port}
            result={result}
            country={country}
            actor={actor}
            onSaved={() => view(result.tax_identifier)}
          />
          {conflict?.identity === identity && (
            <CounterpartyConflict context={conflict.context} />
          )}
          {notApplied === identity && (
            <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
              {t("desktop.ledger.counterparty.not_applied")}
            </Alert>
          )}
        </div>
      )}
    </Panel>
  );
}

function CounterpartyConflict({ context }: { context: [string, string][] }) {
  const t = useStrings();
  const values = new Map(context);
  return (
    <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
      <p>{t("desktop.ledger.counterparty.conflict")}</p>
      {(["scope", "identification_state"] as const).map((axis) => {
        const confirmed = values.get(`confirmed_${axis}`);
        const proposed = values.get(`asserted_${axis}`);
        if (!confirmed || !proposed) return null;
        const words = (value: string) =>
          axis === "scope" ? tokenText(t, "counterparty.scope", value) : value;
        return (
          <div key={axis}>
            <p className="font-medium">
              {t(
                axis === "scope"
                  ? "desktop.ledger.counterparty.scope_label"
                  : "desktop.ledger.counterparty.state",
              )}
            </p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt>{t("desktop.ledger.counterparty.confirmed")}</dt>
              <dd className="wrap-anywhere">{words(confirmed)}</dd>
              <dt>{t("desktop.ledger.counterparty.proposed")}</dt>
              <dd className="wrap-anywhere">{words(proposed)}</dd>
            </dl>
          </div>
        );
      })}
    </Alert>
  );
}
