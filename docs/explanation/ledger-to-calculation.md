# From ledger to tax return: how calculations work

Use this page to understand how your local records become official tax return figures, why the system is designed this way, and how it helps you explain your numbers. For a step-by-step guide to producing a file, see the [Quickstart](../how-to/quickstart.md).

Spanish tax compliance requires absolute clarity. When you submit a tax return, you must be able to justify every single number. If a tax inspector reviews your filing, you need to show the exact transaction history and legal rules behind each box.

The application uses a local tax rules engine to help you organize your records, calculate your boxes, and keep a clear audit trail on your own computer.

---

## High-level data flow

Your financial records move through a simple, one-way path to become a tax return draft:

1. **Raw bank transactions**: These are imported statements of money moving in or out. At this stage, they are just amounts and dates with no tax meaning.
2. **Classified entries**: These are transactions you have reviewed. You assign them to a tax category (such as customer sales or office expenses) and adjust them for business use.
3. **Calculated boxes**: The tax engine reads your classified entries, applies official tax rules and math formulas, and produces the final values for the numbered boxes (*casillas*) on the tax form.

---

## Filing periods and date limits

A tax return is prepared for a specific year and period. The tool maps period tokens to calendar date ranges:

- **Quarters**: Period tokens like `1T` (first quarter) convert to January 1 through March 31, and `4T` (fourth quarter) converts to October 1 through December 31.
- **Months**: Period tokens like `01` (January) through `12` (December) convert to the corresponding calendar months.

When you run a calculation, the engine selects transactions whose operation date falls within the start and end dates of the target period. The operation date is the date when the money actually moved (the bank value date) or when the bank recorded the entry (the booked date).

---

## Tax rules and box mapping

Official Spanish tax forms consist of numbered boxes (*casillas*). The application manages these using a local database of tax rules compiled from official state layout designs. 

The calculation process uses two main mechanisms:

- **Category mapping**: The rules specify how transaction categories connect to form boxes. For example, if you classify a purchase under office supplies, the rules route the amount to the specific box designated for business expenses.
- **Formulas**: The rules define the math relationships between boxes. For example, the engine automatically subtracts total deductible expenses from total income to calculate net profit, and applies the tax rate to find the final tax due.

Every calculated box carries a detailed record of the specific article in the tax law or the official manual that establishes the rule, plus the ID of the formula used. This record stays attached to the data through every step.

---

## Proportionality and mixed-use expenses

For expenses that serve both your business and your personal life (such as a phone bill or home internet), you cannot deduct the full cost. The system supports three ways to allocate mixed-use expenses:

1. **Transaction-level percentage**: You specify the business percentage (such as 50 percent) directly when classifying a single transaction.
2. **Category-level percentage**: You set a default business percentage for a whole category of expenses.
3. **Census-derived ratios**: If you link your official tax registration details (from your Modelo 036 censo), the engine can calculate a business ratio automatically. For example, it can use the square meters of your registered home office to calculate the deductible portion of your utility bills.

---

## Manual values and carry-forwards

Some numbers on a tax return cannot be derived from bank transactions. These are handled separately:

- **Manual inputs**: Certain boxes require direct entry (such as a personal tax reduction or a special regional deduction). You supply these values directly when running the calculation.
- **Carry-forwards**: If you have an unused tax credit from a previous quarter (such as negative VAT/IVA to compensate), the system retrieves the balance from your local filing history or a local tax wallet, carrying it forward to the new period automatically.

---

## Related guides

- [Quickstart](../how-to/quickstart.md) - the shortest path to an exported file.
- [Set up your taxpayer profile](../how-to/profile-setup.md) - how to configure taxpayer details and activities.
- [Work with Transactions](../how-to/import-bank-statements.md) - how to import and manage bank statements.
- [Classify transactions](../how-to/classify-transactions.md) - how to assign categories and tax fields.
- [Glossary](../glossary.md) - definitions for Spanish tax terms.
