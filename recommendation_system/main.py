import psycopg
import os
import json
from psycopg import sql

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
                colnames = [desc.name for desc in cur.description]
                rows = cur.fetchall()
                print(f"\nTop {limit} rows from table '{table_name}':")
                print(", ".join(colnames))
                for row in rows:
                    print(row)

    except psycopg.OperationalError as e:
        print("❌ Connection failed:", e)
    except psycopg.errors.UndefinedTable:
        print(f"❌ Table '{table_name}' does not exist.")

if __name__ == '__main__':
    test_connection()
    print_schema()
    get_top_rows("Tag",5)