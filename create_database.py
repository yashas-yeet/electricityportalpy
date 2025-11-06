import sqlite3
import os
from datetime import datetime, timedelta
from faker import Faker
import random
import bcrypt

# --- Import from your own project files ---
# This ensures we use the same logic as the app
from database import DB_FILE, setup_database, db_query, db_query_lastrowid
from billing import calculate_mahadiscom_bill

# Initialize Faker for generating names
fake = Faker()

def main():
    """
    Deletes the old DB and creates a new one,
    populating it with a large, realistic dataset.
    """
    
    # 1. Delete old DB if it exists
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed old '{DB_FILE}'.")

    # 2. Setup fresh tables from your database.py
    setup_database()
    print(f"Created new '{DB_FILE}' with all tables.")

    admin_info = {} # To store admin user info for replying to tickets
    client_info_list = [] # To store (id, username, full_name)
    total_users_added = 0
    total_consumption_records = 0

    # --- 3. Add 1 main Admin + 4 fake Admins ---
    print("Generating 5 Admins...")
    try:
        # Main Admin
        admin_pass = b'admin123'
        hashed_admin_pass = bcrypt.hashpw(admin_pass, bcrypt.gensalt()).decode('utf-8')
        db_query("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                 ('admin', hashed_admin_pass, 'admin', 'Administrator'))
        admin_info = (1, 'admin', 'Administrator') # (id, username, name)
        total_users_added += 1

        # Fake Admins
        for i in range(4):
            full_name = fake.name()
            username = f"admin_user{i}"
            password = b"adminpass"
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
            user = (username, hashed_password, 'admin', full_name)
            db_query("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)", user)
            total_users_added += 1
            
    except Exception as e:
        print(f"Error adding admins: {e}")

    # --- 4. Add 40 Clients (with Hashed Passwords) ---
    print("Generating 40 Clients...")
    try:
        for _ in range(40):
            full_name = fake.name()
            # Create a simple, clean username
            username = ".".join(full_name.split()[:2]).lower().replace("'", "").replace(".", "")
            password = b"pass123" # Keep password simple for testing
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
            
            user = (username, hashed_password, 'client', full_name)
            
            client_id = db_query_lastrowid("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)", user)
            if client_id:
                client_info_list.append((client_id, username, full_name))
                total_users_added += 1
            
    except Exception as e:
        print(f"Error adding clients: {e}")
        
    print(f"Added {total_users_added} total users (5 admins, 40 clients).")

    # --- 5. Add Consumption Data (with Bills and Status) ---
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
                
                # Pre-calculate the bill
                bill_data, _ = calculate_mahadiscom_bill(usage)
                total_bill = round(bill_data['F_Total_Bill'], 2)
                
                # Randomly mark some as Paid
                if random.random() < 0.3: # 30% chance of being paid
                    status = 'Paid'
                    timestamp = f"2025-10-{random.randint(1,25):02d} {random.randint(9,17):02d}:{random.randint(0,59):02d}:00"
                else:
                    status = 'Pending'
                    timestamp = None
                
                data = (user_id, month, usage, total_bill, status, timestamp)
                db_query("INSERT INTO consumption (user_id, month, usage_kwh, total_bill, bill_status, payment_timestamp) VALUES (?, ?, ?, ?, ?, ?)", data)
                total_consumption_records += 1
        print(f"Added {total_consumption_records} sample consumption records.")
    except Exception as e:
        print(f"Error adding consumption data: {e}")

    # --- 6. Add Sample Grievance Chat ---
    print("Generating sample grievance chat...")
    try:
        # --- Ticket 1 (Pending, 1 message) ---
        user = client_info_list[0]
        token1 = f"T-{random.randint(100000, 999999)}"
        ts1 = "2025-10-28 09:15:00"
        subject1 = "Incorrect bill for 2025-09"
        
        ticket1_id = db_query_lastrowid("INSERT INTO grievance_tickets (token, user_id, username, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'Pending', ?, ?)",
                       (token1, user[0], user[1], subject1, ts1, ts1))
        
        body1 = f"My bill for September (2025-09) seems way too high. My usage was calculated but my neighbor used more and paid less. Please check the slab calculation.\n\nThanks,\n{user[2]}"
        db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (ticket1_id, user[0], user[2], body1, ts1))

        # --- Ticket 2 (Resolved, 3 messages) ---
        user = client_info_list[1]
        token2 = f"T-{random.randint(100000, 999999)}"
        ts2_client = "2025-10-25 14:30:00"
        ts2_admin = "2025-10-26 10:00:00"
        ts2_client_reply = "2025-10-26 11:00:00"
        subject2 = "Meter Reading Question"
        
        ticket2_id = db_query_lastrowid("INSERT INTO grievance_tickets (token, user_id, username, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'Resolved', ?, ?)",
                       (token2, user[0], user[1], subject2, ts2_client, ts2_admin))
        
        body2_client = "Hi, I don't think my meter was read correctly last month. Can someone please come and check it? My usage shows 610.8 kWh which is impossible."
        db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (ticket2_id, user[0], user[2], body2_client, ts2_client))
                       
        admin_body = f"Hi {user[2]},\n\nI have checked your meter reading data. The high usage (610.8 kWh) was correct. We show a large spike in usage on 2025-10-15.\n\nBest,\n{admin_info[2]}"
        db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (ticket2_id, admin_info[0], admin_info[2], admin_body, ts2_admin))
        
        body3_client = "Oh, I see. That must have been when my family was visiting. Thank you for checking!"
        db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (ticket2_id, user[0], user[2], body3_client, ts2_client_reply))

        # --- THIS LINE WAS REMOVED ---
        # conn.commit() 
        
        print("Added 2 sample grievance tickets with chat history.")
    except Exception as e:
        print(f"Error adding grievances: {e}")

    # 7. Add a log entry
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_query("INSERT INTO action_log (timestamp, actor, action) VALUES (?, ?, ?)", 
                   (now, 'System', 'Database created and populated with 45 users.'))
    
    print("\n--- Success! ---")
    print("Your database is now populated with a large, secure, and feature-rich sample dataset.")
    print("You can run your main 'app.py' now.")

if __name__ == "__main__":
    main()