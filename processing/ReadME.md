## Accessing the data with Python

### Duplicate the `.env.example` file to a `.env` file

```bash
cp .env.example .env
```

And fill the required `DATABASE_URL` variable in the `.env` file with the database connection string.

### Use Prisma Client to query the database

Because the Python Prisma client is kinda deprecated, we have a hack in progress. The generate prisma client is copied 
to this folder `.prisma/` and is accessible through the `prisma` package.

```python
from prisma import Prisma
import asyncio


async def main():
    db = Prisma()
    await db.connect()

    # Query with relations
    markets = await db.market.count()  # Your IDE will autocomplete this!

    # Type-safe access
    print(f'Market count {markets}')

    await db.disconnect()


asyncio.run(main())
```

### Alternative: Use plain old SQL with `asyncpg`

```python
import os
import asyncio
import asyncpg
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    market_count = await conn.fetchval('SELECT COUNT(*) FROM market;')
    print(f'Market count: {market_count}')
    await conn.close()
asyncio.run(main())
```
