import { get } from 'env-var';

export class Config {
  applicationName = 'Polymarket Scraper';

  server = {
    host: get('SERVER_HOST').default('0.0.0.0').asString(),
    port: get('SERVER_PORT').default('3000').asString(),
  };

  database = {
    url: get('DATABASE_URL').required().asString(),
  };

  polymarket = {
    // API endpoints (can be overridden in tests or for custom deployments)
    dataEndpoint: get('POLYMARKET_DATA_ENDPOINT')
      .default('https://data-api.polymarket.com')
      .asString(),
    gammaEndpoint: get('POLYMARKET_GAMMA_ENDPOINT')
      .default('https://gamma-api.polymarket.com')
      .asString(),
    clobEndpoint: get('POLYMARKET_CLOB_ENDPOINT')
      .default('https://clob.polymarket.com')
      .asString(),
  };

  scraper = {
    // Batch sizes for fetching data
    marketsBatchSize: get('MARKETS_BATCH_SIZE').default('100').asIntPositive(),
    commentsBatchSize: get('COMMENTS_BATCH_SIZE').default('50').asIntPositive(),

    // Rate limiting (per 10 seconds as per Polymarket docs)
    // Gamma API: 750 req/10s general, 100 req/10s for comments/markets
    // CLOB API: Conservative default for price history
    // Data API: Conservative defaults for user positions/trades
    gammaGeneralRateLimit: get('GAMMA_GENERAL_RATE_LIMIT')
      .default('750')
      .asIntPositive(),
    gammaMarketsRateLimit: get('GAMMA_MARKETS_RATE_LIMIT')
      .default('100')
      .asIntPositive(),
    gammaCommentsRateLimit: get('GAMMA_COMMENTS_RATE_LIMIT')
      .default('100')
      .asIntPositive(),
    clobPriceHistoryRateLimit: get('CLOB_PRICE_HISTORY_RATE_LIMIT')
      .default('100')
      .asIntPositive(),
    dataPositionsRateLimit: get('DATA_POSITIONS_RATE_LIMIT')
      .default('90')
      .asIntPositive(),
    dataTradesRateLimit: get('DATA_TRADES_RATE_LIMIT')
      .default('90')
      .asIntPositive(),

    // Concurrency settings
    maxConcurrentMarketRequests: get('MAX_CONCURRENT_MARKET_REQUESTS')
      .default('5')
      .asIntPositive(),
    maxConcurrentCommentRequests: get('MAX_CONCURRENT_COMMENT_REQUESTS')
      .default('3')
      .asIntPositive(),
    maxConcurrentPriceHistoryRequests: get(
      'MAX_CONCURRENT_PRICE_HISTORY_REQUESTS',
    )
      .default('10')
      .asIntPositive(),

    // Price history settings
    priceHistoryInterval: get('PRICE_HISTORY_INTERVAL')
      .default('1d')
      .asEnum(['1m', '1h', '6h', '1d', '1w', 'max']),
    priceHistoryFidelity: get('PRICE_HISTORY_FIDELITY')
      .default('60')
      .asIntPositive(), // minutes
    priceHistoryLookbackDays: get('PRICE_HISTORY_LOOKBACK_DAYS')
      .default('30')
      .asIntPositive(),

    // Retry configuration
    maxRetries: get('MAX_RETRIES').default('3').asIntPositive(),
    retryDelayMs: get('RETRY_DELAY_MS').default('1000').asIntPositive(),

    // Logging
    verboseLogging: get('VERBOSE_LOGGING').default('false').asBool(),
  };
}
