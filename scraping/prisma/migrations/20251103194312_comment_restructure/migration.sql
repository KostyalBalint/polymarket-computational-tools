/*
  Warnings:

  - You are about to drop the column `marketId` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `parentCommentId` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `parentEntityId` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `reactionToCommentId` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `userIsCreator` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `userIsMod` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `userName` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `userProfileImage` on the `Comment` table. All the data in the column will be lost.
  - You are about to drop the column `userPseudonym` on the `Comment` table. All the data in the column will be lost.
  - Added the required column `parentEntityID` to the `Comment` table without a default value. This is not possible if the table is not empty.

*/
-- DropForeignKey
ALTER TABLE "polymarket"."Comment" DROP CONSTRAINT "Comment_marketId_fkey";

-- DropForeignKey
ALTER TABLE "polymarket"."Comment" DROP CONSTRAINT "Comment_parentCommentId_fkey";

-- DropForeignKey
ALTER TABLE "polymarket"."Comment" DROP CONSTRAINT "Comment_reactionToCommentId_fkey";

-- DropForeignKey
ALTER TABLE "polymarket"."Comment" DROP CONSTRAINT "Comment_userAddress_fkey";

-- DropForeignKey
ALTER TABLE "polymarket"."CommentCheckpoint" DROP CONSTRAINT "CommentCheckpoint_marketId_fkey";

-- DropForeignKey
ALTER TABLE "polymarket"."MarketOutcome" DROP CONSTRAINT "MarketOutcome_marketId_fkey";

-- DropIndex
DROP INDEX "polymarket"."Comment_marketId_idx";

-- DropIndex
DROP INDEX "polymarket"."Comment_parentCommentId_idx";

-- DropIndex
DROP INDEX "polymarket"."Comment_parentEntityType_parentEntityId_idx";

-- DropIndex
DROP INDEX "polymarket"."Comment_reactionToCommentId_idx";

-- AlterTable
ALTER TABLE "Comment" DROP COLUMN "marketId",
DROP COLUMN "parentCommentId",
DROP COLUMN "parentEntityId",
DROP COLUMN "reactionToCommentId",
DROP COLUMN "userIsCreator",
DROP COLUMN "userIsMod",
DROP COLUMN "userName",
DROP COLUMN "userProfileImage",
DROP COLUMN "userPseudonym",
ADD COLUMN     "parentCommentID" TEXT,
ADD COLUMN     "parentEntityID" TEXT NOT NULL;

-- CreateTable
CREATE TABLE "CommentReaction" (
    "id" TEXT NOT NULL,
    "reactionType" TEXT NOT NULL,
    "userAddress" TEXT NOT NULL,
    "commentID" TEXT NOT NULL,

    CONSTRAINT "CommentReaction_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Comment_parentEntityType_parentEntityID_idx" ON "Comment"("parentEntityType", "parentEntityID");

-- CreateIndex
CREATE INDEX "Comment_parentCommentID_idx" ON "Comment"("parentCommentID");

-- AddForeignKey
ALTER TABLE "MarketOutcome" ADD CONSTRAINT "MarketOutcome_marketId_fkey" FOREIGN KEY ("marketId") REFERENCES "Market"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Comment" ADD CONSTRAINT "Comment_userAddress_fkey" FOREIGN KEY ("userAddress") REFERENCES "UserProfile"("address") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Comment" ADD CONSTRAINT "Comment_parentEntityID_fkey" FOREIGN KEY ("parentEntityID") REFERENCES "Event"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Comment" ADD CONSTRAINT "Comment_parentCommentID_fkey" FOREIGN KEY ("parentCommentID") REFERENCES "Comment"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CommentReaction" ADD CONSTRAINT "CommentReaction_commentID_fkey" FOREIGN KEY ("commentID") REFERENCES "Comment"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CommentCheckpoint" ADD CONSTRAINT "CommentCheckpoint_marketId_fkey" FOREIGN KEY ("marketId") REFERENCES "Market"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
