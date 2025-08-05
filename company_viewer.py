import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import webbrowser
import re
import subprocess

try:
    from dotenv import set_key, load_dotenv
except ImportError:
    messagebox.showerror("Missing Dependency",
                         "The 'python-dotenv' library is required for this script.\n"
                         "Please install it by running: pip install python-dotenv")
    exit()

PASTEL_COLORS = [
    "#FFB6C1",  # Light Pink
    "#ADD8E6",  # Light Blue
    "#98FB98",  # Pale Green
    "#FFFACD",  # Lemon Chiffon (pale yellow)
    "#D8BFD8",  # Thistle (light purple)
    "#FFDAB9",  # Peach Puff (light orange)
    "#AFEEEE",  # Pale Turquoise
    "#F0E68C",  # Khaki (a muted yellow)
    "#E6E6FA",  # Lavender
    "#C4F4C4",  # A softer green
    "#F5DEB3"   # Wheat (muted beige)
]

def clean_key(key):
    """Cleans up a dictionary key for display."""
    replacements = {
        "website_link": "Website", "former_names": "Former Names", "also_known_as": "Also Known As",
        "legal_name": "Legal Name", "contact_name": "Contact Name", "contact_profile_link": "Contact Profile Link",
        "contact_title": "Contact Title", "contact_email": "Contact Email", "contact_business_phone": "Business Phone",
        "contact_mobile_phone": "Mobile Phone", "office_address_line1": "Office Address Line 1",
        "office_address_line2": "Office Address Line 2", "office_address_line3": "Office Address Line 3",
        "office_email": "Office Email", "office_phone": "Office Phone", "Deal Date": "Deal Date",
        "Deal Type": "Deal Type", "Deal Size": "Deal Size", "Co-Investors": "Co-Investors",
        "Company Stage": "Company Stage", "Lead Partner": "Lead Partner", "rnd_budget_usd": "R&D Budget USD",
        "key_products": "Key Products", "employees": "Employees", "funding_rounds": "Funding Rounds",
        "last_valuation": "Last Valuation", "founded_year": "Founded Year", "headquarters": "Headquarters",
        "specialization": "Specialization", "focus": "Focus", "next_gen_tech": "Next-Gen Tech",
        "solution": "Solution", "clients": "Clients", "Year Founded": "Year Founded", "Source_Type": "Source Type"
    }
    display_key = replacements.get(key, key)
    if display_key == key:
        display_key = ' '.join(word.capitalize() for word in key.split('_'))
    return display_key

def extract_pitchbook_id(company_data):
    """Extracts Pitchbook ID from profile URLs."""
    url_fields = ["profile_url", "Name_link", "contact_profile_link"]
    for field in url_fields:
        url = company_data.get(field)
        if url:
            match = re.search(r'/profile/([^/]+)/', url)
            if match:
                return match.group(1)
    return None

def open_link(url):
    """Opens a URL in the default web browser."""
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    webbrowser.open_new_tab(url)


class PitchbookViewerApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Pitchbook Company Hierarchy Viewer")
        self.root.geometry("900x750")

        self.style = ttk.Style(self.root)
        self.checkbox_data = []
        self.account_id_lookup = {}

        self._setup_styles()
        self._setup_ui()
        self._load_credentials_from_env()

    def _setup_styles(self):
        try:
            self.root.tk.call("source", "forest-dark.tcl")
            self.style.theme_use("forest-dark")
            self.style.configure("Header.TLabel", font=("Arial", 18, "bold"))
            self.style.configure("SubHeader.TLabel", font=("Arial", 12, "bold"))
            self.style.configure("CompanyEntry.TLabel", font=("Arial", 12, "bold"))
            self.style.configure("Details.TLabel", font=("Arial", 10))
            self.style.configure("Accent.Details.TLabel", font=("Arial", 10, "bold"))
            self.style.configure("Italic.TLabel", font=("Arial", 10, "italic"))
            self.style.configure("Link.TLabel", font=("Arial", 10, "underline"), foreground="#4a90d9")
            self.style.map("Link.TLabel", foreground=[('active', '#6eb8ff')])
        except tk.TclError:
            print("Forest-dark theme not found. Applying basic dark mode styling.")
            self.style.theme_use("clam")
            DARK_BG = "#2e2e2e"; MID_DARK_BG = "#3c3c3c"; LIGHT_TEXT = "#ffffff"
            ACCENT_BLUE = "#4a90d9"; GRAY_TEXT = "#bbbbbb"; RAISED_BORDER_COLOR = "#5c5c5c"
            self.root.configure(bg=DARK_BG)
            self.style.configure("TFrame", background=DARK_BG)
            self.style.configure("Raised.TFrame", background=MID_DARK_BG, borderwidth=1, relief="raised", bordercolor=RAISED_BORDER_COLOR)
            self.style.configure("TButton", background=MID_DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 10), borderwidth=1)
            self.style.map("TButton", background=[("active", "#5c5c5c")])
            self.style.configure("TLabel", background=MID_DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 10))
            self.style.configure("Header.TLabel", background=DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 18, "bold"))
            self.style.configure("SubHeader.TLabel", background=DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 12, "bold"))
            self.style.configure("CompanyEntry.TLabel", background=MID_DARK_BG, foreground=LIGHT_TEXT)
            self.style.configure("Italic.TLabel", background=MID_DARK_BG, foreground=GRAY_TEXT, font=("Arial", 10, "italic"))
            self.style.configure("Link.TLabel", background=MID_DARK_BG, foreground=ACCENT_BLUE, font=("Arial", 10, "underline"))
            self.style.configure("Details.TLabel", background=MID_DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 10))
            self.style.configure("Accent.Details.TLabel", background=MID_DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 10, "bold"))
            self.style.configure("Vertical.TScrollbar", background=MID_DARK_BG, troughcolor=DARK_BG, bordercolor=DARK_BG, arrowcolor=LIGHT_TEXT)
            self.style.map("Vertical.TScrollbar", background=[("active", ACCENT_BLUE)])
            self.style.configure("TSeparator", background=RAISED_BORDER_COLOR)

    def _setup_ui(self):
        control_frame = ttk.Frame(self.root, padding="10", style="TFrame")
        control_frame.pack(side="top", fill="x", expand=False)
        
        credentials_frame = ttk.Frame(control_frame, style="TFrame")
        credentials_frame.pack(side="top", fill="x", pady=(0, 5))
        
        ttk.Label(credentials_frame, text="Pitchbook User:", style="TLabel").pack(side="left", padx=(0, 5))
        self.user_entry = ttk.Entry(credentials_frame, width=20)
        self.user_entry.pack(side="left", padx=5)
        ttk.Label(credentials_frame, text="Pitchbook Pass:", style="TLabel").pack(side="left", padx=(10, 5))
        self.pass_entry = ttk.Entry(credentials_frame, width=20, show="*")
        self.pass_entry.pack(side="left", padx=5)
        ttk.Button(credentials_frame, text="Save Credentials", command=self._save_credentials).pack(side="left", padx=10)

        # Account ID File Input
        account_id_frame = ttk.Frame(control_frame, style="TFrame")
        account_id_frame.pack(side="top", fill="x", pady=5)
        ttk.Label(account_id_frame, text="Account ID File:", style="TLabel").pack(side="left", padx=(0, 5))
        self.account_id_entry = ttk.Entry(account_id_frame, width=30)
        self.account_id_entry.pack(side="left", expand=True, fill="x", padx=5)
        self.account_id_entry.insert(0, "processed_pitchbook_data_with_ids.json") # Updated default filename


        ttk.Separator(control_frame, style="TSeparator").pack(fill='x', pady=5)
        ttk.Label(control_frame, text="Actions", style="SubHeader.TLabel").pack(side="top", anchor="w", pady=(5, 2))
        script_button_frame = ttk.Frame(control_frame, style="TFrame")
        script_button_frame.pack(side="top", fill="x", pady=(0, 10))
        
        ttk.Button(script_button_frame, text="Queue Scrape", command=lambda: self._run_external_script("queue_scrape.py")).pack(side="left", padx=5)
        ttk.Button(script_button_frame, text="Crawl PB Tree", command=lambda: self._run_external_script("pb_tree_crawler.py")).pack(side="left", padx=5)
        ttk.Button(script_button_frame, text="Run Retool Bot", command=lambda: self._run_external_script("retool_bot.py")).pack(side="left", padx=5)

        ttk.Label(control_frame, text="Display Selection", style="SubHeader.TLabel").pack(side="top", anchor="w", pady=(0, 2))
        data_load_button_frame = ttk.Frame(control_frame, style="TFrame")
        data_load_button_frame.pack(side="top", fill="x")

        ttk.Button(data_load_button_frame, text="Current Tree Data", command=lambda: self.load_data_and_display("multi_company_pitchbook_data.json")).pack(side="left", padx=5)
        ttk.Button(data_load_button_frame, text="Companies Ready To Scrape", command=lambda: self.load_data_and_display("cleanup_queue_names.json")).pack(side="left", padx=5)
        ttk.Button(data_load_button_frame, text="Companies To Review", command=lambda: self.load_data_and_display("companies_to_review.json")).pack(side="left", padx=5)
        
        self.save_button_frame = ttk.Frame(control_frame, style="TFrame")
        self.save_button_frame.pack(side="top", fill="x", pady=5)
        ttk.Button(self.save_button_frame, text="Save Selection", command=self._save_selection).pack(side="left", padx=5)
        self.save_button_frame.pack_forget()

        self.main_display_frame = ttk.Frame(self.root, style="TFrame")
        self.main_display_frame.pack(side="bottom", fill="both", expand=True)

    def _load_credentials_from_env(self):
        if os.path.exists(".env"):
            load_dotenv(dotenv_path=".env")
            user = os.getenv("PITCHBOOK_USER"); password = os.getenv("PITCHBOOK_PASSWORD")
            if user: self.user_entry.insert(0, user)
            if password: self.pass_entry.insert(0, password)

    def _save_credentials(self):
        username = self.user_entry.get(); password = self.pass_entry.get()
        try:
            set_key(".env", "PITCHBOOK_USER", username); set_key(".env", "PITCHBOOK_PASSWORD", password)
            messagebox.showinfo("Success", "Credentials saved to .env file.")
        except Exception as e: messagebox.showerror("Error", f"Failed to save credentials: {e}")

    def _run_external_script(self, script_name):
        if not os.path.exists(script_name): messagebox.showerror("File Not Found", f"The script '{script_name}' was not found.")
        else:
            try: subprocess.Popen(['python', script_name]); messagebox.showinfo("Script Started", f"The script '{script_name}' has been started.")
            except Exception as e: messagebox.showerror("Error", f"Failed to run script '{script_name}':\n{e}")

    def _save_selection(self):
        selected_companies = [data for var, data in self.checkbox_data if var.get()]
        if not selected_companies: messagebox.showwarning("No Selection", "No companies were selected to save."); return
        output_filename = "selected_for_scraping.json"
        try:
            with open(output_filename, 'w', encoding='utf-8') as f: json.dump(selected_companies, f, indent=2)
            messagebox.showinfo("Success", f"Saved {len(selected_companies)} selected companies to '{output_filename}'.")
        except Exception as e: messagebox.showerror("Save Error", f"Failed to save the file: {e}")

    def _load_account_id_lookup(self):
        self.account_id_lookup = {}
        lookup_filename = self.account_id_entry.get().strip()
        if not lookup_filename or not os.path.exists(lookup_filename):
            messagebox.showwarning("Lookup File Not Found", f"Account ID file '{lookup_filename}' not found. No account IDs will be displayed.")
            return

        try:
            with open(lookup_filename, 'r', encoding='utf-8') as f:
                lookup_data = json.load(f)
            for entry in lookup_data:
                name = entry.get("legal_name") or entry.get("Name")
                account_ids = entry.get("account_ids")
                if name and isinstance(account_ids, list):
                    self.account_id_lookup[name] = account_ids
        except Exception as e:
            messagebox.showerror("Lookup File Error", f"Failed to load or process '{lookup_filename}': {e}")
            self.account_id_lookup = {}

    def load_data_and_display(self, filename):
        self._load_account_id_lookup()
        for widget in self.main_display_frame.winfo_children(): widget.destroy()
        self.checkbox_data.clear()

        try:
            if not os.path.exists(filename): messagebox.showerror("File Not Found", f"The file '{filename}' was not found."); return
            with open(filename, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data, list) or not data: messagebox.showwarning("Invalid JSON Format", f"Content of '{filename}' is not a list or is empty."); return
        except Exception as e: messagebox.showerror("Error", f"Failed to load or parse '{filename}': {e}"); return
        
        show_checkboxes = (filename == "cleanup_queue_names.json")
        if show_checkboxes: self.save_button_frame.pack(side="top", fill="x", pady=5)
        else: self.save_button_frame.pack_forget()

        scroll_content_frame = ttk.Frame(self.main_display_frame, style="TFrame")
        scroll_content_frame.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(scroll_content_frame, borderwidth=0, bg=self.style.lookup("TFrame", "background"), highlightbackground=self.style.lookup("TFrame", "background"))
        scrollbar = ttk.Scrollbar(scroll_content_frame, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
        scrollable_frame = ttk.Frame(canvas, style="TFrame")

        canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y"); canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def configure_scroll_region(event): canvas.configure(scrollregion=canvas.bbox("all"))
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        def configure_canvas_window(event): canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_canvas_window)
        def _on_mousewheel(event):
            if event.num == 5 or event.delta < 0: canvas.yview_scroll(1, "unit")
            elif event.num == 4 or event.delta > 0: canvas.yview_scroll(-1, "unit")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        use_root_name_flag = (filename == "cleanup_queue_names.json")
        
        if filename == "multi_company_pitchbook_data.json":
            for main_company_entry in data: self._build_indented_tree_recursively(scrollable_frame, main_company_entry, 0, self.style)
        else:
            for main_company_entry in data: self._create_accordion_root_entry(scrollable_frame, main_company_entry, self.style, use_root_name_flag, show_checkboxes)

    def _display_company_details(self, parent_frame, company_data):
        excluded_keys = [
            "profile_url", "depth", "status", "legal_name", "root_name", "Name", "Name_link", "Industry_link", 
            "Location_link", "Year Founded_link", "contact_profile_link", "contact_email_link", 
            "Deal Date_link", "Deal Type_link", "Deal Size_link", "Co-Investors_link", 
            "Company Stage_link", "Lead Partner_link", "related_companies", "nested_related_companies", "website_link"
        ]
        
        company_name_for_lookup = company_data.get("legal_name") or company_data.get("Name")
        if company_name_for_lookup and company_name_for_lookup in self.account_id_lookup:
            account_ids = self.account_id_lookup[company_name_for_lookup]
            ttk.Label(parent_frame, text=f"Account IDs: {', '.join(map(str, account_ids))}", style="Accent.Details.TLabel", wraplength=700).pack(anchor="w", padx=(10, 0), fill="x")

        pb_id = extract_pitchbook_id(company_data)
        if pb_id: ttk.Label(parent_frame, text=f"Pitchbook ID: {pb_id}", style="Details.TLabel", wraplength=700).pack(anchor="w", padx=(10, 0), fill="x")
        
        for key, value in company_data.items():
            if key in excluded_keys or value is None or (isinstance(value, str) and value.strip() in ["", "N/A", "None"]): continue
            if isinstance(value, list):
                display_value = ", ".join(str(item) for item in value if item is not None and str(item).strip() != "")
                if not display_value: continue
            else: display_value = str(value).strip()
            ttk.Label(parent_frame, text=f"{clean_key(key)}: {display_value}", style="Details.TLabel", wraplength=700).pack(anchor="w", padx=(10, 0), fill="x")

    def _build_indented_tree_recursively(self, parent_tk_frame, company_data, current_level, style_obj):
        company_name = company_data.get("legal_name") or company_data.get("root_name") or company_data.get("Name", "Unknown Company")
        display_name = company_name
        if company_name and company_name in self.account_id_lookup:
            display_name += " *"

        color_index = current_level % len(PASTEL_COLORS); name_color = PASTEL_COLORS[color_index]
        style_name = f"CompanyEntry.Level{current_level}.TLabel"
        if style_obj: style_obj.configure(style_name, foreground=name_color)
        
        entry_frame = ttk.Frame(parent_tk_frame, padding="5 5 5 5", style="Raised.TFrame")
        entry_frame.pack(fill="x", expand=True, pady=3, padx=current_level * 20)
        
        name_font_size = max(10, 14 - min(current_level * 2, 8))
        name_label = ttk.Label(entry_frame, text=display_name, font=("Arial", name_font_size, "bold"), cursor="hand2", style=style_name)
        name_label.pack(anchor="w")

        details_content_frame = ttk.Frame(entry_frame, padding="5 0 0 0", style="TFrame")
        self._display_company_details(details_content_frame, company_data)
        
        website = company_data.get("website_link")
        if website and website.strip() not in ["", "N/A", "None"]:
            link_label = ttk.Label(details_content_frame, text=f"Website: {website}", style="Link.TLabel")
            link_label.pack(anchor="w", padx=(10, 0)); link_label.bind("<Button-1>", lambda e, url=website: open_link(url))
        
        def toggle_details():
            if details_content_frame.winfo_ismapped(): details_content_frame.pack_forget()
            else: details_content_frame.pack(fill="x", expand=True)
        name_label.bind("<Button-1>", lambda e: toggle_details())

        children_to_process = []
        if isinstance(company_data.get("related_companies"), list): children_to_process.extend(company_data["related_companies"])
        if isinstance(company_data.get("nested_related_companies"), list): children_to_process.extend(company_data["nested_related_companies"])

        if children_to_process:
            for child_company in children_to_process:
                self._build_indented_tree_recursively(parent_tk_frame, child_company, current_level + 1, style_obj)

    def _create_accordion_root_entry(self, parent_tk_frame, company_data, style_obj, use_root_name_only, show_checkboxes):
        if use_root_name_only: company_name = company_data.get("root_company_name", "Unknown Company")
        else: company_name = company_data.get("legal_name") or company_data.get("root_name") or company_data.get("Name", "Main Company")
        
        display_name = company_name
        if company_name and company_name in self.account_id_lookup:
            display_name += " *"

        color_index = 0; name_color = PASTEL_COLORS[color_index]
        style_name = f"CompanyEntry.Level{color_index}.TLabel"
        if style_obj: style_obj.configure(style_name, foreground=name_color)
        
        root_entry_frame = ttk.Frame(parent_tk_frame, padding="5 5 5 5", style="Raised.TFrame")
        root_entry_frame.pack(fill="x", expand=True, pady=3, padx=0)
        
        if show_checkboxes:
            check_var = tk.BooleanVar(); ttk.Checkbutton(root_entry_frame, variable=check_var).pack(side="left", padx=(0, 5))
            self.checkbox_data.append((check_var, company_data))

        name_label = ttk.Label(root_entry_frame, text=f"▶ {display_name}", font=("Arial", 14, "bold"), cursor="hand2", style=style_name)
        name_label.pack(side="left", anchor="w")

        children_container_frame = ttk.Frame(root_entry_frame, style="TFrame")

        def toggle_root_expansion():
            if children_container_frame.winfo_ismapped():
                children_container_frame.pack_forget(); name_label.config(text=f"▶ {display_name}")
            else:
                if not children_container_frame.winfo_children():
                    children = company_data.get("related_companies", [])
                    for child in children:
                        self._build_indented_tree_recursively(children_container_frame, child, 1, self.style)
                children_container_frame.pack(fill="x", expand=True); name_label.config(text=f"▼ {display_name}")
        name_label.bind("<Button-1>", lambda e: toggle_root_expansion())


if __name__ == "__main__":
    if not os.path.exists("multi_company_pitchbook_data.json"):
        with open("multi_company_pitchbook_data.json", 'w') as f: json.dump([{"legal_name": "Dummy Tree Data", "related_companies": [{"Name": "Child 1"}]}], f)
        print("Created dummy 'multi_company_pitchbook_data.json'.")
    if not os.path.exists("cleanup_queue_names.json"):
        with open("cleanup_queue_names.json", 'w') as f: json.dump([{"root_company_name": "Dummy Scrape Company"}], f)
        print("Created dummy 'cleanup_queue_names.json'.")
    if not os.path.exists("companies_to_review.json"):
        with open("companies_to_review.json", 'w') as f: json.dump([{"Name": "Dummy Review Company"}], f)
        print("Created dummy 'companies_to_review.json'.")
    if not os.path.exists("processed_pitchbook_data_with_ids.json"):
        dummy_account_data = [{"legal_name": "Dummy Tree Data", "account_ids": [101, 202]}, {"Name": "Child 1", "account_ids": [999]}]
        with open("processed_pitchbook_data_with_ids.json", 'w') as f: json.dump(dummy_account_data, f, indent=2)
        print("Created dummy 'processed_pitchbook_data_with_ids.json'.")
    
    root = tk.Tk()
    app = PitchbookViewerApp(root)
    root.mainloop()
