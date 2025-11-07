import { Injectable, Logger } from '@nestjs/common';
import { PolymarketClientService } from './polymarket-client.service';
import { RateLimiterService } from './rate-limiter.service';
import { PrismaService } from '../prisma/PrismaService';

@Injectable()
export class UserPositionsScraperService {
  private readonly logger = new Logger(UserPositionsScraperService.name);

  constructor(
    private readonly polymarketClient: PolymarketClientService,
    private readonly rateLimiter: RateLimiterService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Scrape positions for all users in the UserProfile table
   * Returns the number of positions scraped
   */
  async scrapeAllUserPositions(): Promise<{
    usersProcessed: number;
    positionsScraped: number;
    errors: string[];
  }> {
    const startTime = Date.now();
    this.logger.log('Starting user positions scraping...');

    let usersProcessed = 0;
    let positionsScraped = 0;
    const errors: string[] = [];
    let lastProgressLog = Date.now();
    const logInterval = 10000; // Log every 10 seconds

    try {
      // Get all users from UserProfile table
      const users = await this.prisma.userProfile.findMany({
        select: {
          //address: true,
          proxyWallet: true,
        },
      });

      this.logger.log(`Found ${users.length} users to process`);

      // Process each user
      for (const user of users) {
        try {
          const userPositions = await this.scrapeUserPositions(
            user.proxyWallet,
          );
          positionsScraped += userPositions;
          usersProcessed++;

          // Log progress periodically
          const now = Date.now();
          if (now - lastProgressLog > logInterval) {
            const elapsed = (now - startTime) / 1000; // seconds
            const rate = usersProcessed / elapsed; // users per second

            this.logger.log(
              `Progress: ${usersProcessed}/${users.length} users processed | ` +
                `Rate: ${rate.toFixed(2)} users/sec | ` +
                `Total positions: ${positionsScraped.toLocaleString()}`,
            );
            lastProgressLog = now;
          }
        } catch (error) {
          const errorMsg = `Failed to scrape positions for user ${user.proxyWallet}: ${(error as Error).message}`;
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
      `User positions scraping completed: ${usersProcessed} users, ${positionsScraped} positions in ${duration}ms`,
    );

    if (errors.length > 0) {
      this.logger.warn(`Encountered ${errors.length} errors during scraping`);
    }

    return { usersProcessed, positionsScraped, errors };
  }

  /**
   * Scrape positions for a specific user
   * Returns the number of positions scraped
   */
  async scrapeUserPositions(userAddress: string): Promise<number> {
    //this.logger.log(`Fetching positions for user: ${userAddress}`);

    try {
      // Fetch positions with rate limiting
      const positions = await this.rateLimiter.executePositions(async () => {
        return await this.polymarketClient.withRetry(
          () =>
            this.polymarketClient.getClient().data.core.getPositions({
              user: userAddress,
              sizeThreshold: 0,
              redeemable: false,
              mergeable: false,
              limit: 500,
              offset: 0,
              sortBy: 'CURRENT',
              sortDirection: 'DESC',
            }),
          `Fetch positions for user ${userAddress}`,
        );
      });

      if (!positions || positions.length === 0) {
        //this.logger.debug(`No positions found for user: ${userAddress}`);

        // Delete old positions for this user since they have none now
        await this.prisma.userPosition.deleteMany({
          where: { proxyWallet: userAddress },
        });

        return 0;
      }

      // Use transaction to ensure consistency
      // Delete old positions and insert new ones (full refresh)
      await this.prisma.$transaction(async (tx) => {
        // Delete existing positions for this user
        await tx.userPosition.deleteMany({
          where: { proxyWallet: userAddress },
        });

        // Insert new positions
        for (const position of positions) {
          await tx.userPosition.create({
            data: {
              proxyWallet: position.proxyWallet,
              asset: position.asset,
              conditionId: position.conditionId,
              size: position.size,
              avgPrice: position.avgPrice,
              initialValue: position.initialValue,
              currentValue: position.currentValue,
              cashPnl: position.cashPnl,
              percentPnl: position.percentPnl,
              totalBought: position.totalBought,
              realizedPnl: position.realizedPnl,
              percentRealizedPnl: position.percentRealizedPnl,
              curPrice: position.curPrice,
              redeemable: position.redeemable,
              mergeable: position.mergeable,
              negativeRisk: position.negativeRisk,
              title: position.title,
              slug: position.slug,
              icon: position.icon || null,
              eventSlug: position.eventSlug,
              outcome: position.outcome,
              outcomeIndex: position.outcomeIndex,
              oppositeOutcome: position.oppositeOutcome,
              oppositeAsset: position.oppositeAsset,
              endDate: position.endDate,
            },
          });
        }
      });

      return positions.length;
    } catch (error) {
      this.logger.error(
        `Error scraping positions for user ${userAddress}: ${(error as Error).message}`,
      );
      throw error;
    }
  }
}
