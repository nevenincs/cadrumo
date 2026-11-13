import { expect, test } from "@playwright/test";
import { answerInvoiceDuplicate } from "../src/dev/ledgerDuplicateFixture";
import type { LedgerInvoiceDuplicateRequest } from "../src/shell/ledgerInvoiceOperations";
import type { CatalogueInvoiceSnapshot } from "../src/shell/ledgerInvoiceContract";
import recorded from "@fixtures/ledger-recordings/ledgerInvoiceDuplicate.json" with { type: "json" };

// The stand-in stories use for `ledger.invoice.duplicate`, held to what the real
// backend answered over the same catalogue. A test in the owning Python package
// holds the recording to the live answer.

const stored = recorded.invoices.map((invoice) => ({
  ...invoice,
  kind: invoice.kind as CatalogueInvoiceSnapshot["kind"],
  grand_total: { decimal: invoice.grand_total },
}));

for (const { name, question, answer } of recorded.answers) {
  test(`the stand-in answers as the backend did: ${name}`, () => {
    expect(
      answerInvoiceDuplicate(
        question as LedgerInvoiceDuplicateRequest,
        stored,
        "profile",
      ),
    ).toEqual({ profile_id: "profile", ...answer });
  });
}
