from __future__ import annotations

import re
import time
from datetime import date, datetime

import httpx
from selectolax.parser import HTMLParser
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Filing

_HEADERS = {"User-Agent": settings.sec_user_agent}
_ITEM_RE = re.compile(r"(item\s+\d+[a-z]?\.?)", re.IGNORECASE)

# SEC asks for <= ~10 requests/second; 0.12s spacing keeps us comfortably under.
_MIN_REQUEST_INTERVAL = 0.12
_last_request_ts = 0.0


def _throttle() -> None:
    """Sleep just enough to keep every request <= ~10/s (SEC fair-access)."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_ts = time.monotonic()


def _get(url: str, client: httpx.Client, *, timeout: float) -> httpx.Response:
    """Rate-limited GET carrying the SEC User-Agent; raises on 4xx/5xx."""
    _throttle()
    r = client.get(url, headers=_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def submissions(cik: str, client: httpx.Client) -> dict:
    """GET the SEC submissions metadata for a CIK (zero-padded to 10 digits)."""
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    return _get(url, client, timeout=30).json()


def filings_of(subs: dict, form: str, n: int = 1) -> list[dict]:
    """Pick the n most-recent filings of a given form from the submissions blob."""
    recent = subs["filings"]["recent"]
    rows = zip(
        recent["form"],
        recent["accessionNumber"],
        recent["primaryDocument"],
        recent["filingDate"],
        recent["reportDate"],
    )
    out: list[dict] = []
    for form_type, accession, primary_doc, filing_date, report_date in rows:
        if form_type == form:
            out.append(
                {
                    "form_type": form_type,
                    "accession": accession,
                    "primary_doc": primary_doc,
                    "filing_date": filing_date,
                    "report_date": report_date,
                }
            )
            if len(out) >= n:
                break
    return out


def fetch_doc(cik: str, accession: str, primary_doc: str, client: httpx.Client) -> str:
    """Fetch the primary document HTML and flatten to text."""
    acc_nodash = accession.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{acc_nodash}/{primary_doc}"
    )
    return HTMLParser(_get(url, client, timeout=60).text).text(separator="\n")


def split_sections(text: str) -> dict[str, str]:
    """PURE: split a filing's flat text into {item_label: section_text}.

    Accumulates lines under the most recent 'Item N' heading seen. 10-K vs 10-Q
    numbering differs — tune the regex / heading detection per form if needed.
    """
    sections: dict[str, list[str]] = {}
    current = "preamble"
    sections[current] = []
    for line in text.splitlines():
        m = _ITEM_RE.match(line.strip())
        if m:
            current = m.group(1).lower().rstrip(".").strip()
            sections.setdefault(current, [])
        sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "".join(v).strip()}

def ingest_latest(ticker: str, cik: str, form: str, db: Session, client: httpx.Client) -> Filing:
    subs = submissions(cik, client)
    meta = filings_of(subs, form, n=1)[0]
    text = fetch_doc(cik, meta["accession"], meta["primary_doc"], client)
    sections = split_sections(text)

    rd = meta["report_date"]  # SEC period-of-report, "YYYY-MM-DD" (may be "")
    filing = Filing(
        ticker=ticker.upper(),                    # ticker keying convention
        cik=cik,
        form_type=meta["form_type"],
        accession=meta["accession"],
        report_date=date.fromisoformat(rd) if rd else None,  # store the truth, no fiscal label
        filed_at=datetime.fromisoformat(meta["filing_date"]),
        sections=sections,
    )
    db.add(filing)
    db.commit()
    db.refresh(filing)
    return filing