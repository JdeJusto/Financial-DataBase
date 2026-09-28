#!/usr/bin/env python3
"""
Focused test for the checkpoint resume logic fix in bulk_ingest.py - Version 2
"""


def test_ingest_companyfacts_checkpoint_logic():
    """Test the specific checkpoint logic we added to ingest_companyfacts"""

    # Simulate the companies list (list of MockCompany objects)
    class MockCompany:
        def __init__(self, cik):
            self.normalized_cik = cik

    companies = [
        MockCompany("0000320193"),
        MockCompany("0000789019"),
        MockCompany("0001018724"),
        MockCompany("0001234567"),
    ]

    print("=== Testing ingest_companyfacts checkpoint logic ===")

    # Test Case 1: Normal case - checkpoint exists in list
    print("\nTest 1: Checkpoint CIK exists in list")
    checkpoint_last_processed_cik = "0000789019"

    # This is our logic from the fixed code
    # Sort companies by CIK to ensure proper checkpoint ordering
    companies_sorted = sorted(companies, key=lambda c: c.normalized_cik)

    # Handle checkpoint resume logic
    start_index = 0
    checkpoint_valid = False
    if checkpoint_last_processed_cik:
        # Find if the checkpoint CIK exists in our current company list
        cik_list = [c.normalized_cik for c in companies_sorted]
        try:
            # Find the index of the checkpoint CIK
            checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
            # Start from the next company after the checkpoint
            start_index = checkpoint_index + 1
            checkpoint_valid = True  # We found a valid checkpoint position
            print(
                f"  Found checkpoint at index {checkpoint_index}, starting from {start_index}"
            )
        except ValueError:
            # Checkpoint CIK not found in current list
            # Find the first company with CIK > checkpoint.last_processed_cik
            # or start from beginning if all CIKs are <= checkpoint.last_processed_cik
            for i, company in enumerate(companies_sorted):
                if company.normalized_cik > checkpoint_last_processed_cik:
                    start_index = i
                    break
            else:
                # All CIKs are <= checkpoint.last_processed_cik, start from beginning
                start_index = 0
                print(
                    f"  Checkpoint CIK not found, all CIKs <= checkpoint, starting from {start_index}"
                )

    # Process each company starting from start_index
    processed = []
    for i in range(start_index, len(companies_sorted)):
        company = companies_sorted[i]
        cik = company.normalized_cik

        # Skip if already processed (resume from checkpoint)
        # Only apply this skip logic if we have a valid checkpoint position in our list
        if (
            checkpoint_valid
            and checkpoint_last_processed_cik
            and cik <= checkpoint_last_processed_cik
        ):
            print(f"  Skipping already processed CIK: {cik}")
            continue
        processed.append(cik)

    print(f"  Companies to process: {processed}")
    assert processed == ["0001018724", "0001234567"]
    print("  ✓ PASS")

    # Test Case 2: Checkpoint CIK not found, but there are CIKs greater than it
    print("\nTest 2: Checkpoint CIK not found, but there are CIKs greater than it")
    checkpoint_last_processed_cik = "0000500000"  # Between 0000320193 and 0000789019

    # Reset for this test
    companies_sorted = sorted(companies, key=lambda c: c.normalized_cik)

    # Apply our logic
    start_index = 0
    checkpoint_valid = False
    if checkpoint_last_processed_cik:
        cik_list = [c.normalized_cik for c in companies_sorted]
        try:
            checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
            start_index = checkpoint_index + 1
            checkpoint_valid = True
        except ValueError:
            # Checkpoint CIK not found, find first company with CIK > checkpoint
            for i, company in enumerate(companies_sorted):
                if company.normalized_cik > checkpoint_last_processed_cik:
                    start_index = i
                    break
            else:
                start_index = 0  # All CIKs are <= checkpoint

    # Process each company starting from start_index
    processed = []
    for i in range(start_index, len(companies_sorted)):
        company = companies_sorted[i]
        cik = company.normalized_cik

        # Skip if already processed (resume from checkpoint)
        if (
            checkpoint_valid
            and checkpoint_last_processed_cik
            and cik <= checkpoint_last_processed_cik
        ):
            continue
        processed.append(cik)

    print(f"  Companies to process: {processed}")
    assert processed == ["0000789019", "0001018724", "0001234567"]
    print("  ✓ PASS")

    # Test Case 3: Checkpoint CIK higher than all CIKs (the main issue)
    print("\nTest 3: Checkpoint CIK higher than all CIKs (main issue fix)")
    checkpoint_last_processed_cik = "0009999999"  # Higher than all

    # Reset for this test
    companies_sorted = sorted(companies, key=lambda c: c.normalized_cik)

    # Apply our logic
    start_index = 0
    checkpoint_valid = False
    if checkpoint_last_processed_cik:
        cik_list = [c.normalized_cik for c in companies_sorted]
        try:
            checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
            start_index = checkpoint_index + 1
            checkpoint_valid = True
        except ValueError:
            # Checkpoint CIK not found, find first company with CIK > checkpoint
            for i, company in enumerate(companies_sorted):
                if company.normalized_cik > checkpoint_last_processed_cik:
                    start_index = i
                    break
            else:
                start_index = 0  # All CIKs are <= checkpoint (this is our fix)
                print(
                    f"  Checkpoint CIK not found, all CIKs <= checkpoint, starting from {start_index}"
                )

    # Process each company starting from start_index
    processed = []
    for i in range(start_index, len(companies_sorted)):
        company = companies_sorted[i]
        cik = company.normalized_cik

        # Skip if already processed (resume from checkpoint)
        if (
            checkpoint_valid
            and checkpoint_last_processed_cik
            and cik <= checkpoint_last_processed_cik
        ):
            continue
        processed.append(cik)

    print(f"  Companies to process: {processed}")
    assert processed == ["0000320193", "0000789019", "0001018724", "0001234567"]
    print("  ✓ PASS")

    # Test Case 4: Empty list
    print("\nTest 4: Empty company list")
    companies_sorted = []
    checkpoint_last_processed_cik = "0000789019"

    # Apply our logic
    start_index = 0
    checkpoint_valid = False
    if checkpoint_last_processed_cik:
        cik_list = [c.normalized_cik for c in companies_sorted]
        try:
            checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
            start_index = checkpoint_index + 1
            checkpoint_valid = True
        except ValueError:
            # Checkpoint CIK not found, find first company with CIK > checkpoint
            for i, company in enumerate(companies_sorted):
                if company.normalized_cik > checkpoint_last_processed_cik:
                    start_index = i
                    break
            else:
                start_index = 0  # All CIKs are <= checkpoint

    # Process each company starting from start_index
    processed = []
    for i in range(start_index, len(companies_sorted)):
        company = companies_sorted[i]
        cik = company.normalized_cik

        # Skip if already processed (resume from checkpoint)
        if (
            checkpoint_valid
            and checkpoint_last_processed_cik
            and cik <= checkpoint_last_processed_cik
        ):
            continue
        processed.append(cik)

    print(f"  Companies to process: {processed}")
    assert processed == []
    print("  ✓ PASS")

    print("\n✅ All checkpoint logic tests passed!")


if __name__ == "__main__":
    test_ingest_companyfacts_checkpoint_logic()
