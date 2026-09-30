"""Base provider interfaces and common functionality."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ImportResult:
    """Result of an import operation."""

    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: list[dict[str, Any]] | None = None


class BaseProvider(ABC):
    """Abstract base class for data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'SEC EDGAR')."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider type (e.g., 'sec', 'price', 'fundamental')."""

    @abstractmethod
    def validate_config(self) -> None:
        """Validate provider configuration."""

    @abstractmethod
    async def import_data(self, *args, **kwargs) -> ImportResult:
        """Import data from the provider."""


class BaseHTTPClient(BaseProvider):
    """Base HTTP client for data providers."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._client = httpx.AsyncClient(*args, **kwargs)
        self.headers = {}

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Perform GET request."""
        return await self._client.get(url, **kwargs)

    async def close(self) -> None:
        """Close client connections."""
        await self._client.aclose()


class BaseClient(ABC):
    """Abstract base class for HTTP clients."""

    @abstractmethod
    async def get(self, url: str, **kwargs) -> Any:
        """Perform GET request."""

    @abstractmethod
    async def close(self) -> None:
        """Close client connections."""
