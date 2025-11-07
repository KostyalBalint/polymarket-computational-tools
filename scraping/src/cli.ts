#!/usr/bin/env node

import { NestFactory } from '@nestjs/core';
import { Command } from 'commander';
import { AppModule } from './app.module';
import { ScraperOrchestratorService } from './scraper/scraper-orchestrator.service';
import { Logger } from '@nestjs/common';

const logger = new Logger('CLI');

/**
 * CLI entry point for Polymarket Scraper
 */
async function bootstrap() {
  const program = new Command();

  program
    .name('polymarket-scraper')
    .description('CLI tool for scraping Polymarket data')
    .version('1.0.0');

  // Scrape all command
  program
    .command('scrape:all')
    .description(
      'Run all scrapers (markets, comments, price history, and price snapshots)',
    )
    .action(async () => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: ['log', 'error', 'warn', 'debug'],
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        await orchestrator.runAll();
        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(`Scraper failed: ${(error as Error).message}`);
        await app.close();
        process.exit(1);
      }
    });

  // Scrape markets command
  program
    .command('scrape:markets')
    .description('Scrape all markets from Polymarket')
    .action(async () => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: ['log', 'error', 'warn', 'debug'],
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        await orchestrator.runMarkets();
        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(`Market scraper failed: ${(error as Error).message}`);
        await app.close();
        process.exit(1);
      }
    });

  // Scrape comments command
  program
    .command('scrape:comments')
    .description('Scrape comments for all markets')
    .action(async () => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: ['log', 'error', 'warn', 'debug'],
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        await orchestrator.runComments();
        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(`Comment scraper failed: ${(error as Error).message}`);
        await app.close();
        process.exit(1);
      }
    });

  // Scrape prices command
  program
    .command('scrape:prices')
    .description('Capture price snapshots for all markets')
    .action(async () => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: ['log', 'error', 'warn', 'debug'],
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        await orchestrator.runPrices();
        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(`Price snapshot failed: ${(error as Error).message}`);
        await app.close();
        process.exit(1);
      }
    });

  // Scrape price history command
  program
    .command('scrape:price-history')
    .description('Scrape historical price data for all tokens from CLOB API')
    .option(
      '-r, --resume',
      'Resume scraping from the last marketOutcome without prices',
    )
    .action(async (options) => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: ['log', 'error', 'warn', 'debug'],
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        await orchestrator.runPriceHistory(options.resume);
        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(
          `Price history scraper failed: ${(error as Error).message}`,
        );
        await app.close();
        process.exit(1);
      }
    });

  // Scrape user positions command
  program
    .command('scrape:user-positions')
    .description('Scrape current positions for all users in UserProfile table')
    .action(async () => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: ['log', 'error', 'warn', 'debug'],
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        await orchestrator.runUserPositions();
        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(
          `User positions scraper failed: ${(error as Error).message}`,
        );
        await app.close();
        process.exit(1);
      }
    });

  // Scrape user trades command
  program
    .command('scrape:user-trades')
    .description('Scrape historical trades for all users in UserProfile table')
    .action(async () => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: ['log', 'error', 'warn', 'debug'],
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        await orchestrator.runUserTrades();
        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(
          `User trades scraper failed: ${(error as Error).message}`,
        );
        await app.close();
        process.exit(1);
      }
    });

  // Show recent runs
  program
    .command('runs')
    .description('Show recent scraper runs')
    .option('-l, --limit <number>', 'Number of runs to show', '10')
    .action(async (options) => {
      const app = await NestFactory.createApplicationContext(AppModule, {
        logger: false,
      });

      try {
        const orchestrator = app.get(ScraperOrchestratorService);
        const runs = await orchestrator.getRecentRuns(parseInt(options.limit));

        console.log('\nRecent Scraper Runs:');
        console.log('='.repeat(120));

        for (const run of runs) {
          console.log(
            `ID: ${run.id} | Type: ${run.runType.padEnd(15)} | Status: ${run.status.padEnd(10)} | Duration: ${run.durationMs || 0}ms`,
          );
          console.log(
            `  Markets: ${run.marketsScraped} | Comments: ${run.commentsScraped} | Snapshots: ${run.priceSnapshotsTaken}`,
          );
          console.log(
            `  Tokens: ${run.tokensProcessed} | Price Data Points: ${run.priceDataPointsStored}`,
          );
          console.log(
            `  Users: ${run.usersProcessed} | Positions: ${run.userPositionsScraped} | Trades: ${run.userTradesScraped}`,
          );
          console.log(`  Started: ${run.startTime.toISOString()}`);
          if (run.errorCount > 0) {
            console.log(`  Errors: ${run.errorCount}`);
          }
          console.log('-'.repeat(120));
        }

        await app.close();
        process.exit(0);
      } catch (error) {
        logger.error(`Failed to fetch runs: ${(error as Error).message}`);
        await app.close();
        process.exit(1);
      }
    });

  await program.parseAsync(process.argv);
}

bootstrap().catch((error) => {
  logger.error(`Bootstrap failed: ${error.message}`);
  process.exit(1);
});
