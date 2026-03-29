import edgar

edgar.set_identity("Your Name youremail@example.com")

async def get_10_k_filing(ticker:str):
    company = edgar.Company("ACN")
    # get their latest 10-K
    filings = company.get_filings(form="10-K")
    latest_10k = filings[0]
    doc = latest_10k.obj()
    sections = {
        "risk_factors": doc.risk_factors,
        "mda": doc.management_discussion,
        "business": doc.business
    }

    print(sections)
    return sections