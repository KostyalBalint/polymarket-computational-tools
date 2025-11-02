import { Test, TestingModule } from '@nestjs/testing';
import { DucksResolver } from './ducks.resolver';
import { DucksService } from './ducks.service';

describe('DucksResolver', () => {
  let resolver: DucksResolver;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [DucksResolver, DucksService],
    }).compile();

    resolver = module.get<DucksResolver>(DucksResolver);
  });

  it('should be defined', () => {
    expect(resolver).toBeDefined();
  });
});
