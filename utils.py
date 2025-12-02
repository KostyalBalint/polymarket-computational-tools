import os
import glob
import math
import pandas as pd


events_cache_dir = "data/events_df_cache"
user_events_cache_dir = "data/user_event_associations_cache"
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


async def load_events_df(conn, cache_dir=events_cache_dir):
    if os.path.isdir(cache_dir):
        df = load_from_cache(cache_dir, "events_part_*.parquet")
        if df is not None:
            if "id" in df.columns:
                df["id"] = df["id"].astype("int64")
                df = df.drop_duplicates(subset="id", keep="first")
                df = df.set_index("id")
            df = df[~df.index.duplicated(keep="first")]
            return df

    print("No cache, querying database...")

    # events from Event table
    event_rows = await conn.fetch('SELECT id, title, description, "endDate" FROM "Event";')
    events_df = pd.DataFrame([dict(r) for r in event_rows])
    events_df.set_index("id", inplace=True)

    # events from user_event_associations
    user_events = await conn.fetch(
        'SELECT event_id, event_title, event_description FROM user_event_associations;'
    )
    user_events_df = pd.DataFrame([dict(r) for r in user_events])

    events_from_users = (
        user_events_df[["event_id", "event_title", "event_description"]]
        .drop_duplicates()
        .rename(columns={
            "event_id": "id",
            "event_title": "title",
            "event_description": "description",
        })
    )
    events_from_users["id"] = events_from_users["id"].astype("int64")
    events_from_users = events_from_users.set_index("id")

    # combine, prefer Event table
    combined = pd.concat([events_df, events_from_users])
    combined = combined[~combined.index.duplicated(keep="first")]
    combined.index = combined.index.astype("int64")
    combined.index.name = "id"

    # cache
    to_save = combined.reset_index()
    to_save["id"] = to_save["id"].astype("string")
    save_to_cache(to_save, cache_dir, "events_part")

    combined = to_save.set_index("id")
    combined.index = combined.index.astype("int64")
    combined = combined[~combined.index.duplicated(keep="first")]
    return combined


async def load_user_event_associations(conn, cache_dir=user_events_cache_dir):
    if os.path.isdir(cache_dir):
        df = load_from_cache(cache_dir, "user_events_part_*.parquet")
        if df is not None:
            return df

    print("No user_event cache, querying database...")

    rows = await conn.fetch('SELECT * FROM user_event_associations;')
    df = pd.DataFrame([dict(r) for r in rows])

    if "event_id" in df.columns:
        df["event_id"] = df["event_id"].astype("int64")

    save_to_cache(df, cache_dir, "user_events_part")
    return df
