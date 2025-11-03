import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { Config } from './config/config';
import { Logger } from '@nestjs/common';

/**
 * Server mode bootstrap
 * This is primarily for health checks and monitoring
 * For scraping operations, use the CLI (src/cli.ts)
 */
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const logger = new Logger('Bootstrap');

  app.enableCors();

  const config = app.get(Config);

  const { port, host } = config.server;
  logger.log(`Polymarket Scraper - Server mode`);
  logger.log(`Health checks available at http://${host}:${port}/health/liveness`);
  logger.log(`Health checks available at http://${host}:${port}/health/readiness`);
  logger.log('');
  logger.log('For scraping operations, use the CLI:');
  logger.log('  npm run scrape:all      - Run all scrapers');
  logger.log('  npm run scrape:markets  - Scrape markets only');
  logger.log('  npm run scrape:comments - Scrape comments only');
  logger.log('  npm run scrape:prices   - Capture price snapshots');
  logger.log('  npm run runs            - Show recent scraper runs');

  await app.listen(port, host);
}

bootstrap();
