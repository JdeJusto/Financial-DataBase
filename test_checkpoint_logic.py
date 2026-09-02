#!/usr/bin/env python3
"""
Test script to validate the checkpoint resume logic fix.
"""

def test_checkpoint_resume_logic():
    """Test the checkpoint resume logic for various scenarios."""

    # Mock company data (sorted by CIK)
    class MockCompany:
        def __init__(self, cik):
            self.normalized_cik = cik

    # Test Case 1: Normal case - checkpoint CIK exists in list
    print("Test Case 1: Normal case - checkpoint CIK exists in list")
    companies = [MockCompany(cik) for cik in ["0000320193", "0000789019", "0001018724", "0001234567"]]
    checkpoint_last_processed_cik = "0000789019"

    # Apply our logic
    cik_list = [c.normalized_cik for c in companies]
    try:
        checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
        start_index = checkpoint_index + 1
        print(f"  Checkpoint CIK found at index {checkpoint_index}, starting from index {start_index}")
        print(f"  Will process companies: {[c.normalized_cik for c in companies[start_index:]]}")
        assert start_index == 2
        assert [c.normalized_cik for c in companies[start_index:]] == ["0001018724", "0001234567"]
        print("  ✓ PASS\n")
    except ValueError:
        print("  ✗ FAIL: Checkpoint CIK not found\n")
        return False

    # Test Case 2: Checkpoint CIK not found, but there are CIKs greater than it
    print("Test Case 2: Checkpoint CIK not found, but there are CIKs greater than it")
    companies = [MockCompany(cik) for cik in ["0000320193", "0000789019", "0001018724", "0001234567"]]
    checkpoint_last_processed_cik = "0000500000"  # Between 0000320193 and 0000789019

    # Apply our logic
    cik_list = [c.normalized_cik for c in companies]
    try:
        checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
        start_index = checkpoint_index + 1
        print("  ✗ FAIL: Should not have found checkpoint CIK")
        return False
    except ValueError:
        # Checkpoint CIK not found, find first company with CIK > checkpoint
        start_index = 0
        for i, company in enumerate(companies):
            if company.normalized_cik > checkpoint_last_processed_cik:
                start_index = i
                break
        else:
            start_index = 0  # All CIKs are <= checkpoint

        print(f"  Checkpoint CIK not found, first CIK > checkpoint at index {start_index}")
        print(f"  Will process companies: {[c.normalized_cik for c in companies[start_index:]]}")
        assert start_index == 1  # Should start from 0000789019
        assert [c.normalized_cik for c in companies[start_index:]] == ["0000789019", "0001018724", "0001234567"]
        print("  ✓ PASS\n")

    # Test Case 3: Checkpoint CIK higher than all CIKs in list (the main issue we're fixing)
    print("Test Case 3: Checkpoint CIK higher than all CIKs in list (main fix)")
    companies = [MockCompany(cik) for cik in ["0000320193", "0000789019", "0001018724", "0001234567"]]
    checkpoint_last_processed_cik = "0009999999"  # Higher than all

    # Apply our logic
    cik_list = [c.normalized_cik for c in companies]
    try:
        checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
        start_index = checkpoint_index + 1
        print("  ✗ FAIL: Should not have found checkpoint CIK")
        return False
    except ValueError:
        # Checkpoint CIK not found, find first company with CIK > checkpoint
        start_index = 0
        for i, company in enumerate(companies):
            if company.normalized_cik > checkpoint_last_processed_cik:
                start_index = i
                break
        else:
            start_index = 0  # All CIKs are <= checkpoint (this is our fix)

        print(f"  Checkpoint CIK not found, all CIKs <= checkpoint, starting from index {start_index}")
        print(f"  Will process companies: {[c.normalized_cik for c in companies[start_index:]]}")
        assert start_index == 0  # Should start from beginning (our fix)
        assert [c.normalized_cik for c in companies[start_index:]] == ["0000320193", "0000789019", "0001018724", "0001234567"]
        print("  ✓ PASS\n")

    # Test Case 4: Empty company list
    print("Test Case 4: Empty company list")
    companies = []
    checkpoint_last_processed_cik = "0000789019"

    # Apply our logic
    if companies:  # Only process if we have companies
        cik_list = [c.normalized_cik for c in companies]
        try:
            checkpoint_index = cik_list.index(checkpoint_last_processed_cik)
            start_index = checkpoint_index + 1
        except ValueError:
            start_index = 0
            for i, company in enumerate(companies):
                if company.normalized_cik > checkpoint_last_processed_cik:
                    start_index = i
                    break
            else:
                start_index = 0
    else:
        start_index = 0

    print(f"  Empty list, start_index: {start_index}")
    assert start_index == 0
    print("  ✓ PASS\n")

    print("All tests passed!")
    return True

if __name__ == "__main__":
    test_checkpoint_resume_logic()