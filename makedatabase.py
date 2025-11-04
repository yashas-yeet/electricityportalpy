import sqlite3
import os
from datetime import datetime
from faker import Faker  # --- NEW: Import Faker
import random             # --- NEW: Import Random

DB_FILE = 'electricity.db'
fake = Faker() # --- NEW: Initialize Faker

# --- 1. The Blueprint (Unchanged) ---
def setup_database():
    """Creates the database tables and a default admin user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # User table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'client')),
        full_name TEXT
    )
    ''')
    
    # Consumption table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month TEXT NOT NULL,  -- e.g., "2025-10"
        usage_kwh REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    # Action Log Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()

# --- 2. The Main Function (MODIFIED) ---
def main():
    """Deletes the old DB and creates a new one with 45 users."""
    
    # 1. Delete old DB if it exists
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed old '{DB_FILE}'.")

    # 2. Setup fresh tables
    setup_database()
    print(f"Created new '{DB_FILE}' with all tables.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    client_ids = [] # To store the new IDs for data generation
    total_users_added = 0
    total_consumption_records = 0

    # --- 3. Add 5 Admins ---
    print("Generating 5 Admins...")
    try:
        for i in range(1, 6):
            full_name = fake.name()
            username = f"admin{i}"
            password = f"adminpass{i}"
            user = (username, password, 'admin', full_name)
            cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)", user)
            total_users_added += 1
        conn.commit()
    except Exception as e:
        print(f"Error adding admins: {e}")

    # --- 4. Add 40 Clients (using Faker) ---
    print("Generating 40 Clients...")
    try:
        for _ in range(40):
            full_name = fake.name()
            # Create a simple username (e.g., 'john.doe')
            username = ".".join(full_name.split()[:2]).lower().replace("'", "")
            password = "pass123" # Keep password simple for testing
            user = (username, password, 'client', full_name)
            
            cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)", user)
            client_ids.append(cursor.lastrowid) # Save the new client's ID
            total_users_added += 1
        conn.commit()
    except Exception as e:
        print(f"Error adding clients: {e}")
        
    print(f"Added {total_users_added} total users (5 admins, 40 clients).")

    # --- 5. Add Consumption Data (Randomized) ---
    print(f"Generating random consumption data for {len(client_ids)} clients...")
    months = ['2025-06', '2025-07', '2025-08', '2025-09', '2025-10']
    
    try:
        for user_id in client_ids:
            for month in months:
                # Generate random usage.
                # 80% chance of "normal" usage (50-400)
                # 20% chance of "high" usage (400-900) to make charts interesting
                if random.random() < 0.8:
                    usage = random.uniform(50.0, 400.0)
                else:
                    usage = random.uniform(400.0, 900.0)
                
                data = (user_id, month, round(usage, 2))
                cursor.execute("INSERT INTO consumption (user_id, month, usage_kwh) VALUES (?, ?, ?)", data)
                total_consumption_records += 1
        conn.commit()
        print(f"Added {total_consumption_records} sample consumption records.")
    except Exception as e:
        print(f"Error adding consumption data: {e}")

    # 6. Add a log entry
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO action_log (timestamp, actor, action) VALUES (?, ?, ?)", 
                   (now, 'System', 'Database created and populated with 45 users.'))
    conn.commit()
    conn.close()
    
    print("\n--- Success! ---")
    print("Your database is now populated with a large sample dataset.")
    print("You can run your main 'app.py' or 'cli_app.py' now.")

if __name__ == "__main__":
    main()