import customtkinter as ctk
from tkinter import messagebox
import bcrypt
from database import db_query, db_query_to_df, log_action
from datetime import datetime

class ChangePasswordDialog(ctk.CTkToplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.title("Change Password")
        self.geometry("350x300")
        
        self.font_normal = self.controller.font_normal
        self.font_bold = self.controller.font_bold_large

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_frame, text="Change Your Password", font=self.font_bold).pack(pady=(0, 15))
        
        ctk.CTkLabel(main_frame, text="Current Password:", font=self.font_normal).pack(anchor="w", padx=10)
        self.current_pass_entry = ctk.CTkEntry(main_frame, show="*", width=250)
        self.current_pass_entry.pack(pady=(0, 10), padx=10)
        
        ctk.CTkLabel(main_frame, text="New Password:", font=self.font_normal).pack(anchor="w", padx=10)
        self.new_pass_entry = ctk.CTkEntry(main_frame, show="*", width=250)
        self.new_pass_entry.pack(pady=(0, 10), padx=10)

        ctk.CTkLabel(main_frame, text="Confirm New Password:", font=self.font_normal).pack(anchor="w", padx=10)
        self.confirm_pass_entry = ctk.CTkEntry(main_frame, show="*", width=250)
        self.confirm_pass_entry.pack(pady=(0, 20), padx=10)
        
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack()

        save_button = ctk.CTkButton(button_frame, text="Save Password", command=self.save_password)
        save_button.pack(side="left", padx=10)
        
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy, fg_color="gray")
        cancel_button.pack(side="left", padx=10)
        
        self.after(100, self.lift) 
        self.grab_set()
        self.current_pass_entry.focus()

    def save_password(self):
        current_pass = self.current_pass_entry.get()
        new_pass = self.new_pass_entry.get()
        confirm_pass = self.confirm_pass_entry.get()
        
        if not current_pass or not new_pass or not confirm_pass:
            messagebox.showerror("Error", "All fields are required.", parent=self)
            return
        if new_pass != confirm_pass:
            messagebox.showerror("Error", "New passwords do not match.", parent=self)
            return
        if current_pass == new_pass:
            messagebox.showerror("Error", "New password must be different from the current password.", parent=self)
            return

        user_id = self.controller.current_user_id
        user_df = db_query_to_df("SELECT password FROM users WHERE id = ?", params=(user_id,))
        
        if user_df.empty:
            messagebox.showerror("Error", "Could not find user record.", parent=self)
            return
            
        stored_hash = user_df.iloc[0]['password'].encode('utf-8')
        
        if not bcrypt.checkpw(current_pass.encode('utf-8'), stored_hash):
            messagebox.showerror("Error", "Your 'Current Password' is incorrect.", parent=self)
            log_action(self.controller.current_user_name, "Failed password change (wrong current pass).")
            return
            
        try:
            new_hashed_pass = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db_query("UPDATE users SET password = ? WHERE id = ?", (new_hashed_pass, user_id))
            
            log_action(self.controller.current_user_name, "Changed their password successfully.")
            messagebox.showinfo("Success", "Password changed successfully.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}", parent=self)

class ResetPasswordDialog(ctk.CTkToplevel):
    def __init__(self, parent, controller, user_id, username):
        super().__init__(parent)
        self.controller = controller
        self.user_id = user_id
        
        self.title("Reset Password")
        self.geometry("350x250")
        
        self.font_normal = self.controller.font_normal
        self.font_bold = self.controller.font_bold_large

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_frame, text="Reset Password", font=self.font_bold).pack(pady=(0, 10))
        ctk.CTkLabel(main_frame, text=f"User: {username}", font=self.font_normal).pack(pady=(0, 15))
        
        ctk.CTkLabel(main_frame, text="New Password:", font=self.font_normal).pack(anchor="w", padx=10)
        self.new_pass_entry = ctk.CTkEntry(main_frame, show="*", width=250)
        self.new_pass_entry.pack(pady=(0, 10), padx=10)

        ctk.CTkLabel(main_frame, text="Confirm New Password:", font=self.font_normal).pack(anchor="w", padx=10)
        self.confirm_pass_entry = ctk.CTkEntry(main_frame, show="*", width=250)
        self.confirm_pass_entry.pack(pady=(0, 20), padx=10)
        
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack()

        save_button = ctk.CTkButton(button_frame, text="Set Password", command=self.save_password)
        save_button.pack(side="left", padx=10)
        
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy, fg_color="gray")
        cancel_button.pack(side="left", padx=10)
        
        self.after(100, self.lift) 
        self.grab_set()
        self.new_pass_entry.focus()

    def save_password(self):
        new_pass = self.new_pass_entry.get()
        confirm_pass = self.confirm_pass_entry.get()
        
        if not new_pass or not confirm_pass:
            messagebox.showerror("Error", "All fields are required.", parent=self)
            return
        if new_pass != confirm_pass:
            messagebox.showerror("Error", "New passwords do not match.", parent=self)
            return
            
        try:
            new_hashed_pass = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db_query("UPDATE users SET password = ? WHERE id = ?", (new_hashed_pass, self.user_id))
            
            log_action(self.controller.current_user_name, f"Reset password for user ID {self.user_id}.")
            messagebox.showinfo("Success", "Password has been reset successfully.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}", parent=self)

class UpdateUserDialog(ctk.CTkToplevel):
    def __init__(self, parent, controller, user_id, username, full_name):
        super().__init__(parent)
        self.controller = controller
        self.user_id = user_id
        
        self.title("Update User Info")
        self.geometry("350x250")
        
        self.font_normal = self.controller.font_normal
        self.font_bold = self.controller.font_bold_large

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_frame, text="Update User Info", font=self.font_bold).pack(pady=(0, 15))
        
        ctk.CTkLabel(main_frame, text="Full Name:", font=self.font_normal).pack(anchor="w", padx=10)
        self.full_name_entry = ctk.CTkEntry(main_frame, width=250)
        self.full_name_entry.insert(0, full_name)
        self.full_name_entry.pack(pady=(0, 10), padx=10)

        ctk.CTkLabel(main_frame, text="Username:", font=self.font_normal).pack(anchor="w", padx=10)
        self.username_entry = ctk.CTkEntry(main_frame, width=250)
        self.username_entry.insert(0, username)
        self.username_entry.pack(pady=(0, 20), padx=10)
        
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack()

        save_button = ctk.CTkButton(button_frame, text="Save Changes", command=self.save_changes)
        save_button.pack(side="left", padx=10)
        
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy, fg_color="gray")
        cancel_button.pack(side="left", padx=10)
        
        self.after(100, self.lift)
        self.grab_set()
        self.full_name_entry.focus()

    def save_changes(self):
        new_full_name = self.full_name_entry.get()
        new_username = self.username_entry.get()
        
        if not new_full_name or not new_username:
            messagebox.showerror("Error", "All fields are required.", parent=self)
            return
            
        try:
            db_query("UPDATE users SET full_name = ?, username = ? WHERE id = ?", (new_full_name, new_username, self.user_id))
            log_action(self.controller.current_user_name, f"Updated info for user ID {self.user_id}.")
            messagebox.showinfo("Success", "User information updated successfully.", parent=self)
            self.controller.frames["AdminView"].refresh_user_list()
            self.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "That username is already taken.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}", parent=self)

class BillViewDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, bill_text):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x700")
        
        font_mono = ctk.CTkFont(family="Courier", size=14)
        
        textbox = ctk.CTkTextbox(self, font=font_mono, wrap="word")
        textbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        textbox.insert("1.0", bill_text)
        textbox.configure(state="disabled")
        
        close_button = ctk.CTkButton(self, text="Close", command=self.destroy)
        close_button.pack(pady=10)
        
        self.after(100, self.lift)
        self.grab_set()

class GrievanceViewDialog(ctk.CTkToplevel):
    def __init__(self, parent, controller, ticket_id, subject):
        super().__init__(parent)
        self.controller = controller
        self.ticket_id = ticket_id
        
        self.title(f"Ticket: {subject}")
        self.geometry("500x600")
        
        self.font_normal = self.controller.font_normal
        self.font_bold = self.controller.font_normal_bold
        self.font_small = self.controller.font_small

        self.chat_frame_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_frame_wrapper.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_frame_wrapper.grid_rowconfigure(0, weight=1)
        self.chat_frame_wrapper.grid_columnconfigure(0, weight=1)

        self.chat_frame = ctk.CTkScrollableFrame(self.chat_frame_wrapper)
        self.chat_frame.grid(row=0, column=0, sticky="nsew")

        self.reply_entry = ctk.CTkTextbox(self, height=100, font=self.font_normal)
        self.reply_entry.pack(fill="x", padx=10, pady=(0, 5))
        
        self.send_button = ctk.CTkButton(self, text="✉️ Send Reply", font=self.font_normal, command=self.send_reply)
        self.send_button.pack(pady=(0, 10))
        
        # --- FIX: Bind to the inner canvas, not bind_all ---
        self.chat_frame._parent_canvas.bind_all("<MouseWheel>", self._on_mousewheel, add=True)
        self.bind("<Destroy>", self._on_destroy, add=True)
        # --- END FIX ---

        self.load_chat_history()
        self.check_ticket_status()
        
        self.after(100, self.lift)
        self.grab_set()
    
    # --- NEW FUNCTION TO HANDLE SCROLLING SAFELY ---
    def _on_mousewheel(self, event):
        try:
            # Check if the canvas still exists
            if self.chat_frame._parent_canvas.winfo_exists():
                self.chat_frame._parent_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception:
            # Widget might be destroyed, do nothing
            pass

    # --- NEW FUNCTION TO UNBIND SCROLLING ON CLOSE ---
    def _on_destroy(self, event):
        # Unbind the global mouse wheel event when this window is destroyed
        # to prevent the TclError
        self.chat_frame._parent_canvas.unbind_all("<MouseWheel>")
        
    def load_chat_history(self):
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
            
        messages_df = db_query_to_df("SELECT sender_name, timestamp, message FROM grievance_messages WHERE ticket_id = ? ORDER BY timestamp ASC",
                                     params=(self.ticket_id,))
        
        if messages_df.empty:
            ctk.CTkLabel(self.chat_frame, text="No messages found for this ticket.", font=self.font_normal).pack(anchor="w")
        else:
            for index, row in messages_df.iterrows():
                header = f"--- {row['sender_name']} ({row['timestamp']}) ---\n"
                message = f"{row['message']}\n\n"
                
                msg_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
                msg_label = ctk.CTkLabel(msg_frame, text=header+message, font=self.font_normal, justify="left", wraplength=400)
                
                if row['sender_name'] == self.controller.current_user_name:
                    msg_label.pack(anchor="e", padx=5, pady=0)
                    msg_frame.pack(fill="x", anchor="e", padx=5, pady=2)
                else:
                    msg_label.pack(anchor="w", padx=5, pady=0)
                    msg_frame.pack(fill="x", anchor="w", padx=5, pady=2)

        self.after(100, self.chat_frame._parent_canvas.yview_moveto, 1.0)

    def send_reply(self):
        reply_text = self.reply_entry.get("1.0", "end-1c").strip()
        if not reply_text:
            messagebox.showerror("Error", "Cannot send an empty message.", parent=self)
            return
            
        try:
            sender_id = self.controller.current_user_id
            sender_name = self.controller.current_user_name
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            db_query("INSERT INTO grievance_messages (ticket_id, sender_id, sender_name, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                     (self.ticket_id, sender_id, sender_name, reply_text, timestamp))
            
            new_status = 'Answered' if self.controller.current_user_role == 'admin' else 'Pending' 
            
            db_query("UPDATE grievance_tickets SET status = ?, updated_at = ? WHERE id = ?", (new_status, timestamp, self.ticket_id))
            
            log_action(sender_name, f"Replied to grievance ticket ID {self.ticket_id}.")
            self.reply_entry.delete("1.0", "end")
            self.load_chat_history()
            
            if self.controller.current_user_role == 'admin':
                self.controller.frames["AdminView"].refresh_grievance_list()
            else:
                self.controller.frames["ClientView"].refresh_grievance_list()
                
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}", parent=self)

    def check_ticket_status(self):
        status_df = db_query_to_df("SELECT status FROM grievance_tickets WHERE id = ?", params=(self.ticket_id,))
        if not status_df.empty and status_df.iloc[0]['status'] == 'Resolved':
            self.reply_entry.insert("1.0", "This ticket is marked as 'Resolved' and can no longer be replied to.")
            self.reply_entry.configure(state="disabled")
            self.send_button.configure(state="disabled")