import os
import glob
import math
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine


trades_cache_dir = "df_trade_tags_cache"
events_cache_dir = "events_tag_cache"
chunk_size_mb = 40


def load_from_cache(cache_dir, pattern):
    file_pattern = os.path.join(cache_dir, pattern)
    files = sorted(glob.glob(file_pattern))

    if not files:
        return None

    print(f"Loading from {len(files)} parquet files in '{cache_dir}/'...")
    dfs = [pd.read_parquet(f) for f in files]
    return pd.concat(dfs, ignore_index=True)


def save_to_cache(df, cache_dir, prefix):
    os.makedirs(cache_dir, exist_ok=True)

    total_bytes = df.memory_usage(deep=True).sum()
    target_bytes = chunk_size_mb * 1024 * 1024

    n_chunks = max(1, math.ceil(total_bytes / target_bytes))
    rows_per_chunk = math.ceil(len(df) / n_chunks)

    print(f"Saving {len(df):,} rows to {n_chunks} files in '{cache_dir}/'")

    for i in range(n_chunks):
        start = i * rows_per_chunk
        end = min(start + rows_per_chunk, len(df))
        chunk = df.iloc[start:end]
        out_path = os.path.join(cache_dir, f"{prefix}_{i:03d}.parquet")
        chunk.to_parquet(out_path, index=False)

    print("done")


def load_trade_tags(cache_dir=trades_cache_dir, env_var="DATABASE_URL"):
    if os.path.isdir(cache_dir):
        df = load_from_cache(cache_dir, "df_trade_tags_part_*.parquet")
        if df is not None:
            return df

    print("No cache, querying database...")
    load_dotenv()
    db_url = os.getenv(env_var)

    if not db_url:
        raise ValueError(f"{env_var} not set")

    engine = create_engine(db_url)

    # join with UserProfile to get address instead of proxyWallet
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

    save_to_cache(df, cache_dir, "df_trade_tags_part")
    return df


def load_events_with_tags(cache_dir=events_cache_dir, env_var="DATABASE_URL"):
    if os.path.isdir(cache_dir):
        df = load_from_cache(cache_dir, "events_tag_part_*.parquet")
        if df is not None:
            return df

    print("No events cache, querying database...")
    load_dotenv()
    db_url = os.getenv(env_var)

    if not db_url:
        raise ValueError(f"{env_var} not set")

    engine = create_engine(db_url)

    query = """
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

    df = pd.read_sql(query, engine)
    save_to_cache(df, cache_dir, "events_tag_part")
    return df
