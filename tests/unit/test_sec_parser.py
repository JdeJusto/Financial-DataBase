"""Unit tests for SEC parser."""

from datetime import date

import pytest

from financial_database.providers.sec.models import (
    SECCompany,
    SECCompanyFact,
    SECCompanyFacts,
    SECCompanyFactValue,
    SECFiling,
    SECSubmissions,
)
from financial_database.providers.sec.parser import (
    ParsedCompany,
    ParsedFinancialFact,
    SECParser,
    validate_financial_fact,
)


class TestSECParser:
    """Tests for SECParser."""

    @pytest.fixture
    def parser(self):
        return SECParser()

    @pytest.fixture
    def sample_sec_company(self):
        return SECCompany(
            cik="0000320193",
            name="Apple Inc.",
            ticker="AAPL",
            exchange="NASDAQ",
            sic="3571",
            sic_description="Electronic Computers",
        )

    @pytest.fixture
    def sample_sec_company_no_ticker(self):
        return SECCompany(
            cik="0000000001",
            name="Private Company Inc.",
            ticker=None,
            exchange=None,
        )

    def test_parse_company_with_ticker_and_exchange(self, parser, sample_sec_company):
        parsed = parser.parse_company(sample_sec_company)

        assert isinstance(parsed, ParsedCompany)
        assert parsed.cik == "0000320193"
        assert parsed.legal_name == "Apple Inc."
        assert parsed.country == "USA"
        assert parsed.currency == "USD"
        assert "CIK" in parsed.identifiers
        assert parsed.identifiers["CIK"] == "0000320193"
        assert "TICKER" in parsed.identifiers
        assert parsed.identifiers["TICKER"] == "AAPL"
        assert len(parsed.listings) == 1
        assert parsed.listings[0].ticker == "AAPL"
        assert parsed.listings[0].exchange_code == "NASDAQ"
        assert parsed.listings[0].is_primary is True

    def test_parse_company_without_ticker(self, parser, sample_sec_company_no_ticker):
        parsed = parser.parse_company(sample_sec_company_no_ticker)

        assert parsed.cik == "0000000001"
        assert parsed.legal_name == "Private Company Inc."
        assert "CIK" in parsed.identifiers
        assert "TICKER" not in parsed.identifiers
        assert len(parsed.listings) == 0

    def test_parse_company_unknown_exchange(self, parser):
        company = SECCompany(
            cik="0000000002",
            name="Unknown Exchange Co.",
            ticker="UNKN",
            exchange="UNKNOWN_EXCHANGE",
        )
        parsed = parser.parse_company(company)

        assert len(parsed.listings) == 0
        assert "TICKER" in parsed.identifiers

    def test_parse_filings_filters_financial_forms(self, parser):
        submissions = SECSubmissions(
            cik="0000320193",
            entity_name="Apple Inc.",
            filings=[
                SECFiling(
                    accession_number="0000320193-23-000106",
                    form="10-K",
                    filing_date=date(2023, 11, 3),
                    period_end=date(2023, 9, 30),
                    fiscal_year=2023,
                    fiscal_period="FY",
                ),
                SECFiling(
                    accession_number="0000320193-23-000010",
                    form="10-Q",
                    filing_date=date(2023, 8, 3),
                    period_end=date(2023, 6, 24),
                    fiscal_year=2023,
                    fiscal_period="Q3",
                ),
                SECFiling(
                    accession_number="0000320193-23-000005",
                    form="8-K",
                    filing_date=date(2023, 5, 1),
                    period_end=date(2023, 5, 1),
                    fiscal_year=2023,
                    fiscal_period="Q2",
                ),
                SECFiling(
                    accession_number="0000320193-23-000001",
                    form="DEF 14A",
                    filing_date=date(2023, 1, 15),
                    period_end=date(2023, 1, 15),
                ),
            ],
        )

        parsed = parser.parse_filings(submissions)

        # Should include 10-K, 10-Q, 8-K (financial forms)
        # Should exclude DEF 14A (proxy statement)
        assert len(parsed) == 3
        forms = {f.form for f in parsed}
        assert "10-K" in forms
        assert "10-Q" in forms
        assert "8-K" in forms
        assert "DEF 14A" not in forms

    def test_parse_filings_amended_forms(self, parser):
        submissions = SECSubmissions(
            cik="0000320193",
            entity_name="Apple Inc.",
            filings=[
                SECFiling(
                    accession_number="0000320193-23-000106",
                    form="10-K",
                    filing_date=date(2023, 11, 3),
                    period_end=date(2023, 9, 30),
                ),
                SECFiling(
                    accession_number="0000320193-23-000107",
                    form="10-K/A",
                    filing_date=date(2023, 12, 1),
                    period_end=date(2023, 9, 30),
                    is_amended=True,
                ),
            ],
        )

        parsed = parser.parse_filings(submissions)

        assert len(parsed) == 2
        amended = [f for f in parsed if f.is_amended]
        assert len(amended) == 1
        assert amended[0].form == "10-K/A"

    def test_parse_company_facts(self, parser):
        facts = SECCompanyFacts(
            cik="0000320193",
            entity_name="Apple Inc.",
            facts={
                "us-gaap": {
                    "Assets": SECCompanyFact(
                        concept="Assets",
                        namespace="us-gaap",
                        unit="USD",
                        values=[
                            SECCompanyFactValue(
                                value=352755000000,
                                period_start=date(2022, 10, 1),
                                period_end=date(2023, 9, 30),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2023, 11, 3),
                                accession_number="0000320193-23-000106",
                                is_instant=False,
                            ),
                            SECCompanyFactValue(
                                value=29965000000,
                                period_start=None,
                                period_end=date(2023, 9, 30),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2023, 11, 3),
                                accession_number="0000320193-23-000106",
                                is_instant=True,
                            ),
                        ],
                    ),
                },
                "dei": {
                    "EntityRegistrantName": SECCompanyFact(
                        concept="EntityRegistrantName",
                        namespace="dei",
                        unit="pure",
                        values=[
                            SECCompanyFactValue(
                                value="Apple Inc.",
                                period_start=None,
                                period_end=date(2023, 9, 30),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2023, 11, 3),
                                accession_number="0000320193-23-000106",
                                is_instant=True,
                            ),
                        ],
                    ),
                },
            },
        )

        filing_id_map = {
            "000032019323000106": "filing-uuid-1",
        }

        parsed_facts = parser.parse_company_facts(facts, filing_id_map)

        assert (
            len(parsed_facts) == 2
        )  # 2 Assets (1 duration + 1 instant), non-numeric DEI skipped

        # Check first Assets fact (duration)
        assets_duration = next(
            f for f in parsed_facts if f.concept == "Assets" and not f.is_instant
        )
        assert assets_duration.namespace == "us-gaap"
        assert assets_duration.value == 352755000000
        assert assets_duration.unit == "USD"
        assert assets_duration.period_start == date(2022, 10, 1)
        assert assets_duration.period_end == date(2023, 9, 30)
        assert assets_duration.fiscal_year == 2023
        assert assets_duration.fiscal_period == "FY"
        assert assets_duration.filing_id == "filing-uuid-1"
        assert assets_duration.is_instant is False

        # Check instant fact
        cash_instant = next(
            f for f in parsed_facts if f.is_instant and f.concept == "Assets"
        )
        assert cash_instant.period_start is None
        assert cash_instant.period_end == date(2023, 9, 30)
        assert cash_instant.is_instant is True

        # Check source_id format
        assert "us-gaap:Assets" in assets_duration.source_id
        assert "000032019323000106" in assets_duration.source_id

    def test_parse_company_facts_preserves_value_unit(self, parser):
        """Value-level unit (shares, USD/shares, pure) must override concept unit."""
        facts = SECCompanyFacts(
            cik="0000320193",
            entity_name="Apple Inc.",
            facts={
                "us-gaap": {
                    "CommonStockSharesOutstanding": SECCompanyFact(
                        concept="CommonStockSharesOutstanding",
                        namespace="us-gaap",
                        unit="",  # SEC provides no concept-level unit
                        values=[
                            SECCompanyFactValue(
                                value=15500000000,
                                unit="shares",
                                period_start=None,
                                period_end=date(2023, 9, 30),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2023, 11, 3),
                                accession_number="0000320193-23-000106",
                                is_instant=True,
                            ),
                        ],
                    ),
                    "EarningsPerShareBasic": SECCompanyFact(
                        concept="EarningsPerShareBasic",
                        namespace="us-gaap",
                        unit="",
                        values=[
                            SECCompanyFactValue(
                                value=6.13,
                                unit="USD/shares",
                                period_start=date(2022, 10, 1),
                                period_end=date(2023, 9, 30),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2023, 11, 3),
                                accession_number="0000320193-23-000106",
                                is_instant=False,
                            ),
                        ],
                    ),
                },
            },
        )

        parsed = parser.parse_company_facts(facts, {})

        assert len(parsed) == 2
        shares = next(f for f in parsed if f.concept == "CommonStockSharesOutstanding")
        eps = next(f for f in parsed if f.concept == "EarningsPerShareBasic")
        assert shares.unit == "shares"
        assert eps.unit == "USD/shares"

    def test_parse_company_facts_defaults_unit_to_usd(self, parser):
        """Facts with no unit anywhere fall back to USD."""
        facts = SECCompanyFacts(
            cik="0000320193",
            entity_name="Apple Inc.",
            facts={
                "us-gaap": {
                    "Revenue": SECCompanyFact(
                        concept="Revenue",
                        namespace="us-gaap",
                        unit="",
                        values=[
                            SECCompanyFactValue(
                                value=383285000000,
                                unit=None,
                                period_start=date(2022, 10, 1),
                                period_end=date(2023, 9, 30),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2023, 11, 3),
                                accession_number="0000320193-23-000106",
                                is_instant=False,
                            ),
                        ],
                    ),
                },
            },
        )

        parsed = parser.parse_company_facts(facts, {})
        assert len(parsed) == 1
        assert parsed[0].unit == "USD"

    def test_parse_company_facts_uses_decimal_preserving_precision(self, parser):
        """Fact values must be Decimal, not float, to avoid precision loss."""
        from decimal import Decimal

        facts = SECCompanyFacts(
            cik="0000320193",
            entity_name="Test",
            facts={
                "us-gaap": {
                    "BigInteger": SECCompanyFact(
                        concept="BigInteger",
                        namespace="us-gaap",
                        unit="USD",
                        values=[
                            SECCompanyFactValue(
                                value=123456789012345678901234567890,
                                period_start=date(2023, 1, 1),
                                period_end=date(2023, 12, 31),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2024, 1, 15),
                                accession_number="0000320193-24-000001",
                            ),
                        ],
                    ),
                    "PreciseDecimal": SECCompanyFact(
                        concept="PreciseDecimal",
                        namespace="us-gaap",
                        unit="USD/shares",
                        values=[
                            SECCompanyFactValue(
                                value="123456789.123456789012345678",
                                period_start=date(2023, 1, 1),
                                period_end=date(2023, 12, 31),
                                fiscal_year=2023,
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2024, 1, 15),
                                accession_number="0000320193-24-000001",
                            ),
                        ],
                    ),
                },
            },
        )

        parsed = parser.parse_company_facts(facts, {})

        big = next(f for f in parsed if f.concept == "BigInteger")
        precise = next(f for f in parsed if f.concept == "PreciseDecimal")
        assert isinstance(big.value, Decimal)
        assert isinstance(precise.value, Decimal)
        assert big.value == Decimal(123456789012345678901234567890)
        assert precise.value == Decimal("123456789.123456789012345678")

    def test_parse_company_facts_missing_fiscal_year_infers_from_period_end(
        self, parser
    ):
        facts = SECCompanyFacts(
            cik="0000320193",
            entity_name="Apple Inc.",
            facts={
                "us-gaap": {
                    "TestConcept": SECCompanyFact(
                        concept="TestConcept",
                        namespace="us-gaap",
                        unit="USD",
                        values=[
                            SECCompanyFactValue(
                                value=100,
                                period_start=date(2023, 1, 1),
                                period_end=date(2023, 12, 31),
                                fiscal_year=None,  # Missing
                                fiscal_period="FY",
                                form="10-K",
                                filing_date=date(2024, 1, 15),
                                accession_number="0000320193-24-000001",
                            ),
                        ],
                    ),
                },
            },
        )

        parsed = parser.parse_company_facts(facts, {})

        assert len(parsed) == 1
        assert parsed[0].fiscal_year == 2023  # Inferred from period_end

    def test_parse_company_facts_skips_no_fiscal_year_no_period_end(
        self, parser, caplog
    ):
        facts = SECCompanyFacts(
            cik="0000320193",
            entity_name="Apple Inc.",
            facts={
                "us-gaap": {
                    "BadConcept": SECCompanyFact(
                        concept="BadConcept",
                        namespace="us-gaap",
                        unit="USD",
                        values=[
                            SECCompanyFactValue(
                                value=100,
                                period_start=None,
                                period_end=None,
                                fiscal_year=None,
                                fiscal_period="FY",
                            ),
                        ],
                    ),
                },
            },
        )

        parsed = parser.parse_company_facts(facts, {})

        assert len(parsed) == 0
        assert any(
            "Skipping fact with no fiscal year" in r.message for r in caplog.records
        )


class TestValidateFinancialFact:
    """Tests for financial fact validation."""

    def test_valid_duration_fact(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="us-gaap",
            value=1000000,
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert errors == []

    def test_valid_instant_fact(self):
        fact = ParsedFinancialFact(
            concept="Assets",
            namespace="us-gaap",
            value=500000,
            unit="USD",
            period_start=None,
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
            is_instant=True,
        )
        errors = validate_financial_fact(fact)
        assert errors == []

    def test_missing_concept(self):
        fact = ParsedFinancialFact(
            concept="",
            namespace="us-gaap",
            value=100,
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert "concept is required" in errors

    def test_missing_namespace(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="",
            value=100,
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert "namespace is required" in errors

    def test_missing_value(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="us-gaap",
            value=None,
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert "value is required" in errors

    def test_missing_unit(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="us-gaap",
            value=100,
            unit="",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert "unit is required" in errors

    def test_missing_period_end(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="us-gaap",
            value=100,
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=None,
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert "period_end is required" in errors

    def test_invalid_fiscal_year(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="us-gaap",
            value=100,
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=1800,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert "fiscal_year must be valid" in errors

    def test_period_start_after_period_end(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="us-gaap",
            value=100,
            unit="USD",
            period_start=date(2023, 12, 31),
            period_end=date(2023, 1, 1),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
        )
        errors = validate_financial_fact(fact)
        assert "period_start must be <= period_end" in errors

    def test_instant_fact_with_period_start(self):
        fact = ParsedFinancialFact(
            concept="Assets",
            namespace="us-gaap",
            value=100,
            unit="USD",
            period_start=date(2023, 1, 1),  # Should be None for instant
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
            is_instant=True,
        )
        errors = validate_financial_fact(fact)
        assert "instant facts must have period_start = NULL" in errors

    def test_duration_fact_without_period_start(self):
        fact = ParsedFinancialFact(
            concept="Revenue",
            namespace="us-gaap",
            value=100,
            unit="USD",
            period_start=None,  # Should not be None for duration
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            provider_id="provider-uuid",
            is_instant=False,
        )
        errors = validate_financial_fact(fact)
        assert "duration facts must have period_start != NULL" in errors
