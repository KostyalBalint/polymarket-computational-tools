import { Injectable, Logger } from '@nestjs/common';
import { PolymarketClientService } from './polymarket-client.service';
import { RateLimiterService } from './rate-limiter.service';
import { PrismaService } from '../prisma/PrismaService';
import { type Prisma } from '@prisma/client';
import { Config } from '../config/config';
import { Market } from 'polymarket-data';

@Injectable()
export class MarketScraperService {
  private readonly logger = new Logger(MarketScraperService.name);

  constructor(
    private readonly polymarketClient: PolymarketClientService,
    private readonly rateLimiter: RateLimiterService,
    private readonly prisma: PrismaService,
    private readonly config: Config,
  ) {}

  /**
   * Scrape all markets from Polymarket
   * Returns the number of markets scraped
   */
  async scrapeAllMarkets(): Promise<{
    marketsScraped: number;
    outcomesScraped: number;
    errors: string[];
  }> {
    const startTime = Date.now();
    this.logger.log('Starting market scraping...');

    let marketsScraped = 0;
    let outcomesScraped = 0;
    const errors: string[] = [];
    let offset = 0;
    const limit = this.config.scraper.marketsBatchSize;
    let hasMore = true;

    while (hasMore) {
      try {
        this.logger.log(
          `Fetching markets batch: offset=${offset}, limit=${limit}`,
        );

        // Fetch markets with rate limiting
        const markets = await this.rateLimiter.executeMarkets(async () => {
          return await this.polymarketClient.withRetry(
            () =>
              this.polymarketClient.getClient().gamma.markets.listMarkets({
                limit,
                offset,
                include_tag: true,
              }),
            `Fetch markets batch offset=${offset}`,
          );
        });

        if (!markets || markets.length === 0) {
          this.logger.log('No more markets to fetch');
          hasMore = false;
          break;
        }

        this.logger.log(`Fetched ${markets.length} markets`);

        // Process each market
        for (const market of markets) {
          try {
            await this.saveMarket(market);
            marketsScraped++;
            outcomesScraped += market.outcomes?.length || 0;

            if (this.config.scraper.verboseLogging) {
              this.logger.debug(
                `Saved market: ${market.id} - ${market.question}`,
              );
            }
          } catch (error) {
            const errorMsg = `Failed to save market ${market.id}: ${(error as Error).message}`;
            this.logger.error(errorMsg);
            errors.push(errorMsg);
          }
        }

        // Check if we should continue
        if (markets.length < limit) {
          this.logger.log('Received fewer markets than limit, stopping');
          hasMore = false;
        } else {
          offset += limit;
        }
      } catch (error) {
        const errorMsg = `Failed to fetch markets batch at offset ${offset}: ${(error as Error).message}`;
        this.logger.error(errorMsg);
        errors.push(errorMsg);
        hasMore = false;
      }
    }

    const duration = Date.now() - startTime;
    this.logger.log(
      `Market scraping completed: ${marketsScraped} markets, ${outcomesScraped} outcomes in ${duration}ms`,
    );

    if (errors.length > 0) {
      this.logger.warn(`Encountered ${errors.length} errors during scraping`);
    }

    return { marketsScraped, outcomesScraped, errors };
  }

  /**
   * Save a single market to the database
   */
  private async saveMarket(marketData: Market): Promise<void> {
    // Helper to parse dates
    const parseDate = (dateStr: string | null | undefined): Date | null => {
      if (!dateStr) return null;
      try {
        return new Date(dateStr);
      } catch {
        return null;
      }
    };

    let clobTokenIds = [] as string[];
    try {
      clobTokenIds = JSON.parse(marketData.clobTokenIds) as string[];
      if (!Array.isArray(clobTokenIds)) {
        clobTokenIds = [];
      }
    } catch (e) {
      this.logger.warn(
        'No CLOB token IDs for market ' +
          marketData.id +
          ', we will not be able to get prices for these outcomes',
      );
    }

    // Prepare the market data - spread filtered fields and override special ones
    const marketDbData: Prisma.MarketCreateInput = {
      // Spread all compatible fields from API (already filtered)
      id: marketData.id,
      conditionId: marketData.conditionId,
      questionID: marketData.questionID,
      slug: marketData.slug,
      question: marketData.question,
      description: marketData.description,
      category: marketData.category,
      image: marketData.image,
      icon: marketData.icon,
      resolutionSource: marketData.resolutionSource,
      active: marketData.active,
      closed: marketData.closed,
      archived: marketData.archived,
      new: marketData.new,
      marketType: marketData.marketType,
      formatType: marketData.formatType,
      ammType: marketData.ammType,
      volume: marketData.volume,
      volumeNum: marketData.volumeNum,
      volume24hr: marketData.volume24hr,
      volume1wk: marketData.volume1wk,
      volume1mo: marketData.volume1mo,
      volume1yr: marketData.volume1yr,
      volumeAmm: marketData.volumeAmm,
      volumeClob: marketData.volumeClob,
      volume24hrAmm: marketData.volume24hrAmm,
      volume1wkAmm: marketData.volume1wkAmm,
      volume1moAmm: marketData.volume1moAmm,
      volume1yrAmm: marketData.volume1yrAmm,
      volume24hrClob: marketData.volume24hrClob,
      volume1wkClob: marketData.volume1wkClob,
      volume1moClob: marketData.volume1moClob,
      volume1yrClob: marketData.volume1yrClob,
      liquidity: marketData.liquidity,
      liquidityNum: marketData.liquidityNum,
      liquidityAmm: marketData.liquidityAmm,
      liquidityClob: marketData.liquidityClob,
      oneDayPriceChange: marketData.oneDayPriceChange,
      oneHourPriceChange: marketData.oneHourPriceChange,
      oneWeekPriceChange: marketData.oneWeekPriceChange,
      oneMonthPriceChange: marketData.oneMonthPriceChange,
      oneYearPriceChange: marketData.oneYearPriceChange,
      lastTradePrice: marketData.lastTradePrice,
      bestBid: marketData.bestBid,
      bestAsk: marketData.bestAsk,
      spread: marketData.spread,
      enableOrderBook: marketData.enableOrderBook,
      fee: marketData.fee,
      makerBaseFee: marketData.makerBaseFee,
      takerBaseFee: marketData.takerBaseFee,
      denominationToken: marketData.denominationToken,
      marketMakerAddress: marketData.marketMakerAddress,
      clobTokenIds: clobTokenIds,
      createdBy: marketData.createdBy,
      updatedBy: marketData.updatedBy,
      creator: marketData.creator,
      marketGroup: marketData.marketGroup,
      groupItemTitle: marketData.groupItemTitle,
      groupItemThreshold: marketData.groupItemThreshold,
      groupItemRange: marketData.groupItemRange,
      curationOrder: marketData.curationOrder,
      score: marketData.score,
      mailchimpTag: marketData.mailchimpTag,
      outcomes: marketData.outcomes,
      outcomePrices: marketData.outcomePrices,
      shortOutcomes: marketData.shortOutcomes,
      gameId: marketData.gameId,
      teamAID: marketData.teamAID,
      teamBID: marketData.teamBID,
      sportsMarketType: marketData.sportsMarketType,
      line: marketData.line,
      umaBond: marketData.umaBond,
      umaReward: marketData.umaReward,
      customLiveness: marketData.customLiveness,

      // Parse ISO date fields (override the string versions)
      createdAt: parseDate(marketData.createdAt),
      updatedAt: parseDate(marketData.updatedAt),
      closedTime: parseDate(marketData.closedTime),
      readyTimestamp: parseDate(marketData.readyTimestamp),
      fundedTimestamp: parseDate(marketData.fundedTimestamp),
      acceptingOrdersTimestamp: parseDate(marketData.acceptingOrdersTimestamp),
      deployingTimestamp: parseDate(marketData.deployingTimestamp),
      scheduledDeploymentTimestamp: parseDate(
        marketData.scheduledDeploymentTimestamp,
      ),
      endDate: parseDate(marketData.endDate),
      startDate: parseDate(marketData.startDate),

      events: {
        connectOrCreate: marketData.events.map((event) => ({
          where: { id: event.id },
          create: {
            id: event.id,
            ticker: event.ticker,
            slug: event.slug,
            title: event.title,
            description: event.description,
            resolutionSource: event.resolutionSource,
            startDate: event.startDate,
            creationDate: event.creationDate,
            endDate: event.endDate,
            closedTime: event.closedTime,
            eventDate: parseDate(event.eventDate),
            startTime: event.startTime,
            finishedTimestamp: event.finishedTimestamp,
            image: event.image,
            icon: event.icon,
            active: event.active,
            closed: event.closed,
            archived: event.archived,
            new: event.new,
            featured: event.featured,
            restricted: event.restricted,
            isTemplate: event.isTemplate,
            commentsEnabled: event.commentsEnabled,
            enableOrderBook: event.enableOrderBook,
            automaticallyResolved: event.automaticallyResolved,
            automaticallyActive: event.automaticallyActive,
            showAllOutcomes: event.showAllOutcomes,
            showMarketImages: event.showMarketImages,
            enableNegRisk: event.enableNegRisk,
            live: event.live,
            ended: event.ended,
            pendingDeployment: event.pendingDeployment,
            deploying: event.deploying,
            estimateValue: event.estimateValue,
            cantEstimate: event.cantEstimate,
            liquidity: event.liquidity,
            volume: event.volume,
            openInterest: event.openInterest,
            volume24hr: event.volume24hr,
            volume1wk: event.volume1wk,
            volume1mo: event.volume1mo,
            volume1yr: event.volume1yr,
            liquidityAmm: event.liquidityAmm,
            liquidityClob: event.liquidityClob,
            competitive: event.competitive,
            category: event.category,
            sortBy: event.sortBy,
            publishedAt: event.publishedAt,
            createdBy: event.createdBy,
            updatedBy: event.updatedBy,
            createdAt: event.createdAt,
            updatedAt: event.updatedAt,
            parentEvent: event.parentEvent,
            seriesSlug: event.seriesSlug,
            disqusThread: event.disqusThread,
            commentCount: event.commentCount,
            tweetCount: event.tweetCount,
            featuredOrder: event.featuredOrder,
            eventWeek: event.eventWeek,
            templateVariables: event.templateVariables,
            score: event.score,
            elapsed: event.elapsed,
            period: event.period,
            gmpChartMode: event.gmpChartMode,
            estimatedValue: event.estimatedValue,
            spreadsMainLine: event.spreadsMainLine,
            totalsMainLine: event.totalsMainLine,
            carouselMap: event.carouselMap,
            deployingTimestamp: event.deployingTimestamp,
            scheduledDeploymentTimestamp: event.scheduledDeploymentTimestamp,
            gameStatus: event.gameStatus,
            negRisk: event.negRisk,
            negRiskMarketID: event.negRiskMarketID,
            negRiskFeeBips: event.negRiskFeeBips,
          } as Prisma.EventCreateWithoutMarketsInput,
        })),
      },
      tags: {
        connectOrCreate: marketData.tags.map((tag) => ({
          where: { id: tag.id },
          create: {
            id: tag.id,
            label: tag.label,
            slug: tag.slug,
            forceShow: tag.forceShow,
            forceHide: tag.forceHide,
            isCarousel: tag.isCarousel,
            publishedAt: parseDate(tag.publishedAt),
            createdAt: parseDate(tag.createdAt),
            updatedAt: parseDate(tag.updatedAt),
          } as Prisma.TagCreateWithoutMarketsInput,
        })),
      },
      marketOutcomes: {
        connectOrCreate: clobTokenIds.map((tokenId, index) => ({
          where: {
            clobTokenId: tokenId,
          },
          create: {
            clobTokenId: tokenId,
            outcomeText: JSON.parse(marketData.outcomes)[index] || '',
            // Price snapshots will be populated later
          },
        })),
      },
    };

    // Upsert the market
    const market = await this.prisma.market.upsert({
      where: { id: marketData.id },
      create: marketDbData,
      update: marketDbData,
    });
  }
}
