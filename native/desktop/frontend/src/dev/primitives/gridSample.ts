// Made-up rows for the data grid's catalogue entry and its browser tests.
// Nothing here is anyone's data: names, amounts and dates come from a fixed
// seed, so every run draws the same grid.

export type SampleRow = {
  id: string;
  date: string;
  description: string;
  counterparty: string;
  category: string | null;
  amount: number;
  locked: boolean;
  refused: boolean;
  changed: boolean;
};

export const SAMPLE_CATEGORIES = [
  { value: "office", label: "Office supplies", group: "Running costs" },
  { value: "rent", label: "Rent", group: "Running costs" },
  { value: "power", label: "Electricity", group: "Running costs" },
  { value: "travel", label: "Travel", group: "Work" },
  { value: "meals", label: "Meals with clients", group: "Work" },
  {
    value: "training",
    label: "Training",
    group: "Work",
    disabled: true,
    reason: "Not available for this period",
  },
  { value: "sales", label: "Sales", group: "Income" },
  { value: "fees", label: "Fees received", group: "Income" },
] as const;

const WORDS = [
  "Paper and toner",
  "Monthly rent for the studio on the second floor, including the shared storage room",
  "Train to the client meeting",
  "Invoice 42 paid",
  "Electricity, summer tariff",
  "Lunch with a client",
  "Course on bookkeeping",
  "Refund of a deposit",
];
const PARTIES = [
  "Northwind Supplies",
  "Contoso Rentals",
  "Fabrikam Rail",
  "Tailspin Clients",
  "Litware Power",
  "Adventure Works",
];

function seeded(seed: number) {
  let state = seed;
  return () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    return state / 2147483648;
  };
}

/** `count` rows, in date order. */
export function sampleRows(count: number): SampleRow[] {
  const random = seeded(7);
  const rows: SampleRow[] = [];
  for (let at = 0; at < count; at += 1) {
    const day = 1 + (at % 28);
    const month = 1 + (Math.floor(at / 28) % 12);
    const category = SAMPLE_CATEGORIES[Math.floor(random() * 8)];
    rows.push({
      id: `m${at + 1}`,
      date: `2026-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      description: WORDS[at % WORDS.length] ?? "",
      counterparty: PARTIES[at % PARTIES.length] ?? "",
      category: at % 5 === 4 ? null : (category?.value ?? null),
      amount: Math.round((random() * 2000 - 600) * 100) / 100,
      locked: at % 11 === 10,
      refused: at % 13 === 12,
      changed: at % 7 === 6,
    });
  }
  return rows;
}

export function categoryLabel(value: string | null): string {
  return (
    SAMPLE_CATEGORIES.find((category) => category.value === value)?.label ??
    "Unclassified"
  );
}
