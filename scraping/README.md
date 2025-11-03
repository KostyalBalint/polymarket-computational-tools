# Polymarket Scraper

A NestJS-based CLI tool for scraping data from Polymarket, including markets, comments, and price history. All data is stored in a PostgreSQL database using Prisma ORM.

## Features

- **Market Scraping**: Fetch all markets with their outcomes and metadata
- **Comment Scraping**: Scrape comments for each market with incremental pagination tracking
- **Price History**: Capture price snapshots over time for historical analysis
- **Rate Limiting**: Built-in rate limiting to respect Polymarket's API limits (750 req/10s for Gamma API)
- **Retry Logic**: Automatic retries with exponential backoff for failed requests
- **Normalized Database**: Fully normalized PostgreSQL schema (no JSON fields)
- **CLI Interface**: Easy-to-use command-line interface for manual execution

## Prerequisites

- Node.js 18+ (currently using v23.6.1)
- PostgreSQL 13+
- npm or yarn

## Installation

1. Install dependencies:
```bash
npm install
```

2. Set up your environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. Start PostgreSQL (using Docker Compose):
```bash
docker-compose -f docker-compose.db.yml up -d
```

4. Generate Prisma client:
```bash
npm run db:generate
```

5. Run database migrations:
```bash
npm run db:migrate:dev
```

## Database Schema

The scraper uses the following tables:

### Core Tables
- **Market**: Stores market metadata, financial metrics, and timing information
- **MarketOutcome**: Stores individual outcomes for each market (normalized, no JSON)
- **Comment**: Stores comments associated with markets, including user information and threading
- **CommentCheckpoint**: Tracks pagination state for incremental comment fetching

### Price History Tables
- **PriceSnapshot**: Stores aggregate metrics at a point in time
- **OutcomePriceSnapshot**: Stores individual outcome prices for each snapshot

### Metadata Tables
- **ScraperRun**: Tracks scraper execution history, statistics, and errors

## CLI Commands

### Scraping Commands

Run all scrapers in sequence (markets → comments → prices):
```bash
npm run scrape:all
```

Scrape only markets:
```bash
npm run scrape:markets
```

Scrape only comments (incremental with checkpoints):
```bash
npm run scrape:comments
```

Capture price snapshots:
```bash
npm run scrape:prices
```

### Monitoring Commands

View recent scraper runs:
```bash
npm run runs
```

View recent runs with custom limit:
```bash
npm run runs -- --limit 20
```

## Server Mode

The application can also run in server mode for health checks and monitoring:

```bash
npm start
```

Health check endpoints:
- `http://localhost:3000/health/liveness` - Basic health check
- `http://localhost:3000/health/readiness` - Includes database connectivity check

## Configuration

All configuration is done via environment variables in the `.env` file:

### Required
- `DATABASE_URL` - PostgreSQL connection string

### Optional (with defaults)
- `POLYMARKET_DATA_ENDPOINT` - Data API endpoint (default: https://data-api.polymarket.com)
- `POLYMARKET_GAMMA_ENDPOINT` - Gamma API endpoint (default: https://gamma-api.polymarket.com)
- `MARKETS_BATCH_SIZE` - Number of markets to fetch per batch (default: 100)
- `COMMENTS_BATCH_SIZE` - Number of comments to fetch per batch (default: 50)
- `GAMMA_GENERAL_RATE_LIMIT` - General rate limit per 10s (default: 750)
- `GAMMA_MARKETS_RATE_LIMIT` - Markets rate limit per 10s (default: 100)
- `GAMMA_COMMENTS_RATE_LIMIT` - Comments rate limit per 10s (default: 100)
- `MAX_CONCURRENT_MARKET_REQUESTS` - Max concurrent market requests (default: 5)
- `MAX_CONCURRENT_COMMENT_REQUESTS` - Max concurrent comment requests (default: 3)
- `MAX_RETRIES` - Number of retries for failed requests (default: 3)
- `RETRY_DELAY_MS` - Initial retry delay in milliseconds (default: 1000)
- `VERBOSE_LOGGING` - Enable verbose logging (default: false)

## Rate Limiting

The scraper implements rate limiting according to Polymarket's API documentation:

- **Gamma API General**: 750 requests per 10 seconds
- **Markets Endpoint**: 100 requests per 10 seconds
- **Comments Endpoint**: 100 requests per 10 seconds

Requests are queued and automatically throttled to stay within these limits.

## How It Works

### Market Scraping
1. Fetches all markets in batches using pagination
2. Creates or updates market records in the database
3. Saves market outcomes in a normalized table (no JSON)
4. Handles retries with exponential backoff

### Comment Scraping
1. Iterates through all markets in the database
2. Uses checkpoint system to track pagination state per market
3. Fetches comments incrementally (only new comments on subsequent runs)
4. Supports comment threading and user metadata

### Price History
1. Reads current prices from Market and MarketOutcome tables
2. Creates timestamped snapshots
3. Stores outcome prices in normalized format
4. Enables historical price analysis

## Development

Build the project:
```bash
npm run build
```

Run in development mode with hot reload:
```bash
npm run start:dev
```

Run tests:
```bash
npm test
```

Format code:
```bash
npm run format
```

Lint code:
```bash
npm run lint
```

## Production Deployment

1. Build the application:
```bash
npm run build
```

2. Run migrations:
```bash
npm run db:migrate:prod
```

3. Set up a cron job to run scrapers periodically:
```bash
# Example: Run every hour
0 * * * * cd /path/to/scraper && npm run scrape:all
```

## Database Migrations

Create a new migration:
```bash
npm run db:migrate:dev -- --name your_migration_name
```

Apply migrations in production:
```bash
npm run db:migrate:prod
```

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running: `docker-compose -f docker-compose.db.yml ps`
- Check DATABASE_URL in `.env` file
- Verify database exists and is accessible

### Rate Limiting Errors
- The scraper should handle rate limiting automatically
- If you see errors, check the rate limit configuration in `.env`
- Consider reducing batch sizes or concurrent requests

### Prisma Client Issues
- Regenerate the client: `npm run db:generate`
- Reset the database: `npx prisma migrate reset` (WARNING: deletes all data)

## Architecture

The scraper is built with:
- **NestJS**: Framework for dependency injection and module organization
- **Prisma**: Type-safe database ORM
- **Bottleneck**: Rate limiting with queuing
- **Commander**: CLI argument parsing
- **polymarket-data**: Official Polymarket SDK

### Service Architecture
```
ScraperOrchestratorService (coordinates all operations)
├── MarketScraperService (fetches markets)
├── CommentScraperService (fetches comments with pagination)
├── PriceHistoryService (captures price snapshots)
├── PolymarketClientService (SDK wrapper with retries)
└── RateLimiterService (rate limiting for API endpoints)
```

## License

UNLICENSED

## Support

For issues related to:
- **Polymarket API**: See https://docs.polymarket.com
- **Polymarket SDK**: See https://polymarket-data.com
- **This scraper**: Open an issue in the repository
