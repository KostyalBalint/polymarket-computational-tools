import { Injectable, Logger } from '@nestjs/common';
import { Polymarket } from 'polymarket-data';
import { Config } from '../config/config';
import { ClobClient } from '@polymarket/clob-client';

@Injectable()
export class PolymarketClientService {
  private readonly logger = new Logger(PolymarketClientService.name);
  private readonly client: Polymarket;
  private readonly clobClient: ClobClient;
  private readonly maxRetries: number;
  private readonly retryDelayMs: number;

  constructor(private readonly config: Config) {
    this.client = new Polymarket({
      dataEndpoint: config.polymarket.dataEndpoint,
      gammaEndpoint: config.polymarket.gammaEndpoint,
    });
    this.clobClient = new ClobClient(config.polymarket.clobEndpoint, 137);
    this.maxRetries = config.scraper.maxRetries;
    this.retryDelayMs = config.scraper.retryDelayMs;

    this.logger.log(
      `Initialized Polymarket client with data endpoint: ${config.polymarket.dataEndpoint}`,
    );
    this.logger.log(
      `Initialized Polymarket client with gamma endpoint: ${config.polymarket.gammaEndpoint}`,
    );
  }

  /**
   * Get the raw Polymarket client for direct access
   */
  getClient(): Polymarket {
    return this.client;
  }

  getClobClient(): ClobClient {
    return this.clobClient;
  }

  /**
   * Execute a function with retry logic
   */
  async withRetry<T>(
    operation: () => Promise<T>,
    operationName: string,
  ): Promise<T> {
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error as Error;

        if (attempt < this.maxRetries) {
          const delay = this.retryDelayMs * Math.pow(2, attempt - 1); // Exponential backoff
          this.logger.warn(
            `${operationName} failed (attempt ${attempt}/${this.maxRetries}): ${lastError.message}. Retrying in ${delay}ms...`,
          );
          await this.sleep(delay);
        }
      }
    }

    this.logger.error(
      `${operationName} failed after ${this.maxRetries} attempts: ${lastError?.message}`,
    );
    throw lastError;
  }

  /**
   * Sleep for a given number of milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Health check - verify connectivity to Polymarket API
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.withRetry(
        () => this.client.health(),
        'Polymarket health check',
      );
      return true;
    } catch (error) {
      this.logger.error(`Health check failed: ${(error as Error).message}`);
      return false;
    }
  }
}
