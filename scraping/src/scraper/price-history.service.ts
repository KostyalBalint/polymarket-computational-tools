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

  async scrapeAllTokenPriceHistory(): Promise<{
    tokensProcessed: number;
    dataPointsStored: number;
    errors: string[];
  }> {
    const startTime = Date.now();
    this.logger.log('Starting price history scraping...');

    let tokensProcessed = 0;
    let dataPointsStored = 0;
    const errors: string[] = [];

    try {
      // Get all MarketOutcomes ordered by most recent markets
      const totalTokens = await this.prisma.marketOutcome.count();
      this.logger.log(
        `Found ${totalTokens.toLocaleString()} tokens to process`,
      );

      // Fetch tokens in batches to avoid memory issues
      const batchSize = 1000;
      let processedCount = 0;
      let lastProgressLog = Date.now();
      const logInterval = 10000; // Log every 10 seconds

      // Collect prices for batch insertion
      const priceDataBatch: Array<Prisma.TokenPriceCreateManyInput> = [];

      // Process in batches
      for (let skip = 0; skip < totalTokens; skip += batchSize) {
        const tokens = await this.prisma.marketOutcome.findMany({
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

            tokensProcessed++;
            processedCount++;

            // Log progress periodically
            const now = Date.now();
            if (now - lastProgressLog > logInterval) {
              const elapsed = now - startTime;
              const rate = processedCount / (elapsed / 1000); // tokens per second
              const remaining = totalTokens - processedCount;
              const estimatedTimeMs = (remaining / rate) * 1000;

              this.logger.log(
                `Progress: ${processedCount.toLocaleString()}/${totalTokens.toLocaleString()} tokens ` +
                  `(${((processedCount / totalTokens) * 100).toFixed(1)}%) | ` +
                  `Rate: ${rate.toFixed(2)} tokens/sec | ` +
                  `ETA: ${this.formatDuration(estimatedTimeMs)} | ` +
                  `Batch size: ${priceDataBatch.length.toLocaleString()} data points pending`,
              );
              lastProgressLog = now;
            }

            // Batch insert when batch reaches a good size (every 100 tokens or ~10K data points)
            if (priceDataBatch.length >= 10000 || processedCount % 100 === 0) {
              const inserted = await this.batchInsertPrices(priceDataBatch);
              dataPointsStored += inserted;
              priceDataBatch.length = 0; // Clear the batch

              if (this.config.scraper.verboseLogging) {
                this.logger.debug(
                  `Batch inserted ${inserted.toLocaleString()} data points`,
                );
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
        if (priceDataBatch.length > 0) {
          const inserted = await this.batchInsertPrices(priceDataBatch);
          dataPointsStored += inserted;
          priceDataBatch.length = 0;
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
   * Batch insert price data into database efficiently
   * Uses createMany with skipDuplicates to avoid conflicts on unique constraint
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
