import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/PrismaService';
import { RateLimiterService } from './rate-limiter.service';
import { Config } from '../config/config';
import { PolymarketClientService } from './polymarket-client.service';
import {
  PriceHistoryInterval,
  MarketPrice,
} from '@polymarket/clob-client/dist/types';
import { type Prisma } from '@prisma/client';

@Injectable()
export class PriceHistoryService {
  private readonly logger = new Logger(PriceHistoryService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly rateLimiter: RateLimiterService,
    private readonly config: Config,
    private readonly polymarketClient: PolymarketClientService,
  ) {}
  // ============================================================================
  // TOKEN PRICE HISTORY
  // ============================================================================

  async scrapeAllTokenPriceHistory(resume: boolean = false): Promise<{
    tokensProcessed: number;
    dataPointsStored: number;
    errors: string[];
  }> {
    const startTime = Date.now();
    this.logger.log(
      `Starting price history scraping${resume ? ' (resume mode)' : ''}...`,
    );

    let tokensProcessed = 0;
    let dataPointsStored = 0;
    const errors: string[] = [];

    try {
      // Build where clause for resume mode - use pricesScrapedAt field
      const whereClause: Prisma.MarketOutcomeWhereInput = resume
        ? {
            pricesScrapedAt: null,
          }
        : {};

      // Get total count
      const totalTokens = await this.prisma.marketOutcome.count();
      const tokensToProcess = await this.prisma.marketOutcome.count({
        where: whereClause,
      });

      if (resume) {
        const alreadyProcessed = totalTokens - tokensToProcess;
        this.logger.log(
          `Resume mode: ${alreadyProcessed.toLocaleString()} tokens already processed, ` +
            `${tokensToProcess.toLocaleString()} tokens remaining`,
        );
      } else {
        this.logger.log(
          `Found ${tokensToProcess.toLocaleString()} tokens to process`,
        );
      }

      // Fetch tokens in batches to avoid memory issues
      const batchSize = 1000;
      let processedCount = 0;
      let lastProgressLog = Date.now();
      const logInterval = 10000; // Log every 10 seconds

      // Collect prices for batch insertion
      const priceDataBatch: Array<Prisma.TokenPriceCreateManyInput> = [];
      // Track marketOutcome updates to batch with price inserts
      const marketOutcomeUpdates: Array<{
        id: number;
        pricesCount: number;
      }> = [];

      // Process in batches - only fetch tokens without prices
      for (let skip = 0; skip < tokensToProcess; skip += batchSize) {
        const tokens = await this.prisma.marketOutcome.findMany({
          where: whereClause,
          select: {
            id: true,
            clobTokenId: true,
            outcomeText: true,
            marketId: true,
          },
          orderBy: {
            market: {
              scrapedAt: 'desc',
            },
          },
          skip,
          take: batchSize,
        });

        // Process each token in this batch
        for (const token of tokens) {
          try {
            // Fetch price history with rate limiting
            const priceHistory = await this.rateLimiter.executePriceHistory(
              async () => {
                return await this.polymarketClient.withRetry(async () => {
                  return (
                    (await this.polymarketClient
                      .getClobClient()
                      .getPricesHistory({
                        market: token.clobTokenId,
                        interval: PriceHistoryInterval.MAX,
                        fidelity: 1,
                        //The API returns this, the package is bad
                      })) as unknown as { history: MarketPrice[] }
                  ).history;
                }, `fetchPriceHistory-${token.clobTokenId}`);
              },
            );

            // Convert API response to database format using MarketPrice[]

            const dbPrices = this.convertPricesToDbFormat(
              token.id,
              priceHistory,
            );
            priceDataBatch.push(...dbPrices);

            // Track this marketOutcome for metadata update
            marketOutcomeUpdates.push({
              id: token.id,
              pricesCount: dbPrices.length,
            });

            tokensProcessed++;
            processedCount++;

            // Log progress periodically
            const now = Date.now();
            if (now - lastProgressLog > logInterval) {
              const elapsed = now - startTime;
              const rate = processedCount / (elapsed / 1000); // tokens per second
              const remaining = tokensToProcess - processedCount;
              const estimatedTimeMs =
                remaining > 0 && rate > 0 ? (remaining / rate) * 1000 : 0;

              this.logger.log(
                `Progress: ${processedCount.toLocaleString()}/${tokensToProcess.toLocaleString()} tokens ` +
                  `(${((processedCount / tokensToProcess) * 100).toFixed(1)}%) | ` +
                  `Rate: ${rate.toFixed(2)} tokens/sec | ` +
                  `ETA: ${this.formatDuration(estimatedTimeMs)} | ` +
                  `Batch size: ${priceDataBatch.length.toLocaleString()} data points pending`,
              );
              lastProgressLog = now;
            }

            // Batch insert when batch reaches a good size (50K data points or every 500 tokens)
            if (priceDataBatch.length >= 50000 || processedCount % 500 === 0) {
              const inserted = await this.batchInsertPricesWithMetadata(
                priceDataBatch,
                marketOutcomeUpdates,
              );
              dataPointsStored += inserted;
              priceDataBatch.length = 0; // Clear the batch
              marketOutcomeUpdates.length = 0; // Clear the updates

              if (this.config.scraper.verboseLogging) {
                this.logger.debug(`Batch inserted ${inserted} data points`);
              }
            }
          } catch (error) {
            const errorMsg = `Failed to fetch price history for token ${token.clobTokenId}: ${(error as Error).message}`;
            this.logger.error(errorMsg);
            errors.push(errorMsg);

            // Continue processing other tokens
            if (errors.length > 100) {
              this.logger.warn(
                'Too many errors (>100), stopping price history scraping',
              );
              break;
            }
          }
        }

        // Insert remaining prices from this batch
        if (priceDataBatch.length > 0 || marketOutcomeUpdates.length > 0) {
          const inserted = await this.batchInsertPricesWithMetadata(
            priceDataBatch,
            marketOutcomeUpdates,
          );
          dataPointsStored += inserted;
          priceDataBatch.length = 0;
          marketOutcomeUpdates.length = 0;
        }
      }
    } catch (error) {
      const errorMsg = `Fatal error in price history scraping: ${(error as Error).message}`;
      this.logger.error(errorMsg);
      errors.push(errorMsg);
    }

    const duration = Date.now() - startTime;
    this.logger.log(
      `Price history scraping completed: ${tokensProcessed.toLocaleString()} tokens processed, ` +
        `${dataPointsStored.toLocaleString()} data points stored in ${this.formatDuration(duration)}`,
    );

    if (errors.length > 0) {
      this.logger.warn(
        `Encountered ${errors.length} errors during price history scraping`,
      );
    }

    return { tokensProcessed, dataPointsStored, errors };
  }

  // ============================================================================
  // HELPER METHODS
  // ============================================================================

  /**
   * Convert MarketPrice array to database format
   */
  private convertPricesToDbFormat(
    marketOutcomeId: number,
    prices: MarketPrice[],
  ): Array<Prisma.TokenPriceCreateManyInput> {
    return prices
      .filter((point) => point.t && point.p !== undefined)
      .map((point) => ({
        marketOutcomeId,
        timestamp: new Date(point.t * 1000), // Convert Unix to Date
        price: point.p,
      }));
  }

  /**
   * Batch insert price data and update marketOutcome metadata in a transaction
   * Uses createMany with skipDuplicates to avoid conflicts on unique constraint
   */
  private async batchInsertPricesWithMetadata(
    prices: Array<Prisma.TokenPriceCreateManyInput>,
    marketOutcomeUpdates: Array<{ id: number; pricesCount: number }>,
  ): Promise<number> {
    if (prices.length === 0 && marketOutcomeUpdates.length === 0) return 0;

    try {
      const scrapedAt = new Date();

      // Use transaction to ensure consistency with increased timeout and chunking for large batches
      const CHUNK_SIZE = 10000; // Split large batches into smaller chunks
      const result = await this.prisma.$transaction(async (tx) => {
        // Insert prices in chunks to avoid timeout
        let insertedCount = 0;
        if (prices.length > 0) {
          for (let i = 0; i < prices.length; i += CHUNK_SIZE) {
            const chunk = prices.slice(i, i + CHUNK_SIZE);
            const priceResult = await tx.tokenPrice.createMany({
              data: chunk,
              skipDuplicates: true,
            });
            insertedCount += priceResult.count;
          }
        }

        // Update marketOutcome metadata
        if (marketOutcomeUpdates.length > 0) {
          await Promise.all(
            marketOutcomeUpdates.map((update) =>
              tx.marketOutcome.update({
                where: { id: update.id },
                data: {
                  pricesScrapedAt: scrapedAt,
                  pricesCount: update.pricesCount,
                },
              }),
            ),
          );
        }

        return insertedCount;
      }, {
        maxWait: 30000, // Maximum time to wait for transaction to start (30s)
        timeout: 60000, // Maximum time for transaction to complete (60s)
      });

      if (result === 0 && prices.length > 0) {
        this.logger.warn(
          `Attempted to insert ${prices.length} data points but 0 were inserted (all duplicates). ` +
            `Updated ${marketOutcomeUpdates.length} marketOutcome records with metadata.`,
        );
      }

      return result;
    } catch (error) {
      this.logger.error(
        `Failed to batch insert ${prices.length} prices and update ${marketOutcomeUpdates.length} marketOutcomes: ${(error as Error).message}`,
      );
      throw error;
    }
  }

  /**
   * Batch insert price data into database efficiently
   * Uses createMany with skipDuplicates to avoid conflicts on unique constraint
   * @deprecated Use batchInsertPricesWithMetadata instead
   */
  private async batchInsertPrices(
    prices: Array<Prisma.TokenPriceCreateManyInput>,
  ): Promise<number> {
    if (prices.length === 0) return 0;

    try {
      const result = await this.prisma.tokenPrice.createMany({
        data: prices,
        skipDuplicates: true,
      });

      if (result.count === 0 && prices.length > 0) {
        this.logger.warn(
          `Attempted to insert ${prices.length} data points but 0 were inserted (all duplicates). ` +
            `Sample marketOutcomeId: ${prices[0].marketOutcomeId}`,
        );
      }

      return result.count;
    } catch (error) {
      this.logger.error(
        `Failed to batch insert ${prices.length} prices: ${(error as Error).message}`,
      );
      throw error;
    }
  }

  /**
   * Format time duration in human-readable format
   */
  private formatDuration(ms: number): string {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  }
}
