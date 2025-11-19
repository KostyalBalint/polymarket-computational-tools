from datetime import datetime

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

def test_connection():
    conn_str = get_connection_string()
    with psycopg.connect(conn_str) as conn:
        print("✅ Connected successfully!")
        with conn.cursor() as cur:
            cur.execute("SELECT now()")
            print("Current time:", cur.fetchone()[0])

def print_schema():
    try:
        DATABASE_URL = get_connection_string()
        with psycopg.connect(DATABASE_URL) as conn:
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
        print("❌ Connection failed:", e)


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
        print("❌ Connection failed:", e)
    except psycopg.errors.UndefinedTable:
        print(f"❌ Table '{table_name}' does not exist.")

def export_to_csv(apriori: Apriori):
    rules_df = apriori.export_rules_to_dataframe()
    csv_filename = f'association_rules_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    rules_df.to_csv(csv_filename, index=False)
    print(f"\n💾 Rules exported to: {csv_filename}")

if __name__ == "__main__":
    # test_connection()
    # print_schema()
    # get_top_rows("Tag",200)
    # get_top_rows("UserProfile",1)

    input("Press Enter to start...")

    PARAMS = {
        'mode': 'positions',  # Transaction type: positions/trades/sessions/events
        'min_items': 2,  # Minimum items per transaction
        'days_back': 90,  # Days of history to analyze
        'min_support': 0.01,  # 1% minimum support
        'min_confidence': 0.10,  # 10% minimum confidence
        'min_lift': 1.2  # 1.2x minimum lift
    }

    print(f"\n📊 Parameters:")
    for key, value in PARAMS.items():
        print(f"\t{key}: {value}")

    input("\nPress Enter to continue")
    try:
        conn_str = get_connection_string()
        conn = psycopg.connect(conn_str)
        print("✅ Connected to database successfully!")
        test_connection()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        exit(1)

    apriori = Apriori(conn)

    input("\nPress Enter to continue")

    transactions = apriori.fetch_user_transactions(
        mode=PARAMS['mode'],
        min_items=PARAMS['min_items'],
        days_back=PARAMS['days_back'],
        test=True
    )

    if not transactions:
        print("\n⚠️ No transactions found!")
        conn.close()
        exit(1)

    input("\nPress Enter to continue")

    frequent_item_sets = apriori.generate_frequent_item_sets(
        min_support=PARAMS['min_support'],
        test=True
    )

    if not frequent_item_sets or len(frequent_item_sets) == 1:
        print("\n⚠️  Only 1-item_sets found!")
        conn.close()
        exit(1)

    input("\nPress Enter to continue")

    rules = apriori.generate_association_rules(
        min_confidence=PARAMS['min_confidence'],
        min_lift=PARAMS['min_lift'],
        test=True
    )

    if not rules:
        print("\n⚠️  No rules found!")
        conn.close()
        exit(1)

    input("\nPress Enter to continue")

    # Print summary
    apriori.print_summary()
