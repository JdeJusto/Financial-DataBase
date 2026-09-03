"""SEC EDGAR HTTP client with rate limiting, retries, and backoff."""

import asyncio
import hashlib
import json
import logging
import os
import signal
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Self
from urllib.parse import urljoin

import aiofiles
import aiohttp
from aiohttp import ClientResponseError

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
SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_SUBMISSIONS_URL = f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/"
# Allow overriding the company tickers URL for testing (e.g., to use a filtered list)
SEC_COMPANY_TICKERS_URL = os.environ.get(
    "SEC_CUSTOM_TICKERS_URL", f"{SEC_BASE_URL}/files/company_tickers_exchange.json"
)
SEC_SUBMISSIONS_PATH = "/submissions/CIK{}.json"
SEC_COMPANYFACTS_PATH = "/api/xbrl/companyfacts/CIK{}.json"

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 60.0
RATE_LIMIT_DELAY = 0.1  # 10 requests per second max

# Network resilience configuration
NETWORK_RETRY_INTERVAL = 10.0  # seconds between retry attempts
GRACEFUL_SHUTDOWN_TIMEOUT = 15.0  # seconds to wait for graceful shutdown


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
        max_retries: int = 5,
    ):
        self._user_agent = user_agent or os.environ.get("SEC_USER_AGENT")
        if not self._user_agent:
            raise ValueError(
                "SEC_USER_AGENT is required. Set via environment variable or constructor."
            )
        self._raw_dir = (
            raw_dir or Path(os.environ.get("DATA_RAW_DIR", "./data/raw")) / "sec"
        )
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._max_retries = max_retries
        self._session: aiohttp.ClientSession | None = None
        self._last_request_time = 0.0
        self._rate_limit_lock = asyncio.Lock()

        # Graceful shutdown state
        self._shutdown_requested = False
        self._shutdown_event = asyncio.Event()

        # Ensure raw directories exist
        for subdir in ["submissions", "companyfacts", "reference"]:
            (self._raw_dir / subdir).mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> Self:
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

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        logger.info("Graceful shutdown requested")
        self._shutdown_requested = True
        self._shutdown_event.set()

    async def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown."""
        logger.info("Starting graceful shutdown...")
        self._shutdown_requested = True
        self._shutdown_event.set()
        # Wait for any ongoing request to complete or timeout
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(), timeout=GRACEFUL_SHUTDOWN_TIMEOUT
            )
        except TimeoutError:
            logger.warning("Graceful shutdown timeout, forcing close")
        await self.close()
        logger.info("Graceful shutdown complete")

    def install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._graceful_shutdown()),
            )
        logger.info("Signal handlers installed for graceful shutdown")

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        async with self._rate_limit_lock:
            now: float = time.monotonic()
            elapsed: float = now - self._last_request_time
            if elapsed < RATE_LIMIT_DELAY:
                await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
            self._last_request_time = time.monotonic()

    def _calculate_backoff(self, attempt: int, retry_after: int | None = None) -> float:
        """Calculate exponential backoff delay."""
        if retry_after is not None:
            return min(float(retry_after), MAX_DELAY)
        delay: float = BASE_DELAY * (2**attempt)
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

        # Ensure raw directories exist
        for subdir in ["submissions", "companyfacts", "reference"]:
            (self._raw_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _check_shutdown(self) -> None:
        """Check if shutdown was requested and raise if so."""
        if self._shutdown_requested:
            raise asyncio.CancelledError("Shutdown requested")

    async def _wait_with_shutdown_check(self, delay: float) -> None:
        """Wait for delay seconds while checking for shutdown."""
        waited = 0.0
        while waited < delay:
            if self._shutdown_requested:
                raise asyncio.CancelledError("Shutdown requested during wait")
            await asyncio.sleep(min(NETWORK_RETRY_INTERVAL, delay - waited))
            waited += NETWORK_RETRY_INTERVAL

    async def _request_with_retry(
        self,
        url: str,
        *,
        max_retries: int = MAX_RETRIES,
        save_raw: bool = False,
        raw_subdir: str = "",
        raw_filename: str = "",
    ) -> dict[str, Any]:
        """Perform HTTP GET with retries, backoff, and bounded network retries."""
        await self._ensure_session()
        await self._rate_limit()

        assert self._session is not None
        attempt = 0

        while not self._shutdown_requested:
            try:
                self._check_shutdown()
                await self._rate_limit()

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
                        delay = self._calculate_backoff(
                            attempt, int(retry_after) if retry_after else None
                        )
                        logger.warning(
                            "SEC rate limit hit, backing off",
                            extra={
                                "url": url,
                                "attempt": attempt,
                                "delay": delay,
                                "retry_after": retry_after,
                            },
                        )
                        if attempt < max_retries:
                            await self._wait_with_shutdown_check(delay)
                            attempt += 1
                            continue
                        raise SECRateLimitError(
                            f"Rate limit exceeded after {max_retries} retries"
                        )

                    elif 500 <= response.status < 600:
                        delay = self._calculate_backoff(attempt)
                        logger.warning(
                            "SEC server error, retrying",
                            extra={
                                "url": url,
                                "status": response.status,
                                "attempt": attempt,
                                "delay": delay,
                            },
                        )
                        if attempt < max_retries:
                            await self._wait_with_shutdown_check(delay)
                            attempt += 1
                            continue
                        raise SECServerError(
                            f"Server error {response.status} after {max_retries} retries"
                        )

                    else:
                        text = await response.text()
                        raise SECClientError(f"HTTP {response.status}: {text[:200]}")

            except (TimeoutError, aiohttp.ClientError) as e:
                # Handle ClientResponseError (includes HTTP error statuses) specially
                if isinstance(e, ClientResponseError):
                    status = e.status
                    if status == 404:
                        raise SECNotFoundError(f"Resource not found: {url}")
                    elif status == 429:
                        retry_after = e.headers.get("Retry-After")
                        delay = self._calculate_backoff(
                            attempt, int(retry_after) if retry_after else None
                        )
                        logger.warning(
                            "SEC rate limit hit, backing off",
                            extra={
                                "url": url,
                                "attempt": attempt,
                                "delay": delay,
                                "retry_after": retry_after,
                            },
                        )
                        if attempt < max_retries:
                            await self._wait_with_shutdown_check(delay)
                            attempt += 1
                            continue
                        raise SECRateLimitError(
                            f"Rate limit exceeded after {max_retries} retries"
                        )
                    elif 500 <= status < 600:
                        delay = self._calculate_backoff(attempt)
                        logger.warning(
                            "SEC server error, retrying",
                            extra={
                                "url": url,
                                "status": status,
                                "attempt": attempt,
                                "delay": delay,
                            },
                        )
                        if attempt < max_retries:
                            await self._wait_with_shutdown_check(delay)
                            attempt += 1
                            continue
                        raise SECServerError(
                            f"Server error {status} after {max_retries} retries"
                        )
                    else:
                        # 4xx errors (except 429) and other status codes
                        raise SECClientError(f"HTTP {status}: {e.message}")
                else:
                    # Network errors (timeout, connection errors, etc.)
                    if attempt >= max_retries:
                        raise SECClientError(
                            f"Network error after {max_retries} retries: {e}"
                        )
                    logger.warning(
                        "SEC request failed, will retry",
                        extra={
                            "url": url,
                            "attempt": attempt,
                            "error": str(e),
                        },
                    )
                    # Wait 10 seconds before retry (with shutdown check)
                    await self._wait_with_shutdown_check(NETWORK_RETRY_INTERVAL)
                    attempt += 1
                    continue

    async def _request(
        self,
        url: str,
        *,
        max_retries: int | None = None,
        save_raw: bool = False,
        raw_subdir: str = "",
        raw_filename: str = "",
    ) -> dict[str, Any]:
        """Perform HTTP GET with retries, backoff, and rate limiting.

        For 429/5xx/404: uses max_retries with exponential backoff.
        For network errors: retries with 10-second intervals up to max_retries.
        """
        if max_retries is None:
            max_retries = self._max_retries
        return await self._request_with_retry(
            url,
            max_retries=max_retries,
            save_raw=save_raw,
            raw_subdir=raw_subdir,
            raw_filename=raw_filename,
        )

    def _check_shutdown(self) -> None:
        """Check if shutdown was requested and raise if so."""
        if self._shutdown_requested:
            raise asyncio.CancelledError("Shutdown requested")

    async def _wait_with_shutdown_check(self, delay: float) -> None:
        """Wait for delay seconds while checking for shutdown."""
        waited = 0.0
        while waited < delay:
            if self._shutdown_requested:
                raise asyncio.CancelledError("Shutdown requested during wait")
            await asyncio.sleep(min(NETWORK_RETRY_INTERVAL, delay - waited))
            waited += NETWORK_RETRY_INTERVAL

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
                logger.debug(
                    "Raw file unchanged, skipping write", extra={"path": str(filepath)}
                )
                return str(filepath), checksum
            else:
                # Content changed - preserve old version with timestamp
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                backup_path = filepath.with_stem(f"{filepath.stem}_{timestamp}")
                filepath.rename(backup_path)
                logger.info(
                    "Raw file changed, preserved previous version",
                    extra={"old_path": str(backup_path), "new_path": str(filepath)},
                )

        filepath.write_bytes(content)
        logger.info(
            "Raw file saved", extra={"path": str(filepath), "checksum": checksum[:16]}
        )
        return str(filepath), checksum

    async def get_company_tickers(self) -> list[SECCompany]:
        """Fetch SEC company tickers exchange reference data."""
        logger.info("Fetching SEC company tickers")

        # Check if the URL is a local file (absolute or relative path)
        # Remote URLs contain "://" (http://, https://, etc.)
        # Local files don't contain "://" (including file:// which we handle specially)
        if "://" not in SEC_COMPANY_TICKERS_URL or SEC_COMPANY_TICKERS_URL.startswith(
            "file://"
        ):
            # Local file path
            file_path = SEC_COMPANY_TICKERS_URL
            file_path = file_path.removeprefix(
                "file://"
            )  # Remove 'file://' prefix if present
            try:
                async with aiofiles.open(file_path, "r") as f:
                    content = await f.read()
                data = json.loads(content)
                logger.info(
                    "Loaded company tickers from local file",
                    extra={"file": file_path, "size": len(content)},
                )
            except (OSError, json.JSONDecodeError) as e:
                logger.error(
                    "Failed to load company tickers from local file",
                    extra={"file": file_path, "error": str(e)},
                )
                raise SECClientError(f"Failed to load local file {file_path}: {e}")
        else:
            # Remote URL
            data = await self._request(
                SEC_COMPANY_TICKERS_URL,
                save_raw=True,
                raw_subdir="reference",
                raw_filename="company_tickers_exchange.json",
            )

        companies = []

        # Detect format: official SEC dictionary format or custom list format
        if "data" in data and isinstance(data["data"], list):
            # Custom list format: {"fields": [...], "data": [[cik, name, ticker, exchange], ...]}
            for item in data.get("data", []):
                # data format: [cik, name, ticker, exchange, sic, sic_description, owner_org]
                # Skip None items or items with insufficient data
                if item is None or len(item) < 3:
                    continue

                # Validate that CIK is numeric (contains only digits)
                cik_str = str(item[0])
                if not cik_str.isdigit():
                    continue

                cik = cik_str.zfill(10)
                companies.append(
                    SECCompany(
                        cik=cik,
                        name=item[1],
                        ticker=item[2] if item[2] else None,
                        exchange=item[3] if len(item) > 3 and item[3] else None,
                        sic=item[4] if len(item) > 4 and item[4] else None,
                        sic_description=item[5] if len(item) > 5 and item[5] else None,
                        owner_org=item[6] if len(item) > 6 and item[6] else None,
                    )
                )
        else:
            # Official SEC dictionary format: {"0": {"cik_str": ..., "ticker": ..., "title": ...}, ...}
            for key, item in data.items():
                # Skip non-numeric keys (like metadata)
                if not key.isdigit():
                    continue

                # Validate required fields
                if not isinstance(item, dict):
                    continue

                cik_str = item.get("cik_str")
                ticker = item.get("ticker")
                title = item.get("title")

                if cik_str is None or ticker is None or title is None:
                    continue

                # Validate that CIK is numeric (contains only digits)
                if not str(cik_str).isdigit():
                    continue

                cik = str(cik_str).zfill(10)
                companies.append(
                    SECCompany(
                        cik=cik,
                        name=title,
                        ticker=ticker,
                        exchange="",  # Unknown in official format, can be inferred later
                    )
                )

        logger.info("Fetched SEC companies", extra={"count": len(companies)})
        return companies

    async def get_submissions(self, cik: str) -> SECSubmissions:
        """Fetch submissions for a CIK."""
        normalized_cik = cik.zfill(10)
        url = urljoin(SEC_DATA_BASE_URL, SEC_SUBMISSIONS_PATH.format(normalized_cik))
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
                # SEC uses 'reportDate' for period end (can be empty string)
                period_end_str = recent.get("reportDate", [None] * count)[i]
                if period_end_str == "":
                    period_end_str = None

                filing = SECFiling(
                    accession_number=recent.get("accessionNumber", [None] * count)[i],
                    form=recent.get("form", [None] * count)[i],
                    filing_date=filing_date_str if filing_date_str else None,
                    period_start=None,  # Not directly provided in recent
                    period_end=period_end_str,  # type: ignore[arg-type]
                    fiscal_year=recent.get("fy", [None] * count)[i],
                    fiscal_period=recent.get("fp", [None] * count)[i],
                    filing_url=urljoin(
                        SEC_BASE_URL,
                        f"/Archives/edgar/data/{int(normalized_cik)}/{recent.get('accessionNumber', [None] * count)[i].replace('-', '')}/{recent.get('primaryDocument', [None] * count)[i]}",
                    ),
                    is_amended=recent.get("form", [None] * count)[i]
                    and recent.get("form", [None] * count)[i].endswith("/A"),
                    primary_document=recent.get("primaryDocument", [None] * count)[i],
                    primary_doc_description=recent.get(
                        "primaryDocDescription", [None] * count
                    )[i],
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
        url = f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK{normalized_cik}.json"
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
                for unit, unit_data in concept_data.get("units", {}).items():
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

                        values.append(
                            SECCompanyFactValue(
                                value=val_data.get("val", 0),
                                unit=unit,
                                period_start=period_start,
                                period_end=period_end,
                                fiscal_year=val_data.get("fy"),
                                fiscal_period=val_data.get("fp"),
                                form=val_data.get("form"),
                                filing_date=date.fromisoformat(val_data["filed"])
                                if val_data.get("filed")
                                else None,
                                accession_number=val_data.get("accn"),
                                frame=val_data.get("frame"),
                                is_instant=is_instant,
                                metadata={
                                    k: v
                                    for k, v in val_data.items()
                                    if k
                                    not in {
                                        "val",
                                        "start",
                                        "end",
                                        "fy",
                                        "fp",
                                        "form",
                                        "filed",
                                        "accn",
                                        "frame",
                                    }
                                },
                            )
                        )

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
            metadata={
                k: v for k, v in data.items() if k not in {"facts", "entityName"}
            },
        )
