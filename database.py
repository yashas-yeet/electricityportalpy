import sqlite3
import pandas as pd
from datetime import datetime
import bcrypt

DB_FILE = 'electricity.db'

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    def add_column_if_not_exists(table, column, definition):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [info[1] for info in cursor.fetchall()]
        if column not in columns:
            print(f"Database Migration: Adding column '{column}' to table '{table}'...")
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                print(f"Successfully added '{column}'.")
            except Exception as e:
                print(f"Error adding column {column}: {e}")
            
    def drop_table_if_exists(table):
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Migration: Dropped obsolete table '{table}' for new schema.")
        except Exception as e:
            print(f"Error dropping table {table}: {e}")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'client')),
        full_name TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        usage_kwh REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE(user_id, month)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS grievance_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        subject TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS grievance_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        sender_name TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES grievance_tickets (id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users (id)
    )
    ''')
    
    drop_table_if_exists('grievances')

    try:
        add_column_if_not_exists('consumption', 'total_bill', 'REAL DEFAULT 0.0')
        add_column_if_not_exists('consumption', 'bill_status', "TEXT DEFAULT 'Pending'")
        add_column_if_not_exists('consumption', 'payment_timestamp', 'TEXT')
    except Exception as e:
        print(f"Error during database migration: {e}")
    
    admin_pass = b'admin123'
    hashed_admin_pass = bcrypt.hashpw(admin_pass, bcrypt.gensalt()).decode('utf-8')
    
    try:
        cursor.execute(
            "INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
            ('admin', hashed_admin_pass, 'admin', 'Administrator')
        )
    except sqlite3.IntegrityError:
        pass 

    conn.commit()
    conn.close()

def db_query(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print(f"DB Query Error: {e}")
    finally:
        conn.close()

def db_query_lastrowid(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    last_id = None
    try:
        cursor.execute(query, params)
        last_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        print(f"DB Query Error: {e}")
    finally:
        conn.close()
    return last_id

def db_query_to_df(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        print(f"DB Read Error: {e}")
        df = pd.DataFrame() 
    finally:
        conn.close()
    return df

def log_action(actor, action):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        db_query("INSERT INTO action_log (timestamp, actor, action) VALUES (?, ?, ?)", (now, actor, action))
    except Exception as e:
        print(f"Failed to log action: {e}")