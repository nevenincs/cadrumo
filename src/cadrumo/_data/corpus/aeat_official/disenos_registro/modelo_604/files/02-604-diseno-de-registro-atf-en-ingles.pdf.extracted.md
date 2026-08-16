# Pag. 1

APPENDIX II - LOGICAL DESIGNS TO BE MATCHED BY FILES GENERATED FOR
THE ELECTRONIC FILING OF THE INFORMATIVE APPENDIX TO FORM 604
A.- RECORD TYPE 1: TAX PAYER RECORD.
The identification data of the taxpayer is to be entered together with an overall
summary of the information in the type 2 record.
POSITIONS NATURE DESCRIPTION OF THE FIELDS
1 Numeric TYPE OF RECORD
Constant number '1'.
2-4 Alphabetic FORM FOR THE APPENDIX
“ATF”.
5-8 Numeric FINANCIAL YEAR
The four digits of the tax year to which the appendix
corresponds.
9-17 Alphanumeric NIF/CII OF THE TAXPAYER
Enter the taxpayer's NIF.
This field must be right justified with the final position being
the control character and the positions to the left filled with
zeros in accordance with the rules in the General
Regulation on Tax Management and Audit Actions and
Procedures implementing the common rules for
procedures for applying taxes, approved by Royal Decree
1065/2007, of 27 July (BOE of 5 September).
If no NIF is available, the assigned individual identification
code must be entered.
18-57 Alphanumeric SURNAMES AND NAME OR COMPANY NAME OF
THE TAXPAYER
If the taxpayer is an individual, it must be entered as the
first surname, a space, the second surname, a space and
the full first name, in that order.
For legal persons and entities under the income
apportionment system, the full company name must be
entered, not the shortened form.
This field must not contain a trading name.
1

# Pag. 2

58-107 Blank BLANK
Enter blanks.
108-120 Alphanumeric APPENDIX IDENTIFICATION NUMBER
Enter the identification number for the appendix. It is a
sequential number of which the three first digits
correspond to the ATF code.
121-122 Alphabetic SUPPLEMENTARY OR REPLACEMENT APPENDIX
In the exceptional event of filing a second or subsequent
appendix, one of the following fields must be filled in:
121 SUPPLEMENTARY APPENDIX: A "C" must be
entered if the filing of this appendix is intended to include
records that should have been included in another
appendix filed earlier for the same financial year and
period but were completely omitted from the return.
122 REPLACEMENT APPENDIX: An "S" must be
entered if the purpose of the filing is to cancel and
completely replace a previous appendix for the same
financial year and period. A replacement appendix can
only override one previous appendix.
123-135 Alphanumeric PREVIOUS APPENDIX IDENTIFICATION NUMBER
If a "C" was entered in the "Supplementary Appendix"
field or an "S" in the "Replacement Appendix" field, enter
the identification number corresponding to the appendix it
replaces or supplements.
Alphanumeric field, up to 13 characters.
In all other cases, fill in with ZEROS.
136-137 Numeric PERIOD
State the period to which the appendix corresponds.
Enter the appropriate code from the following list:
"01" - January
"02" - February
"03" - March
"04" - April
"05" - May
"06" - June
"07" - July
"08" - August
2

# Pag. 3

"09" - September
"10" - October
"11" - November
"12" - December
138-154 Numeric TOTAL NUMBER OF TRANSACTIONS DECLARED
Enter the total number of Type 2 records.
155-171 Numeric TOTAL NUMBER OF NON-EXEMPT TAXABLE
TRANSACTIONS INCLUDED IN THE APPENDIX
Enter the number of Type 2 records in which the
"Transaction type: non-exempt or exempt transaction"
field is "S" (position 190 type 2 record) and the
"Correction" field has no content.
(position 325 type 2 record)
172-189 Numeric TOTAL TAXABLE BASE FOR THE NON-EXEMPT
TAXABLE TRANSACTIONS INCLUDED IN THE
APPENDIX
Numeric field with 18 digits.
Without the sign or decimal point, enter the sum of the
Taxable base field (positions 242-259 type 2 record) of all
Type 2 records in which the "Transaction type: non-
exempt or exempt transaction" field is "S "(position 190
type 2 record) and the "Correction" field has no content
(position 325 type 2 record)
This field has two parts:
- 172-187 Integer part of the total taxable base for the
non-exempt taxable transactions included in the
appendix.
- 188-189 Decimal part of the total taxable base for the
non-exempt taxable transactions included in the
appendix.
190-207 Numeric TOTAL LIABILITY FOR THE NON-EXEMPT TAXABLE
TRANSACTIONS INCLUDED IN THE APPENDIX
Numeric field with 18 digits.
Without the sign or decimal point, enter the sum of the
"Tax liability arising from the transaction" (positions 291-
308 type 2 record) of all Type 2 records in which the
"Transaction type: non-exempt or exempt transaction"
field is "S" (position 190 type 2 record) and the
"Correction" field has no content (position 325 type 2
record)
3

# Pag. 4

This field has two parts:
- 190-205 Integer part of the total liability for the non-
exempt taxable transactions included in the appendix.
- 206-207 Decimal part of the total liability for the non-
exempt taxable transactions included in the appendix.
208-224 Numeric TOTAL NUMBER OF EXEMPT TRANSACTIONS
INCLUDED IN THE APPENDIX
Enter the number of Type 2 records in which the
"Transaction type: non-exempt or exempt transaction"
field is "E" (position 190 type 2 record) and the
"Correction" field has no content (position 325 type 2
record)
225-242 Numeric TOTAL AMOUNT OF EXEMPT TRANSACTIONS
INCLUDED IN THE APPENDIX
Numeric field with 18 digits.
Without the sign or decimal point, enter the sum of the
"Acquisition amount of taxable and exempt transactions"
(positions 273-290 type 2 record) of all Type 2 records in
which the "Transaction type: non-exempt or exempt
transaction" field is "E" (position 190 type 2 record) and
the "Correction" field has no content (position 325 type 2
record)
This field has two parts:
- 225-240 Integer part of the total amount of the exempt
transactions included in the appendix.
- 241-242 Decimal part of the total amount of the exempt
transactions included in the appendix.
243-259 Numeric TOTAL NUMBER OF CORRECTIONS
Enter the number of Type 2 records in which the
"Corrections" field is "X" (position 325 type 2 record)
260-278 Alphanumeric TOTAL TAXABLE BASE/AMOUNT OF THE
CORRECTIONS.
Alphanumeric field with 19 characters.
Enter the sum of the amounts (with no decimal point) in
the "Result of the T.B./amount correction) field (positions
387-405 corresponding to the type 2 record) of all Type 2
4

# Pag. 5

records in which the "Corrections" field is "X" (position
325 Type 2 register).
This field is in two parts:
260: SIGN:
Alphabetic field to be filled in when the result of the
transaction referred to above is less than 0 (zero); in this case,
enter an "N". In all other cases, the field will be blank.
261-278 AMOUNT Numeric field with 18 digits.
Enter the amount resulting from the transactions
referred to above.
This field has two parts:
- 261-276 Integer part of the total taxable base for the
corrections.
- 277-278 Decimal part of the total taxable base for the
corrections.
279-296 Alphanumeric LIABILITY RESULTING FROM THE CORRECTIONS.
Alphanumeric field with 18 characters.
Enter the sum of the quantities (with no decimal
point) shown in the AMOUNT OF THE CORRECTION
(LIABILITY) fields (positions 368 to 386 corresponding to
the type 2 record) of all Type 2 records in which the
"Corrections" field is "X" (position 325 Type 2 record).
This field is in two parts:
279 SIGN:
Alphabetic field to be filled in when the result of the sum referred
to above is less than 0 (zero); in this case, enter an "N". In all other
cases, the content of the field will be a space.
280-296 AMOUNT Numeric field with 17 digits.
This field has two parts:
5

# Pag. 6

- 280-294 Integer part of the liability resulting from the
corrections.
- 295-296 Decimal part of the liability resulting from the
corrections.
297 Alphabetic THEORETICAL SETTLEMENT DATE OPTION
Enter an "X" in the first self-assessment
filed for each calendar year if opting for the
theoretical settlement date.
In all other cases, this field is to be left blank.
298 Alphabetical REVERSAL OF THE THEORETICAL SETTLEMENT
DATE OPTION
Enter an "X" in the first self-assessment
filed for each calendar year if the
theoretical settlement date option is reversed.
299-500 Blank BLANK
6

# Pag. 7

TYPE 2 RECORD: RECORD OF TRANSACTIONS.
In the type 2 record, each transaction must be reported individually in accordance with
the following criteria:
POSITIONS NATURE DESCRIPTION OF THE FIELDS
1 Numeric TYPE OF RECORD
Numeric field with 1 digit
Constant "2" (Two)
2-4 Alphabetic FORM FOR THE APPENDIX
Alphabetic field with three characters.
“ATF”
5-8 Numeric FINANCIAL YEAR
The four digits of the tax year to which the appendix
corresponds.
9-17 Alphanumeric NIF/C.I.I OF THE TAXPAYER
Enter the taxpayer's NIF.
Enter the same NIF as in these same positions (9-17) in
the type 1 record.
If no NIF is available, the assigned individual identification
code must be entered.
18-75 Blank BLANK
76-77 Numeric PERIOD
State the period to which the appendix corresponds.
Enter the appropriate code from the following list:
"01" - January
"02" - February
"03" - March
"04" - April
"05" - May
"06" - June
"07" - July
"08" - August
"09" - September
7

# Pag. 8

"10" - October
"11" - November
"12" - December
78-113 Alphanumeric REFERENCE NUMBER OF THE TRANSACTION OR
UNIQUE IDENTIFIER
Enter the reference number of the transaction or the
unique identifier that allows the taxpayer to identify the
transaction reported and the settlement period.
114 Alphabetic PERSONAL OR THIRD-PARTY TRANSACTION
Enter one of the following codes:
P: If this is a personal transaction by the taxpayer.
A: If the transaction was made by the taxpayer for a third
party.
115 Alphabetic TYPE OF FILING: THROUGH A CENTRAL
SECURITIES DEPOSITARY LOCATED IN SPAIN
If the filing takes place through a central securities
depository located in Spain, the manner in which the filing
is made must be identified.
For these purposes, enter one of the following codes:
A. That provided in Art. 3.a) of Royal Decree 366/2021,
may 25th
B. That provided in Art. 3.b) of Royal Decree 366/2021,
may 25th
C. That provided in Art. 4.1.a) of Royal Decree
366/2021, may 25th
D. That provided in Art. 4.1.b) of Royal Decree
366/2021, may 25th
E. That provided in Art. 4.1.c) of Royal Decree
366/2021, may 25th
F. That provided in Art. 2.2 of Royal Decree 366/2021,
may 25th
116 Alphabetic FILING BY THE TAXPAYER
This field is to be filled in when the filing and deposit are
made by the taxpayer.
When the filing and deposit are made by the taxpayer,
enter an "X". In all other cases, this field is to be left blank.
117-132 Numeric NUMBER OF SECURITIES ACQUIRED
Enter the number of securities acquired in the transaction
declared.
8

# Pag. 9

133-144 Alphanumeric ISIN CODE OF THE SECURITIES ACQUIRED
Enter the ISIN identification code of the securities
acquired.
145-153 Alphanumeric ISSUER NIF
Enter the NIF of the issuer of the securities.
154-173 Alphanumeric ISSUER LEI CODE
Enter the LEI code of the issuer of the securities.
174-181 Numeric SETTLEMENT / REGISTRATION DATE
Enter the theoretical settlement date if you exercised the
option for that date, or the record entry date if you did not
exercise the option.
174-177 Numeric Year
178-179 Numeric Month
180-181 Numeric Day
182-189 Numeric EXECUTION DATE
Execution date. Only to be entered if the rule for
determining the taxable base is that provided for in Art.
5.3. of the Tax Act.
182-185 Numeric Year
186-187 Numeric Month
188-189 Numeric Day
190 Alphabetic TRANSACTION TYPE: EXEMPT OR NON-EXEMPT
TRANSACTION
Enter the transaction type using one of the following two
codes:
S: Non-exempt taxable transaction.
E: Exempt taxable transaction.
191 Alphabetic METHODS OF DETERMINING THE TAXABLE BASE
FOR NON-EXEMPT TAXABLE TRANSACTIONS
For non-exempt taxable transactions, enter the
corresponding code using the method of determining the
taxable base provided for in Art. 5 of Law 5/2020, of 15
October, on the Tax on Financial Transactions:
A: Enter this code when the taxable base consists of the
amount of the consideration, excluding the transaction
costs arising from market infrastructure prices, brokerage
commissions, and any other expenses associated with
the transaction. (Article 5.1 of the Financial Transactions
Tax Law).
9

# Pag. 10

B: Enter this code when the taxable base consists of the
value corresponding to the close of the most relevant
regulated market for the settlement of the security in
question on the last trading day prior to the transaction.
(Article 5.1 of the Financial Transactions Tax Law).
C: When the acquisition of securities comes from
convertible or exchangeable bonds or obligations or from
other marketable securities that give rise to the
acquisition, the taxable base will be the value established
in the issue document for these securities. (Article 5.2.a)
of the Financial Transactions Tax Law).
D: When the acquisition comes from the execution or
settlement of options or other derivative financial
instruments that grant a right to acquire or transfer
securities liable to tax, the taxable base will be the
exercise price set in the contract. (Article 5.2.b) of the
Financial Transactions Tax Law).
E: When the acquisition comes from a derivative
instrument that constitutes a forward deal, the taxable
base will be the agreed price, unless that derivative is
traded on a regulated market, in which case the taxable
base will be the delivery price that acquisition must have
at maturity. (Article 5.2.c) of the Financial Transactions
Tax Law).
F: When the acquisition comes from the settlement of a
financial contract defined in paragraph four of Art. 2.1. of
Order EHA/3537/2005, of 10 November, which
implements Art. 27.4 of Law 24/1988, of 28 July, on the
Stock Market; the taxable base will be the value
corresponding to the closing of the most relevant
regulated market for the liquidity of the security in
question on the last trading day prior to the transaction.
(Article 5.2.d) of the Financial Transactions Tax Law).
G: In the case of intra-day transactions provided for in
Article 5.3 of the Financial Transactions Tax Law, the
taxable base will be that established in this same Article
for these cases.
192-207 Numeric NUMBER OF SECURITIES TRANSMITTED
This field only needs to be filled in when the "METHODS
OF DETERMINING THE TAXABLE BASE FOR NON-
EXEMPT TAXABLE TRANSACTIONS" field (position 191
Type 2 record) has the value "G".
In this field, enter the number of securities transmitted in
the intraday transactions declared.
10

# Pag. 11

208-223 Numeric NET SECURITIES ACQUIRED
This field only needs to be filled in when the "METHODS
OF DETERMINING THE TAXABLE BASE FOR NON-
EXEMPT TAXABLE TRANSACTIONS" field (position 191
Type 2 record) has the value "G".
Enter the difference between "NUMBER OF SECURITIES
ACQUIRED" (positions 117-132) and "NUMBER OF
SECURITIES TRANSMITTED" (positions 192-207).
224-241 Numeric TOTAL AMOUNT OF ACQUISITIONS
This field only needs to be filled in when the "METHODS
OF DETERMINING THE TAXABLE BASE FOR NON-
EXEMPT TAXABLE TRANSACTIONS" field (position 191
Type 2 record) has the value "G".
Enter the amount of the acquisitions of the securities
acquired entered in positions (117-132).
The amounts must be entered in EUROS.
This field has two parts:
224-239 Integer part of the total amount of the
acquisitions. If none, enter zeros.
240-241 Decimal part of the total amount of the
acquisitions. If none, enter zeros.
242-259 Numeric TAXABLE BASE OF THE DECLARED NON-EXEMPT
TAXABLE TRANSACTION
Enter the amount of the taxable base for the non-exempt
taxable transaction declared in accordance with the
appropriate method given in Art. 5 of the Tax on Financial
Transactions Act.
The amounts must be entered in EUROS.
This field has two parts:
242-257 Integer part of the taxable base amount. If none,
enter zeros.
258-259 Decimal part of the taxable base amount. If
none, enter zeros.
260-272 Alphanumeric APPLICABLE EXEMPTION EVENTS
For exempt taxable transactions, enter the exemption
event or events applicable to the transaction in
accordance with the provisions of Art. 3 of Law 5/2020, of
15 October, on the Tax on Financial Transactions, using
the following positions and codes:
11

# Pag. 12

260 Alphabetic A: exemption Article 3.1.a) of Law
5/2020, of 15 October, on the Tax on
Financial Transactions.
261 Alphabetic B: exemption 3.1.b) of Law 5/2020, of
15 October, on the Tax on Financial
Transactions.
262 Alphabetic C: exemption 3.1.c) of Law 5/2020, of
15 October, on the Tax on Financial
Transactions.
263 Alphabetic D: exemption 3.1.d) of Law 5/2020, of
15 October, on the Tax on Financial
Transactions.
264 Alphabetic E: exemption 3.1.e) of Law 5/2020, of
15 October, on the Tax on Financial
Transactions.
265 Alphabetic F: exemption 3.1.f) of Law 5/2020, of
15 October, on the Tax on Financial
Transactions.
266 Alphabetic G: exemption Article 3.1.g) of Law
5/2020, of 15 October, on the Tax on
Financial Transactions.
267 Alphabetic H: exemption 3.1.h) of Law 5/2020 of
15 October, on the Tax on Financial
Transactions.
268 Alphabetic I: exemption 3.1.i) of Law 5/2020, of 15
October, on the Tax on Financial
Transactions.
269 Alphabetic J: exemption 3.1.j) of Law 5/2020, of
15 October, on the Tax on Financial
Transactions.
270 Alphabetic K: exemption 3.1.k) of Law 5/2020, of
15 October, on the Tax on Financial
Transactions.
271 Alphabetic L: exemption Article 3.1.l) of Law
5/2020, of 15 October, on the Tax on
Financial Transactions.
272 Alphabetic M: Other exemptions. When using this
code, it is required to indicate the
exemption applied in the "Description"
field (positions 406-449 type 2 record).
273-290 Numeric ACQUISITION AMOUNT OF EXEMPT TAXABLE
TRANSACTIONS
12

# Pag. 13

Enter the amount of the taxable base of the reported
exempt taxable transaction.
Only to be filled in if the "Transaction type: exempt or non-
exempt transaction" field (position 190 type 2 record) is
"E".
The amounts must be entered in EUROS.
This field has two parts:
273-288 Integer part of the amount of the exempt taxable
transactions. If none, enter zeros.
289-290 Decimal part of the amount of the exempt
taxable transactions. If none, enter zeros.
291-308 Numeric TAX LIABILITY RESULTING FROM THE
TRANSACTION DECLARED
Enter the amount of the tax liability of the exempt taxable
transaction declared.
Only to be completed it the "Transaction type: exempt or
non-exempt transaction" field (position 190 type 2 record)
is "S".
The amounts must be entered in EUROS.
This field has two parts:
291-306 Integer part of the tax instalment amount. If
none, enter zeros.
307-308 Decimal part of the tax instalment amount. If
none, enter zeros.
309-316 Numeric DATE OF COMMUNICATING THE INFORMATION TO
THE SCD
A. Enter the date on which the taxpayer communicated
the information established in Art. 5.2 of Royal Decree
366/2021, may 25th, implementing the procedure for
the filing and deposit of self-assessments for the Tax on
Financial Transactions, to the central securities
depository.
309-312 Numeric Year
313-314 Numeric Month
315-316 Numeric Day
317-324 Numeric TAXPAYER'S PAYMENT DATE
Enter the date for the taxpayer's payment to the
participating entity in the central securities depository.
13

# Pag. 14

Not to be completed if the taxpayer has the status of a
participating entity in a central securities depository
established in Spain.
317-320 Numeric Year
321-322 Numeric Month
323-324 Numeric Day
A. 325 Alphabetic CORRECTION.
This field is to be filled in when the record
corresponds to a correction pursuant to Art. 9 of Royal
Decree 366/2021, may 25th
When the record corresponds to a correction, enter an
"X". In all other cases, this field is to be left blank.
326-329 Numeric FINANCIAL YEAR OF THE CORRECTED
TRANSACTION.
The four numbers of the fiscal year in which the
transaction to be corrected was filed.
330-331 Numeric PERIOD OF THE TRANSACTION TO BE CORRECTED.
Enter the period in which the transaction to be corrected
was declared.
.
Enter the appropriate code from the following list:
"01" - January
"02" - February
"03" - March
"04" - April
"05" - May
"06" - June
"07" - July
"08" - August
"09" - September
"10" - October
"11" - November
14

# Pag. 15

"12" - December
332-349 Numeric CORRECTED TB/CORRECTED AMOUNT.
Enter the amount of the taxable base or the
exempt transaction resulting from the correction
in accordance with Article 9 of Royal Decree 366/2021,
The amounts must be entered in EUROS.
This field is in two parts:
332-347 Integer part of the amount of the corrected
taxable base. If none, enter zeros.
348-349 Decimal part of the amount of the corrected
taxable base. If none, enter zeros.
A. 350-367 Numeric CORRECTED TAX
LIABILITY.
Enter the amount of the tax liability resulting from
the correction pursuant to Art. 9 of Royal Decree
366/2021, may 25th
The amounts must be entered in EUROS.
This field has two parts:
350-365 Integer part of the amount of the corrected tax
liability. If none, enter zeros.
366-367 Decimal part of the amount of the corrected tax
liability. If none, enter zeros.
368-386 Alphanumeric AMOUNT OF THE CORRECTION. (LIABILITY)
This field has two parts:
368 SIGN: alpha field. Enter an N when the
amount of the correction is less than zero. In all other
cases, the field is to be left blank.
369-386 AMOUNT: Numeric field with 18
digits.
15

# Pag. 16

Enter the difference between the "Corrected tax liability"
field (positions 350-367 type 2 record) and the "Tax liability resulting from the transaction
declared" field (positions 291-308 type 2 record). If none,
enter zeros.
The amounts must be entered in EUROS.
This field has two parts:
369-384 Integer part of the amount of the correction. If
none, enter zeros.
385-386 Decimal part of the amount of the correction. If
none, enter zeros.
387-405 Alphanumeric RESULT OF THE CORRECTION (TB/AMOUNT)
This field has two parts:
387 SIGN: alpha field. Enter an N when the
amount of the correction is less than zero. In all other
cases, the field is to be left blank.
388-405 AMOUNT: Numeric field with 18
digits.
Enter the difference between the
"Corrected TB/Corrected amount" field (positions 332-349
type 2 record) and the "TB of the declared non-exempt
taxable transaction" field (positions 242-259 type 2
record). If none, it will show zeros.
The amounts must be entered in EUROS.
This field has two parts:
388-403 Integer part of the amount of the correction. If
none, enter zeros.
16

# Pag. 17

404-405 Decimal part of the amount of the correction. If
none, enter zeros.
406-449 Alphanumeric DESCRIPTION
Free text field.
450-500 Blank BLANK
17