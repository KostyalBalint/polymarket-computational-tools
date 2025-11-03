import { Injectable, Logger } from '@nestjs/common';
import { MarketScraperService } from './market-scraper.service';
import { CommentScraperService } from './comment-scraper.service';
import { PriceHistoryService } from './price-history.service';
import { PrismaService } from '../prisma/PrismaService';

export type ScraperRunType =
  | 'markets'
  | 'comments'
  | 'prices'
  | 'price-history'
  | 'all';

@Injectable()
export class ScraperOrchestratorService {
  private readonly logger = new Logger(ScraperOrchestratorService.name);

  constructor(
    private readonly marketScraper: MarketScraperService,
    private readonly commentScraper: CommentScraperService,
    private readonly priceHistory: PriceHistoryService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Run all scrapers in sequence
   */
  async runAll(): Promise<void> {
    this.logger.log('='.repeat(80));
    this.logger.log('Starting full scraper run...');
    this.logger.log('='.repeat(80));

    const runRecord = await this.createScraperRun('all');

    try {
      // Step 1: Scrape markets
      this.logger.log('\n[1/4] Scraping markets...');
      const marketResult = await this.marketScraper.scrapeAllMarkets();
      await this.updateScraperRun(runRecord.id, {
        marketsScraped: marketResult.marketsScraped,
        marketOutcomesScraped: marketResult.outcomesScraped,
        errors: marketResult.errors,
      });

      // Step 2: Scrape comments
      this.logger.log('\n[2/4] Scraping comments...');
      const commentResult = await this.commentScraper.scrapeAllComments();
      await this.updateScraperRun(runRecord.id, {
        commentsScraped: commentResult.commentsScraped,
        errors: [...marketResult.errors, ...commentResult.errors],
      });

      // Step 3: Scrape token price history
      this.logger.log('\n[3/4] Scraping token price history...');
      const priceHistoryResult =
        await this.priceHistory.scrapeAllTokenPriceHistory();
      await this.updateScraperRun(runRecord.id, {
        tokensProcessed: priceHistoryResult.tokensProcessed,
        priceDataPointsStored: priceHistoryResult.dataPointsStored,
        errors: [
          ...marketResult.errors,
          ...commentResult.errors,
          ...priceHistoryResult.errors,
        ],
      });

      // Step 4: Capture price snapshots
      //this.logger.log('\n[4/4] Capturing price snapshots...');
      //const priceResult = await this.priceHistory.captureAllPriceSnapshots();
      //await this.updateScraperRun(runRecord.id, {
      //  priceSnapshotsTaken: priceResult.snapshotsTaken,
      //  errors: [...marketResult.errors, ...commentResult.errors, ...priceHistoryResult.errors, ...priceResult.errors],
      //});

      // Complete the run
      await this.completeScraperRun(runRecord.id, 'completed');

      this.logger.log('\n' + '='.repeat(80));
      this.logger.log('Full scraper run completed successfully!');
      this.logger.log('='.repeat(80));
      this.printSummary(runRecord.id);
    } catch (error) {
      await this.completeScraperRun(runRecord.id, 'failed');
      this.logger.error(`Scraper run failed: ${(error as Error).message}`);
      throw error;
    }
  }

  /**
   * Run only markets scraper
   */
  async runMarkets(): Promise<void> {
    this.logger.log('Starting markets scraper...');
    const runRecord = await this.createScraperRun('markets');

    try {
      const result = await this.marketScraper.scrapeAllMarkets();
      await this.updateScraperRun(runRecord.id, {
        marketsScraped: result.marketsScraped,
        marketOutcomesScraped: result.outcomesScraped,
        errors: result.errors,
      });
      await this.completeScraperRun(runRecord.id, 'completed');
      this.logger.log('Markets scraper completed successfully!');
      this.printSummary(runRecord.id);
    } catch (error) {
      await this.completeScraperRun(runRecord.id, 'failed');
      this.logger.error(`Markets scraper failed: ${(error as Error).message}`);
      throw error;
    }
  }

  /**
   * Run only comments scraper
   */
  async runComments(): Promise<void> {
    this.logger.log('Starting comments scraper...');
    const runRecord = await this.createScraperRun('comments');

    try {
      const result = await this.commentScraper.scrapeAllComments();
      await this.updateScraperRun(runRecord.id, {
        commentsScraped: result.commentsScraped,
        errors: result.errors,
      });
      await this.completeScraperRun(runRecord.id, 'completed');
      this.logger.log('Comments scraper completed successfully!');
      this.printSummary(runRecord.id);
    } catch (error) {
      await this.completeScraperRun(runRecord.id, 'failed');
      this.logger.error(`Comments scraper failed: ${(error as Error).message}`);
      throw error;
    }
  }

  /**
   * Run only price snapshot capture
   */
  async runPrices(): Promise<void> {
    this.logger.log('Starting price snapshot capture...');
    const runRecord = await this.createScraperRun('prices');

    try {
      //const result = await this.priceHistory.captureAllPriceSnapshots();
      //await this.updateScraperRun(runRecord.id, {
      //  priceSnapshotsTaken: result.snapshotsTaken,
      //  errors: result.errors,
      //});
      //await this.completeScraperRun(runRecord.id, 'completed');
      //this.logger.log('Price snapshot capture completed successfully!');
      //this.printSummary(runRecord.id);
    } catch (error) {
      await this.completeScraperRun(runRecord.id, 'failed');
      this.logger.error(
        `Price snapshot capture failed: ${(error as Error).message}`,
      );
      throw error;
    }
  }

  /**
   * Run only token price history scraper
   */
  async runPriceHistory(): Promise<void> {
    this.logger.log('Starting token price history scraper...');
    const runRecord = await this.createScraperRun('price-history');

    try {
      const result = await this.priceHistory.scrapeAllTokenPriceHistory();
      await this.updateScraperRun(runRecord.id, {
        tokensProcessed: result.tokensProcessed,
        priceDataPointsStored: result.dataPointsStored,
        errors: result.errors,
      });
      await this.completeScraperRun(runRecord.id, 'completed');
      this.logger.log('Token price history scraper completed successfully!');
      this.printSummary(runRecord.id);
    } catch (error) {
      await this.completeScraperRun(runRecord.id, 'failed');
      this.logger.error(
        `Token price history scraper failed: ${(error as Error).message}`,
      );
      throw error;
    }
  }

  /**
   * Create a scraper run record
   */
  private async createScraperRun(runType: ScraperRunType): Promise<any> {
    return await this.prisma.scraperRun.create({
      data: {
        runType,
        status: 'running',
        startTime: new Date(),
      },
    });
  }

  /**
   * Update scraper run statistics
   */
  private async updateScraperRun(
    runId: number,
    data: {
      marketsScraped?: number;
      marketOutcomesScraped?: number;
      commentsScraped?: number;
      priceSnapshotsTaken?: number;
      tokensProcessed?: number;
      priceDataPointsStored?: number;
      errors?: string[];
    },
  ): Promise<void> {
    const updateData: any = {};

    if (data.marketsScraped !== undefined) {
      updateData.marketsScraped = data.marketsScraped;
    }
    if (data.marketOutcomesScraped !== undefined) {
      updateData.marketOutcomesScraped = data.marketOutcomesScraped;
    }
    if (data.commentsScraped !== undefined) {
      updateData.commentsScraped = data.commentsScraped;
    }
    if (data.priceSnapshotsTaken !== undefined) {
      updateData.priceSnapshotsTaken = data.priceSnapshotsTaken;
    }
    if (data.tokensProcessed !== undefined) {
      updateData.tokensProcessed = data.tokensProcessed;
    }
    if (data.priceDataPointsStored !== undefined) {
      updateData.priceDataPointsStored = data.priceDataPointsStored;
    }
    if (data.errors && data.errors.length > 0) {
      updateData.errors = data.errors.join('\n');
      updateData.errorCount = data.errors.length;
    }

    await this.prisma.scraperRun.update({
      where: { id: runId },
      data: updateData,
    });
  }

  /**
   * Complete a scraper run
   */
  private async completeScraperRun(
    runId: number,
    status: 'completed' | 'failed',
  ): Promise<void> {
    const run = await this.prisma.scraperRun.findUnique({
      where: { id: runId },
    });

    if (!run) return;

    const endTime = new Date();
    const durationMs = endTime.getTime() - run.startTime.getTime();

    await this.prisma.scraperRun.update({
      where: { id: runId },
      data: {
        status,
        endTime,
        durationMs,
      },
    });
  }

  /**
   * Print summary of scraper run
   */
  private async printSummary(runId: number): Promise<void> {
    const run = await this.prisma.scraperRun.findUnique({
      where: { id: runId },
    });

    if (!run) return;

    this.logger.log('\n' + '-'.repeat(80));
    this.logger.log('SCRAPER RUN SUMMARY');
    this.logger.log('-'.repeat(80));
    this.logger.log(`Run ID: ${run.id}`);
    this.logger.log(`Type: ${run.runType}`);
    this.logger.log(`Status: ${run.status}`);
    this.logger.log(`Duration: ${run.durationMs}ms`);
    this.logger.log(`Markets scraped: ${run.marketsScraped}`);
    this.logger.log(`Market outcomes scraped: ${run.marketOutcomesScraped}`);
    this.logger.log(`Comments scraped: ${run.commentsScraped}`);
    this.logger.log(`Price snapshots taken: ${run.priceSnapshotsTaken}`);
    this.logger.log(`Tokens processed: ${run.tokensProcessed}`);
    this.logger.log(`Price data points stored: ${run.priceDataPointsStored}`);
    if (run.errorCount > 0) {
      this.logger.log(`Errors: ${run.errorCount}`);
    }
    this.logger.log('-'.repeat(80));
  }

  /**
   * Get recent scraper runs
   */
  async getRecentRuns(limit: number = 10): Promise<any[]> {
    return await this.prisma.scraperRun.findMany({
      orderBy: { startTime: 'desc' },
      take: limit,
    });
  }
}
