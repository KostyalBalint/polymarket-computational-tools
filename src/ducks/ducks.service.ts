import { Injectable } from '@nestjs/common';
import { CreateDuckInput } from './dto/create-duck.input';
import { UpdateDuckInput } from './dto/update-duck.input';

@Injectable()
export class DucksService {
  create(createDuckInput: CreateDuckInput) {
    return 'This action adds a new duck';
  }

  findAll() {
    return `This action returns all ducks`;
  }

  findOne(id: number) {
    return `This action returns a #${id} duck`;
  }

  update(id: number, updateDuckInput: UpdateDuckInput) {
    return `This action updates a #${id} duck`;
  }

  remove(id: number) {
    return `This action removes a #${id} duck`;
  }
}
