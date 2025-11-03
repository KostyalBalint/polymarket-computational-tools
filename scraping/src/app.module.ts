import { Module } from '@nestjs/common';
import { ConfigModule } from './config/config.module';
import { HealthModule } from './health/health.module';
import { ScraperModule } from './scraper/scraper.module';

@Module({
  imports: [
    ConfigModule,
    HealthModule,
    ScraperModule,
  ],
  controllers: [],
  providers: [],
})
export class AppModule {}
