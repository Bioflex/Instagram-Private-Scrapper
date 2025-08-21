import customtkinter as ctk
import instaloader
import time
import random
import re
import os
import shutil
import sys
import threading
from urllib.parse import urlparse
from instaloader.exceptions import (
    LoginException,
    TwoFactorAuthRequiredException,
    ConnectionException,
    QueryReturnedBadRequestException,
    InstaloaderException,
    ProfileNotExistsException
)
from PIL import Image

# --- Instaloader Configuration ---
loader = instaloader.Instaloader()
loader.download_comments = False
loader.save_metadata = False
loader.save_captions = False
loader.compress_json = False
loader.download_geotags = False
loader.download_videos_thumbnails = False
loader.download_video_info = False
loader.download_json = False
loader.dirname_pattern = "{profile}"

class InstaDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Configure window ---
        self.title("Instagram Scraper")
        self.geometry("600x650")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Create main frame for tabs ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(padx=20, pady=20, fill="both", expand=True)

        # --- Main Downloader Tab ---
        self.downloader_tab = self.tab_view.add("Scraper")
        self.downloader_tab.grid_columnconfigure(0, weight=1)
        self.downloader_tab.grid_rowconfigure(7, weight=1)

        # --- Widgets ---
        self.create_widgets()

        # --- Redirect print to GUI log ---
        self.original_stdout = sys.stdout
        sys.stdout = self
        
        # State variables
        self.password_visible = False
        self.is_logged_in = False
        self.login_username = ""
        self.loader = loader  # Use the global loader instance
        
        # Dynamic 2FA widgets
        self.twofa_frame = ctk.CTkFrame(self.downloader_tab)
        self.twofa_label = ctk.CTkLabel(self.twofa_frame, text="Enter 2FA Code:")
        self.twofa_entry = ctk.CTkEntry(self.twofa_frame, placeholder_text="Enter 2FA code", width=150)
        self.twofa_button = ctk.CTkButton(self.twofa_frame, text="Submit 2FA", command=self.submit_2fa_code)
        
        # Lock to prevent race conditions during login
        self.login_lock = threading.Lock()

    def create_widgets(self):
        # Frame for credentials
        credentials_frame = ctk.CTkFrame(self.downloader_tab)
        credentials_frame.pack(fill="x", padx=10, pady=10)

        # Username
        self.username_label = ctk.CTkLabel(credentials_frame, text="Your Username:")
        self.username_label.pack(pady=(10, 0), padx=10, anchor="w")
        self.username_entry = ctk.CTkEntry(credentials_frame, placeholder_text="Enter your Instagram username", width=250)
        self.username_entry.pack(pady=5, padx=10, anchor="w")

        # Password
        self.password_frame = ctk.CTkFrame(credentials_frame)
        self.password_frame.pack(pady=5, padx=10, fill="x", anchor="w")
        self.password_frame.configure(fg_color="transparent")
        
        self.password_label = ctk.CTkLabel(self.password_frame, text="Password:")
        self.password_label.pack(side="left", padx=(0, 5))
        
        self.password_entry = ctk.CTkEntry(self.password_frame, placeholder_text="Enter your password", show="*", width=250)
        self.password_entry.pack(side="left", padx=(0, 5), expand=True)
        
        self.toggle_password_btn = ctk.CTkButton(self.password_frame, text="👁️", width=30, command=self.toggle_password_visibility)
        self.toggle_password_btn.pack(side="left")

        # Login Button
        self.login_button = ctk.CTkButton(credentials_frame, text="Log In / Load Session", command=self.start_login_thread)
        self.login_button.pack(pady=10)

        # Target Profile
        self.target_label = ctk.CTkLabel(self.downloader_tab, text="Profile to Scrape:")
        self.target_label.pack(pady=(10, 0), padx=10, anchor="w")
        self.target_entry = ctk.CTkEntry(self.downloader_tab, placeholder_text="Enter username of profile to scrape", width=250)
        self.target_entry.pack(pady=5, padx=10, anchor="w")

        # Scrape Button
        self.scrape_button = ctk.CTkButton(self.downloader_tab, text="Start Scrape", command=self.start_scrape_thread, state="disabled")
        self.scrape_button.pack(pady=15)

        # Progress bar and label
        self.progress_label = ctk.CTkLabel(self.downloader_tab, text="Progress: 0%", font=("Arial", 12))
        self.progress_label.pack(pady=(5, 0), padx=10, anchor="w")
        self.progress_bar = ctk.CTkProgressBar(self.downloader_tab, orientation="horizontal")
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)

        # Status and Log
        self.status_label = ctk.CTkLabel(self.downloader_tab, text="Status: Ready", text_color="green", font=("Arial", 12, "bold"))
        self.status_label.pack(pady=(5, 0), padx=10, anchor="w")
        self.log_textbox = ctk.CTkTextbox(self.downloader_tab, height=150)
        self.log_textbox.pack(pady=10, padx=10, fill="both", expand=True)
        self.log_textbox.configure(state="disabled")

        # --- About Tab ---
        self.about_tab = self.tab_view.add("About")
        self.about_tab.grid_columnconfigure(0, weight=1)
        
        # Main Info Section
        about_text = ("This tool scrapes public Instagram profiles, downloading all their posts (images and videos). "
                      "It requires you to log in with your account to access more content and avoid rate limits. "
                      "\n\nFeatures:\n- Organizes files by type\n- Converts .webp to .jpg\n- Handles login and session management"
                      "\n\nWarning: Use this tool responsibly and respect Instagram's terms of service. "
                      "Downloading large quantities of posts in a short period may lead to a temporary account block.")
        self.about_label = ctk.CTkLabel(self.about_tab, text=about_text, wraplength=500, justify="left")
        self.about_label.pack(padx=20, pady=20)
        
        # "Created By" Section
        try:
            profile_image = ctk.CTkImage(light_image=Image.open("D:\Instagram Private Scraper\creator.png"),
                                         dark_image=Image.open("D:\Instagram Private Scraper\creator.png"),
                                         size=(148, 188))
            self.profile_image_label = ctk.CTkLabel(self.about_tab, text="", image=profile_image)
            self.profile_image_label.pack(pady=(20, 5))
        except FileNotFoundError:
            print("[!] Profile image file not found. Skipping image display.")

        # Placeholders for name and socials
        self.name_label = ctk.CTkLabel(self.about_tab, text="Created By: Atharva Patil", font=("Arial", 16, "bold"))
        self.name_label.pack(pady=5)
        
        self.socials_label = ctk.CTkLabel(self.about_tab, text="GitHub: [Your_GitHub] | Instagram: atharvasowwy", font=("Arial", 12))
        self.socials_label.pack(pady=5)
    
    def toggle_password_visibility(self):
        """Toggles the visibility of the password."""
        self.password_visible = not self.password_visible
        if self.password_visible:
            self.password_entry.configure(show="")
            self.toggle_password_btn.configure(text="🔒")
        else:
            self.password_entry.configure(show="*")
            self.toggle_password_btn.configure(text="👁️")

    def write(self, text):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text)
        self.log_textbox.configure(state="disabled")
        self.log_textbox.see("end")
        self.update()

    def flush(self):
        pass

    def start_login_thread(self):
        self.login_button.configure(state="disabled", text="Logging In...")
        self.status_label.configure(text="Status: Attempting to log in...", text_color="orange")
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("0.0", "end")
        self.log_textbox.configure(state="disabled")
        
        self.login_username = self.username_entry.get()
        password = self.password_entry.get()

        if not self.login_username or not password:
            self.status_label.configure(text="Status: Username and password cannot be empty!", text_color="red")
            self.login_button.configure(state="normal", text="Log In / Load Session")
            return
        
        # Start a new thread for the login process
        login_thread = threading.Thread(target=self.safe_login, args=(self.login_username, password))
        login_thread.start()

    def submit_2fa_code(self):
        code = self.twofa_entry.get()
        if code:
            self.twofa_button.configure(state="disabled", text="Submitting...")
            self.twofa_entry.configure(state="disabled")
            
            # Start a thread to handle the 2FA login to avoid blocking the GUI
            threading.Thread(target=self.perform_2fa_login, args=(code,)).start()

    def show_2fa_input(self):
        self.twofa_frame.pack(padx=10, pady=10, fill="x", before=self.login_button)
        self.twofa_label.pack(side="left", padx=(0, 5))
        self.twofa_entry.pack(side="left", padx=(0, 5), expand=True)
        self.twofa_button.pack(side="left")
        self.twofa_entry.focus()
        self.status_label.configure(text="Status: Two-Factor Authentication required.", text_color="red")

    def hide_2fa_input(self):
        self.twofa_frame.pack_forget()
        self.twofa_entry.delete(0, "end")
        self.twofa_button.configure(state="normal", text="Submit 2FA")
        self.twofa_entry.configure(state="normal")

    def perform_2fa_login(self, code):
        try:
            self.loader.two_factor_login(code)
            print("[+] 2FA login successful.")
            self.loader.save_session_to_file(f"session-{self.login_username}.json")
            self.is_logged_in = True
        except LoginException:
            print("[!] Invalid 2FA code. Please try again.")
            self.is_logged_in = False
        except Exception as e:
            print(f"[!] An unexpected error occurred during 2FA: {e}")
            self.is_logged_in = False
        finally:
            self.after(0, self.update_status_and_buttons_on_login)

    def safe_login(self, username, password):
        session_file = f"session-{username}.json"
        
        with self.login_lock:
            try:
                if os.path.exists(session_file):
                    print(f"[+] Found session file '{session_file}'. Loading session...")
                    self.loader.load_session_from_file(username, session_file)
                    self.is_logged_in = True
                    print("[+] Loaded existing session. You are ready to scrape.")
                else:
                    print("[!] No session file found. Attempting fresh login...")
                    self.loader.login(username, password)
                    print("[+] Login successful.")
                    self.loader.save_session_to_file(session_file)
                    print(f"[+] New session saved to '{session_file}'.")
                    self.is_logged_in = True
            except TwoFactorAuthRequiredException:
                self.after(0, self.show_2fa_input)
                return
            except LoginException as e:
                print(f"[!] Login failed: {e}")
                self.is_logged_in = False
            except Exception as e:
                print(f"[!] An unexpected error occurred during login: {e}")
                self.is_logged_in = False
            
            self.after(0, self.update_status_and_buttons_on_login)

    def update_status_and_buttons_on_login(self):
        self.hide_2fa_input()
        if self.is_logged_in:
            self.status_label.configure(text="Status: Logged in!", text_color="green")
            self.login_button.configure(state="disabled", text="Logged In")
            self.scrape_button.configure(state="normal")
        else:
            self.status_label.configure(text="Status: Login Failed. Check logs.", text_color="red")
            self.login_button.configure(state="normal", text="Log In / Load Session")
            self.scrape_button.configure(state="disabled")

    def start_scrape_thread(self):
        if not self.is_logged_in:
            self.status_label.configure(text="Status: Not logged in!", text_color="red")
            return
            
        target_profile_name = self.target_entry.get()
        if not target_profile_name:
            self.status_label.configure(text="Status: Please enter a profile username!", text_color="red")
            return
        
        self.scrape_button.configure(state="disabled", text="Scraping...")
        self.status_label.configure(text="Status: Scraping in progress...", text_color="orange")
        
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0% (ETA: Calculating...)")
        
        scrape_thread = threading.Thread(target=self.download_profile_media, args=(target_profile_name,))
        scrape_thread.start()

    def download_profile_media(self, profile_name):
        try:
            profile = instaloader.Profile.from_username(self.loader.context, profile_name)
            base_download_dir = profile.username
            print(f"[+] Starting download for profile: {profile.username}")

            images_dir = os.path.join(base_download_dir, "images")
            videos_dir = os.path.join(base_download_dir, "videos")
            os.makedirs(images_dir, exist_ok=True)
            os.makedirs(videos_dir, exist_ok=True)

            posts_list = list(profile.get_posts()) # Convert generator to list
            total_posts = len(posts_list)
            downloaded_count = 0
            start_time = time.time()
            
            self.after(0, lambda: self.progress_label.configure(text=f"Progress: 0% (ETA: Calculating...)"))
            
            for post in posts_list:
                temp_post_dir = os.path.join(base_download_dir, post.shortcode)
                os.makedirs(temp_post_dir, exist_ok=True)
                
                original_dirname_pattern = self.loader.dirname_pattern
                self.loader.dirname_pattern = temp_post_dir
                
                try:
                    self.loader.download_post(post, target=temp_post_dir)
                    
                    self.loader.dirname_pattern = original_dirname_pattern

                    if os.path.exists(temp_post_dir):
                        all_files = os.listdir(temp_post_dir)
                        
                        for filename in all_files:
                            src_path = os.path.join(temp_post_dir, filename)
                            
                            is_image = any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif'])
                            is_video = any(filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.webm'])
                            is_webp = filename.lower().endswith('.webp')

                            if is_webp:
                                try:
                                    img = Image.open(src_path)
                                    dest_filename = os.path.splitext(filename)[0] + ".jpg"
                                    dest_path = os.path.join(images_dir, dest_filename)
                                    img.save(dest_path, "jpeg")
                                    print(f"[+] Converted and moved '{filename}' to '{dest_path}'")
                                    os.remove(src_path)
                                except Exception as img_e:
                                    print(f"[x] Failed to convert '{filename}': {img_e}. Moving original file.")
                                    shutil.move(src_path, os.path.join(images_dir, filename))
                            elif is_image:
                                dest_path = os.path.join(images_dir, filename)
                                shutil.move(src_path, dest_path)
                                print(f"[+] Moved '{filename}' to '{dest_path}'")
                            elif is_video:
                                dest_path = os.path.join(videos_dir, filename)
                                shutil.move(src_path, dest_path)
                                print(f"[+] Moved '{filename}' to '{dest_path}'")
                            else:
                                os.remove(src_path)
                                print(f"[*] Removed non-media file: '{filename}'")

                        shutil.rmtree(temp_post_dir, ignore_errors=True)
                
                except Exception as e:
                    print(f"[!] Error processing post {post.shortcode}: {e}. Skipping post.")
                    shutil.rmtree(temp_post_dir, ignore_errors=True)
                    continue

                downloaded_count += 1
                
                if total_posts > 0:
                    progress_percentage = (downloaded_count / total_posts) * 100
                    elapsed_time = time.time() - start_time
                    avg_time_per_post = elapsed_time / downloaded_count
                    remaining_posts = total_posts - downloaded_count
                    eta_seconds = remaining_posts * avg_time_per_post
                    eta_minutes, eta_seconds_rem = divmod(int(eta_seconds), 60)
                    eta_text = f"ETA: {eta_minutes:02d}:{eta_seconds_rem:02d}"

                    self.after(0, lambda: self.progress_bar.set(progress_percentage / 100))
                    self.after(0, lambda: self.progress_label.configure(text=f"Progress: {progress_percentage:.1f}% ({eta_text})"))
                
                time.sleep(random.uniform(5, 10))
            
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self.progress_label.configure(text="Progress: 100% (Complete)"))
            self.after(0, lambda: self.status_label.configure(text="Status: Scraping complete!", text_color="green"))
            self.after(0, lambda: self.scrape_button.configure(state="normal", text="Start Scrape"))
            
        except ProfileNotExistsException:
            print(f"[!] Profile '{profile_name}' does not exist or is private and inaccessible.")
            self.after(0, lambda: self.status_label.configure(text="Status: Profile not found!", text_color="red"))
            self.after(0, lambda: self.scrape_button.configure(state="normal", text="Start Scrape"))
        except Exception as e:
            print(f"[!] An unexpected error occurred: {e}")
            self.after(0, lambda: self.status_label.configure(text="Status: An error occurred. Check logs.", text_color="red"))
            self.after(0, lambda: self.scrape_button.configure(state="normal", text="Start Scrape"))

# --- Run the application ---
if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = InstaDownloaderApp()
    app.mainloop()