"""Precisely reviewed casilla wording equivalences and contextual renderings."""

from __future__ import annotations

from typing import Final

#: Per (locale, modelo, translation), Spanish wordings a reviewer found equivalent, so one
#: translation is correct for all of them: an abbreviation, a typo, punctuation or a synonym.
#: Never widened by modelo or prefix; each entry names the difference the reviewer saw.
#: Per locale, composed segments a reviewer found to need more than one rendering, with the
#: reason the context forces it. Each entry names one segment; never a modelo or a prefix.
#: Per locale, renderings a reviewer found to state two Spanish segments correctly, with the
#: difference seen: an official typo, an abbreviation, or two spellings of one province.
REVIEWED_SHARED_SEGMENTS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "Acquirer": ("Adquirente and the official misspelling Adquiriente"),
        "Address": ("Domicilio, and the bilingual Domicilio / Address of the same box"),
        "Adjustments for the tax year": ("Correcciones and the official misspelling Correciones"),
        (
            "Amortization of intangible fixed assets and goodwill (art. 12.2 LIS) and amortization "
            "under Transitional Provision 13.1 LIS"
        ): ("one edition cites the transitional provision as art. DT 13a.1, the other as DT 13a.1"),
        (
            "Amount excluded for capital or equity increases by set-off of claims not integrated into "
            "the tax base (art. 17.2 LIS)"
        ): ("no integrado en la base imponible, restated as que no se integren por aplicacion del art. 17.2"),
        "Amount payable": ("A ingresar states what the box holds and Importe a ingresar names its amount, for one box"),
        "Bizkaia": ("the Basque and Castilian spellings of one province"),
        "Chartered provincial councils and Navarre": ("D. Forales abbreviates Diputaciones Forales"),
        "Country code": ("Codigo de pais, abbreviated in one edition and given with its English gloss in another"),
        "Credit of R&D&I deductions due to insufficient tax liability": (
            "insuf. cuota abbreviates por insuficiencia de cuota"
        ),
        "Decreases": ("Disminuciones and the official misspellings Diminuciones and Disminuciones with a stray accent"),
        "Deductible VAT on intra-Community acquisitions of current goods": (
            "adquisiciones intracomunitarias corrientes abbreviates the same box"
        ),
        "Deduction still outstanding": (
            "pendiente de aplicacion and pendiente de aplicar state one thing, a deduction not yet taken"
        ),
        "Gipuzkoa": ("the Basque and Castilian spellings of one province"),
        "Income and expenses recognized in equity": (
            "imputados al patrimonio neto, restated as reconocidos en patrimonio neto"
        ),
        "Legal name": ("razon social and denominacion social name one thing, the registered name of a company"),
        (
            "Part integrated into the tax base at liability level for debt-relief or deferral "
            "arrangements (cooperatives only)"
        ): ("op. abbreviates operaciones"),
        "Postcode": ("C. Postal abbreviates Codigo postal, which one edition also capitalises"),
        "Postcode (ZIP)": ("C. Postal abbreviates Codigo postal, whose ZIP note one edition brackets"),
        "Province, region or state": (
            "the same wording, its parts separated by slashes in one edition and by words in the other"
        ),
        "Reduction of income from certain intangible assets (art. 23 LIS)": (
            "ingresos, restated as rentas for the same art. 23 LIS reduction"
        ),
        "Result of the previous return (supplementary)": ("complementaria and the official plural complementarias"),
        "Street name": ("Nombre de la via, written out as via publica and capitalised in other editions"),
        "Surnames and first name or company name": (
            "razon social and denominacion social name one thing, the registered name of a company"
        ),
        "Surnames or company name": (
            "Denominacion Social and Razon social, with the official o accented in one edition"
        ),
        "Taxation by territory": ("por razon de territorio, shortened to por territorio"),
    },
    "ca": {
        "1r fraccionament": ("1er and 1o spell the same first instalment"),
        "Adquirent": ("Adquirente and the official misspelling Adquiriente"),
        "Altres 1a": ("1a and the ordinal 1a written with a superscript"),
        "Altres 2a": ("2a and the ordinal 2a written with a superscript"),
        "Altres 3a": ("3a and the ordinal 3a written with a superscript"),
        "Altres 4a": ("4a and the ordinal 4a written with a superscript"),
        "Altres 5a": ("5a and the ordinal 5a written with a superscript"),
        "Altres diferències d'imputació temporal d'ingressos i despeses (art. 11 LIS)": (
            "imputac. abbreviates imputacion"
        ),
        "Codi de país": ("Codigo de pais, abbreviated in one edition and given with its English gloss in another"),
        "Correccions de l'exercici": ("Correcciones and the official misspelling Correciones"),
        "Correu electrònic": ("E-mail and Email spell one word"),
        "Diputacions Forals i Navarra": ("D. Forales abbreviates Diputaciones Forales"),
        "Disminucions": (
            "Disminuciones and the official misspellings Diminuciones and Disminuciones with a stray accent"
        ),
        "Domicili": ("Domicilio, and the bilingual Domicilio / Address of the same box"),
        "IVA deduïble en operacions interiors de béns d'inversió": ("ops abbreviates operaciones"),
        (
            "Import exclòs per operacions d'augment de capital o fons propis per compensació de crèdits "
            "no integrat en la base imposable (art. 17.2 LIS)"
        ): ("no integrado en la base imponible, restated as que no se integren por aplicacion del art. 17.2"),
        (
            "Part integrada en la base imposable a nivell de quota per operacions de quitament o espera "
            "(només cooperatives)"
        ): ("op. abbreviates operaciones"),
    },
    "hu": {
        "1. részletfizetés": ("1er fraccionamiento and 1er. pago fraccionado name the same first instalment"),
        "A korábbi bevallás eredménye (kiegészítő)": ("complementaria and the official plural complementarias"),
        "Adóalap": ("Base is the column heading for the Base imponible the row states"),
        "Az adóalapba adóösszeg szintjén beszámított rész adósságelengedési ügyletek után (csak szövetkezetek)": (
            "op. abbreviates operaciones"
        ),
        "Bizkaia": ("the Basque and Castilian spellings of one province"),
        "Csökkentett adóalap": (
            "base liquidable is the base imponible after its reductions, which the other names directly"
        ),
        "Csökkenések": (
            "Disminuciones and the official misspellings Diminuciones and Disminuciones with a stray accent"
        ),
        "Cégnév": ("razon social and denominacion social name one thing, the registered name of a company"),
        "Cím": ("Domicilio, and the bilingual Domicilio / Address of the same box"),
        "E-mail": ("E-mail and Email spell one word"),
        "E-mail cím": ("Correo electronico, given as Direccion de correo electronico in another edition"),
        "Egyéb 1.": ("1a and the ordinal 1a written with a superscript"),
        "Egyéb 2.": ("2a and the ordinal 2a written with a superscript"),
        "Egyéb 3.": ("3a and the ordinal 3a written with a superscript"),
        "Egyéb 4.": ("4a and the ordinal 4a written with a superscript"),
        "Egyéb 5.": ("5a and the ordinal 5a written with a superscript"),
        "Fizetendő összeg": (
            "A ingresar states what the box holds and Importe a ingresar names its amount, for one box"
        ),
        "Gipuzkoa": ("the Basque and Castilian spellings of one province"),
        "Helység": ("Localidad, written Localidad/Poblacion in another edition"),
        "Irányítószám": ("C. Postal abbreviates Codigo postal, which one edition also capitalises"),
        "Irányítószám (ZIP)": ("C. Postal abbreviates Codigo postal, whose ZIP note one edition brackets"),
        "K+F+i levonások jóváírása elégtelen adókötelezettség miatt": (
            "insuf. cuota abbreviates por insuficiencia de cuota"
        ),
        (
            "Követelés-beszámítással történő tőke- vagy sajáttőke-emelés miatt kizárt, az adóalapba be "
            "nem számított összeg (LIS 17.2. cikk)"
        ): ("no integrado en la base imponible, restated as que no se integren por aplicacion del art. 17.2"),
        "Közterület neve": ("Nombre de la via, written out as via publica and capitalised in other editions"),
        "Külföldi cím": ("Direccion en el extranjero and Domicilio extranjero name one address"),
        "Külön jogállású tartományi tanácsok és Navarra": ("D. Forales abbreviates Diputaciones Forales"),
        "Még érvényesíthető levonás": (
            "pendiente de aplicacion and pendiente de aplicar state one thing, a deduction not yet taken"
        ),
        "Országkód": ("Codigo de pais, abbreviated in one edition and given with its English gloss in another"),
        "Saját tőkében elszámolt bevételek és ráfordítások": (
            "imputados al patrimonio neto, restated as reconocidos en patrimonio neto"
        ),
        "Tartomány, régió vagy állam": (
            "the same wording, its parts separated by slashes in one edition and by words in the other"
        ),
        "Vezetéknév vagy cégnév": ("Denominacion Social and Razon social, with the official o accented in one edition"),
        "Vezetéknév és utónév vagy cégnév": (
            "razon social and denominacion social name one thing, the registered name of a company"
        ),
        "Évi korrekciók": ("Correcciones and the official misspelling Correciones"),
    },
}


REVIEWED_SEGMENT_RENDERINGS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "Cuota": "the amount of the IVA, of the recargo or of a fee, named by the label it sits in",
    },
    "ca": {
        "NIF": "the acronym as a field tag, and the number named in full where the label stands alone",
    },
}


REVIEWED_SHARED_TRANSLATIONS: Final[dict[tuple[str, str, str], str]] = {
    (
        "ca",
        "100",
        "Introduïu el nombre d'anys de permanència fins al 31-12-1994, si escau.",
    ): "the later edition drops del elemento patrimonial from the same sentence",
    (
        "hu",
        "100",
        "Adja meg a 2022-ben keletkezett, még alkalmazásra váró összeget.",
    ): "pendiente de aplicacion, written y pendiente de aplicacion in another edition",
    (
        "hu",
        "100",
        "Adja meg a 2023-ban keletkezett, még alkalmazásra váró összeget.",
    ): "pendiente de aplicacion, written y pendiente de aplicacion in another edition",
    (
        "hu",
        "100",
        "Adja meg a 2024-ben keletkezett, még alkalmazásra váró összeget.",
    ): "pendiente de aplicacion, written y pendiente de aplicacion in another edition",
    (
        "hu",
        "100",
        "Adja meg a 65 év feletti és/vagy fogyatékossággal élő személyek nem díjazott befogadása utáni levonást.",
    ): "the editions differ only in how they join the two conditions",
    ("hu", "100", "Adja meg a jármű rendszámát."): "el numero de matricula del vehiculo, shortened to la matricula",
    (
        "hu",
        "100",
        "Tüntesse fel annak az adózónak a NIF azonosítóját, aki átruházta a levonáshoz való jogot.",
    ): "un contribuyente and el contribuyente name the same person",
    (
        "ca",
        "100",
        "IVA suportat (per exemple, recàrrec d'equivalència i/o compensació d'agricultura, ramaderia i pesca)",
    ): "one edition misspells por ejemplo as por ejermplo",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.6. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.8. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az "
        "összeget vigye át a B.6. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az "
        "összeget vigye át a B.8. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe "
        "történő befektetés miatt (ezt az összeget vigye át a B.7. melléklet [1136] rovatába)",
    ): "acciones o participaciones sociales, written with y in another edition",
    (
        "hu",
        "100",
        "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe "
        "történő befektetés miatt (ezt az összeget vigye át a B.8. melléklet [1136] rovatába)",
    ): "acciones o participaciones sociales, written with y in another edition",
    (
        "en",
        "100",
        "For illness expenses",
    ): "number (gasto / gastos)",
    (
        "en",
        "100",
        "Amount applied in the tax year",
    ): "synonym (aplicado / que se aplica)",
    (
        "hu",
        "100",
        "Gyermek születése vagy örökbefogadása után",
    ): "number (un hijo / hijos)",
    (
        "en",
        "100",
        "Cadastral reference (property 1)",
    ): "punctuation/synonym (inmueble / vivienda, missing space before the parenthesis)",
    (
        "ca",
        "100",
        "Fill/Filla 1 (*): NIF/NIE",
    ): "synonym (word order variant of the same field)",
    (
        "ca",
        "100",
        "Fill/Filla 2 (*): NIF/NIE",
    ): "synonym (word order variant of the same field)",
    (
        "ca",
        "100",
        (
            "Per arrendament d'habitatge habitual per contribuents menors de 36 anys (import de la "
            "casella [1130] de l'annex B.9)"
        ),
    ): "punctuation (preposition de / en)",
    (
        "ca",
        "100",
        "Per obligació de presentar la declaració de l'IRPF per raó de tenir més d'un pagador",
    ): "synonym (en razon de / por razon de)",
    (
        "ca",
        "100",
        "Referència cadastral 1",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "100",
        "Referència cadastral 2",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "100",
        "Referència cadastral 3",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "100",
        "Referència cadastral 4",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "202",
        (
            "Informació addicional (5) - Import de renda exempta de les entitats que apliquen el règim "
            "fiscal especial del Cap. XIV del Tít. VII LIS"
        ),
    ): "punctuation/typo (de/del, Tit./Tit.)",
    (
        "ca",
        "202",
        (
            "Informació addicional (5) - Import exclòs per operacions d'augment de capital o fons "
            "propis per compensació de crèdits no integrat en la base imposable (art. 17.2 LIS)"
        ),
    ): "synonym (rewording, same concept)",
    (
        "ca",
        "202",
        (
            "Informació addicional (5) - Part integrada en la base imposable a nivell de quota per "
            "operacions de quitament o espera (només cooperatives)"
        ),
    ): "abbreviation (op. / operaciones)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 1a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 2a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 3a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 4a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 5a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 1a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 2a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 3a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 4a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 5a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "en",
        "100",
        "Cadastral reference 1",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "Cadastral reference 2",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "Cadastral reference 3",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "Cadastral reference 4",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "For a large family",
    ): "synonym (por / para)",
    (
        "en",
        "100",
        "For donations for ecological purposes",
    ): "synonym (donaciones / donativos)",
    (
        "en",
        "100",
        "For education expenses",
    ): "synonym (gastos educativos / gastos de educacion)",
    (
        "en",
        "100",
        (
            "For investment in shares of entities listed on the growth-companies segment of the "
            "Alternative Stock Market (amount from box [1142] of Annex B.11)"
        ),
    ): "synonym (Bursatil / Bolsista)",
    (
        "en",
        "100",
        (
            "For investment in the acquisition of shares or company units of newly or recently created "
            "entities (amount from box [1136] of Annex B.11)"
        ),
    ): "punctuation/typo (o/y conjunction, stray parenthesis, capitalization)",
    (
        "en",
        "100",
        "For rental of the habitual residence (amount from box [1130] of annex B.9)",
    ): "synonym (arrendamiento / alquiler)",
    (
        "en",
        "100",
        "For rental of the habitual residence (this amount is transferred to box [1130] of annex B.9)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "en",
        "100",
        ("For rental of the habitual residence for taxpayers under 36 years old (amount from box [1130] of annex B.9)"),
    ): "punctuation (preposition de / en)",
    (
        "en",
        "100",
        "For single-parent families",
    ): "synonym (por / para)",
    (
        "en",
        "100",
        "For taxpayers with a disability",
    ): "synonym (con discapacidad / afectados por discapacidad)",
    (
        "en",
        "100",
        "For the international adoption of children",
    ): "synonym (rewording, same concept)",
    (
        "en",
        "100",
        "For the lease of a primary residence (this amount is carried to box [1130] of Annex B.11)",
    ): "punctuation (added article el)",
    (
        "en",
        "100",
        (
            "For the lease of a primary residence for taxpayers under 36 years old (amount from box "
            "[1130] of Annex B.11)"
        ),
    ): "punctuation (preposition de / en)",
    (
        "en",
        "100",
        (
            "For the lease of a primary residence linked to certain debt-for-property settlement "
            "transactions (amount from box [1170] of Annex B.12)"
        ),
    ): "punctuation (added article el)",
    (
        "en",
        "100",
        "For the purchase of school supplies",
    ): "synonym (compra / adquisicion)",
    (
        "en",
        "100",
        "For the purchase of textbooks and school supplies",
    ): "punctuation (added article la)",
    (
        "en",
        "100",
        'If you do not have a cadastral reference, mark this box with an "X"',
    ): "punctuation (quote style)",
    (
        "en",
        "100",
        "Number of days",
    ): "abbreviation (Numero / No)",
    (
        "en",
        "100",
        "Payments on account passed on",
    ): "abbreviation (Ing. / Ingr.)",
    (
        "en",
        "100",
        "Reduction for income from artistic activities obtained exceptionally",
    ): "typo (artisticas / artisticos)",
    (
        "en",
        "100",
        "Social Security contribution account code",
    ): "punctuation (missing de)",
    (
        "en",
        "100",
        "Tax ID (NIF) of entity 1, newly or recently created",
    ): "punctuation (missing de)",
    (
        "en",
        "100",
        "Tax ID (NIF) of entity 2, newly or recently created",
    ): "punctuation (missing de)",
    (
        "en",
        "100",
        "Tax ID number (NIF) of the person with the disability holding the protected estate",
    ): "abbreviation (Numero / No)",
    (
        "en",
        "100",
        "Utilities (electricity, water, gas, telephone and internet)",
    ): "synonym (luz / electricidad)",
    (
        "en",
        "202",
        (
            "Additional information (5) - Amount excluded for capital or equity increases by set-off of"
            " claims not integrated into the tax base (art. 17.2 LIS)"
        ),
    ): "synonym (rewording, same concept)",
    (
        "en",
        "202",
        (
            "Additional information (5) - Amount of exempt income of entities applying the special tax "
            "regime of Chapter XIV of Title VII LIS"
        ),
    ): "punctuation/typo (de/del, Tit./Tit.)",
    (
        "en",
        "202",
        (
            "Additional information (5) - Part integrated into the tax base at liability level for "
            "debt-relief or deferral arrangements (cooperatives only)"
        ),
    ): "abbreviation (op. / operaciones)",
    (
        "en",
        "303",
        "Total accrued VAT amount",
    ): "synonym (short label vs. detailed elaboration of the same total)",
    (
        "hu",
        "100",
        "1. Kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        "1. Új vagy nemrég alapított entitás adóazonosító száma",
    ): "punctuation (missing de)",
    (
        "hu",
        "100",
        "2. Kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        "2. Új vagy nemrég alapított entitás adóazonosító száma",
    ): "punctuation (missing de)",
    (
        "hu",
        "100",
        "3. Kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        "36 év alatti adózók szokásos lakóhelyének bérlése után (a B.9 melléklet [1130] rovatának összege)",
    ): "punctuation (preposition de / en)",
    (
        "hu",
        "100",
        "4. kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        (
            "A 2021. adóévre vonatkozó korábbi önadózásokból vagy közigazgatási adómegállapításokból "
            "származó, befizetendő eredmények"
        ),
    ): "punctuation (added article las)",
    (
        "hu",
        "100",
        (
            "A 2022. adóévre vonatkozó korábbi önadózásokból vagy közigazgatási adómegállapításokból "
            "származó, befizetendő eredmények"
        ),
    ): "punctuation (added article las)",
    (
        "hu",
        "100",
        (
            "A 2023. adóévre vonatkozó korábbi önadózásokból vagy közigazgatási adómegállapításokból "
            "származó, befizetendő eredmények"
        ),
    ): "punctuation (added article las)",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.6. melléklet [1130] casillájába)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.8. melléklet [1130] casillájába)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        (
            "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az összeget "
            "vigye át a B.6. melléklet [1130] casillájába)"
        ),
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        (
            "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az összeget "
            "vigye át a B.8. melléklet [1130] casillájába)"
        ),
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlése után (ez az összeg a B.9 melléklet [1130] rovatába kerül át)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        ("A szokásos lakóingatlan bérbevétele után (ez az összeg átvitelre kerül a B.11 melléklet [1130] rovatába)"),
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        (
            "Az Alternatív Tőzsde terjeszkedő vállalkozási szegmensében jegyzett entitások részvényeibe"
            " történő befektetés után (a B.11 melléklet [1142] rovatának összege)"
        ),
    ): "synonym (Bursatil / Bolsista)",
    (
        "hu",
        "100",
        "Az adóévben alkalmazott összeg",
    ): "synonym (grammar/voice variant, same meaning)",
    (
        "hu",
        "100",
        "Csökkentés kivételes módon szerzett művészi tevékenységekből származó jövedelmek után",
    ): "typo (artisticas / artisticos)",
    (
        "hu",
        "100",
        "Gyermekek nemzetközi örökbefogadása után",
    ): "synonym (rewording, same concept)",
    (
        "hu",
        "100",
        "Járulékfizetési számlakód",
    ): "punctuation (missing de)",
    (
        "hu",
        "100",
        "Napok száma",
    ): "abbreviation (Numero de dias / No de dias)",
    (
        "hu",
        "100",
        "Oktatási kiadások után",
    ): "synonym (gastos educativos / gastos de educacion)",
    (
        "hu",
        "100",
        "Szokásos lakóhely bérlése után (a B.9 melléklet [1130] rovatának összege)",
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        "Szokásos lakóingatlan beszerzése vagy felújítása után vidéki övezetekben",
    ): "punctuation (added article la)",
    (
        "hu",
        "100",
        "Szokásos lakóingatlan bérbevétele után (a B.11 melléklet [1130] rovatának összege)",
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        "Tankönyvek és iskolai felszerelés beszerzése után",
    ): "punctuation (added article la)",
    (
        "hu",
        "100",
        "Életjáradékokba történő újrabefektetés miatt mentesített nyereségek",
    ): "punctuation (preposition de / en)",
    (
        "hu",
        "100",
        "Ökológiai célú adományok után",
    ): "synonym (donaciones / donativos)",
    (
        "hu",
        "100",
        (
            "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe történő "
            "befektetés miatt (ezt az összeget vigye át a B.7. melléklet [1136] casillájába)"
        ),
    ): "punctuation/typo (o/y conjunction)",
    (
        "hu",
        "100",
        (
            "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe történő "
            "befektetés miatt (ezt az összeget vigye át a B.8. melléklet [1136] casillájába)"
        ),
    ): "punctuation/typo (o/y conjunction)",
    (
        "hu",
        "202",
        (
            "Kiegészítő információ (5) - A LIS VII. cím XIV. fejezete szerinti különös adórendszert "
            "alkalmazó szervezetek adómentes jövedelme"
        ),
    ): "punctuation/typo (de/del, Tit./Tit.)",
    (
        "hu",
        "202",
        (
            "Kiegészítő információ (5) - Az adóalapba adóösszeg szintjén beszámított rész "
            "adósságelengedési ügyletek után (csak szövetkezetek)"
        ),
    ): "abbreviation (op. / operaciones)",
    (
        "hu",
        "202",
        (
            "Kiegészítő információ (5) - Követelés-beszámítással történő tőke- vagy sajáttőke-emelés "
            "miatt kizárt, az adóalapba be nem számított összeg (LIS 17.2. cikk)"
        ),
    ): "synonym (rewording, same concept)",
    (
        "hu",
        "303",
        "Összes keletkezett ÁFA összeg",
    ): "synonym (short label vs. detailed elaboration of the same total)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 1.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 2.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 3.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 4.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 5.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 1.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 2.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 3.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 4.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 5.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
}


#: Lineages whose Spanish wording changed between editions without changing meaning, so one
#: translation correctly renders every edition. Keyed per (locale, modelo, lineage), each with
#: the reviewer's reason; never widened by modelo or prefix.
REVIEWED_EQUIVALENT_SPANISH: Final[dict[tuple[str, str, str], str]] = {
    **{
        (locale, "202", lineage): "The later edition only spells out abbreviations ('op.', 'Tit.') of the same text."
        for locale in ("ca", "en", "hu")
        for lineage in (
            "importe-excluido-aumento-capital-art-17-2-lis",
            "importe-integrado-cuota-quita-espera-cooperativas",
            "renta-exenta-cap-xiv-tit-vii-lis",
        )
    },
    ("en", "100", "irpf-ed-suministros"): "'Electricity' renders both 'luz' and 'electricidad'.",
    ("ca", "100", "irpf-ed-iva-soportado"): "One edition misspells 'por ejemplo' as 'por ejermplo'.",
}
