import sqlite3
import os
from datetime import datetime
from faker import Faker
import random
import bcrypt

DB_FILE = 'electricity.db'
fake = Faker()

# --- 1. Billing Constants (Copied from app.py) ---
FIXED_CHARGE_SINGLE_PHASE = 115.00
WHEELING_CHARGE_PER_KWH = 1.40
FAC_PER_KWH = 0.00
ELECTRICITY_DUTY_RATE = 0.16
slabs = [
    (100, 3.46), (200, 7.43), (200, 10.32), (500, 11.71), (float('inf'), 11.71)
]

# --- 2. Billing Calculator (Copied from app.py) ---
def calculate_mahadiscom_bill(kwh_units):
    bill = {}
    bill_details = []
    energy_charge = 0.0
    remaining_units = kwh_units
    
    for slab_width, rate in slabs:
        if remaining_units <= 0: break
        units_in_this_slab = min(remaining_units, slab_width)
        slab_cost = units_in_this_slab * rate
        energy_charge += slab_cost
        remaining_units -= units_in_this_slab
    
    bill['A_Energy_Charge'] = energy_charge
    bill['B_Fixed_Charge'] = FIXED_CHARGE_SINGLE_PHASE
    bill['C_Wheeling_Charge'] = kwh_units * WHEELING_CHARGE_PER_KWH
    bill['D_FAC'] = kwh_units * FAC_PER_KWH
    sub_total = (bill['A_Energy_Charge'] + bill['B_Fixed_Charge'] + 
                 bill['C_Wheeling_Charge'] + bill['D_FAC'])
    bill['E_Electricity_Duty'] = sub_total * ELECTRICITY_DUTY_RATE
    bill['F_Total_Bill'] = sub_total + bill['E_Electricity_Duty']
    
    return bill, bill_details

# --- 3. The Blueprint (Updated for Chat) ---
def setup_database():
    """Creates all tables matching the latest app.py schema."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    def drop_table_if_exists(table):
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Migration: Dropped obsolete table '{table}' for new schema.")
        except Exception as e:
            print(f"Error dropping table {table}: {e}")
    
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
    
    # Consumption table (Updated Schema)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        usage_kwh REAL NOT NULL,
        total_bill REAL DEFAULT 0.0,
        bill_status TEXT DEFAULT 'Pending',
        payment_timestamp TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE(user_id, month)
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
    
    # --- NEW: Grievance Ticket Table (Parent) ---
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
    
    # --- NEW: Grievance Messages Table (Child) ---
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
    
    # --- Migration: Drop old 'grievances' table if it exists ---
    drop_table_if_exists('grievances')

    conn.commit()
    conn.close()

# --- Helper to get last row ID ---
def db_execute_lastrowid(query, params=()):
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

# --- 4. The Main Data Generation Function (Modified) ---
def main():
    """Deletes the old DB and creates a new one with 45 users."""
    
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed old '{DB_FILE}'.")

    setup_database()
    print(f"Created new '{DB_FILE}' with all tables.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    admin_info = {} # Will store (id, username, full_name)
    client_info_list = [] # Will store (id, username, full_name)
    total_users_added = 0
    total_consumption_records = 0

    # --- Add 5 Admins (with Hashed Passwords) ---
    print("Generating 5 Admins...")
    try:
        for i in range(1, 6):
            full_name = fake.name()
            username = f"admin{i}"
            password = f"adminpass{i}".encode('utf-8')
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
            
            user = (username, hashed_password, 'admin', full_name)
            cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)", user)
            if i == 1: # Save first admin for grievance reply
                admin_info = (cursor.lastrowid, username, full_name)
            total_users_added += 1
        conn.commit()
    except Exception as e:
        print(f"Error adding admins: {e}")

    # --- Add 40 Clients (with Hashed Passwords) ---
    print("Generating 40 Clients...")
    try:
        for _ in range(40):
            full_name = fake.name()
            username = ".".join(full_name.split()[:2]).lower().replace("'", "").replace(".", "")
            password = b"pass123" # Simple password for all clients
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
            
            user = (username, hashed_password, 'client', full_name)
            
            cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)", user)
            client_info_list.append((cursor.lastrowid, username, full_name))
            total_users_added += 1
        conn.commit()
    except Exception as e:
        print(f"Error adding clients: {e}")
        
    print(f"Added {total_users_added} total users (5 admins, 40 clients).")

    # --- Add Consumption Data (with Bills and Status) ---
    print(f"Generating random consumption data for {len(client_info_list)} clients...")
    months = ['2025-06', '2025-07', '2025-08', '2025-09', '2025-10']
    
    try:
        for user_id, _, _ in client_info_list:
            for month in months:
                if random.random() < 0.8:
                    usage = random.uniform(50.0, 400.0)
                else:
                    usage = random.uniform(400.0, 900.0)
                usage = round(usage, 2)
                
                bill_data, _ = calculate_mahadiscom_bill(usage)
                total_bill = round(bill_data['F_Total_Bill'], 2)
                
                if random.random() < 0.3: # 30% chance of being paid
                    status = 'Paid'
                    timestamp = f"2025-10-{random.randint(1,25):02d} {random.randint(9,17):02d}:{random.randint(0,59):02d}:00"
                else:
                    status = 'Pending'
                    timestamp = None
                
                data = (user_id, month, usage, total_bill, status, timestamp)
                cursor.execute("INSERT INTO consumption (user_id, month, usage_kwh, total_bill, bill_status, payment_timestamp) VALUES (?, ?, ?, ?, ?, ?)", data)
                total_consumption_records += 1
        conn.commit()
        print(f"Added {total_consumption_records} sample consumption records.")
    except Exception as e:
        print(f"Error adding consumption data: {e}")

    # --- NEW: Add Sample Grievance Chat ---
    print("Generating sample grievance chat...")
    try:
        # --- Ticket 1 (Pending, 1 message) ---
        user = client_info_list[0]
        token1 = f"T-{random.randint(100000, 999999)}"
        ts1 = "2025-10-28 09:15:00"
        subject1 = "Incorrect bill for 2025-09"
        
        # 1. Create the parent ticket
        cursor.execute("INSERT INTO grievance_tickets (token, user_id, username, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'Pending', ?, ?)",
                       (token1, user[0], user[1], subject1, ts1, ts1))
        ticket1_id = cursor.lastrowid
        
        # 2. Add the first message
        body1 = f"My bill for September (2025-09) seems way too high. My usage was calculated but my neighbor used more and paid less. Please check the slab calculation.\n\nThanks,\n{user[2]}"
        cursor.execute("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (ticket1_id, user[0], user[2], body1, ts1))

        # --- Ticket 2 (Resolved, 2 messages) ---
        user = client_info_list[1]
        token2 = f"T-{random.randint(100000, 999999)}"
        ts2_client = "2025-10-25 14:30:00"
        ts2_admin = "2025-10-26 10:00:00"
        subject2 = "Meter Reading Question"
        
        # 1. Create the parent ticket
        cursor.execute("INSERT INTO grievance_tickets (token, user_id, username, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'Resolved', ?, ?)",
                       (token2, user[0], user[1], subject2, ts2_client, ts2_admin))
        ticket2_id = cursor.lastrowid
        
        # 2. Add client message
        body2 = "Hi, I don't think my meter was read correctly last month. Can someone please come and check it? My usage shows 610.8 kWh which is impossible."
        cursor.execute("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (ticket2_id, user[0], user[2], body2, ts2_client))
                       
        # 3. Add admin reply
        admin_body = f"Hi {user[2]},\n\nI have checked your meter reading data. The high usage (610.8 kWh) was correct. We show a large spike in usage on 2025-10-15. This may have been due to a new appliance, like an A/C unit, being left on.\n\nI am marking this as resolved, but please let us know if you have other questions.\n\nBest,\n{admin_info[2]}"
        cursor.execute("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (ticket2_id, admin_info[0], admin_info[2], admin_body, ts2_admin))

        conn.commit()
        print("Added 2 sample grievance tickets with chat history.")
    except Exception as e:
        print(f"Error adding grievances: {e}")

    # 7. Add a log entry
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO action_log (timestamp, actor, action) VALUES (?, ?, ?)", 
                   (now, 'System', 'Database created and populated with 45 users.'))
    conn.commit()
    conn.close()
    
    print("\n--- Success! ---")
    print("Your database is now populated with a large, secure, and feature-rich sample dataset.")
    print("You can run your main 'app.py' or 'cli_app.py' now.")

if __name__ == "__main__":
    main()