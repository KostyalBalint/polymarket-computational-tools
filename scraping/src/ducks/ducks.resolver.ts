import { Resolver, Query, Mutation, Args } from '@nestjs/graphql';
import { DucksService } from './ducks.service';
import { CreateDuckInput } from './dto/create-duck.input';
import { UpdateDuckInput } from './dto/update-duck.input';

@Resolver('Duck')
export class DucksResolver {
  constructor(private readonly ducksService: DucksService) {}

  @Mutation('createDuck')
  create(@Args('createDuckInput') createDuckInput: CreateDuckInput) {
    return this.ducksService.create(createDuckInput);
  }

  @Query('ducks')
  findAll() {
    return this.ducksService.findAll();
  }

  @Query('duck')
  findOne(@Args('id') id: number) {
    return this.ducksService.findOne(id);
  }

  @Mutation('updateDuck')
  update(@Args('updateDuckInput') updateDuckInput: UpdateDuckInput) {
    return this.ducksService.update(updateDuckInput.id, updateDuckInput);
  }

  @Mutation('removeDuck')
  remove(@Args('id') id: number) {
    return this.ducksService.remove(id);
  }
}
