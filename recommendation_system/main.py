from collections import defaultdict
from datetime import datetime
from multiprocessing.spawn import prepare
from typing import Tuple, List, Set

import psycopg
import os
import json
from psycopg import sql

from apriori import Apriori

def get_connection_string():
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    with open("config.json") as f:
        cfg = json.load(f)
    return cfg["connection"]

def get_apriori_params():
    # Default values
    params = {
        'mode': 'trades',  # Transaction type: positions/trades/sessions/events
        'min_items': 3,  # Minimum items per transaction
        'days_back': 90,  # Days of history to analyze
        'min_support': 0.01,  # 1% minimum support
        'min_confidence': 0.3,  # 10% minimum confidence
        'min_lift': 1.1  # 1.2x minimum lift
    }
    with open("config.json") as f:
        cfg = json.load(f)

    params.update(cfg)
    return params

def test_connection():
    conn_str = get_connection_string()
    with psycopg.connect(conn_str) as conn:
        print("Connected successfully!")
        with conn.cursor() as cur:
            cur.execute("SELECT now()")
            print("Current time:", cur.fetchone()[0])

def print_schema():
    try:
        database_url = get_connection_string()
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = cur.fetchall()

            if not tables:
                print("No tables found in schema 'public'.")
            else:
                with conn.cursor() as cur:
                    for (tname,) in tables:
                        cur.execute("""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = %s
                            ORDER BY ordinal_position;
                        """, (tname,))
                        cols = [row[0] for row in cur.fetchall()]
                        print(f" - {tname} : {', '.join(cols)}")
    except psycopg.OperationalError as e:
        print("Connection failed:", e)

def get_top_rows(table_name, limit=5):
    url = get_connection_string()
    try:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                query = sql.SQL("SELECT * FROM {} LIMIT %s").format(
                    sql.Identifier(table_name)
                )
                cur.execute(query, (limit,))
                col_names = [desc.name for desc in cur.description]
                rows = cur.fetchall()
                print(f"\nTop {limit} rows from table '{table_name}':")
                print(", ".join(col_names))
                for row in rows:
                    print(row)

    except psycopg.OperationalError as e:
        print("Connection failed:", e)
    except psycopg.errors.UndefinedTable:
        print(f"Table '{table_name}' does not exist.")

def export_to_csv(apriori: Apriori):
    rules_df = apriori.export_rules_to_dataframe()
    csv_filename = f'association_rules_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    rules_df.to_csv(csv_filename, index=False)
    print(f"Rules exported to: {csv_filename}")

def get_users():
    # Get some example user positions from database
    conn = psycopg.connect(get_connection_string())
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT
            up."proxyWallet",
            ARRAY_AGG(up.slug || '_' || up.outcome) as markets
        FROM "UserPosition" up
        WHERE up.size > 0 
            AND (up."endDate" IS NULL 
                 OR up."endDate" = '' 
                 OR up."endDate"::timestamp > NOW())
        GROUP BY up."proxyWallet"
        HAVING COUNT(*) >= 2
    """)

    users = cursor.fetchall()
    cursor.close()
    return users

def get_address_from_username(conn, username: str) -> str | None:
    """
    Return a user's proxyWallet given a username.
    Matches on name, pseudonym, or address.
    Case-insensitive. Handles NULL values safely.
    """

    query = """
        SELECT "proxyWallet"
        FROM "UserProfile"
        WHERE COALESCE(name, '') ILIKE %s
           OR COALESCE(pseudonym, '') ILIKE %s
           OR COALESCE(address, '') ILIKE %s
        LIMIT 1;
    """

    like = f"%{username}%"

    with conn.cursor() as cur:
        cur.execute(query, (like, like, like))
        row = cur.fetchone()

    if row:
        return row[0]

    print(f"No user found matching username '{username}'")
    return None

def get_users_with_min_transactions(conn, min_transactions: int = 2, mode: str = "trades", days_back: int = 30):
    if mode == "positions":
        query = """
            SELECT 
                up."proxyWallet",
                COUNT(*) AS tx_count
            FROM "UserPosition" up
            WHERE up.size > 0
              AND (up."endDate" IS NULL
                   OR up."endDate" = ''
                   OR up."endDate"::timestamp > NOW())
            GROUP BY up."proxyWallet"
            HAVING COUNT(*) > %s;
        """
        params = (min_transactions,)

    elif mode == "trades":
        query = """
            SELECT 
                ut."proxyWallet",
                COUNT(*) AS tx_count
            FROM "UserTrade" ut
            WHERE ut.timestamp >= NOW() - INTERVAL '1 day' * %s
            GROUP BY ut."proxyWallet"
            HAVING COUNT(*) > %s;
        """
        params = (days_back, min_transactions)

    elif mode == "sessions":
        query = """
            SELECT 
                ut."proxyWallet",
                COUNT(DISTINCT ut."proxyWallet" || '_' || DATE(ut.timestamp)) AS tx_count
            FROM "UserTrade" ut
            WHERE ut.timestamp >= NOW() - INTERVAL '1 day' * %s
            GROUP BY ut."proxyWallet"
            HAVING COUNT(DISTINCT ut."proxyWallet" || '_' || DATE(ut.timestamp)) > %s;
        """
        params = (days_back, min_transactions)

    elif mode == "events":
        query = """
            SELECT
                ut."proxyWallet",
                COUNT(DISTINCT ut."proxyWallet" || '_' || ut."eventSlug") AS tx_count
            FROM "UserTrade" ut
            WHERE ut."eventSlug" IS NOT NULL
              AND ut.timestamp >= NOW() - INTERVAL '1 day' * %s
            GROUP BY ut."proxyWallet"
            HAVING COUNT(DISTINCT ut."proxyWallet" || '_' || ut."eventSlug") > %s;
        """
        params = (days_back, min_transactions)

    else:
        raise ValueError(f"Invalid mode '{mode}'")

    with conn.cursor() as cur:
        cur.execute(query, params)
        wallets = cur.fetchall()

    if not wallets:
        return []

    # Map proxyWallet → usernames (name or pseudonym)
    results = []
    with conn.cursor() as cur:
        for wallet, tx_count in wallets:
            cur.execute("""
                SELECT COALESCE("name", "pseudonym", "address") 
                FROM "UserProfile"
                WHERE "proxyWallet" = %s
                LIMIT 1;
            """, (wallet,))
            row = cur.fetchone()
            username = row[0] if row else None
            results.append((username, wallet, tx_count))

    return results

def get_user_transactions_by_username(
    conn,
    username: str,
    mode: str = "trades",
    min_items: int = 2,
    days_back: int = 60,
) -> Tuple[str | None, List[Set[str]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                up."proxyWallet"
            FROM "UserProfile" up
            WHERE LOWER(up.name) = LOWER(%s)
               OR LOWER(up.pseudonym) = LOWER(%s)
            LIMIT 1
            """,
            (username, username),
        )
        row = cur.fetchone()

    if not row:
        print(f"No user found with name/pseudonym = {username}")
        return None, []

    proxy_wallet = row[0]
    print(f"Found proxyWallet for '{username}': {proxy_wallet}")

    cursor = conn.cursor()
    print("FETCHING TRANSACTION DATA FOR SINGLE USER")

    if mode == "positions":
        query = """
        SELECT 
            up."proxyWallet" as transaction_id,
            up.slug || '_' || up.outcome as item
        FROM "UserPosition" up
        WHERE up.size > 0 
            AND (up."endDate" IS NULL 
                 OR up."endDate" = '' 
                 OR up."endDate"::timestamp > NOW())
            AND up."proxyWallet" = %s
        ORDER BY up."proxyWallet"
        """
        cursor.execute(query, (proxy_wallet,))

    elif mode == "trades":
        query = """
        SELECT 
            ut."proxyWallet" as transaction_id,
            ut.slug || '_' || ut.outcome as item
        FROM "UserTrade" ut
        WHERE ut."proxyWallet" = %s
          AND ut.timestamp >= NOW() - INTERVAL '1 day' * %s
        ORDER BY ut."proxyWallet"
        """
        cursor.execute(query, (proxy_wallet, days_back))

    elif mode == "sessions":
        query = """
        SELECT 
            ut."proxyWallet" || '_' || DATE(ut.timestamp) as transaction_id,
            ut.slug || '_' || ut.outcome as item
        FROM "UserTrade" ut
        WHERE ut."proxyWallet" = %s
          AND ut.timestamp >= NOW() - INTERVAL '1 day' * %s
        ORDER BY transaction_id
        """
        cursor.execute(query, (proxy_wallet, days_back))

    elif mode == "events":
        query = """
        SELECT 
            ut."proxyWallet" || '_' || ut."eventSlug" as transaction_id,
            ut.slug || '_' || ut.outcome as item
        FROM "UserTrade" ut
        WHERE ut."proxyWallet" = %s
          AND ut.timestamp >= NOW() - INTERVAL '1 day' * %s
          AND ut."eventSlug" IS NOT NULL
        ORDER BY transaction_id
        """
        cursor.execute(query, (proxy_wallet, days_back))

    else:
        cursor.close()
        raise ValueError(f"Invalid mode: {mode}")

    results = cursor.fetchall()
    cursor.close()

    print(f"Raw rows fetched for user: {len(results)}")

    transaction_dict = defaultdict(set)
    for transaction_id, item in results:
        if item:
            transaction_dict[transaction_id].add(item)

    transactions = [
        items for items in transaction_dict.values()
        if len(items) >= min_items
    ]

    print(f"User '{username}' transaction statistics:")
    print(f"\tTotal transactions (after min_items={min_items}): {len(transactions)}")
    if transactions:
        avg_items = sum(len(t) for t in transactions) / len(transactions)
        print(f"\tAverage items per transaction: {avg_items:.2f}")
        print(f"\tTotal unique items: {len(set().union(*transactions))}")

    return proxy_wallet, transactions

def get_user_transactions_by_address(
    conn,
    user_address: str,
    mode: str = "trades",
    min_items: int = 2,
    days_back: int = 60
):
    cursor = conn.cursor()
    print(f"Fetching transactions for address: {user_address}")

    if mode == "positions":
        query = """
        SELECT 
            up."proxyWallet" AS transaction_id,
            up.slug || '_' || up.outcome AS item
        FROM "UserPosition" up
        WHERE up."proxyWallet" = %s
          AND up.size > 0
          AND (up."endDate" IS NULL
               OR up."endDate" = ''
               OR up."endDate"::timestamp > NOW())
        ORDER BY up."proxyWallet";
        """
        cursor.execute(query, (user_address,))

    elif mode == "trades":
        query = """
        SELECT 
            ut."proxyWallet" AS transaction_id,
            ut.slug || '_' || ut.outcome AS item
        FROM "UserTrade" ut
        WHERE ut."proxyWallet" = %s
          AND ut.timestamp >= NOW() - INTERVAL '1 day' * %s
        ORDER BY ut."proxyWallet";
        """
        cursor.execute(query, (user_address, days_back))

    elif mode == "sessions":
        query = """
        SELECT 
            ut."proxyWallet" || '_' || DATE(ut.timestamp) AS transaction_id,
            ut.slug || '_' || ut.outcome AS item
        FROM "UserTrade" ut
        WHERE ut."proxyWallet" = %s
          AND ut.timestamp >= NOW() - INTERVAL '1 day' * %s
        ORDER BY transaction_id;
        """
        cursor.execute(query, (user_address, days_back))

    elif mode == "events":
        query = """
        SELECT 
            ut."proxyWallet" || '_' || ut."eventSlug" AS transaction_id,
            ut.slug || '_' || ut.outcome AS item
        FROM "UserTrade" ut
        WHERE ut."proxyWallet" = %s
          AND ut.timestamp >= NOW() - INTERVAL '1 day' * %s
          AND ut."eventSlug" IS NOT NULL
        ORDER BY transaction_id;
        """
        cursor.execute(query, (user_address, days_back))

    else:
        cursor.close()
        raise ValueError(f"Invalid mode: {mode}")

    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        print("No transactions found for this address.")
        return user_address, []

    from collections import defaultdict
    transaction_dict = defaultdict(set)

    for tx_id, item in rows:
        if item:
            transaction_dict[tx_id].add(item)
    transactions = [
        items for items in transaction_dict.values()
        if len(items) >= min_items
    ]

    print(f"Found {len(transactions)} valid transactions for {user_address}")
    return user_address, transactions


def get_recommendations_for_user(address: str):
    test_connection()
    conn = psycopg.connect(get_connection_string())
    params = get_apriori_params()
    apriori = Apriori(conn)
    transactions = apriori.fetch_user_transactions(
        mode=params['mode'],
        min_items=params['min_items'],
        days_back=params['days_back'],
        test=False
    )
    if not transactions:
        print("No transactions found!")
        conn.close()
        exit(1)
    frequent_item_sets = apriori.generate_frequent_item_sets(
        min_support=params['min_support'],
        test=False
    )
    if not frequent_item_sets or len(frequent_item_sets) == 1:
        print("Only 1-item_sets found!")
        conn.close()
        exit(1)
    rules = apriori.generate_association_rules(
        min_confidence=params['min_confidence'],
        min_lift=params['min_lift'],
        test=False
    )
    if not rules:
        print("No rules found!")
        conn.close()
        exit(1)
    apriori.print_summary()
    export_to_csv(apriori)
    wallet, transactions = get_user_transactions_by_address(
        conn=conn,
        user_address=address,
        mode=params['mode'],
        min_items=params['min_items'],
        days_back=params['days_back']
    )
    if transactions is None:
        print(f"No transactions found for user name address {address}")
    else:
        user_markets = list({item for group in transactions for item in group})
        recommendations = apriori.get_recommendations(
            user_markets=user_markets,
            top_n=5,
            test=True,
        )
        print(recommendations)
        return recommendations
    conn.close()
    return None

def get_recommendations_for_user_by_name(username: str):
    test_connection()
    conn = psycopg.connect(get_connection_string())
    params = get_apriori_params()
    apriori = Apriori(conn)
    transactions = apriori.fetch_user_transactions(
        mode=params['mode'],
        min_items=params['min_items'],
        days_back=params['days_back'],
        test=False
    )
    if not transactions:
        print("No transactions found!")
        conn.close()
        exit(1)
    frequent_item_sets = apriori.generate_frequent_item_sets(
        min_support=params['min_support'],
        test=False
    )
    if not frequent_item_sets or len(frequent_item_sets) == 1:
        print("Only 1-item_sets found!")
        conn.close()
        exit(1)
    rules = apriori.generate_association_rules(
        min_confidence=params['min_confidence'],
        min_lift=params['min_lift'],
        test=False
    )
    if not rules:
        print("No rules found!")
        conn.close()
        exit(1)
    apriori.print_summary()
    export_to_csv(apriori)
    wallet, transactions = get_user_transactions_by_username(
        conn=conn,
        username=username,
        mode=params['mode'],
        min_items=params['min_items'],
        days_back=params['days_back']
    )
    if transactions is None:
        print(f"No transactions found for user name {username}")
    else:
        user_markets = list({item for group in transactions for item in group})
        recommendations = apriori.get_recommendations(
            user_markets=user_markets,
            top_n=5,
            test=True,
        )
        print(recommendations)
        return recommendations
    conn.close()
    return None

def default_run():
    input("Press Enter to start...")
    params = get_apriori_params()
    print(f"Parameters:")
    for key, value in params.items():
        print(f"\t{key}: {value}")

    try:
        conn_str = get_connection_string()
        conn = psycopg.connect(conn_str)
        print("Connected to database successfully!")
        test_connection()
    except Exception as e:
        print(f"Database connection failed: {e}")
        exit(1)

    apriori = Apriori(conn)
    transactions = apriori.fetch_user_transactions(
        mode=params['mode'],
        min_items=params['min_items'],
        days_back=params['days_back'],
        test=True
    )

    if not transactions:
        print("No transactions found!")
        conn.close()
        exit(1)

    frequent_item_sets = apriori.generate_frequent_item_sets(
        min_support=params['min_support'],
        test=True
    )

    if not frequent_item_sets or len(frequent_item_sets) == 1:
        print("Only 1-item_sets found!")
        conn.close()
        exit(1)

    rules = apriori.generate_association_rules(
        min_confidence=params['min_confidence'],
        min_lift=params['min_lift'],
        test=True
    )

    if not rules:
        print("No rules found!")
        conn.close()
        exit(1)

    # Print summary
    apriori.print_summary()
    export_to_csv(apriori)

    users = get_users()
    test_users = users[:3]
    print(test_users)
    if test_users:
        print("Example users with current positions")
        for i, (user_id, transations) in enumerate(test_users, 1):
            print(f"\n{i}. User {user_id}")
            print(f"\tMarkets: {transations[:3]}{'...' if len(transations) > 3 else ''}")

        for i, (user_id, transations) in enumerate(test_users, 1):
            print("---------------------------------------------------------")
            print(f"RECOMMENDATIONS FOR USER ID{i}")
            recommendations = apriori.get_recommendations(
                user_markets=transations,
                top_n=5,
                test=True
            )
            if not recommendations:
                print("\tNo recommendations found for this user.")

    while True:
        username = input("\nPlease enter user to get recommendations for or press Enter to quit:")
        if username == "":
            break
        wallet, transactions = get_user_transactions_by_username(
            conn = conn,
            username=username,
            mode=params['mode'],
            min_items=params['min_items'],
            days_back=params['days_back']
        )
        if transactions is None:
            print(f"No transactions found for user name {username}")
        else:
            user_markets = list({item for group in transactions for item in group})
            recommendations = apriori.get_recommendations(
                user_markets=user_markets,
                top_n=5,
                test=True,
            )
            print(recommendations)

    conn.close()
    print("\nProgram finished...")

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Apriori-based betting recommender"
    )
    parser.add_argument(
        "--user",
        "-u",
        type=str,
        help="Generate recommendations for a specific username"
    )

    args = parser.parse_args()

    # CASE 1: No arguments → run full Apriori pipeline
    if len(sys.argv) == 1:
        default_run()
        sys.exit(0)

    # CASE 2: Command-line username → only run recommendations for user
    if args.user:
        get_recommendations_for_user_by_name(args.user)
        sys.exit(0)

    parser.print_help()