/*
  Warnings:

  - You are about to drop the column `marketId` on the `CommentCheckpoint` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[eventId]` on the table `CommentCheckpoint` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `eventId` to the `CommentCheckpoint` table without a default value. This is not possible if the table is not empty.

*/
-- DropForeignKey
ALTER TABLE "polymarket"."CommentCheckpoint" DROP CONSTRAINT "CommentCheckpoint_marketId_fkey";

-- DropIndex
DROP INDEX "polymarket"."CommentCheckpoint_marketId_key";

-- AlterTable
ALTER TABLE "CommentCheckpoint" DROP COLUMN "marketId",
ADD COLUMN     "eventId" TEXT NOT NULL;

-- CreateIndex
CREATE UNIQUE INDEX "CommentCheckpoint_eventId_key" ON "CommentCheckpoint"("eventId");

-- AddForeignKey
ALTER TABLE "CommentCheckpoint" ADD CONSTRAINT "CommentCheckpoint_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES "Event"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
