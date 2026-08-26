"""Unit tests for SEC EDGAR HTTP client."""
import json
import os
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import aiohttp
from aiohttp import ClientError, ClientResponseError

from financial_database.providers.sec.client import (
    SECClient,
    SECClientError,
    SECRateLimitError,
    SECNotFoundError,
    SECServerError,
    SEC_COMPANY_TICKERS_URL,
)
from financial_database.providers.sec.models import SECCompany


@pytest.fixture
def mock_aiohttp_session():
    """Create a mock aiohttp session."""
    session = AsyncMock()

    # Mock response that works as async context manager
    response = AsyncMock()
    response.status = 200
    response.read = AsyncMock(return_value=b'{"data": []}')
    response.headers = {"Content-Type": "application/json"}
    response.text = AsyncMock(return_value='{"data": []}')

    # Mock session.get to return a context manager when called
    # session.get() should return an async context manager
    context_manager = AsyncMock()
    # When we call __aenter__ on the context manager, it returns a coroutine
    # When that coroutine is awaited, it yields the response
    context_manager.__aenter__ = AsyncMock()
    # Make the coroutine from __aenter__ yield our response when awaited
    context_manager.__aenter__.return_value = response
    # __aexit__ should return a coroutine (yielding None)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    # session.get is a method that when called returns the context manager
    session.get = MagicMock(return_value=context_manager)

    session.closed = False
    return session


@pytest.fixture
def sec_client():
    """Create an SEC client for testing."""
    with patch.dict(os.environ, {"SEC_USER_AGENT": "test-agent"}):
        return SECClient(max_retries=2)


class TestSECClientInitialization:
    """Test SEC client initialization."""

    def test_init_with_user_agent(self):
        """Test client initialization with user agent."""
        client = SECClient(user_agent="test-agent")
        assert client._user_agent == "test-agent"

    def test_init_with_env_user_agent(self):
        """Test client initialization with environment user agent."""
        with patch.dict(os.environ, {"SEC_USER_AGENT": "env-agent"}):
            client = SECClient()
            assert client._user_agent == "env-agent"

    def test_init_without_user_agent_raises(self):
        """Test that missing user agent raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="SEC_USER_AGENT is required"):
                SECClient()

    def test_init_with_max_retries(self):
        """Test client initialization with custom max_retries."""
        client = SECClient(user_agent="test", max_retries=5)
        assert client._max_retries == 5

    def test_init_default_max_retries(self):
        """Test client initialization with default max_retries."""
        client = SECClient(user_agent="test")
        assert client._max_retries == 5  # Updated default


class TestGetCompanyTickers:
    """Test get_company_tickers method."""

    @pytest.mark.asyncio
    async def test_get_company_tickers_from_remote_url(self, sec_client, mock_aiohttp_session):
        """Test fetching company tickers from remote URL."""
        # Mock response data
        mock_data = {
            "data": [
                ["0000320193", "Apple Inc.", "AAPL", "NASDAQ"],
                ["0000020340", "Tesla Inc.", "TSLA", "NASDAQ"],
            ]
        }

        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_request_with_retry', return_value=mock_data) as mock_request:

            companies = await sec_client.get_company_tickers()

            # Verify the request was made
            mock_request.assert_called_once()
            call_args = mock_request.call_args[0]
            assert call_args[0] == SEC_COMPANY_TICKERS_URL

            # Verify results
            assert len(companies) == 2
            assert companies[0].cik == "0000320193"
            assert companies[0].name == "Apple Inc."
            assert companies[0].ticker == "AAPL"
            assert companies[0].exchange == "NASDAQ"

            assert companies[1].cik == "0000020340"
            assert companies[1].name == "Tesla Inc."
            assert companies[1].ticker == "TSLA"
            assert companies[1].exchange == "NASDAQ"

    @pytest.mark.asyncio
    async def test_get_company_tickers_from_local_file(self):
        """Test fetching company tickers from local file."""
        # Create a temporary file with test data
        test_data = {
            "data": [
                ["0000320193", "Apple Inc.", "AAPL", "NASDAQ"],
                ["0000020340", "Tesla Inc.", "TSLA", "NASDAQ"],
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name

        try:
            # Patch the SEC_COMPANY_TICKERS_URL constant directly
            with patch('financial_database.providers.sec.client.SEC_COMPANY_TICKERS_URL', temp_file):
                # Create a client with the updated URL
                with patch.dict(os.environ, {"SEC_USER_AGENT": "test-agent"}):
                    test_client = SECClient(max_retries=2)
                    companies = await test_client.get_company_tickers()

                    # Verify results
                    assert len(companies) == 2
                    assert companies[0].cik == "0000320193"
                    assert companies[0].name == "Apple Inc."
                    assert companies[0].ticker == "AAPL"
                    assert companies[0].exchange == "NASDAQ"

                    assert companies[1].cik == "0000020340"
                    assert companies[1].name == "Tesla Inc."
                    assert companies[1].ticker == "TSLA"
                    assert companies[1].exchange == "NASDAQ"
        finally:
            # Clean up temp file
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_get_company_tickers_from_file_url(self):
        """Test fetching company tickers from file:// URL."""
        # Create a temporary file with test data
        test_data = {
            "data": [
                ["0000320193", "Apple Inc.", "AAPL", "NASDAQ"],
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name

        try:
            file_url = f"file://{temp_file}"
            # Patch the SEC_COMPANY_TICKERS_URL constant directly
            with patch('financial_database.providers.sec.client.SEC_COMPANY_TICKERS_URL', file_url):
                # Create a client with the updated URL
                with patch.dict(os.environ, {"SEC_USER_AGENT": "test-agent"}):
                    test_client = SECClient(max_retries=2)
                    companies = await test_client.get_company_tickers()

                    # Verify results
                    assert len(companies) == 1
                    assert companies[0].cik == "0000320193"
                    assert companies[0].name == "Apple Inc."
                    assert companies[0].ticker == "AAPL"
                    assert companies[0].exchange == "NASDAQ"
        finally:
            # Clean up temp file
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_get_company_tickers_local_file_not_found(self):
        """Test handling of missing local file."""
        # Patch the SEC_COMPANY_TICKERS_URL constant directly
        with patch('financial_database.providers.sec.client.SEC_COMPANY_TICKERS_URL', "/nonexistent/file.json"):
            # Create a client with the updated URL
            with patch.dict(os.environ, {"SEC_USER_AGENT": "test-agent"}):
                test_client = SECClient(max_retries=2)
                with pytest.raises(SECClientError, match="Failed to load local file"):
                    await test_client.get_company_tickers()

    @pytest.mark.asyncio
    async def test_get_company_tickers_local_file_invalid_json(self):
        """Test handling of invalid JSON in local file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')  # Invalid JSON
            temp_file = f.name

        try:
            # Patch the SEC_COMPANY_TICKERS_URL constant directly
            with patch('financial_database.providers.sec.client.SEC_COMPANY_TICKERS_URL', temp_file):
                # Create a client with the updated URL
                with patch.dict(os.environ, {"SEC_USER_AGENT": "test-agent"}):
                    test_client = SECClient(max_retries=2)
                    with pytest.raises(SECClientError, match="Failed to load local file"):
                        await test_client.get_company_tickers()
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_get_company_tickers_empty_data(self, sec_client):
        """Test handling of empty data response."""
        mock_data = {"data": []}

        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_request_with_retry', return_value=mock_data):

            companies = await sec_client.get_company_tickers()
            assert len(companies) == 0

    @pytest.mark.asyncio
    async def test_get_company_tickers_malformed_items(self):
        """Test handling of malformed items in data array."""
        mock_data = {
            "data": [
                ["0000320193", "Apple Inc.", "AAPL", "NASDAQ"],  # Valid
                ["0000020340"],  # Missing fields
                ["not_a_number", "Invalid CIK", "INVALID", "NYSE"],  # Invalid CIK type
                [],  # Empty item
                None,  # None item
            ]
        }

        # Patch the _request_with_retry method directly on a client instance
        with patch.dict(os.environ, {"SEC_USER_AGENT": "test-agent"}):
            test_client = SECClient(max_retries=2)
            with patch.object(test_client, '_request_with_retry', return_value=mock_data):
                companies = await test_client.get_company_tickers()
                # Only the first valid item should be processed
                assert len(companies) == 1
                assert companies[0].cik == "0000320193"


class TestRequestWithRetry:
    """Test _request_with_retry method."""

    @pytest.mark.asyncio
    async def test_request_with_retry_success(self, sec_client, mock_aiohttp_session):
        """Test successful request."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'):

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # Set up the mock session.get to return our context manager
            mock_aiohttp_session.get.return_value.__aenter__.return_value.read = AsyncMock(return_value=b'{"key": "value"}')
            mock_aiohttp_session.get.return_value.__aenter__.return_value.headers = {"Content-Type": "application/json"}
            mock_aiohttp_session.get.return_value.__aenter__.return_value.status = 200

            result = await sec_client._request_with_retry("http://test.com")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_request_with_retry_404(self, sec_client, mock_aiohttp_session):
        """Test 404 response raises SECNotFoundError."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'):

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # Make the response return status 404
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            # Configure the mock session.get to return a context manager that yields this response
            mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response
            mock_aiohttp_session.get.return_value.__aexit__.return_value = None

            with pytest.raises(SECNotFoundError):
                await sec_client._request_with_retry("http://test.com/notfound")

    @pytest.mark.asyncio
    async def test_request_with_retry_429_then_success(self, sec_client, mock_aiohttp_session):
        """Test 429 response with retry-after header, then success."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'), \
             patch.object(sec_client, '_wait_with_shutdown_check') as mock_wait:

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # First response: 429 with Retry-After
            response_429 = AsyncMock()
            response_429.status = 429
            response_429.headers = {"Retry-After": "1"}
            response_429.__aenter__ = AsyncMock(return_value=response_429)
            response_429.__aexit__ = AsyncMock(return_value=None)

            # Second response: 200 OK
            response_200 = AsyncMock()
            response_200.status = 200
            response_200.read = AsyncMock(return_value=b'{"success": true}')
            response_200.headers = {"Content-Type": "application/json"}
            response_200.__aenter__ = AsyncMock(return_value=response_200)
            response_200.__aexit__ = AsyncMock(return_value=None)

            # Set up the mock session.get to return context managers that yield these responses
            mock_aiohttp_session.get.return_value.__aenter__.side_effect = [response_429, response_200]
            mock_aiohttp_session.get.return_value.__aexit__.side_effect = [None, None]

            result = await sec_client._request_with_retry("http://test.com", max_retries=2)
            assert result == {"success": True}
            # Should have called wait once for the retry delay
            assert mock_wait.call_count >= 1

    @pytest.mark.asyncio
    async def test_request_with_retry_429_exhausted(self, sec_client, mock_aiohttp_session):
        """Test 429 response when retries are exhausted."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'):

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # Response: 429 with Retry-After
            response = AsyncMock()
            response.status = 429
            response.headers = {"Retry-After": "1"}
            response.__aenter__ = AsyncMock(return_value=response)
            response.__aexit__ = AsyncMock(return_value=None)

            # Configure the mock session.get to return a context manager that yields this response
            mock_aiohttp_session.get.return_value.__aenter__.return_value = response
            mock_aiohttp_session.get.return_value.__aexit__.return_value = None

            with pytest.raises(SECRateLimitError, match="Rate limit exceeded after 2 retries"):
                await sec_client._request_with_retry("http://test.com", max_retries=2)

    @pytest.mark.asyncio
    async def test_request_with_retry_5xx_then_success(self, sec_client, mock_aiohttp_session):
        """Test 5xx response with retry, then success."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'), \
             patch.object(sec_client, '_wait_with_shutdown_check') as mock_wait:

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # First response: 500 Internal Server Error
            response_500 = AsyncMock()
            response_500.status = 500
            response_500.__aenter__ = AsyncMock(return_value=response_500)
            response_500.__aexit__ = AsyncMock(return_value=None)

            # Second response: 200 OK
            response_200 = AsyncMock()
            response_200.status = 200
            response_200.read = AsyncMock(return_value=b'{"success": true}')
            response_200.headers = {"Content-Type": "application/json"}
            response_200.__aenter__ = AsyncMock(return_value=response_200)
            response_200.__aexit__ = AsyncMock(return_value=None)

            # Set up the mock session.get to return context managers that yield these responses
            mock_aiohttp_session.get.return_value.__aenter__.side_effect = [response_500, response_200]
            mock_aiohttp_session.get.return_value.__aexit__.side_effect = [None, None]

            result = await sec_client._request_with_retry("http://test.com", max_retries=2)
            assert result == {"success": True}
            # Should have called wait once for the retry delay
            assert mock_wait.call_count >= 1

    @pytest.mark.asyncio
    async def test_request_with_retry_5xx_exhausted(self, sec_client, mock_aiohttp_session):
        """Test 5xx response when retries are exhausted."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'):

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # Response: 500 Internal Server Error
            response = AsyncMock()
            response.status = 500
            response.__aenter__ = AsyncMock(return_value=response)
            response.__aexit__ = AsyncMock(return_value=None)

            # Configure the mock session.get to return a context manager that yields this response
            mock_aiohttp_session.get.return_value.__aenter__.return_value = response
            mock_aiohttp_session.get.return_value.__aexit__.return_value = None

            with pytest.raises(SECServerError, match="Server error 500 after 2 retries"):
                await sec_client._request_with_retry("http://test.com", max_retries=2)

    @pytest.mark.asyncio
    async def test_request_with_retry_network_error_then_success(self, sec_client, mock_aiohttp_session):
        """Test network error with retry, then success."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'), \
             patch.object(sec_client, '_wait_with_shutdown_check') as mock_wait:

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # First call raises ClientError
            # Second call returns success
            response_200 = AsyncMock()
            response_200.status = 200
            response_200.read = AsyncMock(return_value=b'{"success": true}')
            response_200.headers = {"Content-Type": "application/json"}
            response_200.__aenter__ = AsyncMock(return_value=response_200)
            response_200.__aexit__ = AsyncMock(return_value=None)

            # Set up the mock session.get to raise ClientError first, then return success
            mock_aiohttp_session.get.return_value.__aenter__.side_effect = ClientError("Network error")
            mock_aiohttp_session.get.return_value.__aexit__.side_effect = None

            # Second call - need to set up the return value for when it's called again
            # We'll use a side effect that changes on the second call
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call raises ClientError
                    raise ClientError("Network error")
                else:
                    # Second call returns success response
                    context_manager = AsyncMock()
                    context_manager.__aenter__.return_value = response_200
                    context_manager.__aexit__.return_value = None
                    return context_manager

            sec_client._session.get.side_effect = side_effect

            result = await sec_client._request_with_retry("http://test.com", max_retries=2)
            assert result == {"success": True}
            # Should have called wait for network error retry
            assert mock_wait.call_count >= 1

    @pytest.mark.asyncio
    async def test_request_with_retry_network_error_exhausted(self, sec_client, mock_aiohttp_session):
        """Test that network errors retry indefinitely (until shutdown)."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'), \
             patch.object(sec_client, '_check_shutdown') as mock_check_shutdown, \
             patch.object(sec_client, '_wait_with_shutdown_check') as mock_wait:

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # Simulate shutdown being requested after first wait
            mock_check_shutdown.side_effect = [None, asyncio.CancelledError("Shutdown")]

            # Always return network error
            error_response = AsyncMock()
            error_response.__aenter__ = AsyncMock(side_effect=ClientError("Network error"))
            error_response.__aexit__ = AsyncMock(return_value=None)

            # Configure the mock session.get to return a context manager that yields this error
            mock_aiohttp_session.get.return_value.__aenter__.side_effect = ClientError("Network error")
            mock_aiohttp_session.get.return_value.__aexit__.return_value = None

            with pytest.raises(asyncio.CancelledError):
                await sec_client._request_with_retry("http://test.com", max_retries=2)

            # Should have tried to wait (network errors wait indefinitely)
            assert mock_wait.call_count >= 1

    @pytest.mark.asyncio
    async def test_request_with_retry_client_response_error(self, sec_client, mock_aiohttp_session):
        """Test handling of ClientResponseError."""
        with patch.object(sec_client, '_ensure_session'), \
             patch.object(sec_client, '_rate_limit'):

            # Set the session on the client to our mock
            sec_client._session = mock_aiohttp_session

            # Configure the mock session.get to return a context manager that yields an error
            error_context_manager = AsyncMock()
            error_context_manager.__aenter__ = AsyncMock(side_effect=ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=400,
                message="Bad Request",
                headers={}
            ))
            error_context_manager.__aexit__ = AsyncMock(return_value=None)

            mock_aiohttp_session.get.return_value = error_context_manager

            with pytest.raises(SECClientError, match="HTTP 400"):
                await sec_client._request_with_retry("http://test.com")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])