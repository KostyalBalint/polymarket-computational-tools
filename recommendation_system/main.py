from datetime import datetime
from typing import Tuple, List

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

def get_user_markets_by_name(user_name: str) -> Tuple[str, List[str]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                up."proxyWallet",
                ARRAY_AGG(upos.slug || '_' || upos.outcome) as markets
            FROM "UserProfile" up
            LEFT JOIN "UserPosition" upos 
                ON up."proxyWallet" = upos."proxyWallet"
                AND upos.size > 0
                AND (upos."endDate" IS NULL 
                     OR upos."endDate" = '' 
                     OR upos."endDate"::timestamp > NOW())
            WHERE LOWER(up.name) = LOWER(%s) 
                OR LOWER(up.pseudonym) = LOWER(%s)
            GROUP BY up."proxyWallet"
        """, (user_name, user_name))
        result = cur.fetchone()

    if result:
        proxy_wallet = result[0]
        markets = result[1] if result[1] and result[1][0] is not None else []
        return proxy_wallet, markets

    return None, []

if __name__ == "__main__":
    # test_connection()
    # print_schema()
    # get_top_rows("Tag",200)
    # get_top_rows("UserProfile",1)

    # conn_str = get_connection_string()
    # conn = psycopg.connect(conn_str)
    #
    # best = optimize_apriori_parameters(conn)
    # print("\nRecommended best parameters:")
    # print(best)

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
        print("Example users with current positions:")
        for i, (user_id, markets) in enumerate(test_users, 1):
            print(f"\n{i}. User {user_id}")
            print(f"\tMarkets: {markets[:3]}{'...' if len(markets) > 3 else ''}")

        input("\nPress Enter to generate recommendations for these users...")

        for i, (user_id, markets) in enumerate(test_users, 1):
            print("---------------------------------------------------------")
            print(f"RECOMMENDATIONS FOR USER ID{i}")
            recommendations = apriori.get_recommendations(
                user_markets=markets,
                top_n=5,
                test=True
            )
            if not recommendations:
                print("\tNo recommendations found for this user.")


    while True:
        username = input("\nPlease enter user to get recommendations for or press Enter to quit:")
        if username == "":
            break
        markets = get_user_markets_by_name(username)
        if markets is None:
            print(f"No transactions found for user name {username}")
        else:
            recommendations = apriori.get_recommendations(
                user_markets=markets[1],
                top_n=5,
                test=True,
            )

    conn.close()
    print("\nProgram finished...")