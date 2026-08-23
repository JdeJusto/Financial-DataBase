-- 0016_fix_duplicate_listings.sql
-- Fix duplicate listings issue: prevent duplicate active listings for same company+exchange+ticker+share_class
-- The original unique constraint (company_id, exchange_id, share_class, listing_date) doesn't prevent
-- duplicates when listing_date is NULL.

-- Add partial unique index to prevent duplicate active listings for same company+exchange+ticker+share_class
-- This allows historical listings (delisted) but prevents duplicate active listings
CREATE UNIQUE INDEX idx_company_listings_unique_active
    ON company_listings (company_id, exchange_id, ticker, share_class)
    WHERE delisting_date IS NULL;

-- Also add unique constraint for the case when listing_date is provided
-- to prevent duplicate listings with same date
-- (The existing unique constraint already handles this: UNIQUE (company_id, exchange_id, share_class, listing_date))

COMMENT ON INDEX idx_company_listings_unique_active IS 'Prevents duplicate active listings for same company+exchange+ticker+share_class. Allows historical (delisted) listings.';