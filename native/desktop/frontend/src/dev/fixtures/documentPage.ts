import { hex64 } from "./ledger";

// One drawn page the scenario answers `ledger.evidence.page` with: an
// invented grey layout of a receipt, 240 by 340 pixels, holding no text.

export const DOCUMENT_PAGE = {
  width: 240,
  height: 340,
  image_data_url:
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPAAAAFUCAIAAACVzSaJAAAC/UlEQVR42u3dMaqDQBiF0WtwZULKgEsQsq6ASxBSBtyWMJUrmDTRIHpO/4o3fPykuUlTyhI4i5snQNAgaBA0CBpBg6BB0CBoEDSCBkGDoEHQIGgEDYIGQYOgoab95Y+77u4F/2OePx7BhUbQIGgQNAgaBI2gQdAgaBA0CBpBg6BB0LCFxk9S4EKDoEHQIGgEDYIGQYOgQdAIGgQNggZBg6ARNAgaBA2CBkEjaBA0CBoEDYImfqewZpreXpA99P3DhQZBI2gQNAgaBI2gQdAQ3+APLjQIGkGDoEHQIGgQNIIGQYOgQdAgaGL1Hatvssc224UGQSNoEDQIGgQNgkbQEKtvcKFB0CBoBA2CBkGDoEHQCBoEDYIGQUOsvmOb7UKDoEHQIGgE7QkQNAgaBA2x+saFBkGDoEHQIGgEDYIGQYOgQdAIGgQNsfqGbLdUd6HxkQMEDYIGQSNoEDQIGmL1DS40ggZBg6BB0CBoBA2CBkGDoEHQCBpi9U1ss11oEDQIGkGDoEHQIGgQNLH6BhcaBA2CBkEjaBA0CBoEjaBB0CBoEDTE6pscdZvtQoOgETQIGgQNggZBI2iI1Te40CBoEDSCBkGDoEHQIGgEDYIGQYOgIVbf5IRLdRcaHzlA0CBoEDSCBkGDoCFW3+BCI2gQNAgaBA2CRtAgaBA0CBoEjaAhVt/ENtuFBkGDoBE0CBoEDYIGQROrb3ChQdAgaBA0ggZBg6BB0AgaBA2CBkGDoBE0CBoEDYIGQSNoEDQIGgQNgkbQIGgQNAgaBI2gQdAgaBA0CBpBg6BB0CBoEDSCBkGDoEHQCBoEDYIGQYOgETQIGgQNggZBI2gQNAgaBA1ftZ7g+IbhebV/eRxfLjQIGkGDoEHQIGgEDYIGQYOgQdAIGgQNggZBg6ARNAgaBA2ChrqmlMUr4EKDoEHQIGgEDYIGQYOgQdAIGgQNggZBg6ARNAgaBA2CBkEjaBA0CBoEDYJG0CBoEDQIGgSNoEHQIGgQNAgaQYOgQdAgaC5sBWsyQMsWOOZuAAAAAElFTkSuQmCC",
} as const;

const FACT = "application.ledger.evidence.structured.fact.";
const LINE = "application.ledger.evidence.structured.line.";

/** Stored documents that are structured e-invoices, by file name. They are
 * reachable by their reference but are in no queue, so they change no list. */
export const STRUCTURED_SAMPLE_NAMES = {
  withLines: "factura-ubl-con-lineas.xml",
  withoutLines: "factura-facturae-sin-lineas.xml",
} as const;

const text = (key: string, value: string) => ({
  label_key: `${FACT}${key}`,
  text: value,
});
const figure = (key: string, value: string) => ({
  label_key: `${FACT}${key}`,
  number: value,
});
const lineFacts = (
  description: string,
  quantity: string,
  price: string,
  base: string,
  rate: string,
  iva: string,
) => ({
  facts: [
    { label_key: `${LINE}description`, text: description },
    { label_key: `${LINE}quantity`, number: quantity },
    { label_key: `${LINE}unit_price`, number: price },
    { label_key: `${LINE}taxable_base`, number: base },
    { label_key: `${LINE}iva_rate`, number: rate },
    { label_key: `${LINE}iva_amount`, number: iva },
  ],
});

const PARTIES = [
  text("supplier_name", "Proveedora Ficticia SL"),
  text("supplier_tax_id", "B00000000"),
  text("customer_name", "Cliente Inventado SA"),
  text("customer_tax_id", "A00000000"),
  text("invoice_series", "F"),
  text("invoice_number", "2026-0001"),
  text("invoice_date", "2026-10-15"),
  text("currency", "EUR"),
];

/** The structured page served for an invented UBL invoice with two lines. */
export const STRUCTURED_WITH_LINES = {
  title_key: "application.ledger.evidence.structured.title.xml_ubl",
  facts: [
    ...PARTIES,
    figure("taxable_base", "300.00"),
    figure("iva_amount", "63.00"),
  ],
  lines: [
    lineFacts("Diseño de cartel", "2", "100.00", "200.00", "21", "42.00"),
    lineFacts("Impresión", "1", "100.00", "100.00", "21", "21.00"),
  ],
};

/** The structured page served for an invented Facturae invoice that states
 * no lines. */
export const STRUCTURED_WITHOUT_LINES = {
  title_key: "application.ledger.evidence.structured.title.xml_facturae",
  facts: [
    ...PARTIES,
    figure("taxable_base", "50.00"),
    figure("iva_amount", "10.50"),
  ],
  lines: [],
};

/** The attachment reference a structured sample is stored under. */
export const structuredSampleId = (name: string) =>
  hex64(`structured-sample:${name}`);
