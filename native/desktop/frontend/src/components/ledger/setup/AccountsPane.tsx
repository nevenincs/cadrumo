import { useState } from "react";
import { BicEditor } from "@/components/editors/BicEditor";
import { CountryEditor } from "@/components/editors/CountryEditor";
import { CurrencyEditor } from "@/components/editors/CurrencyEditor";
import { DateEditor } from "@/components/editors/DateEditor";
import { IbanEditor } from "@/components/editors/IbanEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { facts } from "@/shell/compose";
import { ownAccountChange, type OwnAccountChange } from "../../../shell/ledger";
import { parseIsoDate } from "../../../shell/ledgerGrammar";
import type {
  LedgerOwnAccountResult,
  OwnAccount,
  OwnAccountDesignation,
  OwnAccountRole,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { useWritePause, WriteHold, type Landing } from "../WritePause";
import { formatDay } from "../../../shared/dateFormats";
import { ibanProblem, ibanText } from "../../../shared/iban";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  Reading,
  readLanding,
  SetupTable,
  TextField,
  useSetupDraft,
  useSetupRead,
  useSetupWrite,
  type Column,
} from "./SetupParts";
import { EditorField } from "./EditorField";
import type { SetupProps } from "./setupProps";
import {
  callFailure,
  callOutcome,
  setupCall,
  type SetupCall,
} from "./setupModel";
import { grammarText } from "./setupWords";

const ROLES: readonly OwnAccountRole[] = ["charge", "refund"];
const HOLDINGS = ["titular", "cotitular"] as const;
const MODELO = /^\d{3}$/;
const CURRENCY = /^[A-Za-z]{3}$/;

/** The private part of an account form: its number and bank block. They
 * live in this form only, until the one call that sends them. */
type Secrets = {
  iban: string;
  swift_bic: string;
  bank_name: string;
  bank_address: string;
  bank_city: string;
  bank_country_code: string;
};
const NO_SECRETS: Secrets = {
  iban: "",
  swift_bic: "",
  bank_name: "",
  bank_address: "",
  bank_city: "",
  bank_country_code: "",
};

type Form =
  | { kind: "add" }
  | { kind: "update"; account: OwnAccount }
  | { kind: "close"; account: OwnAccount }
  | { kind: "designate"; account: OwnAccount };

/** Sends an own account's details through the host's raw body: the only
 * way an account number leaves the window. The bytes are zeroed by the
 * call that consumes them. */
async function sendChange(
  port: SetupProps["port"],
  change: OwnAccountChange,
): Promise<SetupCall<LedgerOwnAccountResult>> {
  const bytes = ownAccountChange(change);
  try {
    return callOutcome(
      await port.changeOwnAccount(bytes),
      true,
    ) as SetupCall<LedgerOwnAccountResult>;
  } catch (error) {
    return callFailure(error);
  } finally {
    bytes.fill(0);
  }
}

/**
 * The person's own bank accounts, which statements bind to: each shown by
 * its name and masked number, with when it opened and closed and what it
 * is designated for. Its number and bank block are entered here and sent
 * once, through the host, never kept or shown again.
 */
export function AccountsPane({ port, reader, locale }: SetupProps) {
  const t = useStrings();
  const { read, reload } = useSetupRead(
    port,
    reader,
    "ledger.own_account",
    { action: "list" },
    "accounts",
  );
  const write = useSetupWrite(t("desktop.ledger.accounts.title"));
  const { held } = useWritePause();
  const [form, setForm] = useState<Form | null>(null);
  const [label, setLabel] = useState("");
  const [holding, setHolding] = useState("");
  const [currency, setCurrency] = useState("");
  const [opened, setOpened] = useState("");
  const [secrets, setSecrets] = useState<Secrets>(NO_SECRETS);
  const [closedOn, setClosedOn] = useState("");
  const [role, setRole] = useState("");
  const [modelo, setModelo] = useState("");

  const listed = read?.kind === "done" ? read.result : null;
  const open = (next: Form | null) => {
    write.clear();
    setForm(next);
    setLabel(next?.kind === "update" ? next.account.label : "");
    setHolding("");
    setCurrency("");
    setOpened("");
    setSecrets(NO_SECRETS);
    setClosedOn("");
    setRole("");
    setModelo("");
  };
  const secret = (field: keyof Secrets) => (value: string) =>
    setSecrets((current) => ({ ...current, [field]: value }));
  // An open form with anything typed into it, beyond the label it opened on.
  useSetupDraft(
    form !== null &&
      (label !== (form.kind === "update" ? form.account.label : "") ||
        [holding, currency, opened, closedOn, role, modelo].some(Boolean) ||
        Object.values(secrets).some(Boolean)),
  );

  const iban = ibanText(secrets.iban);
  const ibanWrong = iban !== "" ? ibanProblem(iban) : null;
  const openedOn = parseIsoDate(opened);
  const closing = parseIsoDate(closedOn);
  const bankBlock = (
    [
      "swift_bic",
      "bank_name",
      "bank_address",
      "bank_city",
      "bank_country_code",
    ] as const
  ).filter((field) => secrets[field].trim() !== "");
  const dateError = (parsed: ReturnType<typeof parseIsoDate>) =>
    parsed.kind === "refused" ? grammarText(t, parsed.refusal) : null;

  const finish = (done: SetupCall<LedgerOwnAccountResult>) => {
    // The number and bank block go with the attempt, whatever its outcome.
    setSecrets(NO_SECRETS);
    if (done.kind === "done") {
      setForm(null);
      reload();
    }
    return done;
  };
  const details = (): Omit<OwnAccountChange, "action"> => {
    const out: Omit<OwnAccountChange, "action"> = {};
    if (iban) out.iban = iban;
    for (const field of bankBlock) out[field] = secrets[field].trim();
    if (out.swift_bic) out.swift_bic = out.swift_bic.toUpperCase();
    if (out.bank_country_code)
      out.bank_country_code = out.bank_country_code.toUpperCase();
    return out;
  };

  /** How a write of the account list landed, judged on the list read
   * again. */
  const listLanding = (judge: (result: LedgerOwnAccountResult) => Landing) =>
    readLanding(port, "ledger.own_account", { action: "list" }, judge);
  const accountOf = (result: LedgerOwnAccountResult, id: string) =>
    result.accounts.find((found) => found.own_account_id === id);

  const addReady =
    label.trim() !== "" &&
    holding !== "" &&
    iban !== "" &&
    ibanWrong === null &&
    CURRENCY.test(currency) &&
    openedOn.kind === "value";
  const add = () => {
    const before = new Set(
      (listed?.accounts ?? []).map((found) => found.own_account_id),
    );
    const named = label.trim();
    return write.run(
      async () =>
        finish(
          await sendChange(port, {
            action: "add",
            label: label.trim(),
            holding,
            currency: currency.toUpperCase(),
            opened_on: openedOn.kind === "value" ? openedOn.value : undefined,
            ...details(),
          }),
        ),
      // A new account is one the list did not hold, under the label sent.
      listLanding((result) =>
        result.accounts.some(
          (found) => !before.has(found.own_account_id) && found.label === named,
        )
          ? "saved"
          : "not_saved",
      ),
    );
  };
  const update = (account: OwnAccount) => {
    const secretsGiven = iban !== "" || bankBlock.length > 0;
    const renamed = label.trim() !== "" && label.trim() !== account.label;
    const named = label.trim();
    return write.run(
      async () => {
        if (secretsGiven)
          return finish(
            await sendChange(port, {
              action: "update",
              own_account_id: account.own_account_id,
              ...(renamed ? { label: label.trim() } : {}),
              ...details(),
            }),
          );
        return finish(
          await setupCall(
            port,
            "ledger.own_account",
            {
              action: "update",
              own_account_id: account.own_account_id,
              label: label.trim(),
            },
            true,
          ),
        );
      },
      renamed
        ? // The label travels in the same write as any account details.
          listLanding((result) =>
            accountOf(result, account.own_account_id)?.label === named
              ? "saved"
              : "not_saved",
          )
        : // The list shows no account number: an update that sends only the
          // number and bank block is told by no read, and sent again it
          // stores the same details over themselves.
          async () => "repeatable",
    );
  };
  const updateReady = (account: OwnAccount) =>
    (iban === "" || ibanWrong === null) &&
    (iban !== "" ||
      bankBlock.length > 0 ||
      (label.trim() !== "" && label.trim() !== account.label));
  const close = (account: OwnAccount) =>
    write.run(
      async () =>
        finish(
          await setupCall(
            port,
            "ledger.own_account",
            {
              action: "close",
              own_account_id: account.own_account_id,
              closed_on: closing.kind === "value" ? closing.value : "",
            },
            true,
          ),
        ),
      listLanding((result) =>
        accountOf(result, account.own_account_id)?.closed_on ===
        (closing.kind === "value" ? closing.value : null)
          ? "saved"
          : "not_saved",
      ),
    );
  const designate = (account: OwnAccount) =>
    write.run(
      async () =>
        finish(
          await setupCall(
            port,
            "ledger.own_account",
            {
              action: "designate",
              own_account_id: account.own_account_id,
              role: role as OwnAccountRole,
              modelo: modelo.trim() || null,
            },
            true,
          ),
        ),
      listLanding((result) =>
        result.designations.some(
          (found) =>
            found.own_account_id === account.own_account_id &&
            found.role === role &&
            found.modelo === (modelo.trim() || null),
        )
          ? "saved"
          : "not_saved",
      ),
    );
  const undesignate = (found: OwnAccountDesignation) =>
    write.run(
      async () =>
        finish(
          await setupCall(
            port,
            "ledger.own_account",
            { action: "undesignate", role: found.role, modelo: found.modelo },
            true,
          ),
        ),
      listLanding((result) =>
        result.designations.some(
          (other) => other.role === found.role && other.modelo === found.modelo,
        )
          ? "not_saved"
          : "saved",
      ),
    );
  const remove = (account: OwnAccount) =>
    write.run(
      async () =>
        finish(
          await setupCall(
            port,
            "ledger.own_account",
            { action: "remove", own_account_id: account.own_account_id },
            true,
          ),
        ),
      listLanding((result) =>
        accountOf(result, account.own_account_id) ? "not_saved" : "saved",
      ),
    );

  const designationText = (found: OwnAccountDesignation) =>
    facts(t, [
      t(`desktop.ledger.accounts.role.${found.role}`),
      found.modelo
        ? t("desktop.ledger.accounts.modelo", { modelo: found.modelo })
        : t("desktop.ledger.accounts.every_modelo"),
    ]);
  const day = (value: string | null) =>
    value ? formatDay(locale, value) : null;

  const columns: Column<OwnAccount>[] = [
    {
      key: "label",
      label: t("desktop.ledger.accounts.column.label"),
      sort: (account) => account.label,
      cell: (account) => <span className="font-medium">{account.label}</span>,
    },
    {
      key: "iban",
      label: t("desktop.ledger.accounts.column.iban"),
      sort: (account) => account.masked_iban,
      cell: (account) => (
        <span className="font-mono whitespace-nowrap">
          {account.masked_iban}
        </span>
      ),
    },
    {
      key: "currency",
      label: t("desktop.ledger.accounts.column.currency"),
      sort: (account) => account.currency,
      cell: (account) => account.currency,
    },
    {
      key: "opened",
      label: t("desktop.ledger.accounts.column.opened"),
      sort: (account) => account.opened_on,
      cell: (account) =>
        day(account.opened_on) ?? (
          <span className="text-muted-foreground">
            {t("desktop.ledger.accounts.not_known")}
          </span>
        ),
    },
    {
      key: "closed",
      label: t("desktop.ledger.accounts.column.closed"),
      sort: (account) => account.closed_on,
      cell: (account) =>
        day(account.closed_on) ?? (
          <span className="text-muted-foreground">
            <span aria-hidden="true">—</span>
            <span className="sr-only">
              {t("desktop.ledger.accounts.not_closed")}
            </span>
          </span>
        ),
    },
    {
      key: "holding",
      label: t("desktop.ledger.accounts.column.holding"),
      sort: (account) =>
        t(`desktop.ledger.accounts.holding.${account.holding}`),
      cell: (account) =>
        t(`desktop.ledger.accounts.holding.${account.holding}`),
    },
    {
      key: "designated",
      label: t("desktop.ledger.accounts.column.designated"),
      cell: (account) => {
        const own = (listed?.designations ?? []).filter(
          (found) => found.own_account_id === account.own_account_id,
        );
        if (own.length === 0)
          return <span className="text-muted-foreground">—</span>;
        return (
          <ul className="flex flex-col gap-0.5">
            {own.map((found) => (
              <li
                key={`${found.role}:${found.modelo ?? ""}`}
                className="flex items-center gap-1"
              >
                {designationText(found)}
                <WriteHold>
                  <IconButton
                    size="sm"
                    label={t("desktop.ledger.accounts.undesignate", {
                      designation: designationText(found),
                    })}
                    onClick={() => !write.busy && void undesignate(found)}
                  >
                    <Icon name="close" />
                  </IconButton>
                </WriteHold>
              </li>
            ))}
          </ul>
        );
      },
    },
    {
      key: "actions",
      label: t("desktop.ledger.form.actions"),
      hidden: true,
      resizable: false,
      cell: (account) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <IconButton
              size="sm"
              label={t("desktop.ledger.accounts.actions", {
                account: account.label,
              })}
            >
              <Icon name="settings" />
            </IconButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              icon="edit"
              onSelect={() => open({ kind: "update", account })}
            >
              {t("desktop.ledger.accounts.update")}
            </DropdownMenuItem>
            <DropdownMenuItem
              icon="tick"
              onSelect={() => open({ kind: "designate", account })}
            >
              {t("desktop.ledger.accounts.designate")}
            </DropdownMenuItem>
            <DropdownMenuItem
              icon="clock"
              disabled={account.closed_on !== null}
              onSelect={() => open({ kind: "close", account })}
            >
              {t("desktop.ledger.accounts.close")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              icon="trash"
              className="ledger-account-remove"
              disabled={held !== null}
              title={held ?? undefined}
              onSelect={() => void remove(account)}
            >
              {t("desktop.ledger.accounts.remove")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  const secretFields = (
    <>
      <EditorField
        label={t("desktop.ledger.accounts.iban")}
        hint={t("desktop.ledger.accounts.iban_hint")}
        error={
          ibanWrong
            ? t(`desktop.ledger.accounts.iban_problem.${ibanWrong}`)
            : null
        }
      >
        {(control) => (
          <IbanEditor
            id={control.id}
            name="own-account-number"
            value={secrets.iban}
            onChange={secret("iban")}
            invalid={control.invalid}
            describedBy={control.describedBy}
            required={form?.kind === "add"}
            maxLength={64}
            secret
          />
        )}
      </EditorField>
      <EditorField label={t("desktop.ledger.accounts.swift_bic")}>
        {(control) => (
          <BicEditor
            id={control.id}
            value={secrets.swift_bic}
            onChange={secret("swift_bic")}
            invalid={control.invalid}
            describedBy={control.describedBy}
            maxLength={16}
            secret
          />
        )}
      </EditorField>
      <TextField
        label={t("desktop.ledger.accounts.bank_name")}
        value={secrets.bank_name}
        onValue={secret("bank_name")}
        type="password"
        hint={t("desktop.ledger.accounts.bank_hint")}
        maxLength={70}
      />
      <TextField
        label={t("desktop.ledger.accounts.bank_address")}
        value={secrets.bank_address}
        onValue={secret("bank_address")}
        type="password"
        maxLength={35}
      />
      <TextField
        label={t("desktop.ledger.accounts.bank_city")}
        value={secrets.bank_city}
        onValue={secret("bank_city")}
        type="password"
        maxLength={30}
      />
      <EditorField label={t("desktop.ledger.accounts.bank_country")}>
        {(control) => (
          <CountryEditor
            id={control.id}
            value={secrets.bank_country_code}
            onChange={secret("bank_country_code")}
            invalid={control.invalid}
            describedBy={control.describedBy}
            maxLength={2}
            secret
          />
        )}
      </EditorField>
    </>
  );

  const refusal = (reason: string | null) =>
    reason === "REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION"
      ? t(
          form === null
            ? "desktop.ledger.accounts.refused_remove"
            : "desktop.ledger.accounts.refused",
        )
      : null;

  return (
    <Panel
      title={t("desktop.ledger.accounts.title")}
      actions={
        <Button
          size="xs"
          variant="outline"
          className="ledger-account-add"
          onClick={() => open({ kind: "add" })}
        >
          <Icon name="plus" />
          {t("desktop.ledger.accounts.add")}
        </Button>
      }
    >
      {read === null ? (
        <Reading label={t("desktop.ledger.form.reading")} />
      ) : read.kind !== "done" ? (
        <CallLine call={read} />
      ) : read.result.accounts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.accounts.empty")}
        </p>
      ) : (
        <SetupTable
          label={t("desktop.ledger.accounts.title")}
          rows={read.result.accounts}
          rowKey={(account) => account.own_account_id}
          columns={columns}
          className="ledger-accounts-table"
        />
      )}
      {form && (
        <form
          className="ledger-account-form flex flex-col gap-3 rounded-md bg-accent p-3"
          autoComplete="off"
          onSubmit={(event) => {
            event.preventDefault();
            if (write.busy) return;
            if (form.kind === "add" && addReady) void add();
            if (form.kind === "update" && updateReady(form.account))
              void update(form.account);
            if (form.kind === "close" && closing.kind === "value")
              void close(form.account);
            if (
              form.kind === "designate" &&
              role &&
              (!modelo || MODELO.test(modelo))
            )
              void designate(form.account);
          }}
        >
          <h4 className="font-medium">
            {form.kind === "add"
              ? t("desktop.ledger.accounts.add")
              : t(`desktop.ledger.accounts.named.${form.kind}`, {
                  account: form.account.label,
                })}
          </h4>
          {form.kind === "add" && (
            <FormGrid>
              <EditorField label={t("desktop.ledger.accounts.label")}>
                {(control) => (
                  <TextEditor
                    id={control.id}
                    value={label}
                    onChange={setLabel}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                    maxLength={80}
                    required
                    autoFocus
                  />
                )}
              </EditorField>
              <ChoiceField
                label={t("desktop.ledger.accounts.holding_label")}
                value={holding}
                onValue={setHolding}
                placeholder={t("desktop.ledger.form.choose")}
                options={HOLDINGS.map((value) => ({
                  value,
                  label: t(`desktop.ledger.accounts.holding.${value}`),
                }))}
              />
              <EditorField label={t("desktop.ledger.accounts.currency")}>
                {(control) => (
                  <CurrencyEditor
                    id={control.id}
                    value={currency}
                    onChange={setCurrency}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                    maxLength={3}
                    required
                  />
                )}
              </EditorField>
              <EditorField
                label={t("desktop.ledger.accounts.opened")}
                error={dateError(openedOn)}
              >
                {(control) => (
                  <DateEditor
                    id={control.id}
                    value={opened}
                    onChange={setOpened}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                    required
                  />
                )}
              </EditorField>
              {secretFields}
            </FormGrid>
          )}
          {form.kind === "update" && (
            <FormGrid>
              <EditorField label={t("desktop.ledger.accounts.label")}>
                {(control) => (
                  <TextEditor
                    id={control.id}
                    value={label}
                    onChange={setLabel}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                    maxLength={80}
                    autoFocus
                  />
                )}
              </EditorField>
              {secretFields}
            </FormGrid>
          )}
          {form.kind === "close" && (
            <EditorField
              label={t("desktop.ledger.accounts.closed_on")}
              hint={t("desktop.ledger.accounts.closed_hint")}
              error={dateError(closing)}
              className="max-w-xs"
            >
              {(control) => (
                <DateEditor
                  id={control.id}
                  value={closedOn}
                  onChange={setClosedOn}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  required
                  autoFocus
                />
              )}
            </EditorField>
          )}
          {form.kind === "designate" && (
            <FormGrid>
              <ChoiceField
                label={t("desktop.ledger.accounts.role_label")}
                value={role}
                onValue={setRole}
                placeholder={t("desktop.ledger.form.choose")}
                options={ROLES.map((value) => ({
                  value,
                  label: t(`desktop.ledger.accounts.role.${value}`),
                }))}
              />
              <EditorField
                label={t("desktop.ledger.accounts.modelo_label")}
                error={
                  modelo && !MODELO.test(modelo)
                    ? t("desktop.ledger.accounts.modelo_hint")
                    : null
                }
              >
                {(control) => (
                  <TextEditor
                    id={control.id}
                    value={modelo}
                    onChange={setModelo}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                    maxLength={3}
                    inputMode="numeric"
                  />
                )}
              </EditorField>
            </FormGrid>
          )}
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => open(null)}
            >
              {t("desktop.ledger.form.cancel")}
            </Button>
            <WriteHold>
              <Button
                type="submit"
                size="sm"
                className="ledger-account-submit"
                aria-disabled={
                  write.busy ||
                  (form.kind === "add" && !addReady) ||
                  (form.kind === "update" && !updateReady(form.account)) ||
                  (form.kind === "close" && closing.kind !== "value") ||
                  (form.kind === "designate" &&
                    (!role || (modelo !== "" && !MODELO.test(modelo)))) ||
                  undefined
                }
              >
                {write.busy
                  ? t("desktop.ledger.form.saving")
                  : t(`desktop.ledger.accounts.submit.${form.kind}`)}
              </Button>
            </WriteHold>
          </div>
        </form>
      )}
      <CallLine call={write.last} refusal={refusal} onReread={reload} />
    </Panel>
  );
}
