import { Module } from '@nestjs/common';
import { PolymarketClientService } from './polymarket-client.service';
import { RateLimiterService } from './rate-limiter.service';
import { MarketScraperService } from './market-scraper.service';
import { CommentScraperService } from './comment-scraper.service';
import { PriceHistoryService } from './price-history.service';
import { ScraperOrchestratorService } from './scraper-orchestrator.service';
import { PrismaService } from '../prisma/PrismaService';

@Module({
  providers: [
    PolymarketClientService,
    RateLimiterService,
    MarketScraperService,
    CommentScraperService,
    PriceHistoryService,
    ScraperOrchestratorService,
    PrismaService,
  ],
  exports: [
    ScraperOrchestratorService,
    MarketScraperService,
    CommentScraperService,
    PriceHistoryService,
  ],
})
export class ScraperModule {}
