import customtkinter as ctk
from tkinter import messagebox
import bcrypt
import sqlite3
from database import db_query, db_query_to_df, log_action

class LoginView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.configure(fg_color="transparent")
        frame = ctk.CTkFrame(self, width=300, height=350) 
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        label = ctk.CTkLabel(frame, text="Portal Login", font=controller.font_bold_large)
        label.pack(pady=20, padx=30)
        
        self.username_entry = ctk.CTkEntry(frame, placeholder_text="Username", width=200, font=controller.font_normal)
        self.username_entry.pack(pady=10, padx=30)
        
        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=200, font=controller.font_normal)
        self.password_entry.pack(pady=10, padx=30)
        
        self.show_pass_check = ctk.CTkCheckBox(frame, text="Show Password",
                                               font=controller.font_small,
                                               command=self.toggle_password_visibility)
        self.show_pass_check.pack(pady=5, padx=30, anchor="w")
        
        self.password_entry.bind("<Return>", self.handle_login)
        
        login_button = ctk.CTkButton(frame, text="🔑 Login", command=self.handle_login, width=200, font=controller.font_normal)
        login_button.pack(pady=20, padx=30)
        
        register_button = ctk.CTkButton(frame, text="Register as New User",
                                        command=lambda: controller.show_frame("RegisterView"),
                                        width=200, font=controller.font_normal,
                                        fg_color="transparent", border_width=1,
                                        text_color=("gray10", "gray90"))
        register_button.pack(pady=(0, 20), padx=30)
        
        def change_mode(value):
            ctk.set_appearance_mode(value)
            controller.update_chart_styles() 
        
        mode_switch = ctk.CTkSegmentedButton(self, values=["Light", "Dark", "System"],
                                             command=change_mode,
                                             font=controller.font_small)
        mode_switch.set(ctk.get_appearance_mode())
        mode_switch.pack(side="bottom", pady=20, padx=10)
        mode_label = ctk.CTkLabel(self, text="Appearance Mode", font=controller.font_small)
        mode_label.pack(side="bottom", pady=0, padx=10)

    def toggle_password_visibility(self):
        if self.show_pass_check.get() == 1:
            self.password_entry.configure(show="")
        else:
            self.password_entry.configure(show="*")

    def handle_login(self, event=None):
        username = self.username_entry.get()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showerror("Error", "Please enter username and password")
            return
        
        user_df = db_query_to_df("SELECT id, password, role, full_name FROM users WHERE username = ?", params=(username,))

        if not user_df.empty:
            user = user_df.iloc[0]
            stored_hash = user['password']
            
            if isinstance(stored_hash, str):
                stored_hash_bytes = stored_hash.encode('utf-8')
            elif isinstance(stored_hash, bytes):
                stored_hash_bytes = stored_hash
            else:
                log_action(username, "Failed login (invalid hash format in DB).")
                messagebox.showerror("Login Failed", "Invalid password format in database. Please contact admin.")
                return

            entered_pass_bytes = password.encode('utf-8')
            
            is_correct = False
            try:
                # Check for new hashed password
                if bcrypt.checkpw(entered_pass_bytes, stored_hash_bytes):
                    is_correct = True
            except ValueError:
                # This block catches errors if stored_hash is not a valid hash
                # (e.g., it's a plain-text password from an old DB)
                if password == stored_hash:
                    is_correct = True
                    log_action(username, "Logged in with a legacy plain-text password.")
            except Exception as e:
                # Other bcrypt errors
                print(f"Bcrypt error: {e}")
                is_correct = False

            if is_correct:
                log_action(username, "Logged in successfully.")
                self.controller.current_user_id = int(user['id'])
                self.controller.current_user_role = user['role']
                self.controller.current_user_name = user['full_name']
                self.password_entry.delete(0, 'end')
                self.username_entry.delete(0, 'end')
                self.show_pass_check.deselect()
                self.toggle_password_visibility()
                if user['role'] == 'admin':
                    self.controller.show_frame("AdminView")
                else:
                    self.controller.show_frame("ClientView")
                return

        log_action(username, "Failed login attempt (invalid username/password).")
        messagebox.showerror("Login Failed", "Invalid username or password")

class RegisterView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.configure(fg_color="transparent")
        frame = ctk.CTkFrame(self, width=300, height=450)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        label = ctk.CTkLabel(frame, text="Register New Client", font=controller.font_bold_large)
        label.pack(pady=20, padx=30)

        self.full_name_entry = ctk.CTkEntry(frame, placeholder_text="Full Name", width=200, font=controller.font_normal)
        self.full_name_entry.pack(pady=10, padx=30)

        self.username_entry = ctk.CTkEntry(frame, placeholder_text="Username", width=200, font=controller.font_normal)
        self.username_entry.pack(pady=10, padx=30)

        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=200, font=controller.font_normal)
        self.password_entry.pack(pady=10, padx=30)
        
        self.confirm_password_entry = ctk.CTkEntry(frame, placeholder_text="Confirm Password", show="*", width=200, font=controller.font_normal)
        self.confirm_password_entry.pack(pady=10, padx=30)

        register_button = ctk.CTkButton(frame, text="Register", command=self.handle_register, width=200, font=controller.font_normal)
        register_button.pack(pady=20, padx=30)
        
        login_button = ctk.CTkButton(frame, text="Back to Login",
                                     command=lambda: controller.show_frame("LoginView"),
                                     width=200, font=controller.font_normal,
                                     fg_color="transparent", border_width=1,
                                     text_color=("gray10", "gray90"))
        login_button.pack(pady=(0, 20), padx=30)

    def handle_register(self):
        full_name = self.full_name_entry.get()
        username = self.username_entry.get()
        password = self.password_entry.get()
        confirm_password = self.confirm_password_entry.get()

        if not full_name or not username or not password or not confirm_password:
            messagebox.showerror("Error", "All fields are required.")
            return

        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match.")
            return

        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db_query(
                "INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                (username, hashed_password, 'client', full_name)
            )
            log_action(username, "Registered new client account.")
            messagebox.showinfo("Success", f"User '{username}' registered successfully!\nYou can now log in.")
            
            self.full_name_entry.delete(0, 'end')
            self.username_entry.delete(0, 'end')
            self.password_entry.delete(0, 'end')
            self.confirm_password_entry.delete(0, 'end')
            self.controller.show_frame("LoginView")

        except sqlite3.IntegrityError:
            log_action(username, "Registration failed (username taken).")
            messagebox.showerror("Error", "That username is already taken. Please choose another.")
        except Exception as e:
            log_action(username, f"Registration failed (unknown error: {e}).")
            messagebox.showerror("Error", f"An error occurred: {e}")