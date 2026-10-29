"""Filing periods used to render each export-bearing edition."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from cadrumo.core.period import Period

#: The quarter each Modelo 303 edition is rendered for; each selects exactly that edition.
M303_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2023": Period.from_year_and_code(2023, "1T"),
    "2024-hasta-08-y-2t": Period.from_year_and_code(2024, "1T"),
    "2024-desde-09-y-3t": Period.from_year_and_code(2024, "3T"),
    "2025": Period.from_year_and_code(2025, "1T"),
    "2026-hasta-01-y-1t": Period.from_year_and_code(2026, "1T"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "2T"),
}
#: The annual period each Modelo 189 edition is rendered for.
M189_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 190 edition is rendered for.
M190_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 193 edition is rendered for.
M193_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 232 edition is rendered for.
M232_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    # 2016-2017 is deliberately absent. It was declared here and then withdrawn
    # on evidence: 140 of that edition's generated export fields reference
    # binding ids carrying an offset segment
    # (``modelo-232.page_02.2968-2968.paraiso-valor-12-tipo``) while every
    # binding it declares is offset-free. All 140 resolve once the segment is
    # stripped, and every embedded span agrees exactly with the binding's own
    # declared offset and length, so the segment is pure redundancy -- and the
    # sibling edition settles which spelling is canonical, carrying the same 140
    # fields with none of them. The edition therefore cannot compile, so it
    # cannot render, and its export tree is not regenerated because the edition
    # sits below the supported-filing-years floor. Declaring it would name a
    # render that will not happen.
    "2018-y-siguientes": Period.from_year_and_code(2018, "0A"),
}
#: The annual period each Modelo 345 edition is rendered for.
M345_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025": Period.from_year_and_code(2025, "0A"),
}
M347_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2011-2024": Period.from_year_and_code(2024, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 390 edition is rendered for; 390 files only ``0A``.
M390_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025": Period.from_year_and_code(2025, "0A"),
}
#: The quarter each Modelo 131 edition is rendered for.
M131_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2023": Period.from_year_and_code(2023, "1T"),
    "2024": Period.from_year_and_code(2024, "1T"),
    "2025": Period.from_year_and_code(2025, "1T"),
    "2026": Period.from_year_and_code(2026, "1T"),
}
#: The annual period each Modelo 714 edition is rendered for; 714 files only ``0A``.
M714_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021": Period.from_year_and_code(2021, "0A"),
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025": Period.from_year_and_code(2025, "0A"),
}
#: The month each Modelo 322 edition is rendered for; 322 is a monthly group filer.
M322_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2008-2022": Period.from_year_and_code(2022, "01"),
    "2023": Period.from_year_and_code(2023, "01"),
    "2024-2025": Period.from_year_and_code(2024, "01"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "01"),
}
#: The quarter each Modelo 490 edition is rendered for; the 2022 editions split at 2T.
M490_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021": Period.from_year_and_code(2021, "1T"),
    "2022-1t": Period.from_year_and_code(2022, "1T"),
    "2022-2t-4t": Period.from_year_and_code(2022, "2T"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "1T"),
}
#: The period each Modelo 309 edition is rendered for: 0A wherever the design
#: admits it, and a quarter for the 2004 design, which admits only quarters.
M309_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2004-2015": Period.from_year_and_code(2004, "3T"),
    "2016-2017": Period.from_year_and_code(2016, "0A"),
    "2018-2022": Period.from_year_and_code(2022, "0A"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "0A"),
}
#: The period Modelo 308's one export-bearing edition is rendered for.
M308_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-y-siguientes": Period.from_year_and_code(2022, "0A"),
}
#: The quarter each Modelo 123 edition is rendered for.
M123_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2023": Period.from_year_and_code(2022, "1T"),
    "2024-y-siguientes": Period.from_year_and_code(2024, "1T"),
}
#: The month each Modelo 604 edition is rendered for.
M604_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021-2023": Period.from_year_and_code(2022, "01"),
    "2024-y-siguientes": Period.from_year_and_code(2024, "01"),
}
#: The annual period each Modelo 151 edition is rendered for.
M151_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2015-2022": Period.from_year_and_code(2015, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 165 edition is rendered for.
M165_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2016-2022": Period.from_year_and_code(2016, "0A"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "0A"),
}
#: The annual period each Modelo 184 edition is rendered for.
M184_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2023-2024": Period.from_year_and_code(2023, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period of Modelo 200's export-bearing successor.
M200_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The payment period each Modelo 202 edition is rendered for; 202 files ``1P``-``3P``.
M202_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2022": Period.from_year_and_code(2019, "1P"),
    "2023-2024": Period.from_year_and_code(2023, "1P"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "1P"),
}
#: The first payment period of Modelo 222's export-bearing edition.
M222_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025-y-siguientes": Period.from_year_and_code(2025, "1P"),
}
#: The annual period of Modelo 296's five-record successor design.
M296_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2024-2025": Period.from_year_and_code(2024, "0A"),
}
#: The annual period each Modelo 180 edition is rendered for.
M180_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2022": Period.from_year_and_code(2019, "0A"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "0A"),
}
#: The month Modelo 185's one export-bearing edition is rendered for.
M185_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025-y-siguientes": Period.from_year_and_code(2026, "01"),
}
#: The annual period each Modelo 210 edition is rendered for.
M210_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025": Period.from_year_and_code(2025, "0A"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "0A"),
}
#: The annual period each Modelo 270 edition is rendered for.
M270_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2013-2022": Period.from_year_and_code(2013, "0A"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "0A"),
}
#: The quarter each Modelo 341 edition is rendered for.
M341_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2005-2015": Period.from_year_and_code(2005, "1T"),
    "2016-y-siguientes": Period.from_year_and_code(2016, "1T"),
}
#: The month each Modelo 353 edition is rendered for; the 2026 edition starts at ``02``.
M353_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021-hasta-2026-01": Period.from_year_and_code(2021, "01"),
    "2026-desde-02": Period.from_year_and_code(2026, "02"),
}
#: The annual period Modelo 576's one export-bearing edition is rendered for.
M576_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2008-y-siguientes": Period.from_year_and_code(2008, "0A"),
}
