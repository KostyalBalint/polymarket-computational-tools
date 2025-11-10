import psycopg
import os
import json

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

def test():
    try:
        # Connect using your DATABASE_URL
        DATABASE_URL = get_connection_string()
        with psycopg.connect(DATABASE_URL) as conn:
            print("✅ Connected successfully!")

            # List all user tables
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
                print("\n📋 Tables in your database:")
                for (tname,) in tables:
                    print(" -", tname)

                # Preview first table
                first_table = tables[0][0]
                print(f"\n🔍 Previewing first rows of '{first_table}':")
                with conn.cursor() as cur:
                    cur.execute(f'SELECT * FROM "{first_table}" LIMIT 5;')
                    rows = cur.fetchall()
                    colnames = [desc.name for desc in cur.description]

                print("Columns:", colnames)
                for row in rows:
                    print(row)

    except psycopg.OperationalError as e:
        print("❌ Connection failed:", e)

if __name__ == '__main__':
    test_connection()
    test()