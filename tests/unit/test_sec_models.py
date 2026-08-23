"""Unit tests for SEC provider models and utilities."""


from financial_database.providers.sec.models import (
    SEC_EXCHANGE_MAP,
    SECCompany,
    SECCompanyFact,
    SECCompanyFacts,
    SECCompanyFactValue,
    SECFiling,
    SECSubmissions,
    get_exchange_mappings,
    normalize_accession_number,
    normalize_cik,
    normalize_exchange,
)


class TestCikNormalization:
    """Tests for CIK normalization."""

    def test_normalize_cik_integer(self):
        assert normalize_cik(320193) == "0000320193"

    def test_normalize_cik_string_with_leading_zeros(self):
        assert normalize_cik("0000320193") == "0000320193"

    def test_normalize_cik_string_without_leading_zeros(self):
        assert normalize_cik("320193") == "0000320193"

    def test_normalize_cik_string_with_spaces(self):
        assert normalize_cik("  320193  ") == "0000320193"

    def test_normalize_cik_zero(self):
        assert normalize_cik(0) == "0000000000"
        assert normalize_cik("0") == "0000000000"

    def test_normalize_cik_preserves_ten_digits(self):
        # CIK should always be 10 digits
        assert len(normalize_cik("123")) == 10
        assert len(normalize_cik(123)) == 10
        assert len(normalize_cik("0000000123")) == 10


class TestAccessionNormalization:
    """Tests for accession number normalization."""

    def test_normalize_accession_standard(self):
        assert normalize_accession_number("0000320193-23-000106") == "000032019323000106"

    def test_normalize_accession_no_dashes(self):
        assert normalize_accession_number("000032019323000106") == "000032019323000106"

    def test_normalize_accession_with_spaces(self):
        assert normalize_accession_number(" 0000320193-23-000106 ") == "000032019323000106"

    def test_normalize_accession_empty(self):
        assert normalize_accession_number("") == ""


class TestExchangeNormalization:
    """Tests for exchange normalization."""

    def test_normalize_exchange_nasdaq(self):
        result = normalize_exchange("NASDAQ")
        assert result is not None
        assert result.internal_code == "NASDAQ"
        assert result.mic == "XNAS"

    def test_normalize_exchange_nyse(self):
        result = normalize_exchange("NYSE")
        assert result is not None
        assert result.internal_code == "NYSE"
        assert result.mic == "XNYS"

    def test_normalize_exchange_nyse_american(self):
        result = normalize_exchange("NYSE American")
        assert result is not None
        assert result.internal_code == "NYSEAMERICAN"

    def test_normalize_exchange_nyse_arca(self):
        result = normalize_exchange("NYSE Arca")
        assert result is not None
        assert result.internal_code == "NYSEARCA"

    def test_normalize_exchange_unknown(self):
        result = normalize_exchange("UNKNOWN_EXCHANGE")
        assert result is None

    def test_normalize_exchange_none(self):
        result = normalize_exchange(None)
        assert result is None

    def test_normalize_exchange_empty(self):
        result = normalize_exchange("")
        assert result is None

    def test_get_exchange_mappings(self):
        mappings = get_exchange_mappings()
        assert len(mappings) > 0
        codes = {m.internal_code for m in mappings}
        assert "NASDAQ" in codes
        assert "NYSE" in codes

    def test_sec_exchange_map(self):
        assert "NASDAQ" in SEC_EXCHANGE_MAP
        assert "NYSE" in SEC_EXCHANGE_MAP


class TestSECCompany:
    """Tests for SECCompany model."""

    def test_sec_company_creation(self):
        company = SECCompany(
            cik="320193",
            name="Apple Inc.",
            ticker="AAPL",
            exchange="NASDAQ",
        )
        assert company.cik == "320193"
        assert company.name == "Apple Inc."
        assert company.ticker == "AAPL"
        assert company.exchange == "NASDAQ"

    def test_sec_company_normalized_cik(self):
        company = SECCompany(cik="320193", name="Test")
        assert company.normalized_cik == "0000320193"


class TestSECFiling:
    """Tests for SECFiling model."""

    def test_sec_filing_creation(self):
        from datetime import date
        filing = SECFiling(
            accession_number="0000320193-23-000106",
            form="10-K",
            filing_date=date(2023, 11, 3),
            period_end=date(2023, 9, 30),
        )
        assert filing.accession_number == "0000320193-23-000106"
        assert filing.form == "10-K"

    def test_sec_filing_normalized_accession(self):
        filing = SECFiling(
            accession_number="0000320193-23-000106",
            form="10-K",
            filing_date=None,
            period_end=None,
        )
        assert filing.normalized_accession == "000032019323000106"


class TestSECSubmissions:
    """Tests for SECSubmissions model."""

    def test_sec_submissions_creation(self):
        submissions = SECSubmissions(
            cik="0000320193",
            entity_name="Apple Inc.",
            filings=[],
        )
        assert submissions.cik == "0000320193"
        assert submissions.entity_name == "Apple Inc."

    def test_sec_submissions_normalized_cik(self):
        submissions = SECSubmissions(cik="320193", entity_name="Test")
        assert submissions.normalized_cik == "0000320193"


class TestSECCompanyFact:
    """Tests for SECCompanyFact model."""

    def test_sec_company_fact_creation(self):
        fact = SECCompanyFact(
            concept="Assets",
            namespace="us-gaap",
            label="Assets",
            unit="USD",
            values=[],
        )
        assert fact.concept == "Assets"
        assert fact.namespace == "us-gaap"


class TestSECCompanyFactValue:
    """Tests for SECCompanyFactValue model."""

    def test_sec_company_fact_value_creation(self):
        from datetime import date
        value = SECCompanyFactValue(
            value=1000000,
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            fiscal_year=2023,
            fiscal_period="FY",
            is_instant=False,
        )
        assert value.value == 1000000
        assert value.fiscal_year == 2023
        assert value.is_instant is False

    def test_sec_company_fact_value_instant(self):
        from datetime import date
        value = SECCompanyFactValue(
            value=500000,
            period_start=None,
            period_end=date(2023, 12, 31),
            is_instant=True,
        )
        assert value.is_instant is True
        assert value.period_start is None


class TestSECCompanyFacts:
    """Tests for SECCompanyFacts model."""

    def test_sec_company_facts_creation(self):
        facts = SECCompanyFacts(
            cik="0000320193",
            entity_name="Apple Inc.",
            facts={},
        )
        assert facts.cik == "0000320193"

    def test_sec_company_facts_normalized_cik(self):
        facts = SECCompanyFacts(cik="320193", entity_name="Test")
        assert facts.normalized_cik == "0000320193"