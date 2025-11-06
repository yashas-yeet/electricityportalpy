import sqlite3  #for database
import getpass  #for passwords
from datetime import datetime #for clock and time
import sys #for system tool which helps us to to exit the program
import os #for exporting the bill and the showing file path and clearing the terminal screen every time we press enter

#billing schematic taking from MAHA electricity board's tarrifs for an example tarrif set


FIXED_CHARGE_SINGLE_PHASE = 115.00
WHEELING_CHARGE_PER_KWH = 1.40
FAC_PER_KWH = 0.00
ELECTRICITY_DUTY_RATE = 0.16
slabs = [
    (100, 3.46), (200, 7.43), (200, 10.32), (500, 11.71), (float('inf'), 11.71)
]

#this part creates and connects to a database electricity.db and creates 3 tables, users, user consumption and action log

def setup_database():
    """Creates the database tables if they don't exist."""
    conn = sqlite3.connect('electricity.db')
    cursor = conn.cursor()
    
    #user table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'client')),
        full_name TEXT
    )
    ''')
    
    #consumption table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        usage_kwh REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')
    
    #action log table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL
    )
    ''')
    
    # Add a default admin if one doesn't exist
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                ('admin', 'admin123', 'admin', 'Administrator')
            )
        except sqlite3.IntegrityError:
            pass 

    conn.commit()
    conn.close()

#this part of the code deals with the insert, delete, update functions of the database

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

def db_fetch(query, params=()):
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

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def wait_for_enter():
    """Pauses execution until the user presses Enter."""
    input("\nPress Enter to continue...")

#billing logic

def calculate_mahadiscom_bill(kwh_units):
    bill = {}
    bill_details = []
    energy_charge = 0.0
    remaining_units = kwh_units
    
    for slab_limit, rate in slabs:
        if remaining_units <= 0: break
        units_in_this_slab = min(remaining_units, slab_limit)
        slab_cost = units_in_this_slab * rate
        energy_charge += slab_cost
        remaining_units -= units_in_this_slab
        bill_details.append(f"  - {units_in_this_slab:.2f} kWh @ ₹{rate:.2f}/unit = ₹{slab_cost:.2f}")

    bill['A_Energy_Charge'] = energy_charge
    bill['B_Fixed_Charge'] = FIXED_CHARGE_SINGLE_PHASE
    bill['C_Wheeling_Charge'] = kwh_units * WHEELING_CHARGE_PER_KWH
    bill['D_FAC'] = kwh_units * FAC_PER_KWH
    sub_total = (bill['A_Energy_Charge'] + bill['B_Fixed_Charge'] + 
                 bill['C_Wheeling_Charge'] + bill['D_FAC'])
    bill['E_Electricity_Duty'] = sub_total * ELECTRICITY_DUTY_RATE
    bill['F_Total_Bill'] = sub_total + bill['E_Electricity_Duty']
    
    return bill, bill_details


#printing the bill

def generate_bill_text(kwh_units, month, user_name):
    try:
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
    except Exception as e:
        return f"An error occurred during bill calculation: {e}"
    
    
#exports the bill on user's demand

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

#client interface
#consumption view

def view_my_consumption(user_id):
    clear_screen()
    print("--- Your Monthly Usage ---")
    data = db_fetch("SELECT month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month DESC", (user_id,))
    
    if not data:
        print("No consumption data found.")
        wait_for_enter()
        return
        
    print(f"\n{'Month':<10} | {'Usage (kWh)':<12}")
    print("-" * 25)
    for row in data:
        print(f"{row[0]:<10} | {row[1]:<12.2f}")
    
    wait_for_enter()
#view usage
def view_my_bill(user_id, user_name):
    clear_screen()
    print("--- View Your Bill ---")
    
    # 1. Fetch available months
    months_data = db_fetch("SELECT month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month DESC", (user_id,))
    
    if not months_data:
        print("No consumption data found. Cannot generate a bill.")
        wait_for_enter()
        return

    # 2. Display months and ask user to choose
    print("Available billing months:")
    for i, (month, usage) in enumerate(months_data):
        print(f"  {i+1}. {month} ({usage} kWh)")
    print("  0. Cancel")
    
    try:
        choice_str = input("\nSelect a month to generate a bill: ")
        choice = int(choice_str)
        
        if choice == 0:
            return
        
        selected_data = months_data[choice - 1]
        month, kwh_units = selected_data
        
        # 3. Generate and display bill
        clear_screen()
        bill_text = generate_bill_text(kwh_units, month, user_name)
        print(bill_text)
        
        # 4. Ask to export
        export_choice = input("\nDo you want to export this bill to a .txt file? (y/n): ").lower()
        if export_choice == 'y':
            export_bill_to_txt(bill_text, user_name, month)
            
    except (ValueError, IndexError):
        print("Invalid choice.")
    
    wait_for_enter()
#client loop, keeps showing the user info and breaks when pressed 3 aka exit
def client_menu(user_session):
    user_id, user_name, user_role = user_session
    
    while True:
        clear_screen()
        print(f"--- Client Menu (Logged in as: {user_name}) ---")
        print("1. View My Monthly Usage")
        print("2. View My Bill")
        print("3. Logout")
        choice = input("Enter choice: ")

        if choice == '1':
            view_my_consumption(user_id)
        elif choice == '2':
            view_my_bill(user_id, user_name)
        elif choice == '3':
            break 
        else:
            print("Invalid choice. Please try again.")
            wait_for_enter()

#admin page
#add user client/admin
def add_user(admin_name):
    clear_screen()
    print("--- Add New User ---")
    full_name = input("Enter Full Name: ")
    username = input("Enter Username: ")
    password = getpass.getpass("Enter Password: ")
    role = ""
    while role not in ['admin', 'client']:
        role = input("Enter Role (admin/client): ").lower()
        
    if not all([full_name, username, password, role]):
        print("Error: All fields are required. User not added.")
    else:
        if db_execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                      (username, password, role, full_name)):
            log_action(admin_name, f"Added new user: '{username}' (Role: {role}).")
            print(f"\nSuccess: User '{username}' created as {role}.")
        else:
            print("\nError: Username already exists.")
            
    wait_for_enter()
# remove user, cant remove self
def remove_user(admin_id, admin_name):
    clear_screen()
    print("--- Remove User ---")
    list_search_users(show_pass=False, allow_search=False, allow_sort=False) # Show simple list
    
    try:
        user_id_to_remove = int(input("\nEnter ID of user to remove (0 to cancel): "))
        if user_id_to_remove == 0:
            print("Cancelled.")
            wait_for_enter()
            return

        if user_id_to_remove == admin_id:
            print("\nError: You cannot remove your own account.")
            wait_for_enter()
            return
            
        user = db_fetch("SELECT username FROM users WHERE id = ?", (user_id_to_remove,))
        if not user:
            print("\nError: User ID not found.")
            wait_for_enter()
            return
        
        username_to_remove = user[0][0]
        
        confirm = input(f"Are you sure you want to remove '{username_to_remove}' (ID: {user_id_to_remove})? (y/n): ").lower()
        if confirm == 'y':
            if db_execute("DELETE FROM users WHERE id = ?", (user_id_to_remove,)):
                log_action(admin_name, f"Removed user: '{username_to_remove}' (ID: {user_id_to_remove}).")
                print(f"\nSuccess: User '{username_to_remove}' removed.")
        else:
            print("Removal cancelled.")
            
    except ValueError:
        print("\nError: Invalid ID. Please enter a number.")
    
    wait_for_enter()
# searching and sorting
def list_search_users(show_pass=True, allow_search=True, allow_sort=True):
    clear_screen()
    print("--- List All Users ---")
    
    params = []
    base_query = "SELECT id, username, full_name, role, password FROM users"
    
    # Search
    if allow_search:
        search_term = input("Search by name or username (leave blank to list all): ")
        if search_term:
            base_query += " WHERE (username LIKE ? OR full_name LIKE ?)"
            params.extend([f"%{search_term}%", f"%{search_term}%"])
    
    # Sort
    if allow_sort:
        print("Sort by: [1] Role (default)  [2] Username  [3] Full Name  [4] ID")
        sort_choice = input("Enter sort choice (1-4): ")
        sort_map = {'1': 'role', '2': 'username', '3': 'full_name', '4': 'id'}
        sort_col = sort_map.get(sort_choice, 'role')
        
        order_choice = input("Order: [1] Ascending (default)  [2] Descending: ")
        sort_order = "DESC" if order_choice == '2' else "ASC"
        base_query += f" ORDER BY {sort_col} {sort_order}"
    
    data = db_fetch(base_query, tuple(params))
    
    if not data:
        print("\nNo users found.")
        wait_for_enter()
        return
    
    # Display
    if show_pass:
        print(f"\n{'ID':<5} | {'Username':<20} | {'Full Name':<25} | {'Role':<10} | {'Password':<15}")
        print("-" * 80)
    else:
        print(f"\n{'ID':<5} | {'Username':<20} | {'Full Name':<25} | {'Role':<10}")
        print("-" * 64)

    for row in data:
        if show_pass:
            print(f"{row[0]:<5} | {row[1]:<20} | {row[2]:<25} | {row[3]:<10} | {row[4]:<15}")
        else:
            print(f"{row[0]:<5} | {row[1]:<20} | {row[2]:<25} | {row[3]:<10}")
            
    if allow_search or allow_sort: # Only pause if it's the main function
        wait_for_enter()
#lists the clients every interface for ease
def _select_client_helper():
    """Helper to list and select a client. Returns (id, name) or None."""
    clients = db_fetch("SELECT id, username, full_name FROM users WHERE role = 'client' ORDER BY full_name")
    if not clients:
        print("No clients found.")
        return None
    
    print("Available Clients:")
    for client in clients:
        print(f"  ID: {client[0]} - {client[2]} ({client[1]})")
    
    try:
        client_id = int(input("\nEnter Client ID (0 to cancel): "))
        if client_id == 0:
            return None
            
        client_check = [c for c in clients if c[0] == client_id]
        if not client_check:
            print("\nError: Not a valid client ID.")
            return None
        
        return (client_id, client_check[0][2]) # (id, full_name)
    except ValueError:
        print("\nError: Invalid ID. Please enter a number.")
        return None
# view consumption post selection of client
def view_search_consumption():
    clear_screen()
    print("--- View Client's Consumption ---")
    
    client_info = _select_client_helper()
    if not client_info:
        wait_for_enter()
        return
        
    client_id, client_name = client_info
    
    search_term = input(f"Search by month for {client_name} (e.g., 2025-09, or leave blank): ")
    
    query = "SELECT month, usage_kwh FROM consumption WHERE user_id = ?"
    params = [client_id]
    
    if search_term:
        query += " AND month LIKE ?"
        params.append(f"%{search_term}%")
        
    query += " ORDER BY month DESC"
    
    data = db_fetch(query, tuple(params))
    
    clear_screen()
    print(f"--- Usage for {client_name} (Search: '{search_term}') ---")
    if not data:
        print("No consumption data found.")
    else:
        print(f"\n{'Month':<10} | {'Usage (kWh)':<12}")
        print("-" * 25)
        for row in data:
            print(f"{row[0]:<10} | {row[1]:<12.2f}")
            
    wait_for_enter()
# edit consumption of client post selection
def edit_consumption(admin_name):
    clear_screen()
    print("--- Add/Edit Client's Consumption ---")
    
    client_info = _select_client_helper()
    if not client_info:
        wait_for_enter()
        return
        
    client_id, client_name = client_info
    
    print(f"\nEditing usage for {client_name}:")
    
    try:
        year = input("Enter Year (YYYY): ")
        month = input("Enter Month (MM): ")
        usage_str = input("Enter Usage (kWh): ")
        
        if not (year.isdigit() and len(year) == 4) or not (month.isdigit() and 1 <= int(month) <= 12):
            print("\nError: Invalid date format. Use YYYY and MM.")
            wait_for_enter()
            return
        usage = float(usage_str)
            
        db_month = f"{year}-{month.zfill(2)}"
        
        existing = db_fetch("SELECT id FROM consumption WHERE user_id = ? AND month = ?", (client_id, db_month))
        
        if existing:
            db_execute("UPDATE consumption SET usage_kwh = ? WHERE user_id = ? AND month = ?", (usage, client_id, db_month))
            log_action(admin_name, f"Updated usage for '{client_name}' ({db_month}) to {usage} kWh.")
            print(f"\nSuccess: Usage updated for {client_name}.")
        else:
            db_execute("INSERT INTO consumption (user_id, month, usage_kwh) VALUES (?, ?, ?)", (client_id, db_month, usage))
            log_action(admin_name, f"Added new usage for '{client_name}' ({db_month}): {usage} kWh.")
            print(f"\nSuccess: Usage added for {client_name}.")
            
    except ValueError:
        print("\nError: Invalid usage. Please enter a number.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        
    wait_for_enter()
# print bill post selection of client
def admin_view_bill(admin_name):
    clear_screen()
    print("--- Generate Client Bill ---")
    
    client_info = _select_client_helper()
    if not client_info:
        wait_for_enter()
        return
        
    client_id, client_name = client_info
    
    # Reuse the client's bill-viewing function
    view_my_bill(client_id, client_name)
# view overall analytics
def view_analytics():
    clear_screen()
    print("--- Portal Analytics ---")
    
    # 1. Total by user (like pie chart)
    data_by_user = db_fetch("""
        SELECT u.full_name, SUM(c.usage_kwh) as total_usage
        FROM consumption c JOIN users u ON c.user_id = u.id
        WHERE u.role = 'client'
        GROUP BY u.full_name ORDER BY total_usage DESC
    """)
    print("\nTotal Usage by Client:")
    if not data_by_user:
        print("No client consumption data.")
    else:
        print(f"{'Client Name':<25} | {'Total Usage (kWh)':<15}")
        print("-" * 43)
        total_sum = 0.0
        for row in data_by_user:
            print(f"{row[0]:<25} | {row[1]:<15.2f}")
            total_sum += row[1]
        print("-" * 43)
        print(f"{'TOTAL':<25} | {total_sum:<15.2f}")

    # 2. Total by month (like line graph)
    data_by_month = db_fetch("SELECT month, SUM(usage_kwh) as total_usage FROM consumption GROUP BY month ORDER BY month")
    print("\nTotal Usage by Month:")
    if not data_by_month:
        print("No monthly consumption data.")
    else:
        print(f"{'Month':<10} | {'Total Usage (kWh)':<15}")
        print("-" * 28)
        for row in data_by_month:
            print(f"{row[0]:<10} | {row[1]:<15.2f}")
            
    wait_for_enter()
#action log
def view_log():
    clear_screen()
    print("--- Action Log (Most Recent 100) ---")
    data = db_fetch("SELECT timestamp, actor, action FROM action_log ORDER BY id DESC LIMIT 100")
    if not data:
        print("Log is empty.")
    else:
        print(f"\n{'Timestamp':<20} | {'User':<15} | {'Action':<50}")
        print("-" * 88)
        for row in data:
            print(f"{row[0]:<20} | {row[1]:<15} | {row[2]:<50}")
            
    wait_for_enter()
# admin menu loop, keeps going on till 9 is pressed aka logout
def admin_menu(admin_session):
    admin_id, admin_name, admin_role = admin_session
    
    while True:
        clear_screen()
        print(f"--- Admin Menu (Logged in as: {admin_name}) ---")
        print(" 1. Add User (Admin/Client)")
        print(" 2. Remove User")
        print(" 3. List & Search Users")
        print(" 4. View & Search Client Consumption")
        print(" 5. Add/Edit Client's Consumption")
        print(" 6. Generate Client Bill")
        print(" 7. View Portal Analytics")
        print(" 8. View Action Log")
        print(" 9. Logout")
        choice = input("Enter choice: ")

        if choice == '1':
            add_user(admin_name)
        elif choice == '2':
            remove_user(admin_id, admin_name)
        elif choice == '3':
            list_search_users()
        elif choice == '4':
            view_search_consumption()
        elif choice == '5':
            edit_consumption(admin_name)
        elif choice == '6':
            admin_view_bill(admin_name)
        elif choice == '7':
            view_analytics()
        elif choice == '8':
            view_log()
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")
            wait_for_enter()

#Login page, loop till 2 is pressed

def login():
    """Handles the login process. Returns (id, name, role) or None."""
    clear_screen()
    print("--- ELECTRICITY DISTRIBUTION PORTAL ---")
    print("--- Portal Login ---")
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    
    user = db_fetch("SELECT id, password, role, full_name FROM users WHERE username = ?", (username,))
    
    if user and user[0][1] == password:
        user_data = user[0]
        print(f"\nSuccess! Welcome, {user_data[3]}.")
        log_action(username, "Logged in successfully.")
        wait_for_enter()
        return (user_data[0], user_data[3], user_data[2])
    else:
        print("\nError: Invalid username or password.")
        log_action(username, "Failed login attempt.")
        wait_for_enter()
        return None
# calls all the functions 
def main():
    """Main program loop."""
    setup_database()
    
    while True:
        clear_screen()
        print("--- ELECTRICITY DISTRIBUTION PORTAL ---")
        print("--- Main Menu ---")
        print("1. Login")
        print("2. Exit")
        choice = input("Enter choice: ")

        if choice == '1':
            user_session = login() 
            
            if user_session:
                if user_session[2] == 'admin':
                    admin_menu(user_session)
                else: 
                    client_menu(user_session)
                
                log_action(user_session[1], "Logged out.")
                print("You have been logged out.")
                wait_for_enter()

        elif choice == '2':
            print("Exiting program. Goodbye.")
            sys.exit()
        else:
            print("Invalid choice. Please enter 1 or 2.")
            wait_for_enter()

if __name__ == "__main__":
    main()