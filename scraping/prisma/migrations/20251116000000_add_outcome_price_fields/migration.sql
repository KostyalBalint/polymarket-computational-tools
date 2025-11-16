-- AlterTable: Add outcomePrice and priceUpdatedAt fields to MarketOutcome
ALTER TABLE "MarketOutcome" ADD COLUMN "outcomePrice" DOUBLE PRECISION,
ADD COLUMN "priceUpdatedAt" TIMESTAMP(3);

-- Backfill existing MarketOutcome records with prices from Market.outcomePrices
-- This SQL updates each MarketOutcome by:
-- 1. Parsing the Market.outcomePrices JSON array
-- 2. Finding the index of the current outcome's clobTokenId in the Market.clobTokenIds array
-- 3. Extracting the price at that same index from outcomePrices
-- 4. Setting priceUpdatedAt to the Market's scrapedAt timestamp

UPDATE "MarketOutcome" mo
SET
  "outcomePrice" = (
    SELECT
      CAST(
        json_array_elements_text(m."outcomePrices"::json) AS DOUBLE PRECISION
      )
    FROM "Market" m,
         LATERAL (
           SELECT ordinality - 1 as idx
           FROM unnest(m."clobTokenIds") WITH ORDINALITY
           WHERE unnest = mo."clobTokenId"
         ) token_idx,
         LATERAL (
           SELECT json_array_elements_text(m."outcomePrices"::json) as price_val
           FROM generate_series(0, json_array_length(m."outcomePrices"::json) - 1) as idx_gen
           WHERE idx_gen = token_idx.idx
         ) price_at_idx
    WHERE m.id = mo."marketId"
      AND m."outcomePrices" IS NOT NULL
      AND m."outcomePrices" != ''
    LIMIT 1
  ),
  "priceUpdatedAt" = (
    SELECT m."scrapedAt"
    FROM "Market" m
    WHERE m.id = mo."marketId"
  )
WHERE EXISTS (
  SELECT 1
  FROM "Market" m
  WHERE m.id = mo."marketId"
    AND m."outcomePrices" IS NOT NULL
    AND m."outcomePrices" != ''
);