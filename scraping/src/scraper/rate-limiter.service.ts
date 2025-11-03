import { Injectable, Logger } from '@nestjs/common';
import Bottleneck from 'bottleneck';
import { Config } from '../config/config';

/**
 * Rate limiter service using Bottleneck
 * Handles rate limiting for different Polymarket API endpoints
 * According to Polymarket docs:
 * - Gamma API general: 750 req/10s
 * - Gamma Markets: 100 req/10s
 * - Gamma Comments: 100 req/10s
 * - CLOB API price history: Conservative default 100 req/10s
 */
@Injectable()
export class RateLimiterService {
  private readonly logger = new Logger(RateLimiterService.name);

  private readonly gammaMarketsLimiter: Bottleneck;
  private readonly gammaCommentsLimiter: Bottleneck;
  private readonly clobPriceHistoryLimiter: Bottleneck;

  constructor(private readonly config: Config) {
    // Gamma Markets rate limiter (100 req/10s)
    this.gammaMarketsLimiter = new Bottleneck({
      reservoir: config.scraper.gammaMarketsRateLimit,
      reservoirRefreshAmount: config.scraper.gammaMarketsRateLimit,
      reservoirRefreshInterval: 10 * 1000,
      maxConcurrent: config.scraper.maxConcurrentMarketRequests,
      minTime: 0,
    });

    // Gamma Comments rate limiter (100 req/10s)
    this.gammaCommentsLimiter = new Bottleneck({
      reservoir: config.scraper.gammaCommentsRateLimit,
      reservoirRefreshAmount: config.scraper.gammaCommentsRateLimit,
      reservoirRefreshInterval: 10 * 1000,
      maxConcurrent: config.scraper.maxConcurrentCommentRequests,
      minTime: 0,
    });

    // CLOB Price History rate limiter (100 req/10s default)
    this.clobPriceHistoryLimiter = new Bottleneck({
      reservoir: config.scraper.clobPriceHistoryRateLimit,
      reservoirRefreshAmount: config.scraper.clobPriceHistoryRateLimit,
      reservoirRefreshInterval: 10 * 1000,
      maxConcurrent: config.scraper.maxConcurrentPriceHistoryRequests,
      minTime: 0,
    });

    this.logger.log('Rate limiters initialized');
    this.logger.log(
      `- Gamma general: ${config.scraper.gammaGeneralRateLimit} req/10s`,
    );
    this.logger.log(
      `- Gamma markets: ${config.scraper.gammaMarketsRateLimit} req/10s`,
    );
    this.logger.log(
      `- Gamma comments: ${config.scraper.gammaCommentsRateLimit} req/10s`,
    );
    this.logger.log(
      `- CLOB price history: ${config.scraper.clobPriceHistoryRateLimit} req/10s`,
    );
  }

  /**
   * Execute a function with rate limiting for markets endpoint
   */
  async executeMarkets<T>(fn: () => Promise<T>): Promise<T> {
    return this.gammaMarketsLimiter.schedule(() => fn());
  }

  /**
   * Execute a function with rate limiting for comments endpoint
   */
  async executeComments<T>(fn: () => Promise<T>): Promise<T> {
    return this.gammaCommentsLimiter.schedule(() => fn());
  }
}
