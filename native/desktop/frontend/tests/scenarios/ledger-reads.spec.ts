import { expect, test } from "@playwright/test";
import type { EvidenceListResult } from "../../src/shell/ledgerDocumentOperations";
import type { LedgerOutcome, LedgerPort } from "../../src/shell/ledger";

for (const mode of ["documents", "setup"] as const) {
  test(`${mode} reads follow payload availability and discard replaced answers`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await page.evaluate(async (mode) => {
      const { react, dom, client, documents, setup } =
        await window.__scenarioModules!.ledgerReads();
      const pending: {
        resolve(value: LedgerOutcome<EvidenceListResult>): void;
        reject(error: Error): void;
      }[] = [];
      // The hooks only use submit; every answer still passes their real outcome parser.
      const port = {
        submit: () =>
          new Promise<LedgerOutcome<EvidenceListResult>>((resolve, reject) =>
            pending.push({ resolve, reject }),
          ),
      } as unknown as LedgerPort;
      type Snapshot = { phase: string; value: string | null };
      type Props = {
        requestKey: string;
        available: boolean;
        shown: boolean;
        reader: string | null;
      };
      const commits: Snapshot[] = [];
      let refresh = () => {};
      function DocumentsProbe(props: Props) {
        const { read, reread } = documents.useLedgerRead(
          port,
          props.reader,
          props.shown,
          "ledger.evidence.list",
          props.available ? {} : null,
          props.requestKey,
        );
        react.useLayoutEffect(() => {
          refresh = reread;
          commits.push({
            phase: read.phase,
            value: read.value?.profile_id ?? null,
          });
        });
        return null;
      }
      function SetupProbe(props: Props) {
        const { read, reload } = setup.useSetupRead(
          port,
          props.reader,
          "ledger.evidence.list",
          props.available ? {} : null,
          props.requestKey,
        );
        react.useLayoutEffect(() => {
          refresh = reload;
          commits.push({
            phase: read?.kind ?? "reading",
            value: read?.kind === "done" ? read.result.profile_id : null,
          });
        });
        return null;
      }
      const container = document.createElement("div");
      document.body.append(container);
      const root = client.createRoot(container);
      const Probe = mode === "documents" ? DocumentsProbe : SetupProbe;
      let props: Props = {
        requestKey: "same-key",
        available: false,
        shown: true,
        reader: "profile",
      };
      const render = (patch: Partial<Props> = {}) => {
        props = { ...props, ...patch };
        const before = commits.length;
        dom.flushSync(() => root.render(react.createElement(Probe, props)));
        return commits[before];
      };
      const turn = () =>
        new Promise((resolve) => window.setTimeout(resolve, 10));
      const waitForValue = async (value: string) => {
        for (let at = 0; at < 100; at++) {
          if (commits.at(-1)?.value === value) return;
          await turn();
        }
        throw new Error(`Read never displayed ${value}`);
      };
      const answer = (value: string): LedgerOutcome<EvidenceListResult> => ({
        kind: "settled",
        operation_id: "read",
        revision: 1,
        result: { profile_id: value, count: 0, rows: [] },
      });
      let mounted = true;
      try {
        render();
        const disabledRequests = pending.length;
        render({ available: true });
        const openedRequests = pending.length;
        pending.at(-1)!.resolve(answer("first"));
        await waitForValue("first");
        // Fresh payload object, same semantic key: no extra request.
        render();
        const unchangedRequests = pending.length;
        dom.flushSync(refresh);
        await turn();
        const duringRefresh = commits.at(-1);
        const replaced = pending.at(-1)!;
        const firstNewKey = render({ requestKey: "next-key" });
        const current = pending.at(-1)!;
        replaced.reject(new Error("obsolete failure"));
        current.resolve(answer("second"));
        await waitForValue("second");

        let hiddenSnapshot: Snapshot | undefined;
        if (mode === "documents") {
          hiddenSnapshot = render({ shown: false });
          render({ shown: true });
        } else dom.flushSync(refresh);
        const withdrawn = pending.at(-1)!;
        const firstDisabled = render({ available: false });
        await turn();
        const afterWithdrawal = commits.length;
        withdrawn.resolve(answer("withdrawn"));
        await turn();
        const lateWithdrawalCommits = commits.length - afterWithdrawal;

        render({ available: true });
        const hiddenRead = pending.at(-1)!;
        render(mode === "documents" ? { shown: false } : { reader: null });
        await turn();
        const afterHide = commits.length;
        hiddenRead.reject(new Error("hidden failure"));
        await turn();
        const lateHiddenCommits = commits.length - afterHide;
        render({ shown: true, reader: "profile" });
        const unmountedRead = pending.at(-1)!;
        dom.flushSync(() => root.unmount());
        mounted = false;
        const afterUnmount = commits.length;
        unmountedRead.resolve(answer("unmounted"));
        await turn();
        return {
          disabledRequests,
          openedRequests,
          unchangedRequests,
          duringRefresh,
          firstNewKey,
          hiddenSnapshot,
          firstDisabled,
          lateWithdrawalCommits,
          lateHiddenCommits,
          lateUnmountCommits: commits.length - afterUnmount,
        };
      } finally {
        if (mounted) dom.flushSync(() => root.unmount());
        container.remove();
      }
    }, mode);
    expect(result.disabledRequests).toBe(0);
    expect(result.openedRequests).toBe(1);
    expect(result.unchangedRequests).toBe(1);
    expect(result.duringRefresh?.value).toBe(
      mode === "documents" ? "first" : null,
    );
    expect(result.firstNewKey?.value).toBeNull();
    if (mode === "documents")
      expect(result.hiddenSnapshot?.value).toBe("second");
    expect(result.firstDisabled?.value).toBeNull();
    expect(result.lateWithdrawalCommits).toBe(0);
    expect(result.lateHiddenCommits).toBe(0);
    expect(result.lateUnmountCommits).toBe(0);
  });
}
