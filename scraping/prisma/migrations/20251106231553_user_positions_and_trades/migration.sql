-- AlterTable
ALTER TABLE "ScraperRun" ADD COLUMN     "userPositionsScraped" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "userTradesScraped" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "usersProcessed" INTEGER NOT NULL DEFAULT 0;

-- CreateTable
CREATE TABLE "UserPosition" (
    "id" SERIAL NOT NULL,
    "proxyWallet" TEXT NOT NULL,
    "asset" TEXT NOT NULL,
    "conditionId" TEXT NOT NULL,
    "size" DOUBLE PRECISION NOT NULL,
    "avgPrice" DOUBLE PRECISION NOT NULL,
    "initialValue" DOUBLE PRECISION NOT NULL,
    "currentValue" DOUBLE PRECISION NOT NULL,
    "cashPnl" DOUBLE PRECISION NOT NULL,
    "percentPnl" DOUBLE PRECISION NOT NULL,
    "totalBought" DOUBLE PRECISION NOT NULL,
    "realizedPnl" DOUBLE PRECISION NOT NULL,
    "percentRealizedPnl" DOUBLE PRECISION NOT NULL,
    "curPrice" DOUBLE PRECISION NOT NULL,
    "redeemable" BOOLEAN NOT NULL,
    "mergeable" BOOLEAN NOT NULL,
    "negativeRisk" BOOLEAN NOT NULL,
    "title" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "icon" TEXT,
    "eventSlug" TEXT NOT NULL,
    "outcome" TEXT NOT NULL,
    "outcomeIndex" INTEGER NOT NULL,
    "oppositeOutcome" TEXT NOT NULL,
    "oppositeAsset" TEXT NOT NULL,
    "endDate" TEXT NOT NULL,
    "scrapedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdInDb" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "UserPosition_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UserTrade" (
    "id" SERIAL NOT NULL,
    "proxyWallet" TEXT NOT NULL,
    "side" TEXT NOT NULL,
    "asset" TEXT NOT NULL,
    "conditionId" TEXT NOT NULL,
    "size" DOUBLE PRECISION NOT NULL,
    "price" DOUBLE PRECISION NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL,
    "transactionHash" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "icon" TEXT,
    "eventSlug" TEXT NOT NULL,
    "outcome" TEXT NOT NULL,
    "outcomeIndex" INTEGER NOT NULL,
    "scrapedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdInDb" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "UserTrade_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "UserPosition_proxyWallet_idx" ON "UserPosition"("proxyWallet");

-- CreateIndex
CREATE INDEX "UserPosition_conditionId_idx" ON "UserPosition"("conditionId");

-- CreateIndex
CREATE INDEX "UserPosition_scrapedAt_idx" ON "UserPosition"("scrapedAt");

-- CreateIndex
CREATE UNIQUE INDEX "UserPosition_proxyWallet_asset_conditionId_key" ON "UserPosition"("proxyWallet", "asset", "conditionId");

-- CreateIndex
CREATE UNIQUE INDEX "UserTrade_transactionHash_key" ON "UserTrade"("transactionHash");

-- CreateIndex
CREATE INDEX "UserTrade_proxyWallet_idx" ON "UserTrade"("proxyWallet");

-- CreateIndex
CREATE INDEX "UserTrade_conditionId_idx" ON "UserTrade"("conditionId");

-- CreateIndex
CREATE INDEX "UserTrade_timestamp_idx" ON "UserTrade"("timestamp");

-- CreateIndex
CREATE INDEX "UserTrade_transactionHash_idx" ON "UserTrade"("transactionHash");

-- AddForeignKey
ALTER TABLE "UserPosition" ADD CONSTRAINT "UserPosition_proxyWallet_fkey" FOREIGN KEY ("proxyWallet") REFERENCES "UserProfile"("address") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UserTrade" ADD CONSTRAINT "UserTrade_proxyWallet_fkey" FOREIGN KEY ("proxyWallet") REFERENCES "UserProfile"("address") ON DELETE RESTRICT ON UPDATE CASCADE;
