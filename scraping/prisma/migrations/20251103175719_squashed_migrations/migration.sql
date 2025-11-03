-- CreateTable
CREATE TABLE "Event" (
    "id" TEXT NOT NULL,
    "ticker" TEXT,
    "slug" TEXT,
    "title" TEXT,
    "description" TEXT,
    "resolutionSource" TEXT,
    "startDate" TEXT,
    "creationDate" TEXT,
    "endDate" TEXT,
    "closedTime" TIMESTAMP(3),
    "eventDate" TIMESTAMP(3),
    "startTime" TIMESTAMP(3),
    "finishedTimestamp" TIMESTAMP(3),
    "image" TEXT,
    "icon" TEXT,
    "active" BOOLEAN DEFAULT false,
    "closed" BOOLEAN DEFAULT false,
    "archived" BOOLEAN DEFAULT false,
    "new" BOOLEAN DEFAULT false,
    "featured" BOOLEAN DEFAULT false,
    "restricted" BOOLEAN DEFAULT false,
    "isTemplate" BOOLEAN DEFAULT false,
    "commentsEnabled" BOOLEAN DEFAULT false,
    "enableOrderBook" BOOLEAN DEFAULT false,
    "automaticallyResolved" BOOLEAN DEFAULT false,
    "automaticallyActive" BOOLEAN DEFAULT false,
    "showAllOutcomes" BOOLEAN DEFAULT false,
    "showMarketImages" BOOLEAN DEFAULT false,
    "enableNegRisk" BOOLEAN DEFAULT false,
    "live" BOOLEAN DEFAULT false,
    "ended" BOOLEAN DEFAULT false,
    "pendingDeployment" BOOLEAN DEFAULT false,
    "deploying" BOOLEAN DEFAULT false,
    "estimateValue" BOOLEAN DEFAULT false,
    "cantEstimate" BOOLEAN DEFAULT false,
    "liquidity" DOUBLE PRECISION,
    "volume" DOUBLE PRECISION,
    "openInterest" DOUBLE PRECISION,
    "volume24hr" DOUBLE PRECISION,
    "volume1wk" DOUBLE PRECISION,
    "volume1mo" DOUBLE PRECISION,
    "volume1yr" DOUBLE PRECISION,
    "liquidityAmm" DOUBLE PRECISION,
    "liquidityClob" DOUBLE PRECISION,
    "competitive" DOUBLE PRECISION,
    "category" TEXT,
    "sortBy" TEXT,
    "publishedAt" TIMESTAMP(3),
    "createdBy" TEXT,
    "updatedBy" TEXT,
    "createdAt" TIMESTAMP(3),
    "updatedAt" TIMESTAMP(3),
    "parentEvent" TEXT,
    "seriesSlug" TEXT,
    "disqusThread" TEXT,
    "commentCount" INTEGER,
    "tweetCount" INTEGER,
    "featuredOrder" INTEGER,
    "eventWeek" INTEGER,
    "templateVariables" TEXT,
    "score" TEXT,
    "elapsed" TEXT,
    "period" TEXT,
    "gmpChartMode" TEXT,
    "estimatedValue" TEXT,
    "spreadsMainLine" DOUBLE PRECISION,
    "totalsMainLine" DOUBLE PRECISION,
    "carouselMap" TEXT,
    "deployingTimestamp" TIMESTAMP(3),
    "scheduledDeploymentTimestamp" TIMESTAMP(3),
    "gameStatus" TEXT,
    "negRisk" BOOLEAN DEFAULT false,
    "negRiskMarketID" TEXT,
    "negRiskFeeBips" DOUBLE PRECISION,
    "scrapedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdInDb" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Event_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Market" (
    "id" TEXT NOT NULL,
    "conditionId" TEXT,
    "questionID" TEXT,
    "slug" TEXT,
    "question" TEXT,
    "description" TEXT,
    "category" TEXT,
    "image" TEXT,
    "icon" TEXT,
    "resolutionSource" TEXT,
    "startDate" TIMESTAMP(3),
    "endDate" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3),
    "updatedAt" TIMESTAMP(3),
    "closedTime" TIMESTAMP(3),
    "active" BOOLEAN DEFAULT false,
    "closed" BOOLEAN DEFAULT false,
    "archived" BOOLEAN DEFAULT false,
    "new" BOOLEAN DEFAULT false,
    "marketType" TEXT,
    "formatType" TEXT,
    "ammType" TEXT,
    "volume" TEXT,
    "volumeNum" DOUBLE PRECISION,
    "volume24hr" DOUBLE PRECISION,
    "volume1wk" DOUBLE PRECISION,
    "volume1mo" DOUBLE PRECISION,
    "volume1yr" DOUBLE PRECISION,
    "volumeAmm" DOUBLE PRECISION,
    "volumeClob" DOUBLE PRECISION,
    "volume24hrAmm" DOUBLE PRECISION,
    "volume1wkAmm" DOUBLE PRECISION,
    "volume1moAmm" DOUBLE PRECISION,
    "volume1yrAmm" DOUBLE PRECISION,
    "volume24hrClob" DOUBLE PRECISION,
    "volume1wkClob" DOUBLE PRECISION,
    "volume1moClob" DOUBLE PRECISION,
    "volume1yrClob" DOUBLE PRECISION,
    "liquidity" TEXT,
    "liquidityNum" DOUBLE PRECISION,
    "liquidityAmm" DOUBLE PRECISION,
    "liquidityClob" DOUBLE PRECISION,
    "oneDayPriceChange" DOUBLE PRECISION,
    "oneHourPriceChange" DOUBLE PRECISION,
    "oneWeekPriceChange" DOUBLE PRECISION,
    "oneMonthPriceChange" DOUBLE PRECISION,
    "oneYearPriceChange" DOUBLE PRECISION,
    "lastTradePrice" DOUBLE PRECISION,
    "bestBid" DOUBLE PRECISION,
    "bestAsk" DOUBLE PRECISION,
    "spread" DOUBLE PRECISION,
    "enableOrderBook" BOOLEAN DEFAULT false,
    "fee" TEXT,
    "makerBaseFee" DOUBLE PRECISION,
    "takerBaseFee" DOUBLE PRECISION,
    "denominationToken" TEXT,
    "marketMakerAddress" TEXT,
    "clobTokenIds" TEXT[],
    "createdBy" INTEGER,
    "updatedBy" INTEGER,
    "creator" TEXT,
    "marketGroup" INTEGER,
    "groupItemTitle" TEXT,
    "groupItemThreshold" TEXT,
    "groupItemRange" TEXT,
    "curationOrder" INTEGER,
    "score" DOUBLE PRECISION,
    "mailchimpTag" TEXT,
    "outcomes" TEXT,
    "outcomePrices" TEXT,
    "shortOutcomes" TEXT,
    "readyTimestamp" TIMESTAMP(3),
    "fundedTimestamp" TIMESTAMP(3),
    "acceptingOrdersTimestamp" TIMESTAMP(3),
    "deployingTimestamp" TIMESTAMP(3),
    "scheduledDeploymentTimestamp" TIMESTAMP(3),
    "gameId" TEXT,
    "teamAID" TEXT,
    "teamBID" TEXT,
    "sportsMarketType" TEXT,
    "line" DOUBLE PRECISION,
    "umaBond" TEXT,
    "umaReward" TEXT,
    "customLiveness" INTEGER,
    "scrapedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdInDb" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Market_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "MarketOutcome" (
    "clobTokenId" TEXT NOT NULL,
    "marketId" TEXT NOT NULL,
    "outcomeText" TEXT NOT NULL,

    CONSTRAINT "MarketOutcome_pkey" PRIMARY KEY ("clobTokenId")
);

-- CreateTable
CREATE TABLE "Tag" (
    "id" TEXT NOT NULL,
    "label" TEXT,
    "slug" TEXT,
    "forceShow" BOOLEAN DEFAULT false,
    "forceHide" BOOLEAN DEFAULT false,
    "isCarousel" BOOLEAN DEFAULT false,
    "publishedAt" TIMESTAMP(3),
    "createdBy" INTEGER,
    "updatedBy" INTEGER,
    "createdAt" TIMESTAMP(3),
    "updatedAt" TIMESTAMP(3),
    "scrapedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdInDb" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Tag_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Comment" (
    "id" TEXT NOT NULL,
    "body" TEXT NOT NULL,
    "userAddress" TEXT NOT NULL,
    "replyAddress" TEXT,
    "userName" TEXT,
    "userPseudonym" TEXT,
    "userIsMod" BOOLEAN NOT NULL DEFAULT false,
    "userIsCreator" BOOLEAN NOT NULL DEFAULT false,
    "userProfileImage" TEXT,
    "parentEntityType" TEXT NOT NULL,
    "parentEntityId" TEXT NOT NULL,
    "marketId" TEXT,
    "parentCommentId" TEXT,
    "reactionToCommentId" TEXT,
    "reactionCount" INTEGER NOT NULL DEFAULT 0,
    "reportCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3),
    "updatedAt" TIMESTAMP(3),
    "scrapedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Comment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UserProfile" (
    "address" TEXT NOT NULL,
    "name" TEXT,
    "pseudonym" TEXT,
    "displayUsernamePublic" BOOLEAN NOT NULL DEFAULT false,
    "bio" TEXT,
    "isMod" BOOLEAN NOT NULL DEFAULT false,
    "isCreator" BOOLEAN NOT NULL DEFAULT false,
    "proxyWallet" TEXT,
    "baseAddress" TEXT,
    "profileImage" TEXT,

    CONSTRAINT "UserProfile_pkey" PRIMARY KEY ("address")
);

-- CreateTable
CREATE TABLE "CommentCheckpoint" (
    "id" SERIAL NOT NULL,
    "marketId" TEXT NOT NULL,
    "lastOffset" INTEGER NOT NULL DEFAULT 0,
    "totalFetched" INTEGER NOT NULL DEFAULT 0,
    "lastScrapedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CommentCheckpoint_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "TokenPrice" (
    "id" SERIAL NOT NULL,
    "tokenId" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL,
    "price" DOUBLE PRECISION NOT NULL,
    "marketOutcomeClobTokenId" TEXT,

    CONSTRAINT "TokenPrice_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ScraperRun" (
    "id" SERIAL NOT NULL,
    "runType" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'running',
    "marketsScraped" INTEGER NOT NULL DEFAULT 0,
    "marketOutcomesScraped" INTEGER NOT NULL DEFAULT 0,
    "commentsScraped" INTEGER NOT NULL DEFAULT 0,
    "priceSnapshotsTaken" INTEGER NOT NULL DEFAULT 0,
    "tokensProcessed" INTEGER NOT NULL DEFAULT 0,
    "priceDataPointsStored" INTEGER NOT NULL DEFAULT 0,
    "errors" TEXT,
    "errorCount" INTEGER NOT NULL DEFAULT 0,
    "startTime" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endTime" TIMESTAMP(3),
    "durationMs" INTEGER,

    CONSTRAINT "ScraperRun_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "_EventToMarket" (
    "A" TEXT NOT NULL,
    "B" TEXT NOT NULL,

    CONSTRAINT "_EventToMarket_AB_pkey" PRIMARY KEY ("A","B")
);

-- CreateTable
CREATE TABLE "_EventToTag" (
    "A" TEXT NOT NULL,
    "B" TEXT NOT NULL,

    CONSTRAINT "_EventToTag_AB_pkey" PRIMARY KEY ("A","B")
);

-- CreateTable
CREATE TABLE "_MarketToTag" (
    "A" TEXT NOT NULL,
    "B" TEXT NOT NULL,

    CONSTRAINT "_MarketToTag_AB_pkey" PRIMARY KEY ("A","B")
);

-- CreateIndex
CREATE UNIQUE INDEX "Event_slug_key" ON "Event"("slug");

-- CreateIndex
CREATE INDEX "Event_slug_idx" ON "Event"("slug");

-- CreateIndex
CREATE INDEX "Event_active_idx" ON "Event"("active");

-- CreateIndex
CREATE INDEX "Event_featured_idx" ON "Event"("featured");

-- CreateIndex
CREATE INDEX "Event_closed_idx" ON "Event"("closed");

-- CreateIndex
CREATE UNIQUE INDEX "Market_slug_key" ON "Market"("slug");

-- CreateIndex
CREATE INDEX "Market_closed_idx" ON "Market"("closed");

-- CreateIndex
CREATE INDEX "Market_category_idx" ON "Market"("category");

-- CreateIndex
CREATE INDEX "Market_scrapedAt_idx" ON "Market"("scrapedAt");

-- CreateIndex
CREATE INDEX "Market_slug_idx" ON "Market"("slug");

-- CreateIndex
CREATE INDEX "Market_active_idx" ON "Market"("active");

-- CreateIndex
CREATE INDEX "MarketOutcome_marketId_idx" ON "MarketOutcome"("marketId");

-- CreateIndex
CREATE UNIQUE INDEX "Tag_slug_key" ON "Tag"("slug");

-- CreateIndex
CREATE INDEX "Tag_slug_idx" ON "Tag"("slug");

-- CreateIndex
CREATE INDEX "Comment_marketId_idx" ON "Comment"("marketId");

-- CreateIndex
CREATE INDEX "Comment_userAddress_idx" ON "Comment"("userAddress");

-- CreateIndex
CREATE INDEX "Comment_parentEntityType_parentEntityId_idx" ON "Comment"("parentEntityType", "parentEntityId");

-- CreateIndex
CREATE INDEX "Comment_parentCommentId_idx" ON "Comment"("parentCommentId");

-- CreateIndex
CREATE INDEX "Comment_reactionToCommentId_idx" ON "Comment"("reactionToCommentId");

-- CreateIndex
CREATE INDEX "Comment_createdAt_idx" ON "Comment"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "CommentCheckpoint_marketId_key" ON "CommentCheckpoint"("marketId");

-- CreateIndex
CREATE INDEX "CommentCheckpoint_lastScrapedAt_idx" ON "CommentCheckpoint"("lastScrapedAt");

-- CreateIndex
CREATE INDEX "TokenPrice_tokenId_idx" ON "TokenPrice"("tokenId");

-- CreateIndex
CREATE INDEX "TokenPrice_timestamp_idx" ON "TokenPrice"("timestamp");

-- CreateIndex
CREATE UNIQUE INDEX "TokenPrice_tokenId_timestamp_key" ON "TokenPrice"("tokenId", "timestamp");

-- CreateIndex
CREATE INDEX "ScraperRun_runType_idx" ON "ScraperRun"("runType");

-- CreateIndex
CREATE INDEX "ScraperRun_status_idx" ON "ScraperRun"("status");

-- CreateIndex
CREATE INDEX "ScraperRun_startTime_idx" ON "ScraperRun"("startTime");

-- CreateIndex
CREATE INDEX "_EventToMarket_B_index" ON "_EventToMarket"("B");

-- CreateIndex
CREATE INDEX "_EventToTag_B_index" ON "_EventToTag"("B");

-- CreateIndex
CREATE INDEX "_MarketToTag_B_index" ON "_MarketToTag"("B");

-- AddForeignKey
ALTER TABLE "MarketOutcome" ADD CONSTRAINT "MarketOutcome_marketId_fkey" FOREIGN KEY ("marketId") REFERENCES "Market"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Comment" ADD CONSTRAINT "Comment_userAddress_fkey" FOREIGN KEY ("userAddress") REFERENCES "UserProfile"("address") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Comment" ADD CONSTRAINT "Comment_marketId_fkey" FOREIGN KEY ("marketId") REFERENCES "Market"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Comment" ADD CONSTRAINT "Comment_parentCommentId_fkey" FOREIGN KEY ("parentCommentId") REFERENCES "Comment"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Comment" ADD CONSTRAINT "Comment_reactionToCommentId_fkey" FOREIGN KEY ("reactionToCommentId") REFERENCES "Comment"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CommentCheckpoint" ADD CONSTRAINT "CommentCheckpoint_marketId_fkey" FOREIGN KEY ("marketId") REFERENCES "Market"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "TokenPrice" ADD CONSTRAINT "TokenPrice_marketOutcomeClobTokenId_fkey" FOREIGN KEY ("marketOutcomeClobTokenId") REFERENCES "MarketOutcome"("clobTokenId") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "_EventToMarket" ADD CONSTRAINT "_EventToMarket_A_fkey" FOREIGN KEY ("A") REFERENCES "Event"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "_EventToMarket" ADD CONSTRAINT "_EventToMarket_B_fkey" FOREIGN KEY ("B") REFERENCES "Market"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "_EventToTag" ADD CONSTRAINT "_EventToTag_A_fkey" FOREIGN KEY ("A") REFERENCES "Event"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "_EventToTag" ADD CONSTRAINT "_EventToTag_B_fkey" FOREIGN KEY ("B") REFERENCES "Tag"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "_MarketToTag" ADD CONSTRAINT "_MarketToTag_A_fkey" FOREIGN KEY ("A") REFERENCES "Market"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "_MarketToTag" ADD CONSTRAINT "_MarketToTag_B_fkey" FOREIGN KEY ("B") REFERENCES "Tag"("id") ON DELETE CASCADE ON UPDATE CASCADE;
