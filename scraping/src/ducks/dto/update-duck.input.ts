import { CreateDuckInput } from './create-duck.input';
import { PartialType } from '@nestjs/mapped-types';

export class UpdateDuckInput extends PartialType(CreateDuckInput) {
  id: number;
}
