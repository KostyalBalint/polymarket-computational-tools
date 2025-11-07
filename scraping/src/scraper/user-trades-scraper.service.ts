import { Injectable, Logger } from '@nestjs/common';
import { PolymarketClientService } from './polymarket-client.service';
import { RateLimiterService } from './rate-limiter.service';
import { PrismaService } from '../prisma/PrismaService';
import { Config } from 'src/config/config';

@Injectable()
export class UserTradesScraperService {
  private readonly logger = new Logger(UserTradesScraperService.name);

  constructor(
    private readonly polymarketClient: PolymarketClientService,
    private readonly rateLimiter: RateLimiterService,
    private readonly prisma: PrismaService,
    //private readonly config: Config,
  ) {}

  /**
   * Scrape trades for all users in the UserProfile table
   * Returns the number of trades scraped
   */
  async scrapeAllUserTrades(): Promise<{
    usersProcessed: number;
    tradesScraped: number;
    errors: string[];
  }> {
    const startTime = Date.now();
    this.logger.log('Starting user trades scraping...');

    let usersProcessed = 0;
    let tradesScraped = 0;
    const errors: string[] = [];
    let lastProgressLog = Date.now();
    const logInterval = 10000; // Log every 10 seconds

    try {
      // Get all users from UserProfile table
      const users = await this.prisma.userProfile.findMany({
        select: {
          proxyWallet: true,
        },
      });

      this.logger.log(`Found ${users.length} users to process`);

      // Process each user
      for (const user of users) {
        try {
          const userTrades = await this.scrapeUserTrades(user.proxyWallet);
          tradesScraped += userTrades;
          usersProcessed++;

          // Log progress periodically
          const now = Date.now();
          if (now - lastProgressLog > logInterval) {
            const elapsed = (now - startTime) / 1000; // seconds
            const rate = usersProcessed / elapsed; // users per second

            this.logger.log(
              `Progress: ${usersProcessed}/${users.length} users processed | ` +
                `Rate: ${rate.toFixed(2)} users/sec | ` +
                `Total trades: ${tradesScraped.toLocaleString()}`,
            );
            lastProgressLog = now;
          }
        } catch (error) {
          const errorMsg = `Failed to scrape trades for user ${user.proxyWallet}: ${(error as Error).message}`;
          this.logger.error(errorMsg);
          errors.push(errorMsg);
        }
      }
    } catch (error) {
      const errorMsg = `Failed to fetch users: ${(error as Error).message}`;
      this.logger.error(errorMsg);
      errors.push(errorMsg);
    }

    const duration = Date.now() - startTime;
    this.logger.log(
      `User trades scraping completed: ${usersProcessed} users, ${tradesScraped} trades in ${duration}ms`,
    );

    if (errors.length > 0) {
      this.logger.warn(`Encountered ${errors.length} errors during scraping`);
    }

    return { usersProcessed, tradesScraped, errors };
  }

  /**
   * Scrape trades for a specific user with incremental updates
   * Returns the number of new trades scraped
   */
  async scrapeUserTrades(userAddress: string): Promise<number> {
    let totalNewTrades = 0;
    let offset = 0;
    const limit = 500; // Max limit per API docs
    let hasMore = true;

    try {
      // Get the most recent trade timestamp for this user (for incremental updates)
      const lastTrade = await this.prisma.userTrade.findFirst({
        where: { proxyWallet: userAddress },
        orderBy: { timestamp: 'desc' },
        select: { timestamp: true },
      });

      const lastTradeTime = lastTrade?.timestamp;
      if (lastTradeTime) {
        this.logger.debug(
          `Last trade for user ${userAddress}: ${lastTradeTime.toISOString()}`,
        );
      }

      while (hasMore) {
        // Fetch trades with rate limiting
        const trades = await this.rateLimiter.executeTrades(async () => {
          return await this.polymarketClient.withRetry(
            () =>
              this.polymarketClient.getClient().data.core.getTrades({
                user: userAddress,
                limit,
                offset,
                takerOnly: false,
              }),
            `Fetch trades for user ${userAddress} (offset=${offset})`,
          );
        });

        if (!trades || trades.length === 0) {
          if (false) {
            this.logger.debug(
              `No more trades found for user: ${userAddress} at offset ${offset}`,
            );
          }
          hasMore = false;
          break;
        }

        this.logger.debug(
          `Fetched ${trades.length} trades for user: ${userAddress} (offset=${offset})`,
        );

        // Filter out trades we already have (incremental update)
        const newTrades = lastTradeTime
          ? trades.filter(
              (trade) => new Date(trade.timestamp * 1000) > lastTradeTime,
            )
          : trades;

        if (newTrades.length === 0) {
          if (false) {
            this.logger.debug(
              `No new trades for user ${userAddress}, stopping pagination`,
            );
          }
          hasMore = false;
          break;
        }

        // Save new trades
        for (const trade of newTrades) {
          try {
            await this.saveTrade(trade, userAddress);
            totalNewTrades++;
          } catch (error) {
            // If it's a unique constraint violation, skip it (already exists)
            if (
              error instanceof Error &&
              error.message.includes('Unique constraint')
            ) {
              this.logger.debug(
                `Trade ${trade.transactionHash} already exists, skipping`,
              );
            } else {
              throw error;
            }
          }
        }

        // Check if we should continue pagination
        if (trades.length < limit) {
          this.logger.debug(
            `Received fewer trades than limit (${trades.length} < ${limit}), stopping`,
          );
          hasMore = false;
        } else if (newTrades.length < trades.length) {
          // We've reached trades we already have
          if (false) {
            this.logger.debug(
              `Reached previously scraped trades, stopping pagination`,
            );
          }
          hasMore = false;
        } else {
          offset += limit;
        }
      }

      return totalNewTrades;
    } catch (error) {
      this.logger.error(
        `Error scraping trades for user ${userAddress}: ${(error as Error).message}`,
      );
      throw error;
    }
  }

  /**
   * Save a single trade to the database
   */
  private async saveTrade(
    trade: {
      proxyWallet: string;
      side: 'BUY' | 'SELL';
      asset: string;
      conditionId: string;
      size: number;
      price: number;
      timestamp: number;
      title: string;
      slug: string;
      icon?: string;
      eventSlug: string;
      outcome: string;
      outcomeIndex: number;
      transactionHash: string;
    },
    userAddress: string,
  ): Promise<void> {
    await this.prisma.userTrade.create({
      data: {
        proxyWallet: trade.proxyWallet,
        side: trade.side,
        asset: trade.asset,
        conditionId: trade.conditionId,
        size: trade.size,
        price: trade.price,
        timestamp: new Date(trade.timestamp * 1000), // Convert Unix timestamp to Date
        transactionHash: trade.transactionHash,
        title: trade.title,
        slug: trade.slug,
        icon: trade.icon || null,
        eventSlug: trade.eventSlug,
        outcome: trade.outcome,
        outcomeIndex: trade.outcomeIndex,
      },
    });
  }
}
