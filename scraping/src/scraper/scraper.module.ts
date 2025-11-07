import { Module } from '@nestjs/common';
import { PolymarketClientService } from './polymarket-client.service';
import { RateLimiterService } from './rate-limiter.service';
import { MarketScraperService } from './market-scraper.service';
import { CommentScraperService } from './comment-scraper.service';
import { PriceHistoryService } from './price-history.service';
import { UserPositionsScraperService } from './user-positions-scraper.service';
import { UserTradesScraperService } from './user-trades-scraper.service';
import { ScraperOrchestratorService } from './scraper-orchestrator.service';
import { PrismaService } from '../prisma/PrismaService';
import { ConfigModule } from '../config/config.module';
import { Config } from '../config/config';

@Module({
  providers: [
    PolymarketClientService,
    RateLimiterService,
    MarketScraperService,
    CommentScraperService,
    PriceHistoryService,
    UserPositionsScraperService,
    UserTradesScraperService,
    ScraperOrchestratorService,
    PrismaService,
  ],
  exports: [
    ScraperOrchestratorService,
    MarketScraperService,
    CommentScraperService,
    PriceHistoryService,
    UserPositionsScraperService,
    UserTradesScraperService,
  ],
})
export class ScraperModule {}
