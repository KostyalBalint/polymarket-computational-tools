-- CreateIndex
CREATE INDEX "UserTrade_proxyWallet_timestamp_idx" ON "UserTrade"("proxyWallet", "timestamp" DESC);
