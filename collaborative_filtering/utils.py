# utils/trade_cache.py

import os
import glob
import math
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine


DEFAULT_CACHE_DIR = "df_trade_tags_cache"
DEFAULT_EVENTS_TAG_CACHE_DIR = "events_tag_cache"
TARGET_CHUNK_MB = 40  # aim for ~40MB per parquet file


def _load_cached_trades(cache_dir: str) -> pd.DataFrame | None:
    """Load all parquet parts from cache_dir into a single DataFrame, or None if empty."""
    pattern = os.path.join(cache_dir, "df_trade_tags_part_*.parquet")
    files = sorted(glob.glob(pattern))
    if not files:
        return None

    print(f"Loading cached data from {len(files)} parquet files in '{cache_dir}/'...")
    dfs = [pd.read_parquet(f) for f in files]
    return pd.concat(dfs, ignore_index=True)


def _query_trades_from_db(database_url: str) -> pd.DataFrame:
    """Run the SQL query and return the raw trades DataFrame."""
    engine = create_engine(database_url)

    # join with UserProfile to get address instead of proxyWallet
    # this way CF uses same user id as topic-based recommender
    query = """
    SELECT
        up.address as user_id,
        t.id as tag_id,
        t.label as tag_label,
        ut.timestamp,
        COUNT(*) as trade_count
    FROM "UserTrade" ut
    JOIN "UserProfile" up ON ut."proxyWallet" = up."proxyWallet"
    JOIN "Market" m ON ut."conditionId" = m."conditionId"
    JOIN "_MarketToTag" mt ON m.id = mt."A"
    JOIN "Tag" t ON mt."B" = t.id
    WHERE ut."proxyWallet" IS NOT NULL
      AND up.address IS NOT NULL
    GROUP BY up.address, t.id, t.label, ut.timestamp
    ORDER BY ut.timestamp
    """

    df = pd.read_sql(query, engine)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _save_trades_to_cache(df: pd.DataFrame, cache_dir: str) -> None:
    """
    Split df into chunks sized to keep each parquet file around TARGET_CHUNK_MB
    and save them in cache_dir.
    """
    os.makedirs(cache_dir, exist_ok=True)

    # approximate DataFrame size in bytes
    total_bytes = df.memory_usage(deep=True).sum()
    target_bytes = TARGET_CHUNK_MB * 1024**2

    # how many chunks do we need to stay under ~40MB per file?
    n_chunks = max(1, math.ceil(total_bytes / target_bytes))
    rows_per_chunk = math.ceil(len(df) / n_chunks)

    print(
        f"Saving {len(df):,} rows into {n_chunks} parquet file(s) in '{cache_dir}/' "
        f"(~{TARGET_CHUNK_MB}MB target per file)"
    )

    for i in range(n_chunks):
        start = i * rows_per_chunk
        end = min(start + rows_per_chunk, len(df))
        chunk = df.iloc[start:end]

        out_path = os.path.join(cache_dir, f"df_trade_tags_part_{i:03d}.parquet")
        chunk.to_parquet(out_path, index=False)

    print("Caching complete.")


def load_trade_tags(
    cache_dir: str = DEFAULT_CACHE_DIR,
    env_var: str = "DATABASE_URL",
) -> pd.DataFrame:
    """
    Load trade-tag data from parquet cache if available, otherwise query DB and cache it.

    Parameters
    ----------
    cache_dir : str
        Directory where parquet chunks are stored.
    env_var : str
        Name of the environment variable with the database URL.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: user_id, tag_id, tag_label, timestamp, trade_count.
    """
    # 1) Try cache
    if os.path.isdir(cache_dir):
        df = _load_cached_trades(cache_dir)
        if df is not None:
            return df

    # 2) Cache miss → query DB
    print("No cache found. Querying database...")
    load_dotenv()
    database_url = os.getenv(env_var)
    if not database_url:
        raise ValueError(f"{env_var} is not set in environment/.env")

    df = _query_trades_from_db(database_url)
    _save_trades_to_cache(df, cache_dir)
    return df

def load_events_with_tags(
    cache_dir: str = DEFAULT_EVENTS_TAG_CACHE_DIR,
    env_var: str = "DATABASE_URL",
) -> pd.DataFrame:
    """
    Load event–tag data with caching in ~40MB parquet chunks.

    Returns a DataFrame with columns:
    event_id, title, slug, tag_id, tag_label
    """

    # try cache first
    if os.path.isdir(cache_dir):
        pattern = os.path.join(cache_dir, "events_tag_part_*.parquet")
        files = sorted(glob.glob(pattern))
        if files:
            print(f"Loading events_df from {len(files)} cached files in '{cache_dir}/'...")
            dfs = [pd.read_parquet(f) for f in files]
            return pd.concat(dfs, ignore_index=True)

    # no cache → query DB
    print("No events_tag cache found, querying database...")
    load_dotenv()
    db_url = os.getenv(env_var)
    if not db_url:
        raise ValueError(f"{env_var} is not set in environment/.env")

    engine = create_engine(db_url)

    q = """
    SELECT
        e.id as event_id,
        e.title,
        e.slug,
        t.id as tag_id,
        t.label as tag_label
    FROM "Event" e
    JOIN "_EventToMarket" em ON e.id = em."A"
    JOIN "Market" m ON em."B" = m.id
    JOIN "_MarketToTag" mt ON m.id = mt."A"
    JOIN "Tag" t ON mt."B" = t.id
    """

    df = pd.read_sql(q, engine)

    # cache in multiple parquet files
    os.makedirs(cache_dir, exist_ok=True)

    total_bytes = df.memory_usage(deep=True).sum()
    target_bytes = TARGET_CHUNK_MB * 1024**2
    n_chunks = max(1, math.ceil(total_bytes / target_bytes))
    rows_per_chunk = math.ceil(len(df) / n_chunks)

    print(
        f"Caching {len(df):,} rows into {n_chunks} parquet file(s) in '{cache_dir}/' "
        f"(~{TARGET_CHUNK_MB}MB target per file)"
    )

    for i in range(n_chunks):
        start = i * rows_per_chunk
        end = min(start + rows_per_chunk, len(df))
        chunk = df.iloc[start:end]
        out_path = os.path.join(cache_dir, f"events_tag_part_{i:03d}.parquet")
        chunk.to_parquet(out_path, index=False)

    print("Events–tag caching complete.")
    return df