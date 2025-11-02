import { Test, TestingModule } from '@nestjs/testing';
import { DucksService } from './ducks.service';

describe('DucksService', () => {
  let service: DucksService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [DucksService],
    }).compile();

    service = module.get<DucksService>(DucksService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
