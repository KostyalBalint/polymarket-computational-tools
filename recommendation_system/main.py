import csv
from collections import defaultdict
from datetime import datetime
from typing import Tuple, List, Set

import psycopg
import os
import json
from psycopg import sql

from recommendation_system.apriori import Apriori

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
    with open("recommendation_system/config.json") as f:
        cfg = json.load(f)

    params.update(cfg)
    return params

def test_connection():
    conn_str = get_connection_string()
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT now()")

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

def export_to_csv(apriori: Apriori, file_name: str = None):
    rules_df = apriori.export_rules_to_dataframe()
    csv_filename = file_name if file_name else f'data/association_cache/association_rules_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    rules_df.to_csv(csv_filename, index=False)

def load_rules_from_csv(filepath="association_rules.csv"):
    if not os.path.exists(filepath):
        return None

    rules = []
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rules.append({
                "antecedent": row["antecedent"].split(","),
                "consequent": row["consequent"],
                "support": float(row["support"]),
                "confidence": float(row["confidence"]),
                "lift": float(row["lift"]),
            })
    return rules

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

def get_users_with_min_transactions(conn, min_transactions: int = 2, mode: str = "trades", days_back: int = 60):
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
            WHERE up.address = %s
            LIMIT 1
            """,
            (username, ),
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

def get_recommendations_for_user(username: str, force_renew_rules: bool = False, test: bool = False):
    test_connection()
    conn = psycopg.connect(get_connection_string())
    params = get_apriori_params()
    apriori = Apriori(conn)

    rules_file = "association_rules.csv"
    rules = None

    if not force_renew_rules:
        rules = load_rules_from_csv(rules_file)

    if rules:
        apriori.load_rules(rules)
    else:
        transactions = apriori.fetch_user_transactions(
            mode=params['mode'],
            min_items=params['min_items'],
            days_back=params['days_back'],
            test=False
        )
        if not transactions:
            print("No transactions found!")
            conn.close()
            return []
        frequent_item_sets = apriori.generate_frequent_item_sets(
            min_support=params['min_support'],
            test=False
        )
        if not frequent_item_sets or len(frequent_item_sets) == 1:
            print("Only 1-item_sets found!")
            conn.close()
            return []
        rules = apriori.generate_association_rules(
            min_confidence=params['min_confidence'],
            min_lift=params['min_lift'],
            test=False
        )
        if not rules:
            print("No rules found!")
            conn.close()
            return []
        export_to_csv(apriori, rules_file)

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
            test=False,
        )
        conn.close()
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
        get_recommendations_for_user(args.user)
        sys.exit(0)

    parser.print_help()



#Load association rules from most recent CSV cache
import glob
import pandas as pd

# Global cache 
cached_rules = None
cached_rules_df = None

def load_cached_rules():
    global cached_rules, cached_rules_df

    if cached_rules_df is not None:
        return cached_rules_df

    # Find most recent rules file
    cache_pattern = "data/association_cache/association_rules_*.csv"
    cache_files = glob.glob(cache_pattern)

    if not cache_files:
        print("No cached rules found. Run full Apriori first.")
        return None

    latest_file = max(cache_files, key=os.path.getmtime)
    print(f"Loading cached rules from: {latest_file}")

    cached_rules_df = pd.read_csv(latest_file)

    # Parse antecedent/consequent strings back to lists
    cached_rules_df['antecedent_list'] = cached_rules_df['antecedent'].apply(
        lambda x: [item.strip() for item in x.split(',')] if pd.notna(x) else []
    )
    cached_rules_df['consequent_list'] = cached_rules_df['consequent'].apply(
        lambda x: [item.strip() for item in x.split(',')] if pd.notna(x) else []
    )

    print(f"Loaded {len(cached_rules_df)} rules")
    return cached_rules_df

def build_and_cache_association_rules(force_rebuild=False):
    """
    Build association rules from all user transactions and cache them.
    Call this before using get_recommendations_for_user_fast()
    
    Args:
        force_rebuild: If True, rebuild even if cache exists
    """
    global cached_rules_df
    
    # Check if cache already exists
    cache_pattern = "data/association_cache/association_rules_*.csv"
    cache_files = glob.glob(cache_pattern)
    
    if cache_files and not force_rebuild:
        print(f"Cache already exists. Loading from: {max(cache_files, key=os.path.getmtime)}")
        return load_cached_rules()
    
    print("Building association rules from scratch...")
    
    # Connect to database
    conn = psycopg.connect(get_connection_string())
    params = get_apriori_params()
    
    # Initialize Apriori
    apriori = Apriori(conn)
    
    # Fetch ALL user transactions (not user-specific)
    print("Fetching all user transactions...")
    transactions = apriori.fetch_user_transactions(
        mode=params['mode'],
        min_items=params['min_items'],
        days_back=params['days_back'],
        test=False
    )
    
    if not transactions:
        print("ERROR: No transactions found!")
        conn.close()
        return None
    
    # Generate frequent itemsets
    print("Generating frequent itemsets...")
    frequent_item_sets = apriori.generate_frequent_item_sets(
        min_support=params['min_support'],
        test=False
    )
    
    if not frequent_item_sets or len(frequent_item_sets) == 1:
        print("ERROR: Only 1-itemsets found!")
        conn.close()
        return None
    
    # Generate association rules
    print("Generating association rules...")
    rules = apriori.generate_association_rules(
        min_confidence=params['min_confidence'],
        min_lift=params['min_lift'],
        test=False
    )
    
    if not rules:
        print("ERROR: No rules found!")
        conn.close()
        return None
    
    # Export to cache
    print("Caching rules to CSV...")
    export_to_csv(apriori)
    
    # Print summary
    apriori.print_summary()
    
    conn.close()
    
    # Load the newly created cache
    cached_rules_df = load_cached_rules()
    return cached_rules_df

# Added to speedup evaluation
def get_recommendations_for_user_fast(address: str, top_n: int = 10):
    global cached_rules_df

    # Load cached rules if not already loaded
    if cached_rules_df is None:
        cached_rules_df = load_cached_rules()
    
    # If still None, try to build the cache
    if cached_rules_df is None:
        print("No cached rules found. Building association rules...")
        cached_rules_df = build_and_cache_association_rules()
        
        if cached_rules_df is None:
            print("ERROR: Failed to build association rules")
            return []

    # Get user's markets from DB (this is fast - single user query)
    conn = psycopg.connect(get_connection_string())
    params = get_apriori_params()

    _, transactions = get_user_transactions_by_username(
        conn=conn,
        username=address,
        mode=params['mode'],
        min_items=1,  # Get all items for matching
        days_back=params['days_back']
    )
    conn.close()

    if not transactions:
        return []

    # Flatten user's markets
    user_markets = set()
    for t in transactions:
        user_markets.update(t)

    recommendations = []
    seen_consequents = set()

    # Sort by lift (highest first)
    sorted_rules = cached_rules_df.sort_values('lift', ascending=False)

    for _, rule in sorted_rules.iterrows():
        antecedent_set = set(rule['antecedent_list'])

        # Check if user has all antecedent items
        if antecedent_set.issubset(user_markets):
            consequent_items = rule['consequent_list']

            for item in consequent_items:
                # Skip if already in user's markets or already recommended
                if item not in user_markets and item not in seen_consequents:
                    recommendations.append({
                        'recommended_market': item,
                        'based_on': rule['antecedent_list'],
                        'confidence': rule['confidence'],
                        'lift': rule['lift'],
                        'support': rule['support']
                    })
                    seen_consequents.add(item)

                    if len(recommendations) >= top_n:
                        return recommendations

    return recommendations
