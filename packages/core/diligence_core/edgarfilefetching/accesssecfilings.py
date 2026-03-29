import asyncio
from typing import List

import edgar
from pydantic import BaseModel


class FilingDetails(BaseModel):
    company_name: str
    ticker: str
    cik: str
    form_type: str
    filing_date: str
    fiscal_year: int
    period_of_report: str
    accession_no: str
    source_url: str
    primary_document:str


def get_filing_source_url(cik: str, accession_no: str,primary_document:str) -> str:
    cik_padded = str(cik).zfill(10)
    accession_clean = accession_no.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_clean}/{primary_document}"

def _get_fiscal_year(doc) -> int | None:
    period = getattr(doc, "period_of_report", None) or getattr(doc, "report_date", None)
    if period:
        return int(str(period)[:4])
    return None

def _fetch_filing_sync(ticker: str, year: List[int]) -> List[dict]:
    edgar.set_identity("Your Name youremail@example.com")
    company = edgar.Company(ticker)
    filings = company.get_filings(form="10-K")

    matched_filings = []

    for filing in filings:
        doc = filing.obj()
        if _get_fiscal_year(doc) in year:
            matched_filings.append((filing, doc))

    if not matched_filings:
        raise ValueError(f"No 10-K found for '{ticker.upper()}' in fiscal years {year}")

    collected_data = []

    for matched_filing, doc in matched_filings:
        sections = {
            "risk_factors": doc.risk_factors,
            "mda":          doc.management_discussion,
            "business":     doc.business,
        }

        metadata = FilingDetails(
            company_name     = company.name,
            ticker           = ticker.upper(),
            cik              = str(matched_filing.cik),
            form_type        = matched_filing.form,
            filing_date      = str(matched_filing.filing_date),
            fiscal_year      = _get_fiscal_year(doc),
            period_of_report = str(doc.period_of_report),
            accession_no     = matched_filing.accession_no,
            primary_document = matched_filing.primary_document,
            source_url       = get_filing_source_url(matched_filing.cik, matched_filing.accession_no,matched_filing.primary_document),
        )
        collected_data.append({"metadata": metadata, "sections": sections})
    return collected_data


async def get_10_k_filing(ticker: str, year: List[int]) -> List[dict]:
    return await asyncio.to_thread(_fetch_filing_sync, ticker, year)
