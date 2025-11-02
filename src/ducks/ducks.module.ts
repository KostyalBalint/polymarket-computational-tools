import { Module } from '@nestjs/common';
import { DucksService } from './ducks.service';
import { DucksResolver } from './ducks.resolver';

@Module({
  providers: [DucksResolver, DucksService],
})
export class DucksModule {}
