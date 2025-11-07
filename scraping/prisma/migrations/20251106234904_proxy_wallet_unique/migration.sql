/*
  Warnings:

  - A unique constraint covering the columns `[proxyWallet]` on the table `UserProfile` will be added. If there are existing duplicate values, this will fail.

*/
-- DropForeignKey
ALTER TABLE "public"."UserPosition" DROP CONSTRAINT "UserPosition_proxyWallet_fkey";

-- CreateIndex
CREATE UNIQUE INDEX "UserProfile_proxyWallet_key" ON "UserProfile"("proxyWallet");

-- AddForeignKey
ALTER TABLE "UserPosition" ADD CONSTRAINT "UserPosition_proxyWallet_fkey" FOREIGN KEY ("proxyWallet") REFERENCES "UserProfile"("proxyWallet") ON DELETE RESTRICT ON UPDATE CASCADE;
