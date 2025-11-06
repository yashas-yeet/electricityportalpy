import sqlite3
import getpass
from datetime import datetime
import sys
import os
import random
import bcrypt

# --- Import from project files ---
# We are reusing the same logic as the GUI!
try:
    from database import db_query, db_query_to_df, db_query_lastrowid, setup_database, log_action
    from billing import calculate_mahadiscom_bill, slabs, FIXED_CHARGE_SINGLE_PHASE, WHEELING_CHARGE_PER_KWH, ELECTRICITY_DUTY_RATE
except ImportError as e:
    print(f"Error: Could not import project files (database.py, billing.py).")
    print(f"Make sure this script is in the same folder as your other project files.")
    print(f"Details: {e}")
    sys.exit()

# --- Optional Imports for Import/Export ---
try:
    import pandas as pd
    import openpyxl
    import csv
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False
    print("Warning: 'pandas' or 'openpyxl' not found. Excel/CSV features will be disabled.")
    print("To enable them, run: pip install pandas openpyxl")


# --- CLI Helper Functions ---

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def wait_for_enter():
    """Pauses execution until the user presses Enter."""
    input("\nPress Enter to continue...")

def print_header(title, session=None):
    """Clears screen and prints a consistent header."""
    clear_screen()
    print("=" * 60)
    print("--- ELECTRICITY DISTRIBUTION PORTAL (CLI) ---")
    if session:
        print(f"--- Logged in as: {session[2]}")
    print("=" * 60)
    print(f"\n>> {title}\n")

# --- SHARED: Login & Register ---

def handle_login():
    """Handles the login process. Returns session tuple or None."""
    print_header("Portal Login")
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    if not username or not password:
        print("\nError: Username and password cannot be empty.")
        wait_for_enter()
        return None

    user_df = db_query_to_df("SELECT id, password, role, full_name FROM users WHERE username = ?", (username,))
    
    if user_df.empty:
        log_action(username, "Failed login attempt (invalid username).")
        print("\nError: Invalid username or password.")
        wait_for_enter()
        return None

    user = user_df.iloc[0]
    stored_hash = user['password']
    
    if isinstance(stored_hash, str):
        stored_hash_bytes = stored_hash.encode('utf-8')
    elif isinstance(stored_hash, bytes):
        stored_hash_bytes = stored_hash
    else:
        log_action(username, "Failed login (invalid hash format in DB).")
        print("\nLogin Failed: Invalid password format in database. Please contact admin.")
        wait_for_enter()
        return None

    entered_pass_bytes = password.encode('utf-8')
    is_correct = False
    
    try:
        if bcrypt.checkpw(entered_pass_bytes, stored_hash_bytes):
            is_correct = True
    except ValueError:
        if password == stored_hash: # Fallback for legacy plain-text
            is_correct = True
            log_action(username, "Logged in with a legacy plain-text password.")
    
    if is_correct:
        log_action(username, "Logged in successfully.")
        print(f"\nSuccess! Welcome, {user['full_name']}.")
        wait_for_enter()
        return (user['id'], user['role'], user['full_name'], username)
    else:
        log_action(username, "Failed login attempt (invalid password).")
        print("\nError: Invalid username or password.")
        wait_for_enter()
        return None

def handle_register():
    """Handles the new user registration process."""
    print_header("Register New Client Account")
    full_name = input("Full Name: ")
    username = input("New Username: ")
    password = getpass.getpass("New Password: ")
    confirm_password = getpass.getpass("Confirm Password: ")

    if not full_name or not username or not password or not confirm_password:
        print("\nError: All fields are required.")
        wait_for_enter()
        return

    if password != confirm_password:
        print("\nError: Passwords do not match.")
        wait_for_enter()
        return

    try:
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_query(
            "INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
            (username, hashed_password, 'client', full_name)
        )
        log_action(username, "Registered new client account.")
        print(f"\nSuccess! User '{username}' registered successfully. You can now log in.")
    except sqlite3.IntegrityError:
        log_action(username, "Registration failed (username taken).")
        print("\nError: That username is already taken. Please choose another.")
    except Exception as e:
        log_action(username, f"Registration failed (unknown error: {e}).")
        print(f"\nAn error occurred: {e}")
    
    wait_for_enter()

# --- SHARED: Password & Bill Text ---

def handle_change_password(session):
    """Allows a logged-in user to change their own password."""
    user_id, role, full_name, username = session
    print_header("Change Your Password", session)
    
    current_pass = getpass.getpass("Current Password: ")
    new_pass = getpass.getpass("New Password: ")
    confirm_pass = getpass.getpass("Confirm New Password: ")
    
    if not current_pass or not new_pass or not confirm_pass:
        print("\nError: All fields are required.")
        wait_for_enter()
        return
    if new_pass != confirm_pass:
        print("\nError: New passwords do not match.")
        wait_for_enter()
        return
    
    user_df = db_query_to_df("SELECT password FROM users WHERE id = ?", (user_id,))
    if user_df.empty:
        print("\nError: Could not find user record.")
        wait_for_enter()
        return
        
    stored_hash = user_df.iloc[0]['password'].encode('utf-8')
    
    if not bcrypt.checkpw(current_pass.encode('utf-8'), stored_hash):
        print("\nError: Your 'Current Password' is incorrect.")
        log_action(username, "Failed password change (wrong current pass).")
        wait_for_enter()
        return
        
    try:
        new_hashed_pass = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_query("UPDATE users SET password = ? WHERE id = ?", (new_hashed_pass, user_id))
        log_action(username, "Changed their password successfully.")
        print("\nSuccess! Password changed successfully.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        
    wait_for_enter()

def get_bill_text(kwh_units, month, user_name):
    """Uses the billing.py logic to generate bill text."""
    bill_data, bill_details = calculate_mahadiscom_bill(kwh_units)
    
    bill_text = f"--- ESTIMATED ELECTRICITY BILL ---\n\n"
    bill_text += f"Client: {user_name}\n"
    bill_text += f"Billing Month: {month}\n"
    bill_text += f"Total Consumption: {kwh_units:.2f} kWh\n"
    bill_text += "----------------------------------\n\n"
    bill_text += "ITEMIZED CHARGES:\n\n"
    bill_text += f"A. Energy Charges:\n"
    bill_text += "\n".join(bill_details) + "\n"
    bill_text += f"   Total Energy Charge:   ₹{bill_data['A_Energy_Charge']:>10.2f}\n\n"
    bill_text += f"B. Fixed Charge:             ₹{bill_data['B_Fixed_Charge']:>10.2f}\n"
    bill_text += f"C. Wheeling Charge:          ₹{bill_data['C_Wheeling_Charge']:>10.2f}\n"
    bill_text += f"D. Fuel Adjustment (FAC):    ₹{bill_data['D_FAC']:>10.2f}\n"
    bill_text += "----------------------------------\n"
    sub_total = bill_data['A_Energy_Charge'] + bill_data['B_Fixed_Charge'] + bill_data['C_Wheeling_Charge'] + bill_data['D_FAC']
    bill_text += f"   Sub-Total:               ₹{sub_total:>10.2f}\n"
    bill_text += f"E. Electricity Duty (16%):   ₹{bill_data['E_Electricity_Duty']:>10.2f}\n\n"
    bill_text += f"--- TOTAL BILL AMOUNT ---\n"
    bill_text += f"   (A+B+C+D+E):             ₹{bill_data['F_Total_Bill']:>10.2f}\n"
    bill_text += "----------------------------------\n"
    bill_text += "\n\n--- APPLIED TARIFF (Residential LT-I) ---\n"
    bill_text += f"Fixed Charge:      ₹{FIXED_CHARGE_SINGLE_PHASE:.2f}/month\n"
    bill_text += f"Wheeling Charge:   ₹{WHEELING_CHARGE_PER_KWH:.2f}/kWh\n"
    bill_text += f"Electricity Duty:  {ELECTRICITY_DUTY_RATE * 100:.0f}%\n"
    bill_text += "Energy Charges (Telescopic Slabs):\n"
    bill_text += f"  - 0-100 kWh:       ₹{slabs[0][1]:.2f}/unit\n"
    bill_text += f"  - 101-300 kWh:     ₹{slabs[1][1]:.2f}/unit\n"
    bill_text += f"  - 301-500 kWh:     ₹{slabs[2][1]:.2f}/unit\n"
    bill_text += f"  - 501-1000 kWh:    ₹{slabs[3][1]:.2f}/unit\n"
    bill_text += f"  - >1000 kWh:       ₹{slabs[4][1]:.2f}/unit\n"
    return bill_text

def export_bill_to_txt(bill_text, client_name, month):
    try:
        clean_client_name = client_name.replace(" ", "_")
        filename = f"BILL_{clean_client_name}_{month}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(bill_text)
        
        print(f"\nSuccess: Bill exported to {os.path.abspath(filename)}")
        log_action(client_name, f"Exported bill for {month}.")
    except Exception as e:
        print(f"\nError: Could not export bill. {e}")

# --- SHARED: Grievance Chat System ---

def handle_grievance_chat(session, ticket_id, subject):
    """A universal chat interface for both clients and admins."""
    user_id, role, full_name, username = session
    
    while True:
        print_header(f"Chat for Ticket: {subject}", session)
        
        # 1. Load and display all messages
        messages_df = db_query_to_df("SELECT sender_name, timestamp, message FROM grievance_messages WHERE ticket_id = ? ORDER BY timestamp ASC", (ticket_id,))
        if messages_df.empty:
            print("No messages found for this ticket.")
        else:
            for index, row in messages_df.iterrows():
                print(f"--- {row['sender_name']} ({row['timestamp']}) ---")
                print(f"{row['message']}\n")
        
        # 2. Check ticket status
        status_df = db_query_to_df("SELECT status FROM grievance_tickets WHERE id = ?", (ticket_id,))
        status = status_df.iloc[0]['status'] if not status_df.empty else 'Unknown'

        if status == 'Resolved':
            print("--- This ticket is marked as 'Resolved'. You can no longer reply. ---")
            wait_for_enter()
            break # Exit chat
            
        # 3. Prompt for reply
        print("----------------------------------")
        reply = input("Type your reply (or 'q' to go back): ")
        
        if reply.lower() == 'q':
            break
            
        if not reply.strip():
            print("Cannot send an empty message.")
            wait_for_enter()
            continue

        # 4. Send the reply
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                     (ticket_id, user_id, full_name, reply, timestamp))
            
            # Update ticket status
            new_status = 'Answered' if role == 'admin' else 'Pending'
            db_query("UPDATE grievance_tickets SET status = ?, updated_at = ? WHERE id = ?", (new_status, timestamp, ticket_id))
            
            log_action(username, f"Replied to grievance ticket ID {ticket_id}.")
            print("\nReply sent successfully.")
            wait_for_enter()
        except Exception as e:
            print(f"\nError sending reply: {e}")
            wait_for_enter()

# --- CLIENT: Menu Functions ---

def client_bill_history(session):
    """Displays client's bill history and allows paying bills."""
    user_id, role, full_name, username = session
    print_header("My Bills / History", session)
    
    data_df = db_query_to_df("SELECT id, month, usage_kwh, total_bill, bill_status, payment_timestamp FROM consumption WHERE user_id = ? ORDER BY month DESC", (user_id,))
    
    if data_df.empty:
        print("No consumption data found.")
        wait_for_enter()
        return

    # Display Stats
    total_usage = data_df['usage_kwh'].sum()
    avg_usage = data_df['usage_kwh'].mean()
    print(f"--- Your Stats ---")
    print(f"Total All-Time Usage: {total_usage:.2f} kWh")
    print(f"Average Monthly Usage: {avg_usage:.2f} kWh")
    print("--------------------")
    
    # Display Table
    print(f"\n{'ID':<5} | {'Month':<10} | {'Usage (kWh)':<12} | {'Bill (₹)':<10} | {'Status':<25}")
    print("-" * 66)
    
    pending_bills = []
    for index, row in data_df.iterrows():
        status = "Pending"
        if row['bill_status'] == 'Paid' and row['payment_timestamp']:
            status = f"Paid on {row['payment_timestamp']}"
        else:
            pending_bills.append(row) # Add to list of payable bills
            
        print(f"{row['id']:<5} | {row['month']:<10} | {row['usage_kwh']:<12.2f} | {row['total_bill']:<10.2f} | {status:<25}")
    
    print("-" * 66)
    
    # Pay Bill logic
    if not pending_bills:
        print("\nAll your bills are paid up!")
        wait_for_enter()
        return

    try:
        pay_choice = input("\nEnter a Bill ID to pay it (or 0 to cancel): ")
        bill_id_to_pay = int(pay_choice)
        
        if bill_id_to_pay == 0:
            return
            
        # Find the bill in our pending list
        bill_to_pay = next((bill for bill in pending_bills if bill['id'] == bill_id_to_pay), None)
        
        if bill_to_pay:
            confirm = input(f"Confirm payment of ₹{bill_to_pay['total_bill']:.2f} for {bill_to_pay['month']}? (y/n): ").lower()
            if confirm == 'y':
                paid_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_query("UPDATE consumption SET bill_status = 'Paid', payment_timestamp = ? WHERE id = ?", (paid_timestamp, bill_id_to_pay))
                log_action(username, f"Paid bill for {bill_to_pay['month']} (ID: {bill_id_to_pay}).")
                print("\nPayment successful!")
            else:
                print("\nPayment cancelled.")
        else:
            print("\nError: Invalid ID or bill is already paid.")
            
    except ValueError:
        print("\nError: Invalid ID.")
    
    wait_for_enter()

def client_generate_bill(session):
    """Lets client select a month and generate/export the bill."""
    user_id, role, full_name, username = session
    print_header("Generate Bill", session)
    
    months_data = db_query_to_df("SELECT month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month DESC", (user_id,))
    
    if months_data.empty:
        print("No consumption data found. Cannot generate a bill.")
        wait_for_enter()
        return

    print("Available billing months:")
    for i, row in months_data.iterrows():
        print(f"  {i+1}. {row['month']} ({row['usage_kwh']} kWh)")
    print("  0. Cancel")
    
    try:
        choice = int(input("\nSelect a month to generate a bill: "))
        if choice == 0:
            return
        
        selected_row = months_data.iloc[choice - 1]
        month = selected_row['month']
        kwh_units = selected_row['usage_kwh']
        
        clear_screen()
        bill_text = get_bill_text(kwh_units, month, full_name)
        print(bill_text)
        
        export_choice = input("\nDo you want to export this bill to a .txt file? (y/n): ").lower()
        if export_choice == 'y':
            export_bill_to_txt(bill_text, full_name, month)
            
    except (ValueError, IndexError):
        print("Invalid choice.")
    
    wait_for_enter()

def client_view_stats(session):
    """Shows text-based equivalent of the usage graph."""
    user_id, role, full_name, username = session
    print_header("My Usage Statistics", session)
    
    data_df = db_query_to_df("SELECT month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month ASC", (user_id,))
    
    if data_df.empty:
        print("No consumption data found.")
    else:
        print(f"\n{'Month':<10} | {'Usage (kWh)':<12}")
        print("-" * 25)
        for index, row in data_df.iterrows():
            print(f"{row['month']:<10} | {row['usage_kwh']:<12.2f}")
        print("-" * 25)
        
        total_usage = data_df['usage_kwh'].sum()
        avg_usage = data_df['usage_kwh'].mean()
        max_usage = data_df['usage_kwh'].max()
        min_usage = data_df['usage_kwh'].min()
        
        print("\n--- Summary ---")
        print(f"Total All-Time Usage: {total_usage:.2f} kWh")
        print(f"Average Monthly Usage: {avg_usage:.2f} kWh")
        print(f"Highest Month: {max_usage:.2f} kWh")
        print(f"Lowest Month: {min_usage:.2f} kWh")
        
    wait_for_enter()

def client_manage_grievances(session):
    """Main menu for client to submit or view tickets."""
    user_id, role, full_name, username = session
    
    while True:
        print_header("Contact Admin / Grievances", session)
        print("1. Submit a New Ticket")
        print("2. View My Existing Tickets")
        print("3. Back to Client Menu")
        choice = input("Enter choice: ")

        if choice == '1':
            client_submit_grievance(session)
        elif choice == '2':
            client_view_tickets(session)
        elif choice == '3':
            break
        else:
            print("Invalid choice.")
            wait_for_enter()

def client_submit_grievance(session):
    """Lets client submit a new grievance ticket."""
    user_id, role, full_name, username = session
    print_header("Submit New Ticket", session)
    
    subject = input("Subject: ")
    message = input("Message (describe your issue in one line): ")
    
    if not subject or not message:
        print("\nError: Subject and Message are required.")
        wait_for_enter()
        return

    try:
        token = f"T-{random.randint(100000, 999999)}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        ticket_id = db_query_lastrowid("INSERT INTO grievance_tickets (token, user_id, username, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'Pending', ?, ?)",
                                      (token, user_id, username, subject, timestamp, timestamp))
        
        if ticket_id is None:
            print("\nError: Failed to create ticket.")
            wait_for_enter()
            return

        db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                 (ticket_id, user_id, full_name, message, timestamp))
                 
        log_action(username, f"Submitted new grievance (Token: {token}).")
        print(f"\nSuccess! Your ticket has been submitted.")
        print(f"Your Token ID is: {token}")
        
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    
    wait_for_enter()

def client_view_tickets(session):
    """Shows client a list of their tickets and lets them chat."""
    user_id, role, full_name, username = session
    print_header("My Tickets", session)
    
    tickets_df = db_query_to_df("SELECT id, token, created_at, subject, status FROM grievance_tickets WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
    
    if tickets_df.empty:
        print("You have not submitted any tickets.")
        wait_for_enter()
        return

    print(f"\n{'ID':<5} | {'Token':<10} | {'Date':<20} | {'Status':<10} | {'Subject':<30}")
    print("-" * 78)
    for index, row in tickets_df.iterrows():
        print(f"{row['id']:<5} | {row['token']:<10} | {row['created_at']:<20} | {row['status']:<10} | {row['subject']:<30}")
    
    try:
        choice = int(input("\nEnter a Ticket ID to view chat (or 0 to go back): "))
        if choice == 0:
            return
            
        ticket = tickets_df[tickets_df['id'] == choice]
        if ticket.empty:
            print("Invalid Ticket ID.")
            wait_for_enter()
            return
            
        ticket_id = ticket.iloc[0]['id']
        subject = ticket.iloc[0]['subject']
        
        # Enter the chat loop
        handle_grievance_chat(session, ticket_id, subject)
        
    except ValueError:
        print("Invalid ID.")
        wait_for_enter()

def client_menu(session):
    """Main loop for a logged-in client."""
    while True:
        print_header("Client Menu", session)
        print("1. View Bill History & Pay Bill")
        print("2. Generate/Export Full Bill")
        print("3. View My Usage Stats")
        print("4. Contact Admin / View Tickets")
        print("5. Change My Password")
        print("6. Logout")
        
        choice = input("\nEnter choice: ")
        
        if choice == '1':
            client_bill_history(session)
        elif choice == '2':
            client_generate_bill(session)
        elif choice == '3':
            client_view_stats(session)
        elif choice == '4':
            client_manage_grievances(session)
        elif choice == '5':
            handle_change_password(session)
        elif choice == '6':
            break
        else:
            print("Invalid choice.")
            wait_for_enter()

# --- ADMIN: Menu Functions ---

def manage_users_menu(session):
    """Sub-menu for all user management tasks."""
    admin_id, role, admin_name, admin_username = session
    
    while True:
        print_header("Manage Users", session)
        print("1. Add New User")
        print("2. List & Search Users")
        print("3. Update User Info")
        print("4. Remove User")
        print("5. Reset User Password")
        print("6. Export User List to Excel")
        print("7. Back to Admin Menu")
        
        choice = input("\nEnter choice: ")
        
        if choice == '1':
            add_user(admin_username)
        elif choice == '2':
            list_search_users()
        elif choice == '3':
            update_user(admin_username)
        elif choice == '4':
            remove_user(admin_id, admin_username)
        elif choice == '5':
            reset_password(admin_username)
        elif choice == '6':
            export_users_to_excel(admin_username)
        elif choice == '7':
            break
        else:
            print("Invalid choice.")
            wait_for_enter()

def add_user(admin_name):
    print_header("Add New User")
    full_name = input("Full Name: ")
    username = input("New Username: ")
    password = getpass.getpass("New Password: ")
    role = ""
    while role not in ['admin', 'client']:
        role = input("Enter Role (admin/client): ").lower()
        
    if not all([full_name, username, password, role]):
        print("Error: All fields are required. User not added.")
    else:
        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db_query("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                     (username, hashed_password, role, full_name))
            log_action(admin_name, f"Added new user: '{username}' (Role: {role}).")
            print(f"\nSuccess: User '{username}' created as {role}.")
        except sqlite3.IntegrityError:
            print("\nError: Username already exists.")
        except Exception as e:
            print(f"\nAn error occurred: {e}")
    wait_for_enter()

# --- THIS FUNCTION IS FIXED ---
def list_search_users():
    """Finds users with 'as-you-type' search and sorting."""
    print_header("List & Search Users")
    
    search_term = input("Search by name or username (leave blank to list all): ")
    
    # --- FIX: Prefixed ambiguous columns with u. ---
    query = "SELECT u.id, u.username, u.full_name, u.role, COALESCE(SUM(c.usage_kwh), 0) as total_usage FROM users u LEFT JOIN consumption c ON u.id = c.user_id"
    params = []
    if search_term:
        query += " WHERE (u.username LIKE ? OR u.full_name LIKE ?)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])
    
    query += " GROUP BY u.id, u.username, u.full_name, u.role"
    
    print("Sort by: [1] Role (default)  [2] Username  [3] Full Name  [4] ID  [5] Total Usage")
    sort_choice = input("Enter sort choice (1-5): ")
    
    # --- FIX: Prefixed ambiguous columns in sort_map ---
    sort_map = {'1': 'u.role', '2': 'u.username', '3': 'u.full_name', '4': 'u.id', '5': 'total_usage'}
    sort_col = sort_map.get(sort_choice, 'u.role') # Default to u.role
    
    order_choice = input("Order: [1] Ascending (default)  [2] Descending: ")
    sort_order = "DESC" if order_choice == '2' else "ASC"
    query += f" ORDER BY {sort_col} {sort_order}"
    
    data = db_query_to_df(query, tuple(params))
    
    if data.empty:
        print("\nNo users found.")
        wait_for_enter()
        return
    
    print(f"\n{'ID':<5} | {'Username':<20} | {'Full Name':<25} | {'Role':<10} | {'Total Usage':<15}")
    print("-" * 80)

    for index, row in data.iterrows():
        print(f"{row['id']:<5} | {row['username']:<20} | {row['full_name']:<25} | {row['role']:<10} | {row['total_usage']:<15.2f}")
            
    wait_for_enter()

def _find_user_helper():
    """Lists/searches users and returns a chosen user's ID and name."""
    print_header("Find User")
    
    search_term = input("Search by name or username (leave blank to list all): ")
    
    query = "SELECT id, username, full_name, role FROM users"
    params = []
    if search_term:
        query += " WHERE (username LIKE ? OR full_name LIKE ?)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])
    query += " ORDER BY full_name"
    
    users_df = db_query_to_df(query, params)
    
    if users_df.empty:
        print("\nNo users found.")
        return None
        
    print(f"\n{'ID':<5} | {'Username':<20} | {'Full Name':<25} | {'Role':<10}")
    print("-" * 64)
    for index, user in users_df.iterrows():
        print(f"{user['id']:<5} | {user['username']:<20} | {user['full_name']:<25} | {user['role']:<10}")
    
    try:
        user_id = int(input("\nEnter the ID of the user (0 to cancel): "))
        if user_id == 0:
            return None
        
        user = users_df[users_df['id'] == user_id]
        if user.empty:
            print("Invalid ID.")
            return None
        
        return user.iloc[0] # Return the full pandas Series
            
    except ValueError:
        print("Invalid ID.")
        return None

def update_user(admin_name):
    user_to_update = _find_user_helper()
    if user_to_update is None:
        wait_for_enter()
        return

    print(f"\nUpdating user: {user_to_update['full_name']} ({user_to_update['username']})")
    new_full_name = input(f"New Full Name (leave blank to keep '{user_to_update['full_name']}'): ")
    new_username = input(f"New Username (leave blank to keep '{user_to_update['username']}'): ")
    
    if not new_full_name: new_full_name = user_to_update['full_name']
    if not new_username: new_username = user_to_update['username']
    
    try:
        db_query("UPDATE users SET full_name = ?, username = ? WHERE id = ?", (new_full_name, new_username, user_to_update['id']))
        log_action(admin_name, f"Updated info for user ID {user_to_update['id']}.")
        print("User information updated successfully.")
    except sqlite3.IntegrityError:
        print("Error: That username is already taken.")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    wait_for_enter()

def remove_user(admin_id, admin_name):
    user_to_remove = _find_user_helper()
    if user_to_remove is None:
        wait_for_enter()
        return

    user_id = user_to_remove['id']
    username = user_to_remove['username']
    
    if user_id == admin_id:
        print("\nError: You cannot remove your own account.")
        wait_for_enter()
        return
        
    confirm = input(f"\nAre you sure you want to remove '{username}' (ID: {user_id})? (y/n): ").lower()
    if confirm == 'y':
        db_query("DELETE FROM users WHERE id = ?", (user_id,))
        log_action(admin_name, f"Removed user: '{username}' (ID: {user_id}).")
        print(f"\nSuccess: User '{username}' removed.")
    else:
        print("Removal cancelled.")
        
    wait_for_enter()

def reset_password(admin_name):
    user_to_reset = _find_user_helper()
    if user_to_reset is None:
        wait_for_enter()
        return
        
    user_id = user_to_reset['id']
    username = user_to_reset['username']
    
    print(f"\nResetting password for: {username}")
    new_pass = getpass.getpass("New Password: ")
    confirm_pass = getpass.getpass("Confirm New Password: ")
    
    if not new_pass or not confirm_pass:
        print("Error: All fields are required.")
        wait_for_enter()
        return
    if new_pass != confirm_pass:
        print("Error: New passwords do not match.")
        wait_for_enter()
        return
        
    try:
        new_hashed_pass = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_query("UPDATE users SET password = ? WHERE id = ?", (new_hashed_pass, user_id))
        log_action(admin_name, f"Reset password for user {username}.")
        print("Password has been reset successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
    wait_for_enter()

def export_users_to_excel(admin_name):
    if not PANDAS_OK:
        print("Error: 'pandas' and 'openpyxl' libraries are required for this feature.")
        print("Please run: pip install pandas openpyxl")
        wait_for_enter()
        return
        
    print_header("Export Users to Excel")
    try:
        df = db_query_to_df("SELECT id, username, full_name, role FROM users")
        filename = "user_export.xlsx"
        df.to_excel(filename, index=False, engine='openpyxl')
        log_action(admin_name, "Exported user list to Excel.")
        print(f"User list exported successfully to:\n{os.path.abspath(filename)}")
    except Exception as e:
        print(f"An error occurred: {e}")
        
    wait_for_enter()

def manage_consumption_menu(session):
    admin_id, role, admin_name, admin_username = session
    
    while True:
        print_header("Manage Consumption", session)
        print("1. View & Search Client Consumption")
        print("2. Add / Edit Consumption Record")
        print("3. Delete Consumption Record")
        print("4. Import Consumption from CSV")
        print("5. Export All Consumption to Excel")
        print("6. Back to Admin Menu")
        
        choice = input("\nEnter choice: ")
        
        if choice == '1':
            admin_view_consumption()
        elif choice == '2':
            admin_edit_consumption(admin_username)
        elif choice == '3':
            admin_delete_consumption(admin_username)
        elif choice == '4':
            import_consumption_csv(admin_username)
        elif choice == '5':
            export_consumption_to_excel(admin_username)
        elif choice == '6':
            break
        else:
            print("Invalid choice.")
            wait_for_enter()

def _select_client_helper():
    """Lists/searches clients and returns a chosen client's info."""
    print("\n--- Select a Client ---")
    
    search_term = input("Search by name (leave blank to list all): ")
    
    query = "SELECT id, username, full_name FROM users WHERE role = 'client'"
    params = []
    if search_term:
        query += " AND (username LIKE ? OR full_name LIKE ?)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])
    query += " ORDER BY full_name"
    
    clients_df = db_query_to_df(query, params)
    
    if clients_df.empty:
        print("\nNo clients found.")
        return None
        
    print(f"\n{'ID':<5} | {'Username':<20} | {'Full Name':<25}")
    print("-" * 54)
    for index, client in clients_df.iterrows():
        print(f"{client['id']:<5} | {client['username']:<20} | {client['full_name']:<25}")
    
    try:
        client_id = int(input("\nEnter the ID of the client (0 to cancel): "))
        if client_id == 0:
            return None
        
        client = clients_df[clients_df['id'] == client_id]
        if client.empty:
            print("Invalid ID.")
            return None
            
        return client.iloc[0] # Return the full pandas Series
            
    except ValueError:
        print("Invalid ID.")
        return None

def admin_view_consumption():
    client = _select_client_helper()
    if client is None:
        wait_for_enter()
        return
        
    client_id = client['id']
    client_name = client['full_name']
    
    search_term = input(f"\nSearch by month for {client_name} (e.g., 2025-09, or leave blank): ")
    
    query = "SELECT id, month, usage_kwh, total_bill, bill_status, payment_timestamp FROM consumption WHERE user_id = ?"
    params = [client_id]
    
    if search_term:
        query += " AND month LIKE ?"
        params.append(f"%{search_term}%")
    
    query += " ORDER BY month DESC"
    data_df = db_query_to_df(query, params=params)
    
    print_header(f"Consumption for {client_name}")
    
    if data_df.empty:
        print("No consumption data found.")
    else:
        total_usage = data_df['usage_kwh'].sum()
        avg_usage = data_df['usage_kwh'].mean()
        print(f"Total: {total_usage:.2f} kWh | Avg: {avg_usage:.2f} kWh/month\n")
        
        print(f"{'ID':<5} | {'Month':<10} | {'Usage (kWh)':<12} | {'Bill (₹)':<10} | {'Status':<25}")
        print("-" * 66)
        for index, row in data_df.iterrows():
            status = "Pending"
            if row['bill_status'] == 'Paid' and row['payment_timestamp']:
                status = f"Paid on {row['payment_timestamp']}"
            print(f"{row['id']:<5} | {row['month']:<10} | {row['usage_kwh']:<12.2f} | {row['total_bill']:<10.2f} | {status:<25}")
            
    wait_for_enter()

def admin_edit_consumption(admin_name):
    client = _select_client_helper()
    if client is None:
        wait_for_enter()
        return
        
    client_id = client['id']
    client_name = client['full_name']
    
    print(f"\nEditing usage for {client_name}:")
    
    try:
        year = input("Enter Year (YYYY): ")
        month = input("Enter Month (MM): ")
        usage_str = input("Enter Usage (kWh): ")
        
        if not (year.isdigit() and len(year) == 4) or not (month.isdigit() and 1 <= int(month) <= 12):
            print("\nError: Invalid date format. Use YYYY and MM.")
            wait_for_enter()
            return
        usage_float = float(usage_str)
            
        db_month = f"{year}-{month.zfill(2)}"
        
        # Use the upsert logic from the GUI
        action = upsert_consumption_logic(client_id, db_month, usage_float)
        
        log_action(admin_name, f"{action} usage for '{client_name}' ({db_month}) to {usage_float} kWh.")
        print(f"\nSuccess: Usage {action.lower()} for {client_name}.")
            
    except ValueError:
        print("\nError: Invalid usage. Please enter a number.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        
    wait_for_enter()

def upsert_consumption_logic(client_id, db_month, usage_float):
    """Shared logic for adding/updating a bill record."""
    bill_data, _ = calculate_mahadiscom_bill(usage_float)
    total_bill = round(bill_data['F_Total_Bill'], 2)
    
    find_query = "SELECT id FROM consumption WHERE user_id = ? AND month = ?"
    existing_record = db_query_to_df(find_query, params=(client_id, db_month))
    
    if not existing_record.empty:
        record_id = existing_record.iloc[0]['id']
        update_query = "UPDATE consumption SET usage_kwh = ?, total_bill = ?, bill_status = 'Pending', payment_timestamp = NULL WHERE id = ?"
        db_query(update_query, params=(usage_float, total_bill, record_id))
        return "Updated"
    else:
        insert_query = "INSERT INTO consumption (user_id, month, usage_kwh, total_bill, bill_status) VALUES (?, ?, ?, ?, 'Pending')"
        db_query(insert_query, params=(client_id, db_month, usage_float, total_bill))
        return "Added"

def admin_delete_consumption(admin_name):
    client = _select_client_helper()
    if client is None:
        wait_for_enter()
        return
        
    client_id = client['id']
    client_name = client['full_name']
    
    print(f"\n--- Records for {client_name} ---")
    data_df = db_query_to_df("SELECT id, month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month DESC", (client_id,))
    if data_df.empty:
        print("No records found for this client.")
        wait_for_enter()
        return
        
    print(f"{'ID':<5} | {'Month':<10} | {'Usage (kWh)':<12}")
    print("-" * 30)
    for index, row in data_df.iterrows():
        print(f"{row['id']:<5} | {row['month']:<10} | {row['usage_kwh']:<12.2f}")
    
    try:
        record_id = int(input("\nEnter the ID of the record to delete (0 to cancel): "))
        if record_id == 0:
            return
            
        record = data_df[data_df['id'] == record_id]
        if record.empty:
            print("Invalid ID.")
            wait_for_enter()
            return
            
        record_month = record.iloc[0]['month']
        
        # Use a simple text-based confirm
        confirm = input(f"Are you sure you want to delete the record for {client_name} for month {record_month}? (y/n): ").lower()
        if confirm == 'y':
            db_query("DELETE FROM consumption WHERE id = ?", (record_id,))
            log_action(admin_name, f"Deleted usage record for {client_name} (Month: {record_month}, ID: {record_id}).")
            print("Usage record deleted.")
        else:
            print("Delete cancelled.")
            
    except ValueError:
        print("Invalid ID.")
        
    wait_for_enter()

def import_consumption_csv(admin_name):
    if not PANDAS_OK:
        print("Error: 'pandas' and 'csv' libraries are required for this feature.")
        wait_for_enter()
        return
        
    print_header("Import Consumption from CSV")
    filename = input("Enter the path to your .csv file: ")
    
    if not os.path.exists(filename):
        print("Error: File not found.")
        wait_for_enter()
        return
        
    added_count = 0
    updated_count = 0
    failed_count = 0
    
    try:
        with open(filename, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    user_id = int(row['user_id'])
                    month = row['month']
                    usage_kwh = float(row['usage_kwh'])
                    
                    action = upsert_consumption_logic(user_id, month, usage_kwh)
                    if action == "Added":
                        added_count += 1
                    else:
                        updated_count += 1
                except Exception as e:
                    print(f"Failed to process row: {row}. Error: {e}")
                    failed_count += 1
                    
        log_action(admin_name, f"Imported CSV: {added_count} added, {updated_count} updated, {failed_count} failed.")
        print("\n--- Import Complete ---")
        print(f"Added: {added_count}\nUpdated: {updated_count}\nFailed: {failed_count}")
        
    except Exception as e:
        print(f"An error occurred during import: {e}")
        
    wait_for_enter()

def export_consumption_to_excel(admin_name):
    if not PANDAS_OK:
        print("Error: 'pandas' and 'openpyxl' libraries are required for this feature.")
        wait_for_enter()
        return
        
    print_header("Export All Consumption to Excel")
    try:
        df = db_query_to_df("""
            SELECT c.id, u.full_name, c.month, c.usage_kwh, c.total_bill, c.bill_status
            FROM consumption c
            JOIN users u ON c.user_id = u.id
            ORDER BY u.full_name, c.month
        """)
        filename = "consumption_export.xlsx"
        df.to_excel(filename, index=False, engine='openpyxl')
        log_action(admin_name, "Exported consumption list to Excel.")
        print(f"Consumption data exported successfully to:\n{os.path.abspath(filename)}")
    except Exception as e:
        print(f"An error occurred: {e}")
        
    wait_for_enter()

def admin_generate_bill(session):
    print_header("Generate Client Bill", session)
    
    client = _select_client_helper()
    if client is None:
        wait_for_enter()
        return
        
    client_id = client['id']
    client_name = client['full_name']
    
    months_data = db_query_to_df("SELECT month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month DESC", (client_id,))
    
    if months_data.empty:
        print("No consumption data found for this client.")
        wait_for_enter()
        return

    print(f"\nAvailable billing months for {client_name}:")
    for i, row in months_data.iterrows():
        print(f"  {i+1}. {row['month']} ({row['usage_kwh']} kWh)")
    print("  0. Cancel")
    
    try:
        choice = int(input("\nSelect a month to generate a bill: "))
        if choice == 0:
            return
        
        selected_row = months_data.iloc[choice - 1]
        month = selected_row['month']
        kwh_units = selected_row['usage_kwh']
        
        clear_screen()
        bill_text = get_bill_text(kwh_units, month, client_name)
        print(bill_text)
        
        export_choice = input("\nDo you want to export this bill to a .txt file? (y/n): ").lower()
        if export_choice == 'y':
            export_bill_to_txt(bill_text, client_name, month)
            
    except (ValueError, IndexError):
        print("Invalid choice.")
    
    wait_for_enter()
    
def admin_view_analytics():
    print_header("Site-Wide Analytics")
    
    # 1. Total by user
    data_by_user = db_query_to_df("""
        SELECT u.full_name, SUM(c.usage_kwh) as total_usage
        FROM consumption c JOIN users u ON c.user_id = u.id
        WHERE u.role = 'client'
        GROUP BY u.full_name ORDER BY total_usage DESC
    """)
    print("\n--- Total Usage by Client ---")
    if data_by_user.empty:
        print("No client consumption data.")
    else:
        print(f"{'Client Name':<25} | {'Total Usage (kWh)':<15}")
        print("-" * 43)
        total_sum = 0.0
        for index, row in data_by_user.iterrows():
            print(f"{row['full_name']:<25} | {row['total_usage']:<15.2f}")
            total_sum += row['total_usage']
        print("-" * 43)
        print(f"{'TOTAL':<25} | {total_sum:<15.2f}")

    # 2. Total by month
    data_by_month = db_query_to_df("SELECT month, SUM(usage_kwh) as total_usage FROM consumption GROUP BY month ORDER BY month")
    print("\n--- Total Usage by Month ---")
    if data_by_month.empty:
        print("No monthly consumption data.")
    else:
        print(f"{'Month':<10} | {'Total Usage (kWh)':<15}")
        print("-" * 28)
        for index, row in data_by_month.iterrows():
            print(f"{row['month']:<10} | {row['total_usage']:<15.2f}")
            
    wait_for_enter()

def admin_compare_clients():
    print_header("Compare Clients")
    
    clients = db_query_to_df("SELECT id, full_name FROM users WHERE role = 'client' ORDER BY full_name")
    if clients.empty:
        print("No clients found to compare.")
        wait_for_enter()
        return

    print("Available Clients:")
    for index, client in clients.iterrows():
        print(f"  ID: {client['id']} - {client['full_name']}")
        
    client_ids_str = input("\nEnter client IDs to compare, separated by commas (e.g., 1,2,3): ")
    try:
        selected_ids = [int(cid.strip()) for cid in client_ids_str.split(',')]
    except ValueError:
        print("Invalid input. Please enter numbers separated by commas.")
        wait_for_enter()
        return
        
    if not selected_ids:
        print("No clients selected.")
        wait_for_enter()
        return

    print("\n--- Client Comparison ---")
    all_data = {}
    all_months = set()

    for cid in selected_ids:
        client_df = db_query_to_df("SELECT month, usage_kwh, u.full_name FROM consumption c JOIN users u ON c.user_id = u.id WHERE c.user_id = ? ORDER BY month", (cid,))
        if not client_df.empty:
            all_data[client_df.iloc[0]['full_name']] = {row['month']: row['usage_kwh'] for index, row in client_df.iterrows()}
            all_months.update(client_df['month'])

    if not all_data:
        print("No consumption data found for the selected clients.")
        wait_for_enter()
        return

    sorted_months = sorted(list(all_months))
    clients_to_compare = list(all_data.keys())
    
    # Print Header
    header = f"{'Month':<10}"
    for name in clients_to_compare:
        header += f" | {name[:15]:<15}" # Truncate long names
    print(header)
    print("-" * len(header))
    
    # Print Rows
    for month in sorted_months:
        row_str = f"{month:<10}"
        for name in clients_to_compare:
            usage = all_data[name].get(month, 0.0) # Get usage or 0
            row_str += f" | {usage:<15.2f}"
        print(row_str)
        
    wait_for_enter()

def admin_manage_grievances(session):
    """Admin's main view for managing grievance tickets."""
    while True:
        print_header("Manage Grievances", session)
        
        print("Filter by: [1] All  [2] Pending  [3] Answered  [4] Resolved")
        filter_choice = input("Enter choice (default 1): ")
        
        status_map = {'1': 'All', '2': 'Pending', '3': 'Answered', '4': 'Resolved'}
        filter_status = status_map.get(filter_choice, 'All')
        
        base_query = "SELECT id, token, created_at, username, subject, status FROM grievance_tickets"
        params = []
        if filter_status != "All":
            base_query += " WHERE status = ?"
            params.append(filter_status)
        base_query += " ORDER BY updated_at DESC"
        
        tickets_df = db_query_to_df(base_query, params=params)

        if tickets_df.empty:
            print(f"\nNo '{filter_status}' tickets found.")
        else:
            print(f"\n--- Displaying '{filter_status}' Tickets ---")
            print(f"{'ID':<5} | {'Token':<10} | {'Updated':<20} | {'User':<15} | {'Status':<10} | {'Subject':<30}")
            print("-" * 94)
            for index, row in tickets_df.iterrows():
                print(f"{row['id']:<5} | {row['token']:<10} | {row['created_at']:<20} | {row['username']:<15} | {row['status']:<10} | {row['subject']:<30}")
        
        print("\nOptions:")
        print("  Enter a Ticket ID to view/reply to the chat.")
        print("  'r <ID>' to quickly Mark as Resolved (e.g., r 3)")
        print("  'q' to go back to the Admin Menu.")
        
        choice = input("\nEnter choice: ").lower()
        
        if choice == 'q':
            break
        elif choice.startswith('r '):
            try:
                ticket_id = int(choice.split()[1])
                admin_resolve_grievance(session, ticket_id)
            except (IndexError, ValueError):
                print("Invalid format. Use 'r <ID>'.")
                wait_for_enter()
        else:
            try:
                ticket_id = int(choice)
                ticket = tickets_df[tickets_df['id'] == ticket_id]
                if ticket.empty:
                    print("Invalid Ticket ID.")
                    wait_for_enter()
                else:
                    subject = ticket.iloc[0]['subject']
                    handle_grievance_chat(session, ticket_id, subject)
            except ValueError:
                print("Invalid choice. Please enter a Ticket ID, 'r <ID>', or 'q'.")
                wait_for_enter()

def admin_resolve_grievance(session, ticket_id):
    """Quickly resolves a ticket from the admin menu."""
    status_df = db_query_to_df("SELECT status FROM grievance_tickets WHERE id = ?", (ticket_id,))
    if status_df.empty:
        print("Invalid Ticket ID.")
        wait_for_enter()
        return

    status = status_df.iloc[0]['status']
    if status == "Resolved":
        print("That ticket is already resolved.")
        wait_for_enter()
        return

    if input(f"Are you sure you want to mark ticket ID {ticket_id} as 'Resolved'? (y/n): ").lower() == 'y':
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query("UPDATE grievance_tickets SET status = 'Resolved', updated_at = ? WHERE id = ?", (timestamp, ticket_id))
        log_action(session[3], f"Resolved grievance ticket ID {ticket_id}.")
        print("Ticket marked as resolved.")
    else:
        print("Action cancelled.")
    wait_for_enter()

def admin_view_log(session):
    """Allows admin to filter and view the action log."""
    print_header("View Action Log", session)
    
    users_df = db_query_to_df("SELECT username FROM users ORDER BY username")
    user_list = ["All Users"] + list(users_df['username'])
    
    print("Filter by User:")
    for i, user in enumerate(user_list):
        print(f"  {i}. {user}")
        
    try:
        choice = int(input(f"Enter number (0 for All Users): "))
        if choice < 0 or choice >= len(user_list):
            selected_user = "All Users"
        else:
            selected_user = user_list[choice]
    except ValueError:
        selected_user = "All Users"

    base_query = "SELECT timestamp, actor, action FROM action_log"
    params = []
    
    if selected_user != "All Users":
        base_query += " WHERE actor = ?"
        params.append(selected_user)
        
    base_query += " ORDER BY id DESC LIMIT 200"
    
    log_df = db_query_to_df(base_query, params=params)
    
    clear_screen()
    print(f"--- Action Log (Filter: {selected_user}) ---")
    if log_df.empty:
        print("Log is empty.")
    else:
        print(f"\n{'Timestamp':<20} | {'User':<15} | {'Action':<50}")
        print("-" * 88)
        for index, row in log_df.iterrows():
            print(f"{row[0]:<20} | {row['actor']:<15} | {row['action']:<50}")
            
    wait_for_enter()

# --- ADMIN: Main Menu ---

def admin_menu(session):
    """Main loop for a logged-in admin."""
    while True:
        print_header("Admin Menu", session)
        print("--- User Management ---")
        print("  1. Manage Users (Add, Remove, Update, etc.)")
        print("--- Consumption ---")
        print("  2. Manage Consumption (View, Edit, Import, etc.)")
        print("--- Billing & Analytics ---")
        print("  3. Generate Client Bill")
        print("  4. View Site-Wide Analytics")
        print("  5. Compare Clients")
        print("--- System & Support ---")
        print("  6. Manage Grievances")
        print("  7. View Action Log")
        print("  8. Change My Password")
        print("  9. Logout")
        
        choice = input("\nEnter choice: ")

        if choice == '1':
            manage_users_menu(session)
        elif choice == '2':
            manage_consumption_menu(session)
        elif choice == '3':
            admin_generate_bill(session)
        elif choice == '4':
            admin_view_analytics()
        elif choice == '5':
            admin_compare_clients()
        elif choice == '6':
            admin_manage_grievances(session)
        elif choice == '7':
            admin_view_log(session)
        elif choice == '8':
            handle_change_password(session)
        elif choice == '9':
            break
        else:
            print("Invalid choice.")
            wait_for_enter()

# --- MAIN PROGRAM LOOP ---

def main():
    """Main program loop."""
    setup_database()
    
    while True:
        clear_screen()
        print("=" * 60)
        print("--- ELECTRICITY DISTRIBUTION PORTAL (CLI) ---")
        print("=" * 60)
        print("\n--- Main Menu ---")
        print("1. Login")
        print("2. Register New Client Account")
        print("3. Exit")
        choice = input("Enter choice: ")

        if choice == '1':
            user_session = handle_login() 
            
            if user_session:
                if user_session[1] == 'admin':
                    admin_menu(user_session)
                else: 
                    client_menu(user_session)
                
                log_action(user_session[3], "Logged out.")
                print("You have been logged out.")
                wait_for_enter()

        elif choice == '2':
            handle_register()

        elif choice == '3':
            print("Exiting program. Goodbye.")
            sys.exit()
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
            wait_for_enter()

if __name__ == "__main__":
    main()