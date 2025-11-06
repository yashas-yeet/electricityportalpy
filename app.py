import sqlite3
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib
from datetime import datetime
import os 
import random
import bcrypt
import openpyxl
import csv

# --- Local App Imports ---
import database
from billing import calculate_mahadiscom_bill, FIXED_CHARGE_SINGLE_PHASE, WHEELING_CHARGE_PER_KWH, ELECTRICITY_DUTY_RATE, slabs
from views.login_view import LoginView, RegisterView
from views.admin_view import AdminView
from views.client_view import ClientView
from views.dialogs import BillViewDialog, GrievanceViewDialog

# Tell matplotlib to use the Tkinter backend
matplotlib.use("TkAgg")

class ElectricityPortalApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Electricity Portal")
        self.geometry("1100x800")
        
        # --- 1. Define Fonts ---
        self.font_normal = ctk.CTkFont(family="Bahnschrift", size=14)
        self.font_bold = ctk.CTkFont(family="Bahnschrift", size=18, weight="bold")
        self.font_bold_large = ctk.CTkFont(family="Bahnschrift", size=24, weight="bold")
        self.font_title = ctk.CTkFont(family="Bahnschrift", size=28, weight="bold")
        self.font_normal_bold = ctk.CTkFont(family="Bahnschrift", size=14, weight="bold")
        self.font_small = ctk.CTkFont(family="Bahnschrift", size=12)
        
        # --- 2. Configure Styles ---
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Bahnschrift", 14, "bold"))
        style.configure("Treeview", font=("Bahnschrift", 13), rowheight=28)
        
        self.chart_light_style = {
            'figure.facecolor': '#ebebeb', 'axes.facecolor': '#ffffff',
            'text.color': '#1c1c1c', 'axes.labelcolor': '#1c1c1c',
            'xtick.color': '#1c1c1c', 'ytick.color': '#1c1c1c', 'axes.edgecolor': '#1c1c1c'
        }
        self.chart_dark_style = {
            'figure.facecolor': '#2b2b2b', 'axes.facecolor': '#3c3c3c',
            'text.color': '#dce4ee', 'axes.labelcolor': '#dce4ee',
            'xtick.color': '#dce4ee', 'ytick.color': '#dce4ee', 'axes.edgecolor': '#dce4ee'
        }

        # --- 3. Session Management ---
        self.current_user_id = None
        self.current_user_role = None
        self.current_user_name = None

        # --- 4. Main Title ---
        title_label = ctk.CTkLabel(self, text="ELECTRICITY DISTRIBUTION PORTAL", 
                                   font=self.font_title)
        title_label.pack(side="top", pady=(20, 10))

        # --- 5. Frame Container ---
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        # Loop through all view classes and create them
        for F in (LoginView, AdminView, ClientView, RegisterView):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # --- 6. Start at Login Screen ---
        self.show_frame("LoginView")
        self.update_chart_styles()

    def show_frame(self, page_name):
        """Brings the requested frame to the front."""
        frame = self.frames[page_name]
        # Refresh data only if the frame has a refresh method
        if hasattr(frame, 'refresh_data'):
            frame.refresh_data()
        frame.tkraise()
        
    def logout(self):
        """Logs out the user and returns to the LoginView."""
        actor = self.current_user_name if self.current_user_name else "Unknown"
        database.log_action(actor, "Logged out.")
        self.current_user_id = None
        self.current_user_role = None
        self.current_user_name = None
        self.show_frame("LoginView")
        
    def update_chart_styles(self):
        """Updates Matplotlib's theme to match the app's Light/Dark mode."""
        mode = ctk.get_appearance_mode()
        style_dict = self.chart_light_style if mode == "Light" else self.chart_dark_style
        for key, value in style_dict.items():
            plt.rcParams[key] = value
        # Refresh charts in all frames that have them
        for frame in self.frames.values():
            if hasattr(frame, 'update_charts'):
                frame.update_charts()
    
    def generate_bill_text(self, kwh_units, month, user_name):
        """Shared function to create the itemized bill text."""
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
            sub_total = (bill_data['A_Energy_Charge'] + bill_data['B_Fixed_Charge'] + 
                         bill_data['C_Wheeling_Charge'] + bill_data['D_FAC'])
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

    def show_bill_popup(self, bill_text, title="View Bill"):
        """Shared function to open the bill pop-up dialog."""
        if hasattr(self, 'bill_dialog') and self.bill_dialog.winfo_exists():
            self.bill_dialog.focus()
            return
            
        self.bill_dialog = BillViewDialog(parent=self, title=title, bill_text=bill_text)
        self.bill_dialog.grab_set()

    def show_grievance_popup(self, ticket_id, subject):
        """Shared function to open the grievance chat pop-up dialog."""
        if hasattr(self, 'grievance_dialog') and self.grievance_dialog.winfo_exists():
            self.grievance_dialog.focus()
            return
        
        self.grievance_dialog = GrievanceViewDialog(parent=self, 
                                                    controller=self,
                                                    ticket_id=ticket_id, 
                                                    subject=subject)
        self.grievance_dialog.grab_set()


if __name__ == "__main__":
    ctk.set_default_color_theme("blue")
    
    # Run setup/migration first
    database.setup_database()
    
    # Launch the app
    app = ElectricityPortalApp()
    app.mainloop()