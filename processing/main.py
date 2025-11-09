import os
import asyncio
import asyncpg
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
if (DATABASE_URL is None):
    raise ValueError("DATABASE_URL is not set in environment variables")


def remove_schema_param(url):
    """Remove the schema parameter from DATABASE_URL for asyncpg"""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Remove 'schema' parameter if it exists
    query_params.pop('schema', None)

    # Rebuild the URL without schema parameter
    new_query = urlencode(query_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


async def main():
    ## Use regular SQL
    # Remove schema parameter for asyncpg
    asyncpg_url = remove_schema_param(DATABASE_URL)
    conn = await asyncpg.connect(dsn=asyncpg_url)
    market_count = await conn.fetchval('SELECT COUNT(*) FROM "Market";')
    print(f'Market count with SQL: {market_count}')
    await conn.close()


asyncio.run(main())
