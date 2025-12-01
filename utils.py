# utils/event_cache.py

import os
import glob
import math
import pandas as pd


DEFAULT_CACHE_DIR = "events_df_cache"
USER_EVENT_ASSOCIATION_CACHE_DIR = "user_event_associations_cache"
TARGET_CHUNK_MB = 40  # aim for ~40MB per parquet file


async def load_events_df(
    conn,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> pd.DataFrame:
    """
    Load combined events (from Event + user_event_associations) with caching.

    If `cache_dir` exists and contains parquet parts, load and concatenate them.
    Otherwise:
      - query both tables
      - combine them
      - save to multiple parquet chunks (to keep each file < ~40MB)
      - return the combined DataFrame

    Returns a DataFrame indexed by `id` with at least: title, description.
    """

    # 1) Try loading from cache
    if os.path.isdir(cache_dir):
        pattern = os.path.join(cache_dir, "events_part_*.parquet")
        files = sorted(glob.glob(pattern))
        if files:
            print(f"Loading events_df from {len(files)} cached parquet files in '{cache_dir}/'")
            dfs = [pd.read_parquet(f) for f in files]
            combined = pd.concat(dfs, ignore_index=True)

            # make sure id exists and is int
            if "id" in combined.columns:
                combined["id"] = combined["id"].astype("int64")

                # drop duplicates on id before setting index
                combined = combined.drop_duplicates(subset="id", keep="first")

                combined = combined.set_index("id")

            # just in case some weird duplicates slipped through on index
            combined = combined[~combined.index.duplicated(keep="first")]

            return combined

    print("No cache found, querying database for events...")

    # 2) Base events from Event table
    event_rows = await conn.fetch('SELECT id, title, description FROM "Event";')
    events_df = pd.DataFrame([dict(r) for r in event_rows])
    events_df.set_index("id", inplace=True)

    # 3) Events seen in user_event_associations
    user_event_associations = await conn.fetch(
        'SELECT event_id, event_title, event_description FROM user_event_associations;'
    )
    user_event_associations_df = pd.DataFrame([dict(r) for r in user_event_associations])

    events_from_users = (
        user_event_associations_df[["event_id", "event_title", "event_description"]]
        .drop_duplicates()
        .rename(
            columns={
                "event_id": "id",
                "event_title": "title",
                "event_description": "description",
            }
        )
    )

    # ensure id is int and use as index
    events_from_users["id"] = events_from_users["id"].astype("int64")
    events_from_users = events_from_users.set_index("id")

    # 4) Combine: prefer rows from the original Event table if duplicated
    combined_events = pd.concat([events_df, events_from_users])

    # drop duplicate indices, keep first (original Event table wins)
    combined_events = combined_events[~combined_events.index.duplicated(keep="first")]

    # make sure index is a clean int64 and named "id"
    combined_events.index = combined_events.index.astype("int64")
    combined_events.index.name = "id"

    # 5) Cache to multiple parquet chunks to stay safely below ~40MB/file
    os.makedirs(cache_dir, exist_ok=True)

    total_bytes = combined_events.memory_usage(deep=True).sum()
    target_bytes = TARGET_CHUNK_MB * 1024**2

    n_chunks = max(1, math.ceil(total_bytes / target_bytes))
    rows_per_chunk = math.ceil(len(combined_events) / n_chunks)

    print(
        f"Caching {len(combined_events):,} rows "
        f"into {n_chunks} parquet file(s) in '{cache_dir}/' "
        f"(~{TARGET_CHUNK_MB}MB target per file)"
    )

    # reset index so "id" is a column in the saved parquet
    to_save = combined_events.reset_index()

    # store id as string to keep fastparquet happy
    to_save["id"] = to_save["id"].astype("string")

    for i in range(n_chunks):
        start = i * rows_per_chunk
        end = min(start + rows_per_chunk, len(to_save))
        chunk = to_save.iloc[start:end]

        out_path = os.path.join(cache_dir, f"events_part_{i:03d}.parquet")
        chunk.to_parquet(out_path, index=False)

    print("Caching complete.")

    # return with index set (and dedup one more time for safety)
    combined_events = to_save.set_index("id")
    combined_events.index = combined_events.index.astype("int64")
    combined_events = combined_events[~combined_events.index.duplicated(keep="first")]
    return combined_events

async def load_user_event_associations(conn, cache_dir: str = USER_EVENT_ASSOCIATION_CACHE_DIR) -> pd.DataFrame:
    """
    Load user_event_associations with caching.

    - If cached parquet parts exist in cache_dir, load and concat them.
    - Otherwise, query the DB, cast event_id to int, cache to multiple
      ~40MB parquet chunks, and return the DataFrame.
    """

    # 1) Try loading from cache
    if os.path.isdir(cache_dir):
        pattern = os.path.join(cache_dir, "user_events_part_*.parquet")
        files = sorted(glob.glob(pattern))
        if files:
            print(f"Loading user_event_associations_df from {len(files)} cached files...")
            dfs = [pd.read_parquet(f) for f in files]
            return pd.concat(dfs, ignore_index=True)

    print("No user_event cache found, querying database...")
    # 2) Query DB
    user_event_associations = await conn.fetch('SELECT * FROM user_event_associations;')
    df = pd.DataFrame([dict(r) for r in user_event_associations])

    # ensure event_id is int
    if "event_id" in df.columns:
        df["event_id"] = df["event_id"].astype("int64")

    # 3) Cache to multiple parquet files
    os.makedirs(cache_dir, exist_ok=True)

    total_bytes = df.memory_usage(deep=True).sum()
    target_bytes = TARGET_CHUNK_MB * 1024**2

    n_chunks = max(1, math.ceil(total_bytes / target_bytes))
    rows_per_chunk = math.ceil(len(df) / n_chunks)

    print(
        f"Caching {len(df):,} rows into "
        f"{n_chunks} parquet file(s) in '{cache_dir}/' "
        f"(~{TARGET_CHUNK_MB}MB target per file)"
    )

    for i in range(n_chunks):
        start = i * rows_per_chunk
        end = min(start + rows_per_chunk, len(df))
        chunk = df.iloc[start:end]

        out_path = os.path.join(cache_dir, f"user_events_part_{i:03d}.parquet")
        chunk.to_parquet(out_path, index=False)

    print("User-event caching complete.")
    return df