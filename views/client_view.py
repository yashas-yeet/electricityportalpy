import customtkinter as ctk
from tkinter import ttk, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import random

from database import db_query, db_query_to_df, db_query_lastrowid, log_action
from views.dialogs import ChangePasswordDialog

class ClientView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.line_fig = None
        self.line_canvas = None
        
        font_normal = controller.font_normal
        font_bold = controller.font_bold
        font_normal_bold = controller.font_normal_bold
        
        change_pass_button = ctk.CTkButton(self, text="Change Password", command=self.open_change_password_dialog, width=140, font=font_normal)
        change_pass_button.place(relx=0.86, rely=0.02, anchor="ne")
        
        logout_button = ctk.CTkButton(self, text="Logout ➡️", command=controller.logout, width=100, font=font_normal)
        logout_button.place(relx=0.98, rely=0.02, anchor="ne")
        
        self.welcome_label = ctk.CTkLabel(self, text="Client Dashboard", font=font_bold)
        self.welcome_label.place(relx=0.02, rely=0.02, anchor="nw")
        
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.place(relx=0.5, rely=0.53, relwidth=0.98, relheight=0.88, anchor="center")
        self.tab_view._segmented_button.configure(font=font_normal)
        
        self.tab_view.add("My Bills / History")
        self.tab_view.add("Billing Details")
        self.tab_view.add("Usage Graph")
        self.tab_view.add("✉️ Contact Admin")
        
        self.create_history_tab(self.tab_view.tab("My Bills / History"))
        self.create_billing_tab(self.tab_view.tab("Billing Details"))
        self.create_graph_tab(self.tab_view.tab("Usage Graph"))
        self.create_contact_tab(self.tab_view.tab("✉️ Contact Admin"))

    def open_change_password_dialog(self):
        if hasattr(self, 'password_dialog') and self.password_dialog.winfo_exists():
            self.password_dialog.focus()
        else:
            self.password_dialog = ChangePasswordDialog(parent=self, controller=self.controller)
            self.password_dialog.grab_set()

    def create_history_tab(self, tab):
        font_normal_bold = self.controller.font_normal_bold
        
        self.client_stats_label = ctk.CTkLabel(tab, text="Total: 0 kWh | Avg: 0 kWh/month", font=font_normal_bold)
        self.client_stats_label.pack(pady=5)
        
        cons_frame = ctk.CTkFrame(tab)
        cons_frame.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        
        cons_columns = ("id", "month", "usage", "total_bill", "bill_status")
        self.cons_tree = ttk.Treeview(cons_frame, columns=cons_columns, show="headings") 
        self.cons_tree.heading("id", text="Bill ID")
        self.cons_tree.heading("month", text="Month")
        self.cons_tree.heading("usage", text="Usage (kWh)")
        self.cons_tree.heading("total_bill", text="Bill (₹)")
        self.cons_tree.heading("bill_status", text="Status")
        self.cons_tree.column("id", width=60, stretch=False)
        self.cons_tree.column("month", width=100)
        self.cons_tree.column("usage", width=100)
        self.cons_tree.column("total_bill", width=100)
        self.cons_tree.column("bill_status", width=200)
        
        self.cons_tree.pack(side="left", fill="both", expand=True)
        
        cons_scrollbar = ttk.Scrollbar(cons_frame, orient="vertical", command=self.cons_tree.yview)
        self.cons_tree.configure(yscroll=cons_scrollbar.set)
        cons_scrollbar.pack(side="right", fill="y")
        
        self.pay_bill_button = ctk.CTkButton(tab, text="💸 Pay Selected Bill", command=self.pay_selected_bill, font=self.controller.font_normal)
        self.pay_bill_button.pack(side="bottom", pady=10)

    def create_billing_tab(self, tab):
        font_normal_bold = self.controller.font_normal_bold
        font_normal = self.controller.font_normal

        bill_frame = ctk.CTkFrame(tab, fg_color="transparent")
        bill_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        client_bill_top = ctk.CTkFrame(bill_frame, fg_color="transparent")
        client_bill_top.pack(side="top", fill="x", pady=(0, 10))
        
        ctk.CTkLabel(client_bill_top, text="Select Billing Month:", font=font_normal_bold).pack(side="left", padx=5)
        
        self.client_month_menu = ctk.CTkOptionMenu(client_bill_top, values=["No Data"], font=font_normal,
                                                   command=self.generate_client_bill_preview)
        self.client_month_menu.pack(side="left", padx=5)
        
        self.client_view_bill_button = ctk.CTkButton(client_bill_top, text="👁️ View Full Bill",
                                                       font=font_normal, width=120,
                                                       command=self.show_client_bill_popup)
        self.client_view_bill_button.pack(side="left", padx=(20, 5))

        self.export_client_bill_button = ctk.CTkButton(client_bill_top, text="📄 Export to .txt",
                                                       font=font_normal, width=120,
                                                       command=self.export_client_bill_to_txt)
        self.export_client_bill_button.pack(side="left", padx=(5, 5))
        
        self.client_bill_textbox = ctk.CTkTextbox(bill_frame, font=self.controller.font_normal)
        self.client_bill_textbox.pack(fill="both", expand=True)
        self.client_bill_textbox.configure(state="disabled")

    def create_graph_tab(self, tab):
        font_normal_bold = self.controller.font_normal_bold
        self.graph_frame = ctk.CTkFrame(tab)
        self.graph_frame.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(self.graph_frame, text="Your Personal Usage (kWh)", font=font_normal_bold).pack(pady=10)
        
    def create_contact_tab(self, tab):
        font_normal = self.controller.font_normal
        font_normal_bold = self.controller.font_normal_bold

        self.contact_tabs = ctk.CTkTabview(tab)
        self.contact_tabs.pack(fill="both", expand=True, padx=5, pady=5)
        self.contact_tabs.add("Submit New Ticket")
        self.contact_tabs.add("View My Tickets")
        
        submit_tab = self.contact_tabs.tab("Submit New Ticket")
        
        ctk.CTkLabel(submit_tab, text="Subject:", font=font_normal_bold).pack(anchor="w", padx=10, pady=(10, 0))
        self.grievance_subject_entry = ctk.CTkEntry(submit_tab, placeholder_text="e.g., Incorrect bill for 2025-10", font=font_normal)
        self.grievance_subject_entry.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(submit_tab, text="Message:", font=font_normal_bold).pack(anchor="w", padx=10, pady=5)
        self.grievance_body_entry = ctk.CTkTextbox(submit_tab, font=font_normal, height=200)
        self.grievance_body_entry.pack(fill="both", expand=True, padx=10, pady=5)
        
        submit_button = ctk.CTkButton(submit_tab, text="✉️ Submit Ticket", font=font_normal_bold, 
                                      command=self.submit_grievance)
        submit_button.pack(pady=10)
        
        view_tab = self.contact_tabs.tab("View My Tickets")
        
        ticket_cols = ("token", "created_at", "subject", "status")
        self.ticket_tree = ttk.Treeview(view_tab, columns=ticket_cols, show="headings")
        self.ticket_tree.heading("token", text="Token ID")
        self.ticket_tree.heading("created_at", text="Date")
        self.ticket_tree.heading("subject", text="Subject")
        self.ticket_tree.heading("status", text="Status")
        
        self.ticket_tree.column("token", width=80)
        self.ticket_tree.column("created_at", width=150)
        self.ticket_tree.column("subject", width=300)
        self.ticket_tree.column("status", width=100)
        
        self.ticket_tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        ticket_scrollbar = ttk.Scrollbar(view_tab, orient="vertical", command=self.ticket_tree.yview)
        self.ticket_tree.configure(yscroll=ticket_scrollbar.set)
        ticket_scrollbar.pack(side="right", fill="y")
        
        view_details_button = ctk.CTkButton(view_tab, text="👁️ View Chat", font=font_normal,
                                            command=self.view_ticket_details)
        view_details_button.pack(pady=10)

    def submit_grievance(self):
        subject = self.grievance_subject_entry.get()
        body = self.grievance_body_entry.get("1.0", "end-1c").strip()
        
        if not subject or not body:
            messagebox.showerror("Error", "Please fill in both the Subject and Message fields.")
            return
            
        try:
            user_id = self.controller.current_user_id
            username = self.controller.current_user_name
            token = f"T-{random.randint(100000, 999999)}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            ticket_id = db_query_lastrowid("INSERT INTO grievance_tickets (token, user_id, username, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'Pending', ?, ?)",
                                          (token, user_id, username, subject, timestamp, timestamp))
            
            if ticket_id is None:
                messagebox.showerror("Error", "Failed to create grievance ticket.")
                return

            db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                     (ticket_id, user_id, username, body, timestamp))
                     
            log_action(username, f"Submitted new grievance (Token: {token}).")
            messagebox.showinfo("Success", f"Your grievance has been submitted successfully.\n\nYour Token ID is: {token}\n\nAn admin will review it shortly.")
            
            self.grievance_subject_entry.delete(0, 'end')
            self.grievance_body_entry.delete("1.0", "end")
            self.refresh_grievance_list()
            self.contact_tabs.set("View My Tickets")
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def refresh_grievance_list(self):
        if not hasattr(self, 'ticket_tree'):
            return 
            
        for item in self.ticket_tree.get_children():
            self.ticket_tree.delete(item)
            
        user_id = self.controller.current_user_id
        if not user_id:
            return
            
        tickets_df = db_query_to_df("SELECT token, created_at, subject, status, id FROM grievance_tickets WHERE user_id = ? ORDER BY updated_at DESC", 
                                  params=(user_id,))
        
        for index, row in tickets_df.iterrows():
            self.ticket_tree.insert("", "end", values=(row['token'], row['created_at'], row['subject'], row['status']), iid=row['id'])

    def view_ticket_details(self):
        selected_item_id = self.ticket_tree.focus()
        if not selected_item_id:
            messagebox.showerror("Error", "Please select a ticket to view.")
            return
            
        ticket_data = self.ticket_tree.item(selected_item_id)
        subject = ticket_data['values'][2]
        
        self.controller.show_grievance_popup(
            ticket_id=selected_item_id,
            subject=subject
        )

    def refresh_client_table(self):
        for item in self.cons_tree.get_children():
            self.cons_tree.delete(item)
        user_id = self.controller.current_user_id
        if not user_id: return
        
        data_df = db_query_to_df("SELECT id, month, usage_kwh, total_bill, bill_status, payment_timestamp FROM consumption WHERE user_id = ? ORDER BY month DESC", params=(user_id,))
        
        if data_df.empty:
            self.cons_tree.insert("", "end", values=("", "No consumption data found.", "", "", ""))
            self.client_stats_label.configure(text="Total: 0 kWh | Avg: 0 kWh/month")
        else:
            total_usage = data_df['usage_kwh'].sum()
            avg_usage = data_df['usage_kwh'].mean()
            self.client_stats_label.configure(text=f"Total: {total_usage:.2f} kWh | Avg: {avg_usage:.2f} kWh/month")
            
            for index, row in data_df.iterrows():
                if row['bill_status'] == 'Paid' and row['payment_timestamp']:
                    status = f"Paid on {row['payment_timestamp']}"
                else:
                    status = "Pending"
                    
                self.cons_tree.insert("", "end", values=(
                    row['id'], 
                    row['month'], 
                    f"{row['usage_kwh']:.2f}", 
                    f"{row['total_bill']:.2f}", 
                    status
                ))
    
    def pay_selected_bill(self):
        selected_item = self.cons_tree.focus()
        if not selected_item:
            messagebox.showerror("Error", "Please select a bill from the table to pay.")
            return
            
        bill_data = self.cons_tree.item(selected_item)['values']
        bill_id = bill_data[0]
        bill_month = bill_data[1]
        bill_amount = bill_data[3]
        bill_status = bill_data[4]
        
        if "Paid" in bill_status:
            messagebox.showinfo("Info", "This bill has already been paid.")
            return
            
        if messagebox.askyesno("Confirm Payment", f"Do you want to pay ₹{bill_amount} for the bill from {bill_month}?"):
            try:
                paid_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_query("UPDATE consumption SET bill_status = 'Paid', payment_timestamp = ? WHERE id = ?", (paid_timestamp, bill_id))
                
                log_action(self.controller.current_user_name, f"Paid bill for {bill_month} (ID: {bill_id}).")
                messagebox.showinfo("Success", "Payment successful! The bill status has been updated.")
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while updating payment status: {e}")

    def show_client_bill_popup(self):
        bill_text = self.client_bill_textbox.get("1.0", "end-1c")
        if not bill_text or "Please select" in bill_text or "No consumption data" in bill_text:
            messagebox.showerror("Error", "Please select a valid month to view the bill.")
            return
        
        month = self.client_month_menu.get()
        title = f"Your Bill - {month}"
        self.controller.show_bill_popup(bill_text, title=title)

    def export_client_bill_to_txt(self):
        try:
            client_name = self.controller.current_user_name
            month = self.client_month_menu.get()
            if month == "No Data":
                messagebox.showerror("Error", "Cannot export. No bill data available.")
                return
                
            text_to_save = self.client_bill_textbox.get("1.0", "end-1c")
            clean_client_name = client_name.replace(" ", "_")
            filename = f"BILL_{clean_client_name}_{month}.txt"
            
            save_path = filedialog.asksaveasfilename(initialfile=filename,
                                                      defaultextension=".txt",
                                                      filetypes=[("Text files", "*.txt")],
                                                      title="Save Bill As")
            if not save_path:
                return
                
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(text_to_save)
            log_action(client_name, f"Exported their own bill ({month}).")
            messagebox.showinfo("Success", f"Bill exported successfully to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred: {e}")

    def generate_client_bill_preview(self, selected_month):
        self.client_bill_textbox.configure(state="normal")
        self.client_bill_textbox.delete("1.0", "end")
        
        user_id = self.controller.current_user_id
        if not user_id:
            self.client_bill_textbox.insert("1.0", "Error: Not logged in.")
            self.client_bill_textbox.configure(state="disabled")
            return

        if selected_month == "No Data":
            self.client_bill_textbox.insert("1.0", "No consumption data found to generate a bill.")
            self.client_bill_textbox.configure(state="disabled")
            return
            
        data_df = db_query_to_df("SELECT usage_kwh FROM consumption WHERE user_id = ? AND month = ?", params=(user_id, selected_month))
        
        if data_df.empty:
            self.client_bill_textbox.insert("1.0", f"Error: No data found for month {selected_month}.")
        else:
            kwh_units = data_df['usage_kwh'].iloc[0]
            user_name = self.controller.current_user_name
            bill_text = self.controller.generate_bill_text(kwh_units, selected_month, user_name)
            self.client_bill_textbox.insert("1.0", bill_text)
            
        self.client_bill_textbox.configure(state="disabled")

    def refresh_billing_tab(self):
        user_id = self.controller.current_user_id
        if not user_id: return
        
        data_df = db_query_to_df("SELECT month FROM consumption WHERE user_id = ? ORDER BY month DESC", params=(user_id,))
        available_months = list(data_df['month'])
        
        if not available_months:
            self.client_month_menu.configure(values=["No Data"])
            self.client_month_menu.set("No Data")
            self.generate_client_bill_preview("No Data")
        else:
            self.client_month_menu.configure(values=available_months)
            self.client_month_menu.set(available_months[0])
            self.generate_client_bill_preview(available_months[0])
                
    def refresh_client_line_graph(self):
        if self.line_canvas:
            self.line_canvas.get_tk_widget().destroy()

        user_id = self.controller.current_user_id
        if not user_id: return

        query = "SELECT month, usage_kwh FROM consumption WHERE user_id = ? ORDER BY month"
        df = db_query_to_df(query, params=(user_id,))
        
        self.line_fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.line_fig.set_facecolor(plt.rcParams['figure.facecolor'])
        ax = self.line_fig.add_subplot(111)
        
        if df.empty:
            ax.text(0.5, 0.5, "No consumption data", horizontalalignment='center', verticalalignment='center', color=plt.rcParams['text.color'])
        else:
            ax.plot(df['month'], df['usage_kwh'], marker='o', color='#3b8ed0')
            ax.set_xlabel("Month", color=plt.rcParams['axes.labelcolor'])
            ax.set_ylabel("Usage (kWh)", color=plt.rcParams['axes.labelcolor'])
            ax.set_facecolor(plt.rcParams['axes.facecolor'])
            for spine in ax.spines.values():
                spine.set_edgecolor(plt.rcParams['axes.edgecolor'])
            self.line_fig.tight_layout() 
            
        self.line_canvas = FigureCanvasTkAgg(self.line_fig, master=self.graph_frame)
        self.line_canvas.draw()
        self.line_canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        
    def update_charts(self):
        if self.controller.current_user_id: 
            self.refresh_client_line_graph()

    def refresh_data(self):
        if not self.controller.current_user_id:
            return 
        self.welcome_label.configure(text=f"Welcome, {self.controller.current_user_name}")
        self.refresh_client_table()
        self.refresh_billing_tab()
        self.refresh_client_line_graph()
        self.refresh_grievance_list()


if __name__ == "__main__":
    ctk.set_default_color_theme("blue")
    
    setup_database()
    
    app = ElectricityPortalApp()
    app.mainloop()