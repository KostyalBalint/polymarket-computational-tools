/*
  Migration: Optimize MarketOutcome and TokenPrice relationship

  Changes:
  - Add auto-incrementing integer ID to MarketOutcome (keep clobTokenId as unique)
  - Update TokenPrice to use integer foreign key instead of string

  This migration preserves all existing data by:
  1. Adding new columns as nullable
  2. Populating them from existing data IN BATCHES to avoid disk space issues
  3. Making them NOT NULL after population
  4. Cleaning up old columns and constraints
*/

-- Step 1: Drop existing foreign key constraint
ALTER TABLE "polymarket"."TokenPrice" DROP CONSTRAINT IF EXISTS "TokenPrice_tokenId_fkey";

-- Step 2: Add auto-incrementing ID to MarketOutcome (keep existing primary key temporarily)
ALTER TABLE "polymarket"."MarketOutcome" ADD COLUMN "id" SERIAL;

-- Step 3: Add marketOutcomeId to TokenPrice as nullable (will populate it next)
ALTER TABLE "polymarket"."TokenPrice" ADD COLUMN "marketOutcomeId" INTEGER;

-- Step 4: Create temporary index to speed up the update
-- Note: Cannot use CONCURRENTLY inside transaction, but that's OK for a migration
CREATE INDEX IF NOT EXISTS "temp_TokenPrice_tokenId_idx" ON "polymarket"."TokenPrice"("tokenId") WHERE "marketOutcomeId" IS NULL;

-- Step 5: Populate marketOutcomeId in batches using a DO block
-- This processes ~1 million rows at a time to avoid excessive temp space usage
DO $$
DECLARE
  batch_size INTEGER := 1000000;
  rows_updated INTEGER;
  total_updated INTEGER := 0;
BEGIN
  RAISE NOTICE 'Starting batched update of TokenPrice.marketOutcomeId...';

  LOOP
    -- Update a batch of rows
    WITH batch AS (
      SELECT tp.id
      FROM "polymarket"."TokenPrice" tp
      WHERE tp."marketOutcomeId" IS NULL
      LIMIT batch_size
    )
    UPDATE "polymarket"."TokenPrice" tp
    SET "marketOutcomeId" = mo.id
    FROM "polymarket"."MarketOutcome" mo, batch
    WHERE tp."tokenId" = mo."clobTokenId"
      AND tp.id = batch.id;

    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    total_updated := total_updated + rows_updated;

    RAISE NOTICE 'Updated % rows (total: %)', rows_updated, total_updated;

    -- Exit when no more rows to update
    EXIT WHEN rows_updated = 0;

    -- Small delay to allow other operations if needed
    PERFORM pg_sleep(0.1);
  END LOOP;

  RAISE NOTICE 'Batched update completed. Total rows updated: %', total_updated;
END $$;

-- Step 6: Drop temporary index
DROP INDEX IF EXISTS "polymarket"."temp_TokenPrice_tokenId_idx";

-- Step 7: Check for any remaining NULL values (shouldn't be any)
DO $$
DECLARE
  null_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO null_count
  FROM "polymarket"."TokenPrice"
  WHERE "marketOutcomeId" IS NULL;

  IF null_count > 0 THEN
    RAISE EXCEPTION 'Found % rows with NULL marketOutcomeId after update. Migration cannot continue.', null_count;
  END IF;

  RAISE NOTICE 'All TokenPrice rows have marketOutcomeId set. Proceeding...';
END $$;

-- Step 8: Make marketOutcomeId NOT NULL (safe now because it's populated)
ALTER TABLE "polymarket"."TokenPrice" ALTER COLUMN "marketOutcomeId" SET NOT NULL;

-- Step 9: Drop old indexes on TokenPrice.tokenId
DROP INDEX IF EXISTS "polymarket"."TokenPrice_tokenId_idx";
DROP INDEX IF EXISTS "polymarket"."TokenPrice_tokenId_timestamp_key";

-- Step 10: Change MarketOutcome primary key from clobTokenId to id
ALTER TABLE "polymarket"."MarketOutcome" DROP CONSTRAINT "MarketOutcome_pkey";
ALTER TABLE "polymarket"."MarketOutcome" ADD CONSTRAINT "MarketOutcome_pkey" PRIMARY KEY ("id");

-- Step 11: Make clobTokenId unique (it was the old primary key, so already unique)
CREATE UNIQUE INDEX "MarketOutcome_clobTokenId_key" ON "polymarket"."MarketOutcome"("clobTokenId");

-- Step 12: Add index on clobTokenId for lookups
CREATE INDEX "MarketOutcome_clobTokenId_idx" ON "polymarket"."MarketOutcome"("clobTokenId");

-- Step 13: Drop the old tokenId column from TokenPrice
ALTER TABLE "polymarket"."TokenPrice" DROP COLUMN "tokenId";

-- Step 14: Create new indexes on TokenPrice
CREATE INDEX "TokenPrice_marketOutcomeId_idx" ON "polymarket"."TokenPrice"("marketOutcomeId");
CREATE UNIQUE INDEX "TokenPrice_marketOutcomeId_timestamp_key" ON "polymarket"."TokenPrice"("marketOutcomeId", "timestamp");

-- Step 15: Add foreign key constraint
ALTER TABLE "polymarket"."TokenPrice" ADD CONSTRAINT "TokenPrice_marketOutcomeId_fkey"
  FOREIGN KEY ("marketOutcomeId") REFERENCES "polymarket"."MarketOutcome"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Migration complete
DO $$
BEGIN
  RAISE NOTICE '=================================================';
  RAISE NOTICE 'Migration completed successfully!';
  RAISE NOTICE '=================================================';
END $$;