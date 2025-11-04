import sqlite3
import getpass  # For securely typing passwords
from datetime import datetime
import sys

# --- Database Setup ---
# (This is the same as the GUI app)
def setup_database():
    """Creates the database tables if they don't exist."""
    conn = sqlite3.connect('electricity.db')
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
    
    # --- Add a default admin if one doesn't exist ---
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                ('admin', 'admin123', 'admin', 'Administrator')
            )
            print("Default admin user created (admin/admin123).")
        except sqlite3.IntegrityError:
            pass  # Should be caught by the SELECT, but good practice

    conn.commit()
    conn.close()

# --- Database & Logging Utilities ---

def db_execute(query, params=()):
    """For INSERT, UPDATE, DELETE queries."""
    try:
        conn = sqlite3.connect('electricity.db')
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Error]: {e}")
        return False

def db_query(query, params=()):
    """For SELECT queries. Returns a list of tuples."""
    try:
        conn = sqlite3.connect('electricity.db')
        cursor = conn.cursor()
        cursor.execute(query, params)
        data = cursor.fetchall()
        conn.close()
        return data
    except Exception as e:
        print(f"[DB Error]: {e}")
        return []

def log_action(actor, action):
    """Logs an action to the database."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute("INSERT INTO action_log (timestamp, actor, action) VALUES (?, ?, ?)", (now, actor, action))

# --- Client Functions ---

def view_my_usage(user_id):
    """Fetches and prints consumption data for a specific user."""
    print("\n--- Your Monthly Usage ---")
    data = db_query("SELECT month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month DESC", (user_id,))
    
    if not data:
        print("No consumption data found.")
        return
        
    print(f"{'Month':<10} | {'Usage (kWh)':<12}")
    print("-" * 25)
    for row in data:
        print(f"{row[0]:<10} | {row[1]:<12.2f}")

def client_menu(user_id, user_name):
    """Displays the main menu for a logged-in client."""
    while True:
        print(f"\n--- Client Menu (Logged in as: {user_name}) ---")
        print("1. View My Monthly Usage")
        print("2. Logout")
        choice = input("Enter choice: ")

        if choice == '1':
            view_my_usage(user_id)
        elif choice == '2':
            break # Go back to main menu
        else:
            print("Invalid choice. Please try again.")

# --- Admin Functions ---

def add_user(admin_name):
    """Admin function to add a new user (admin or client)."""
    print("\n--- Add New User ---")
    full_name = input("Enter Full Name: ")
    username = input("Enter Username: ")
    password = getpass.getpass("Enter Password: ")
    role = ""
    while role not in ['admin', 'client']:
        role = input("Enter Role (admin/client): ").lower()
        
    if not all([full_name, username, password, role]):
        print("Error: All fields are required. User not added.")
        return

    try:
        db_execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                   (username, password, role, full_name))
        log_action(admin_name, f"Added new user: '{username}' (Role: {role}).")
        print(f"\nSuccess: User '{username}' created as {role}.")
    except sqlite3.IntegrityError:
        print("\nError: Username already exists.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

def remove_user(admin_id, admin_name):
    """Admin function to remove a user by ID."""
    print("\n--- Remove User ---")
    list_all_users(show_pass=False) # Show list to help admin
    
    try:
        user_id_to_remove = int(input("\nEnter ID of user to remove (0 to cancel): "))
        if user_id_to_remove == 0:
            print("Cancelled.")
            return

        if user_id_to_remove == admin_id:
            print("\nError: You cannot remove your own account.")
            return
            
        # Get username for logging before deleting
        user = db_query("SELECT username FROM users WHERE id = ?", (user_id_to_remove,))
        if not user:
            print("\nError: User ID not found.")
            return
        
        username_to_remove = user[0][0]
        
        confirm = input(f"Are you sure you want to remove '{username_to_remove}' (ID: {user_id_to_remove})? (y/n): ").lower()
        if confirm == 'y':
            db_execute("DELETE FROM users WHERE id = ?", (user_id_to_remove,))
            log_action(admin_name, f"Removed user: '{username_to_remove}' (ID: {user_id_to_remove}).")
            print(f"\nSuccess: User '{username_to_remove}' removed.")
        else:
            print("Removal cancelled.")
            
    except ValueError:
        print("\nError: Invalid ID. Please enter a number.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

def list_all_users(show_pass=True):
    """Lists all users, with sorting options. Helper for remove_user."""
    print("\n--- List All Users ---")
    print("Sort by: [1] Role (default)  [2] Username  [3] Full Name  [4] ID")
    sort_choice = input("Enter sort choice (1-4): ")
    
    sort_map = {
        '1': 'role',
        '2': 'username',
        '3': 'full_name',
        '4.': 'id'
    }
    sort_col = sort_map.get(sort_choice, 'role')
    
    order_choice = input("Order: [1] Ascending (default)  [2] Descending: ")
    sort_order = "DESC" if order_choice == '2' else "ASC"
    
    query = f"SELECT id, username, full_name, role, password FROM users ORDER BY {sort_col} {sort_order}"
    data = db_query(query)
    
    if not data:
        print("No users found in the database.")
        return
    
    # Dynamic header
    if show_pass:
        print(f"\n{'ID':<5} | {'Username':<15} | {'Full Name':<20} | {'Role':<10} | {'Password':<15}")
        print("-" * 70)
    else:
        print(f"\n{'ID':<5} | {'Username':<15} | {'Full Name':<20} | {'Role':<10}")
        print("-" * 53)

    for row in data:
        if show_pass:
            print(f"{row[0]:<5} | {row[1]:<15} | {row[2]:<20} | {row[3]:<10} | {row[4]:<15}")
        else:
            print(f"{row[0]:<5} | {row[1]:<15} | {row[2]:<20} | {row[3]:<10}")

def view_client_consumption():
    """Admin function to select a client and view their usage."""
    print("\n--- View Client's Consumption ---")
    clients = db_query("SELECT id, username, full_name FROM users WHERE role = 'client' ORDER BY full_name")
    if not clients:
        print("No clients found.")
        return
    
    print("Available Clients:")
    for client in clients:
        print(f"  ID: {client[0]} - {client[2]} ({client[1]})")
    
    try:
        client_id = int(input("\nEnter Client ID to view (0 to cancel): "))
        if client_id == 0:
            print("Cancelled.")
            return

        client_check = [c for c in clients if c[0] == client_id]
        if not client_check:
            print("\nError: Not a valid client ID.")
            return
            
        client_name = client_check[0][2]
        print(f"\n--- Usage for {client_name} ---")
        view_my_usage(client_id) # Reuse the client's function
    except ValueError:
        print("\nError: Invalid ID. Please enter a number.")

def edit_client_consumption(admin_name):
    """Admin function to add or update a client's consumption record."""
    print("\n--- Add/Edit Client's Consumption ---")
    clients = db_query("SELECT id, username, full_name FROM users WHERE role = 'client' ORDER BY full_name")
    if not clients:
        print("No clients found.")
        return
    
    print("Available Clients:")
    for client in clients:
        print(f"  ID: {client[0]} - {client[2]} ({client[1]})")

    try:
        client_id = int(input("\nEnter Client ID to edit (0 to cancel): "))
        if client_id == 0:
            print("Cancelled.")
            return
            
        client_check = [c for c in clients if c[0] == client_id]
        if not client_check:
            print("\nError: Not a valid client ID.")
            return
        
        client_name = client_check[0][2]
        print(f"\nEditing usage for {client_name}:")
        
        year = input("Enter Year (YYYY): ")
        month = input("Enter Month (MM): ")
        usage_str = input("Enter Usage (kWh): ")
        
        # Validation
        if not (year.isdigit() and len(year) == 4) or not (month.isdigit() and 1 <= int(month) <= 12):
            print("\nError: Invalid date format. Use YYYY and MM. Action cancelled.")
            return
        usage = float(usage_str) # Will raise ValueError if invalid
            
        db_month = f"{year}-{month.zfill(2)}" # e.g., 2025-05
        
        # UPSERT logic
        existing = db_query("SELECT id FROM consumption WHERE user_id = ? AND month = ?", (client_id, db_month))
        
        if existing:
            db_execute("UPDATE consumption SET usage_kwh = ? WHERE user_id = ? AND month = ?", (usage, client_id, db_month))
            log_action(admin_name, f"Updated usage for '{client_name}' ({db_month}) to {usage} kWh.")
            print(f"\nSuccess: Usage updated for {client_name}.")
        else:
            db_execute("INSERT INTO consumption (user_id, month, usage_kwh) VALUES (?, ?, ?)", (client_id, db_month, usage))
            log_action(admin_name, f"Added new usage for '{client_name}' ({db_month}): {usage} kWh.")
            print(f"\nSuccess: Usage added for {client_name}.")
            
    except ValueError:
        print("\nError: Invalid ID or usage. Please enter numbers. Action cancelled.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

def view_total_consumption():
    """Admin function to see site-wide consumption stats."""
    print("\n--- Total Site-Wide Consumption ---")
    
    # 1. Total by user (like pie chart)
    data_by_user = db_query("""
        SELECT u.full_name, SUM(c.usage_kwh) as total_usage
        FROM consumption c JOIN users u ON c.user_id = u.id
        WHERE u.role = 'client'
        GROUP BY u.full_name
        ORDER BY total_usage DESC
    """)
    print("\nTotal Usage by Client:")
    if not data_by_user:
        print("No client consumption data.")
    else:
        print(f"{'Client Name':<20} | {'Total Usage (kWh)':<15}")
        print("-" * 38)
        total_sum = 0.0
        for row in data_by_user:
            print(f"{row[0]:<20} | {row[1]:<15.2f}")
            total_sum += row[1]
        print("-" * 38)
        print(f"{'TOTAL':<20} | {total_sum:<15.2f}")

    # 2. Total by month (like line graph)
    data_by_month = db_query("SELECT month, SUM(usage_kwh) as total_usage FROM consumption GROUP BY month ORDER BY month")
    print("\nTotal Usage by Month:")
    if not data_by_month:
        print("No monthly consumption data.")
    else:
        print(f"{'Month':<10} | {'Total Usage (kWh)':<15}")
        print("-" * 28)
        for row in data_by_month:
            print(f"{row[0]:<10} | {row[1]:<15.2f}")

def view_action_log():
    """Admin function to view the action log."""
    print("\n--- Action Log (Most Recent 100) ---")
    data = db_query("SELECT timestamp, actor, action FROM action_log ORDER BY id DESC LIMIT 100")
    if not data:
        print("Log is empty.")
        return
    
    print(f"{'Timestamp':<20} | {'User':<15} | {'Action':<50}")
    print("-" * 88)
    for row in data:
        print(f"{row[0]:<20} | {row[1]:<15} | {row[2]:<50}")

def admin_menu(admin_id, admin_name):
    """Displays the main menu for a logged-in admin."""
    while True:
        print(f"\n--- Admin Menu (Logged in as: {admin_name}) ---")
        print(" 1. Add User (Admin/Client)")
        print(" 2. Remove User")
        print(" 3. List All Users")
        print(" 4. View Client's Consumption")
        print(" 5. Add/Edit Client's Consumption")
        print(" 6. View Total Site Consumption")
        print(" 7. View Action Log")
        print(" 8. Logout")
        choice = input("Enter choice: ")

        if choice == '1':
            add_user(admin_name)
        elif choice == '2':
            remove_user(admin_id, admin_name)
        elif choice == '3':
            list_all_users(show_pass=True)
        elif choice == '4':
            view_client_consumption()
        elif choice == '5':
            edit_client_consumption(admin_name)
        elif choice == '6':
            view_total_consumption()
        elif choice == '7':
            view_action_log()
        elif choice == '8':
            break # Go back to main menu
        else:
            print("Invalid choice. Please try again.")

# --- Main Login & Program Loop ---

def login():
    """Handles the login process. Returns (id, name, role) or None."""
    print("\n--- Portal Login ---")
    username = input("Username: ")
    password = getpass.getpass("Password: ") # Hides password input
    
    user = db_query("SELECT id, password, role, full_name FROM users WHERE username = ?", (username,))
    
    if user and user[0][1] == password:
        user_data = user[0] # user is a list containing one tuple: [(id, pass, role, name)]
        print(f"\nSuccess! Welcome, {user_data[3]}.")
        log_action(username, "Logged in successfully.")
        # Return (id, full_name, role)
        return (user_data[0], user_data[3], user_data[2])
    else:
        print("\nError: Invalid username or password.")
        log_action(username, "Failed login attempt.")
        return None

def main():
    """Main program loop."""
    print("Welcome to the Electricity Portal (CLI Mode)")
    # Ensure database and tables exist before starting
    setup_database()
    
    while True:
        print("\n--- Main Menu ---")
        print("1. Login")
        print("2. Exit")
        choice = input("Enter choice: ")

        if choice == '1':
            user_session = login() # This function will handle the login logic
            
            if user_session:
                user_id, user_name, user_role = user_session
                
                if user_role == 'admin':
                    admin_menu(user_id, user_name)
                else: # user_role == 'client'
                    client_menu(user_id, user_name)
                
                # After admin_menu() or client_menu() breaks, we log out.
                log_action(user_name, "Logged out.")
                print("You have been logged out.")

        elif choice == '2':
            print("Exiting program. Goodbye.")
            sys.exit()
        else:
            print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main()