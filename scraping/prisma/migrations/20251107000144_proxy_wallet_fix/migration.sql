-- DropForeignKey
ALTER TABLE "public"."UserTrade" DROP CONSTRAINT "UserTrade_proxyWallet_fkey";

-- AddForeignKey
ALTER TABLE "UserTrade" ADD CONSTRAINT "UserTrade_proxyWallet_fkey" FOREIGN KEY ("proxyWallet") REFERENCES "UserProfile"("proxyWallet") ON DELETE RESTRICT ON UPDATE CASCADE;
