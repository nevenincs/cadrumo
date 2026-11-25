import { expect, test } from "@playwright/test";
import type { LedgerEvidencePageProjection } from "../src/shell/ledgerDocumentContract";
import {
  STRUCTURED_SAMPLE_NAMES,
  STRUCTURED_WITH_LINES,
  structuredSampleId,
} from "../src/dev/fixtures/documentPage";
import type { Translate } from "../src/shell/strings";
import { formatDay } from "../src/shared/dateFormats";
import { formatPercent } from "../src/shared/numbers";
import { markupOf } from "./support/markup";
import { label } from "./support/strings";

// A shown page of the document viewer. A structured e-invoice is drawn as
// the facts its record states and never as an image: the runtime draws no
// page of it, so an image there would be an empty frame. Every value is
// synthetic, the structured page the evidence fixture serves.

const t = Object.assign(
  (key: string, values?: Record<string, string | number>) =>
    label(key, values, "en"),
  { locale: "en" },
) as Translate;

const drawPage = () =>
  markupOf<{
    t: Translate;
    shown: LedgerEvidencePageProjection;
    scale: number;
    fileName: string;
  }>("components/ledger/documents/DocumentViewer.tsx", "DocumentPage");

const XML_NAME = STRUCTURED_SAMPLE_NAMES.withLines;
const xmlPage: LedgerEvidencePageProjection = {
  profile_id: "profile",
  evidence_id: null,
  attachment_id: structuredSampleId(XML_NAME),
  media_type: "application/xml",
  page: 1,
  page_count: 1,
  width: null,
  height: null,
  source_sha256: structuredSampleId(XML_NAME),
  file_name: XML_NAME,
  image_data_url: null,
  structured_invoice: STRUCTURED_WITH_LINES,
};

test("a structured e-invoice page draws its served facts and no image", async () => {
  const markup = await (
    await drawPage()
  )({
    t,
    shown: xmlPage,
    scale: 1,
    fileName: XML_NAME,
  });
  expect(markup).not.toContain("<img");
  expect(markup).toContain("ledger-document-structured-facts");
  expect(markup).toContain(label(STRUCTURED_WITH_LINES.title_key));
  for (const fact of STRUCTURED_WITH_LINES.facts) {
    expect(markup).toContain(label(fact.label_key));
    if (fact.text !== null) expect(markup).toContain(fact.text);
    if (fact.iso_date !== null)
      expect(markup).toContain(formatDay("en", fact.iso_date));
  }
  expect(markup).toContain("ledger-document-structured-lines");
  expect(markup).toContain("Diseño de cartel");
});

test("a drawn page shows the runtime's image", async () => {
  const markup = await (
    await drawPage()
  )({
    t,
    shown: {
      ...xmlPage,
      media_type: "image/jpeg",
      width: 10,
      height: 10,
      image_data_url: "data:image/png;base64,AAAA",
      structured_invoice: null,
    },
    scale: 1,
    fileName: "ticket.jpg",
  });
  expect(markup).toContain("<img");
  expect(markup).toContain("data:image/png;base64,AAAA");
  expect(markup).not.toContain("ledger-document-structured");
});

test("a structured e-invoice's figures and dates are drawn in the person's locale by the kind the backend serves", async () => {
  const es = Object.assign(
    (key: string, values?: Record<string, string | number>) =>
      label(key, values, "es"),
    { locale: "es" },
  ) as Translate;
  const markup = await (
    await drawPage()
  )({ t: es, shown: xmlPage, scale: 1, fileName: XML_NAME });
  // An amount keeps its cents and takes the locale's decimal mark.
  expect(markup).toContain("300,00");
  expect(markup).toContain("63,00");
  expect(markup).not.toContain("300.00");
  // A line's rate is a percentage and its quantity a plain number.
  expect(markup).toContain(formatPercent("es", "21", { unit: "points" }));
  // The date is drawn as the locale writes a day, not as the ISO text.
  expect(markup).toContain(formatDay("es", "2026-10-15"));
  expect(markup).not.toContain(">2026-10-15<");
});
