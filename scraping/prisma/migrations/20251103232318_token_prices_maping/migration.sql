/*
  Warnings:

  - You are about to drop the column `marketOutcomeClobTokenId` on the `TokenPrice` table. All the data in the column will be lost.

*/
-- DropForeignKey
ALTER TABLE "polymarket"."TokenPrice" DROP CONSTRAINT "TokenPrice_marketOutcomeClobTokenId_fkey";

-- AlterTable
ALTER TABLE "TokenPrice" DROP COLUMN "marketOutcomeClobTokenId";

-- AddForeignKey
ALTER TABLE "TokenPrice" ADD CONSTRAINT "TokenPrice_tokenId_fkey" FOREIGN KEY ("tokenId") REFERENCES "MarketOutcome"("clobTokenId") ON DELETE RESTRICT ON UPDATE CASCADE;
