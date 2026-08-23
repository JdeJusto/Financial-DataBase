"""SEC EDGAR HTTP client with rate limiting, retries, and backoff."""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import aiohttp

from financial_database.providers.sec.models import (
    SECCompany,
    SECCompanyFact,
    SECCompanyFacts,
    SECCompanyFactValue,
    SECFiling,
    SECSubmissions,
)

logger = logging.getLogger(__name__)

SEC_BASE_URL = "https://www.sec.gov"
SEC_SUBMISSIONS_URL = f"{SEC_BASE_URL}/api/xbrl/companyfacts/"
SEC_COMPANY_TICKERS_URL = f"{SEC_BASE_URL}/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_PATH = "/submissions/CIK{}.json"
SEC_COMPANYFACTS_PATH = "/api/xbrl/companyfacts/CIK{}.json"

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 60.0
RATE_LIMIT_DELAY = 0.1  # 10 requests per second max


class SECClientError(Exception):
    """Base exception for SEC client errors."""


class SECRateLimitError(SECClientError):
    """Rate limit exceeded."""


class SECNotFoundError(SECClientError):
    """Resource not found (404)."""


class SECServerError(SECClientError):
    """Server error (5xx)."""


class SECClient:
    """SEC EDGAR API client with conservative rate limiting and retries."""

    def __init__(
        self,
        user_agent: str | None = None,
        raw_dir: Path | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ):
        self._user_agent = user_agent or os.environ.get("SEC_USER_AGENT")
        if not self._user_agent:
            raise ValueError(
                "SEC_USER_AGENT is required. Set via environment variable or constructor."
            )
        self._raw_dir = raw_dir or Path(os.environ.get("DATA_RAW_DIR", "./data/raw")) / "sec"
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._session: aiohttp.ClientSession | None = None
        self._last_request_time = 0.0
        self._rate_limit_lock = asyncio.Lock()

        # Ensure raw directories exist
        for subdir in ["submissions", "companyfacts", "reference"]:
            (self._raw_dir / subdir).mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> "SECClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _ensure_session(self) -> None:
        """Create aiohttp session if not exists."""
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": self._user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            }
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=self._timeout,
            )

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        async with self._rate_limit_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < RATE_LIMIT_DELAY:
                await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
            self._last_request_time = time.monotonic()

    def _calculate_backoff(self, attempt: int, retry_after: int | None = None) -> float:
        """Calculate exponential backoff delay."""
        if retry_after is not None:
            return min(float(retry_after), MAX_DELAY)
        delay = BASE_DELAY * (2 ** attempt)
        return min(delay, MAX_DELAY)

    async def _request(
        self,
        url: str,
        *,
        max_retries: int = MAX_RETRIES,
        save_raw: bool = False,
        raw_subdir: str = "",
        raw_filename: str = "",
    ) -> dict[str, Any]:
        """Perform HTTP GET with retries, backoff, and rate limiting."""
        await self._ensure_session()
        await self._rate_limit()

        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                async with self._session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        content_type = response.headers.get("Content-Type", "")

                        if save_raw and raw_filename:
                            await self._save_raw_response(
                                content, content_type, raw_subdir, raw_filename
                            )

                        return json.loads(content.decode("utf-8"))

                    elif response.status == 404:
                        raise SECNotFoundError(f"Resource not found: {url}")

                    elif response.status == 429:
                        retry_after = response.headers.get("Retry-After")
                        delay = self._calculate_backoff(attempt, int(retry_after) if retry_after else None)
                        logger.warning(
                            "SEC rate limit hit, backing off",
                            extra={"url": url, "attempt": attempt, "delay": delay, "retry_after": retry_after},
                        )
                        if attempt < max_retries:
                            await asyncio.sleep(delay)
                            continue
                        raise SECRateLimitError(f"Rate limit exceeded after {max_retries} retries")

                    elif 500 <= response.status < 600:
                        delay = self._calculate_backoff(attempt)
                        logger.warning(
                            "SEC server error, retrying",
                            extra={"url": url, "status": response.status, "attempt": attempt, "delay": delay},
                        )
                        if attempt < max_retries:
                            await asyncio.sleep(delay)
                            continue
                        raise SECServerError(f"Server error {response.status} after {max_retries} retries")

                    else:
                        text = await response.text()
                        raise SECClientError(f"HTTP {response.status}: {text[:200]}")

            except (TimeoutError, aiohttp.ClientError) as e:
                last_error = e
                delay = self._calculate_backoff(attempt)
                logger.warning(
                    "SEC request failed, retrying",
                    extra={"url": url, "attempt": attempt, "delay": delay, "error": str(e)},
                )
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    continue
                raise SECClientError(f"Request failed after {max_retries} retries: {last_error}") from last_error

        raise SECClientError(f"Unexpected error after retries: {last_error}")

    async def _save_raw_response(
        self,
        content: bytes,
        content_type: str,
        subdir: str,
        filename: str,
    ) -> tuple[str, str]:
        """Save raw response to filesystem, return (path, checksum)."""
        filepath = self._raw_dir / subdir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Calculate checksum
        checksum = hashlib.sha256(content).hexdigest()

        # Check if file exists and content changed
        if filepath.exists():
            existing_checksum = hashlib.sha256(filepath.read_bytes()).hexdigest()
            if existing_checksum == checksum:
                logger.debug("Raw file unchanged, skipping write", extra={"path": str(filepath)})
                return str(filepath), checksum
            else:
                # Content changed - preserve old version with timestamp
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                backup_path = filepath.with_stem(f"{filepath.stem}_{timestamp}")
                filepath.rename(backup_path)
                logger.info("Raw file changed, preserved previous version",
                           extra={"old_path": str(backup_path), "new_path": str(filepath)})

        filepath.write_bytes(content)
        logger.info("Raw file saved", extra={"path": str(filepath), "checksum": checksum[:16]})
        return str(filepath), checksum

    async def get_company_tickers(self) -> list[SECCompany]:
        """Fetch SEC company tickers exchange reference data."""
        logger.info("Fetching SEC company tickers")
        data = await self._request(
            SEC_COMPANY_TICKERS_URL,
            save_raw=True,
            raw_subdir="reference",
            raw_filename="company_tickers_exchange.json",
        )

        companies = []
        for item in data.get("data", []):
            # data format: [cik, name, ticker, exchange, sic, sic_description, owner_org]
            if len(item) >= 3:
                cik = str(item[0]).zfill(10)
                companies.append(SECCompany(
                    cik=cik,
                    name=item[1],
                    ticker=item[2] if item[2] else None,
                    exchange=item[3] if len(item) > 3 and item[3] else None,
                    sic=item[4] if len(item) > 4 and item[4] else None,
                    sic_description=item[5] if len(item) > 5 and item[5] else None,
                    owner_org=item[6] if len(item) > 6 and item[6] else None,
                ))

        logger.info("Fetched SEC companies", extra={"count": len(companies)})
        return companies

    async def get_submissions(self, cik: str) -> SECSubmissions:
        """Fetch submissions for a CIK."""
        normalized_cik = cik.zfill(10)
        url = urljoin(SEC_BASE_URL, SEC_SUBMISSIONS_PATH.format(normalized_cik))
        logger.info("Fetching SEC submissions", extra={"cik": normalized_cik})

        data = await self._request(
            url,
            save_raw=True,
            raw_subdir="submissions",
            raw_filename=f"{normalized_cik}.json",
        )

        filings = []
        recent = data.get("filings", {}).get("recent", {})
        if recent:
            count = len(recent.get("accessionNumber", []))
            for i in range(count):
                filing_date_str = recent.get("filingDate", [None] * count)[i]
                period_end_str = recent.get("periodOfReport", [None] * count)[i]

                filing = SECFiling(
                    accession_number=recent.get("accessionNumber", [None] * count)[i],
                    form=recent.get("form", [None] * count)[i],
                    filing_date=filing_date_str if filing_date_str else None,
                    period_start=None,  # Not directly provided in recent
                    period_end=period_end_str if period_end_str else None,
                    fiscal_year=recent.get("fy", [None] * count)[i],
                    fiscal_period=recent.get("fp", [None] * count)[i],
                    filing_url=urljoin(SEC_BASE_URL, f"/Archives/edgar/data/{int(normalized_cik)}/{recent.get('accessionNumber', [None] * count)[i].replace('-', '')}/{recent.get('primaryDocument', [None] * count)[i]}"),
                    is_amended=recent.get("form", [None] * count)[i] and recent.get("form", [None] * count)[i].endswith("/A"),
                    primary_document=recent.get("primaryDocument", [None] * count)[i],
                    primary_doc_description=recent.get("primaryDocDescription", [None] * count)[i],
                )
                filings.append(filing)

        return SECSubmissions(
            cik=normalized_cik,
            entity_name=data.get("name", ""),
            filings=filings,
            metadata={k: v for k, v in data.items() if k != "filings"},
        )

    async def get_company_facts(self, cik: str) -> SECCompanyFacts:
        """Fetch CompanyFacts XBRL data for a CIK."""
        normalized_cik = cik.zfill(10)
        url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{normalized_cik}.json"
        logger.info("Fetching SEC CompanyFacts", extra={"cik": normalized_cik})

        data = await self._request(
            url,
            save_raw=True,
            raw_subdir="companyfacts",
            raw_filename=f"{normalized_cik}.json",
        )

        facts: dict[str, dict[str, SECCompanyFact]] = {}

        # Parse the nested facts structure: facts[namespace][concept]
        for namespace, concepts in data.get("facts", {}).items():
            facts[namespace] = {}
            for concept_name, concept_data in concepts.items():
                values = []
                for unit_data in concept_data.get("units", {}).values():
                    for val_data in unit_data:
                        # Parse dates
                        period_start = None
                        period_end = None
                        if val_data.get("start"):
                            try:
                                period_start = date.fromisoformat(val_data["start"])
                            except ValueError:
                                pass
                        if val_data.get("end"):
                            try:
                                period_end = date.fromisoformat(val_data["end"])
                            except ValueError:
                                pass

                        # Determine if instant or duration
                        is_instant = period_start is None or period_start == period_end

                        values.append(SECCompanyFactValue(
                            value=val_data.get("val", 0),
                            period_start=period_start,
                            period_end=period_end,
                            fiscal_year=val_data.get("fy"),
                            fiscal_period=val_data.get("fp"),
                            form=val_data.get("form"),
                            filing_date=date.fromisoformat(val_data["filed"]) if val_data.get("filed") else None,
                            accession_number=val_data.get("accn"),
                            frame=val_data.get("frame"),
                            is_instant=is_instant,
                            metadata={k: v for k, v in val_data.items()
                                      if k not in {"val", "start", "end", "fy", "fp", "form", "filed", "accn", "frame"}},
                        ))

                fact = SECCompanyFact(
                    concept=concept_name,
                    namespace=namespace,
                    label=concept_data.get("label"),
                    unit=concept_data.get("unit", ""),
                    values=values,
                )
                facts[namespace][concept_name] = fact

        return SECCompanyFacts(
            cik=normalized_cik,
            entity_name=data.get("entityName", ""),
            facts=facts,
            metadata={k: v for k, v in data.items() if k not in {"facts", "entityName"}},
        )