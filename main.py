import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk # Added ttk
import ctypes
import subprocess
import re # For removing ANSI escape codes
import threading

# --- Dark Mode Color Palette ---
DARK_THEME_COLORS = {
    "bg": "#2B2B2B",  # Main background
    "fg": "#D3D3D3",  # Main foreground (text)
    "entry_bg": "#3C3C3C",  # Background for Entry, Listbox-like widgets
    "button_bg": "#555555",  # Button background
    "button_fg": "#FFFFFF",  # Button text
    "select_bg": "#0078D7",  # Background for selected items
    "select_fg": "#FFFFFF",  # Foreground for selected items
    "treeview_heading_bg": "#4A4A4A",  # Background for Treeview headings
    "disabled_fg": "#888888"  # Foreground for disabled text/widgets
}

# Function to remove ANSI escape codes
def remove_ansi_codes(text):
    """Removes ANSI escape codes from a string."""
    if text is None:
        return ""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# Function to run Scoop commands and get output (for parsing by search/status)
def get_scoop_command_output(command_parts, timeout=300):
    """
    Runs a Scoop command and returns its stdout, stderr, and return code.
    Hides the console window. Does NOT show message boxes for errors.
    """
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(
            ['scoop'] + command_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True, # shell=True can be convenient for scoop
            text=True,
            encoding='utf-8', # Be explicit about encoding
            errors='replace', # Handle potential decoding errors
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return stdout, stderr, process.returncode
    except FileNotFoundError:
        return None, "Scoop command not found.", -1
    except subprocess.TimeoutExpired:
        return None, "Command timed out.", -1
    except Exception as e:
        return None, f"An unexpected error occurred: {e}", -1


def _execute_scoop_action_with_modal_output(command_parts, parent_window, status_label, refresh_callback=None):
    """
    Executes a Scoop command (install, uninstall, update) and shows its output
    in a new modal Toplevel dialog with live updates.
    This function is intended to be run in a separate thread.
    """
    dialog_title = f"Scoop: {' '.join(command_parts)}"
    dialog = tk.Toplevel(parent_window)
    dialog.title(dialog_title)
    dialog.geometry("700x450")
    dialog.transient(parent_window) # Keep dialog on top of parent
    dialog.configure(bg=DARK_THEME_COLORS["bg"])

    output_display = scrolledtext.ScrolledText(
        dialog, wrap=tk.WORD, height=20, state=tk.DISABLED,
bg=DARK_THEME_COLORS["entry_bg"], fg=DARK_THEME_COLORS["fg"],
insertbackground=DARK_THEME_COLORS["fg"], # Cursor color
selectbackground=DARK_THEME_COLORS["select_bg"],
selectforeground=DARK_THEME_COLORS["select_fg"],
        relief=tk.FLAT, borderwidth=1
    )
    output_display.pack(padx=10, pady=10, expand=True, fill=tk.BOTH)
    dialog.grab_set() # Make modal

    try:
        output_display.config(state=tk.NORMAL)
        output_display.insert(tk.END, f"Executing: scoop {' '.join(command_parts)}\n\n")
        output_display.see(tk.END)
        dialog.update_idletasks()

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen(
            ['scoop'] + command_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Combine stdout and stderr
            shell=True, text=True, encoding='utf-8', errors='replace',
            startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW,
            bufsize=1, universal_newlines=True
        )

        # Progress bar and label
        progress_frame = ttk.Frame(dialog)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0,5))
        progress_label = ttk.Label(progress_frame, text="Running...", style="Dark.TLabel") # Apply style if defined
        progress_label.pack(side=tk.LEFT, padx=(0,5))
        progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=200) # Optional: if you want a visual bar
        progress_bar.pack(side=tk.LEFT, expand=True, fill=tk.X)
        progress_bar.start(10)

        for line in process.stdout:
            if not dialog.winfo_exists(): break
            output_display.insert(tk.END, line)
            output_display.see(tk.END)
            dialog.update_idletasks()

        process.wait(timeout=300) # 5-minute timeout

        if process.returncode == 0:
            final_message = "Command completed successfully."
            if progress_label.winfo_exists(): progress_label.config(text="Success!")
        else:
            final_message = f"Command failed with exit code {process.returncode}."
            if progress_label.winfo_exists(): progress_label.config(text="Failed!")
        
        output_display.insert(tk.END, f"\n{final_message}\n")

    except FileNotFoundError:
        if dialog.winfo_exists():
            output_display.insert(tk.END, "Error: Scoop command not found. Is Scoop installed and in your PATH?\n")
            if 'progress_label' in locals() and progress_label.winfo_exists(): progress_label.config(text="Error: Scoop not found!")
    except subprocess.TimeoutExpired:
        if dialog.winfo_exists():
            output_display.insert(tk.END, "Error: Command timed out.\n")
            if 'progress_label' in locals() and progress_label.winfo_exists(): progress_label.config(text="Error: Timeout!")
    except Exception as e:
        if dialog.winfo_exists():
            output_display.insert(tk.END, f"An unexpected error occurred: {e}\n")
            if 'progress_label' in locals() and progress_label.winfo_exists(): progress_label.config(text="Error: Unexpected!")
    finally:
        if 'progress_bar' in locals() and progress_bar.winfo_exists():
            progress_bar.stop()
            progress_bar.pack_forget() # Clean up progress bar
        if 'progress_label' in locals() and progress_label.winfo_exists() and not (process.returncode == 0 or "Error" in progress_label.cget("text")):
            # If no specific status was set (e.g. early exit), set a generic one or hide
             progress_label.config(text="Operation ended.")

        if dialog.winfo_exists():
            output_display.config(state=tk.DISABLED) # Make text read-only
            # Add close button if not already there
            has_close_button = any(isinstance(child, tk.Button) and child.cget("text") == "Close" for child in dialog.winfo_children())
            if not has_close_button:
                close_button = tk.Button(
                    dialog, text="Close", command=dialog.destroy,
bg=DARK_THEME_COLORS["button_bg"], fg=DARK_THEME_COLORS["button_fg"],
activebackground=DARK_THEME_COLORS["select_bg"], activeforeground=DARK_THEME_COLORS["select_fg"],
                    relief=tk.FLAT, borderwidth=1
                )
                close_button.pack(pady=5)

        
        # Update main status bar after the modal operation is essentially complete
        if status_label and status_label.winfo_exists():
            parent_window.after(0, lambda: status_label.config(text="Ready"))
        
        # Automatically refresh the app list after the operation if a callback is provided
        if refresh_callback and callable(refresh_callback):
            parent_window.after(0, refresh_callback)
        
        if dialog.winfo_exists():
            dialog.wait_window() # Blocks until the dialog is destroyed

def run_scoop_command_threaded(command_parts, status_label, parent_window, refresh_callback=None):
    """
    Runs a Scoop action (install, uninstall, update) in a separate thread,
    displaying its output in a modal dialog.
    Optionally accepts a callback to refresh the app list after the operation.
    """
    status_label.config(text=f"Running 'scoop {' '.join(command_parts)}'...")
    thread = threading.Thread(target=_execute_scoop_action_with_modal_output,
                              args=(command_parts, parent_window, status_label, refresh_callback))
    thread.daemon = True # Allows main program to exit even if thread is running
    thread.start()

class ScoopUI:
    """
    A graphical user interface for managing applications using Scoop, a command-line installer for Windows.
    Provides tabs for searching and installing new applications, as well as managing installed apps and updates.
    
    Args:
        root_window (tk.Tk): The root Tkinter window for the application.
    """
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Scoop UI Interface")
        self.root.geometry("750x750") # Increased height for listbox
        self.root.configure(bg=DARK_THEME_COLORS["bg"])

        # Apply a theme
        style = ttk.Style()
        # print(style.theme_names()) # To see available themes
        style.theme_use('clam') # 'clam' is often a good base for custom theming

        # --- Configure ttk styles for Dark Mode ---
        style.configure('.', background=DARK_THEME_COLORS["bg"], foreground=DARK_THEME_COLORS["fg"], bordercolor=DARK_THEME_COLORS["fg"])
        style.configure('TFrame', background=DARK_THEME_COLORS["bg"])
        style.configure('TLabel', background=DARK_THEME_COLORS["bg"], foreground=DARK_THEME_COLORS["fg"])
        style.configure('Dark.TLabel', background=DARK_THEME_COLORS["bg"], foreground=DARK_THEME_COLORS["fg"]) # For progress_label in modal

        style.configure('TButton', background=DARK_THEME_COLORS["button_bg"], foreground=DARK_THEME_COLORS["button_fg"],
                        relief=tk.FLAT, borderwidth=1, focusthickness=0, padding=5)
        style.map('TButton',
                  background=[('active', DARK_THEME_COLORS["select_bg"]), ('pressed', DARK_THEME_COLORS["select_bg"])],
                  foreground=[('active', DARK_THEME_COLORS["select_fg"]), ('pressed', DARK_THEME_COLORS["select_fg"])])

        style.configure('TEntry', fieldbackground=DARK_THEME_COLORS["entry_bg"], foreground=DARK_THEME_COLORS["fg"],
                        insertcolor=DARK_THEME_COLORS["fg"], relief=tk.FLAT, borderwidth=1)

        style.configure('Treeview', background=DARK_THEME_COLORS["entry_bg"], fieldbackground=DARK_THEME_COLORS["entry_bg"], foreground=DARK_THEME_COLORS["fg"], font=('Segoe UI', 10))
        style.map('Treeview', background=[('selected', DARK_THEME_COLORS["select_bg"])], foreground=[('selected', DARK_THEME_COLORS["select_fg"])])
        style.configure('Treeview.Heading', background=DARK_THEME_COLORS["treeview_heading_bg"], foreground=DARK_THEME_COLORS["fg"], relief="flat", padding=5, font=('Segoe UI', 10))
        style.map('Treeview.Heading', background=[('active', DARK_THEME_COLORS["select_bg"])], relief=[('active', 'groove')]) # Added relief for active heading

        style.configure('TNotebook', background=DARK_THEME_COLORS["bg"], borderwidth=0)
        style.configure('TNotebook.Tab', background=DARK_THEME_COLORS["button_bg"], foreground=DARK_THEME_COLORS["fg"], padding=[8, 4], relief=tk.FLAT, borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', DARK_THEME_COLORS["bg"])], foreground=[('selected', 'white')])
        
        # --- Main Tabbed Interface ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)

        # --- Updates Tab ---
        self.manage_apps_tab = ttk.Frame(self.notebook) # Renamed
        self.notebook.add(self.manage_apps_tab, text='Manage Apps')
        self._create_manage_apps_tab_widgets(self.manage_apps_tab) # Renamed
        
        # --- Search Tab ---
        self.search_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.search_tab, text='Search Apps')
        self._create_search_tab_widgets(self.search_tab) # No change here, just for context

        # --- Status Bar ---
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(self.status_frame, text="Ready", anchor=tk.W, padding=(5, 2))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.status_progress = ttk.Progressbar(self.status_frame, mode='indeterminate', length=200)
        # Progress bar will be packed/unpacked dynamically when needed

        # Optionally, load updates when the app starts or when tab is first selected
        self.refresh_manage_apps_list() # Renamed: To load apps and updates on startup
        # self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
    def _create_search_tab_widgets(self, parent_frame):
        # Input Frame for Search
        input_frame = ttk.Frame(parent_frame, padding=(0, 10, 0, 5)) # Left, Top, Right, Bottom
        input_frame.pack(fill=tk.X, padx=10, pady=(10,0), anchor=tk.N)
        ttk.Label(input_frame, text="App Name:").pack(side=tk.LEFT, padx=(0, 5), pady=5)
        self.app_name_entry = ttk.Entry(input_frame, width=40)
        self.app_name_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, pady=5)
        self.search_button = ttk.Button(input_frame, text="Search", command=self.search_app)
        self.search_button.pack(side=tk.LEFT, padx=(5,0), pady=5)

        # List Display Frame for Search Results
        list_display_frame = ttk.Frame(parent_frame, padding=5)
        list_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.search_list_title_label = ttk.Label(list_display_frame, text="Search Results:")
        self.search_list_title_label.pack(anchor=tk.W, pady=(0,5))

        listbox_container = ttk.Frame(list_display_frame) # Using ttk.Frame for consistency
        listbox_container.pack(fill=tk.BOTH, expand=True)

        self.search_results_treeview_scrollbar = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL)
        self.search_results_treeview = ttk.Treeview(
            listbox_container,
            columns=('name', 'version', 'source'),
            show='headings',
            yscrollcommand=self.search_results_treeview_scrollbar.set,
            selectmode='browse'  # Single selection
        )
        self.search_results_treeview_scrollbar.config(command=self.search_results_treeview.yview)
        self.search_results_treeview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_results_treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Define column headings and widths for search results
        self.search_results_treeview.heading('name', text='Name', anchor=tk.W)
        self.search_results_treeview.column('name', width=200, minwidth=100, stretch=tk.YES)
        self.search_results_treeview.heading('version', text='Version', anchor=tk.W)
        self.search_results_treeview.column('version', width=100, minwidth=50, stretch=tk.YES)
        self.search_results_treeview.heading('source', text='Source', anchor=tk.W)
        self.search_results_treeview.column('source', width=100, minwidth=50, stretch=tk.YES)

        self.search_action_buttons_frame = ttk.Frame(list_display_frame)
        self.search_action_buttons_frame.pack(fill=tk.X, pady=(5,0))
        self.current_search_results_data = []
        self._setup_search_list_actions()
        
        # Bind double-click to install for search results
        self.search_results_treeview.bind("<Double-1>", lambda event: self._handle_install_selected_from_list())

    def _create_manage_apps_tab_widgets(self, parent_frame): # Renamed
        # Action Frame for Updates
        manage_apps_top_actions_frame = ttk.Frame(parent_frame, padding=(0,10,0,5)) # Renamed
        manage_apps_top_actions_frame.pack(fill=tk.X, padx=10, pady=(10,0), anchor=tk.N)


        # List Display Frame for Updates
        list_display_frame = ttk.Frame(parent_frame, padding=5)
        list_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.manage_apps_list_title_label = ttk.Label(list_display_frame, text="Installed Apps & Updates:") # Renamed and text changed
        self.manage_apps_list_title_label.pack(anchor=tk.W, pady=(0,5))

        listbox_container = ttk.Frame(list_display_frame) # Using ttk.Frame for consistency
        listbox_container.pack(fill=tk.BOTH, expand=True)

        self.manage_apps_treeview_scrollbar = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL) # Renamed
        self.manage_apps_treeview = ttk.Treeview( # Renamed
            listbox_container,
            columns=('app_name', 'current_ver', 'new_ver'), # Updated columns
            show='headings',
            yscrollcommand=self.manage_apps_treeview_scrollbar.set, # Renamed
            selectmode='extended'  # Multiple selections
        )
        self.manage_apps_treeview_scrollbar.config(command=self.manage_apps_treeview.yview) # Renamed
        self.manage_apps_treeview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y) # Renamed
        self.manage_apps_treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Renamed

        # Define column headings and widths for updates
        self.manage_apps_treeview.heading('app_name', text='Application Name', anchor=tk.W)
        self.manage_apps_treeview.column('app_name', width=200, minwidth=100, stretch=tk.YES)
        self.manage_apps_treeview.heading('current_ver', text='Current Version', anchor=tk.W)
        self.manage_apps_treeview.column('current_ver', width=100, minwidth=30, stretch=tk.YES)
        self.manage_apps_treeview.heading('new_ver', text='New Version', anchor=tk.W)
        self.manage_apps_treeview.column('new_ver', width=100, minwidth=30, stretch=tk.YES)
        # self.manage_apps_treeview.heading('status', text='Status', anchor=tk.W) # Removed column
        # self.manage_apps_treeview.column('status', width=120, minwidth=50, stretch=tk.YES) # Removed column
        
        # Tag for highlighting rows with updates
        self.UPDATED_APP_TAG = "updated_app_style"
        self.manage_apps_treeview.tag_configure(self.UPDATED_APP_TAG, font=('Segoe UI', 10, 'bold'))

        self.manage_apps_action_buttons_frame = ttk.Frame(list_display_frame) # Renamed
        self.manage_apps_action_buttons_frame.pack(fill=tk.X, pady=(5,0))
        self.current_managed_apps_data = [] # Renamed
        self._setup_manage_apps_list_actions() # Renamed

        # Bind double-click to update for updates list (could be ambiguous if multiple selected, so stick to button)
        # self.manage_apps_treeview.bind("<Double-1>", lambda event: self._handle_update_selected_from_manage_list())


    def _setup_search_list_actions(self):
        for widget in self.search_action_buttons_frame.winfo_children():
            widget.destroy()
        # Clearing data is handled by _clear_search_results
        # self.current_search_results_data = []
        self.search_list_title_label.config(text="Search Results:")
        ttk.Button(self.search_action_buttons_frame, text="Install Selected", command=self._handle_install_selected_from_list).pack(side=tk.LEFT, padx=(0,5), pady=5)
        ttk.Button(self.search_action_buttons_frame, text="Clear Results", command=self._clear_search_results).pack(side=tk.LEFT, padx=(0,5), pady=5)



    def _clear_search_results(self):
        self.search_results_treeview.delete(*self.search_results_treeview.get_children())
        self.current_search_results_data = []
        self.search_list_title_label.config(text="Search Results:") # Keep title consistent
    
    def _setup_manage_apps_list_actions(self): # Renamed
        for widget in self.manage_apps_action_buttons_frame.winfo_children(): # Renamed
            widget.destroy()
        # Clearing data is handled by _clear_manage_apps_list
        # self.current_managed_apps_data = []
        self.manage_apps_list_title_label.config(text="Installed Apps & Updates:") # Renamed and text changed
        ttk.Button(self.manage_apps_action_buttons_frame, text="Refresh List", command=self.refresh_manage_apps_list).pack(side=tk.LEFT, padx=(0,5), pady=5) # Renamed
        ttk.Button(self.manage_apps_action_buttons_frame, text="Update Selected", command=self._handle_update_selected_from_manage_list).pack(side=tk.LEFT, padx=(0,5), pady=5) # Renamed handler
        ttk.Button(self.manage_apps_action_buttons_frame, text="Select All", command=lambda: self.manage_apps_treeview.selection_set(self.manage_apps_treeview.get_children())).pack(side=tk.LEFT, padx=(0,5), pady=5) # Renamed treeview
        ttk.Button(self.manage_apps_action_buttons_frame, text="Uninstall Selected", command=self._handle_uninstall_selected_from_manage_list).pack(side=tk.LEFT, padx=(0,5), pady=5) # Renamed handler
        ttk.Button(self.manage_apps_action_buttons_frame, text="Deselect All", command=lambda: self.manage_apps_treeview.selection_remove(self.manage_apps_treeview.get_children())).pack(side=tk.LEFT, padx=(0,5), pady=5) # Renamed treeview
        ttk.Button(self.manage_apps_action_buttons_frame, text="Clear List", command=self._clear_manage_apps_list).pack(side=tk.LEFT, padx=(0,5), pady=5) # Renamed handler

    def _clear_manage_apps_list(self): # Renamed
        self.manage_apps_treeview.delete(*self.manage_apps_treeview.get_children()) # Renamed
        self.current_managed_apps_data = [] # Renamed
        self.manage_apps_list_title_label.config(text="Installed Apps & Updates:") # Renamed and text changed

    def get_app_name(self):
        app_name = self.app_name_entry.get().strip()
        if not app_name:
            messagebox.showwarning("Input Required", "Please enter an application name.")
            return None
        return app_name

    def search_app(self):
        app_name = self.get_app_name()
        if app_name:
            self.status_label.config(text=f"Searching for '{app_name}'...")
            self._clear_search_results() # Clear previous results
            # _setup_search_list_actions() is called at init and ensures buttons are there
            
            def fetch_and_show_search_results():
                stdout, stderr, returncode = get_scoop_command_output(['search', app_name])

                if not self.root.winfo_exists(): return

                if returncode != 0 or stderr: # Also consider stderr for search errors
                    messagebox.showerror("Search Error", f"Failed to search for '{app_name}'.\n{stderr or stdout or 'Unknown error'}", parent=self.root)
                    self.status_label.config(text="Search failed.")
                    if self.root.winfo_exists(): self._clear_search_results()
                    return
                
                if not stdout:
                    messagebox.showinfo("Search Results", f"No results found for '{app_name}'.", parent=self.root)
                    self.status_label.config(text="Ready")
                    if self.root.winfo_exists(): self._clear_search_results()
                    return

                search_results = self.parse_scoop_search_results(stdout)

                if not search_results:
                    messagebox.showinfo("Search Results", f"No applications found matching '{app_name}' or search output could not be parsed.", parent=self.root)
                    self.status_label.config(text="Ready")
                    if self.root.winfo_exists(): self._clear_search_results()
                    return
                
                self.status_label.config(text="Ready")
                
                if self.root.winfo_exists():
                    self.current_search_results_data = search_results # Ensure correct variable name
                    self.search_results_treeview.delete(*self.search_results_treeview.get_children())
                    for item in search_results:
                        self.search_results_treeview.insert('', tk.END, values=(
                            item['name'], item['version'], item['source']
                        ))

            thread = threading.Thread(target=fetch_and_show_search_results)
            thread.daemon = True
            thread.start()

    def parse_scoop_search_results(self, search_output):
        """
        Parses the output of 'scoop search'.
        Returns a list of dictionaries: [{'name': str, 'version': str, 'source': str}, ...]
        """
        results = []
        lines = search_output.strip().split('\n')
        data_started = False
        for line in lines:
            line = remove_ansi_codes(line).strip()
            if not line: continue
            if "----" in line and "Name" not in line: # Data section starts after header separator
                data_started = True
                continue
            if not data_started or "Name " in line and "Version " in line : # Skip header itself
                continue
            
            parts = line.split() # Simple split
            if len(parts) >= 2: # Need at least Name and Version
                name = parts[0]
                version = parts[1]
                source = parts[2] if len(parts) > 2 else "N/A" # Bucket/Source might be missing or combined
                # Avoid adding 'scoop' if it's listed as an app here, usually not intended for search install
                if name.lower() != 'scoop':
                    results.append({'name': name, 'version': version, 'source': source})
        return results

    def parse_scoop_list_apps(self, list_output):
        """
        Parses the output of 'scoop list'.
        Returns a list of dictionaries: [{'name': str, 'version': str, 'source': str, 'info': str}, ...]
        """
        installed_apps = []
        if not list_output:
            return installed_apps
            
        lines = list_output.strip().split('\n')
        data_started = False
        header_skipped = False 

        for line in lines:
            line = remove_ansi_codes(line).strip()
            if not line:
                continue

            if "----" in line and "Name" not in line: 
                data_started = True
                header_skipped = False 
                continue

            if not data_started:
                continue

            if not header_skipped and ("Name " in line and "Version " in line): 
                header_skipped = True
                continue
            if not header_skipped and data_started : # If data started but header not skipped, this is likely an app line
                pass # proceed to parse as app line

            parts = line.split(None, 3) # Split max 3 times: Name, Version, Source, Info (rest)
            if len(parts) >= 2: 
                name = parts[0]
                version = parts[1]
                source = parts[2] if len(parts) >= 3 else "N/A"
                info = parts[3] if len(parts) >= 4 else "" 
                installed_apps.append({'name': name, 'version': version, 'source': source, 'info': info.strip()})
        return installed_apps

    # Removed: _show_search_results_dialog (functionality integrated into search_app and main UI)

    def _handle_install_selected_from_list(self):
        if not self.current_search_results_data: # Check if there's data to select from
            messagebox.showwarning("No Results", "No search results to select from.", parent=self.root)
            return

        selected_iids = self.search_results_treeview.selection()
        if not selected_iids:
            messagebox.showwarning("No Selection", "Please select an app to install.", parent=self.root)
            return
        
        # For single selection ('browse' mode), selection() returns a tuple with one IID
        selected_iid = selected_iids[0]
        selected_index = self.search_results_treeview.index(selected_iid)
        selected_app_info = self.current_search_results_data[selected_index]
        app_to_install = selected_app_info['name']
        if messagebox.askyesno("Confirm Install", f"Are you sure you want to install '{app_to_install}' ({selected_app_info['version']})?", parent=self.root):
            run_scoop_command_threaded(['install', app_to_install], self.status_label, self.root, self.refresh_manage_apps_list)

    def parse_scoop_updates_info(self, status_output):
        """
        Parses the output of 'scoop status' to find available updates for Scoop and apps.
        Returns a dictionary: {'scoop': {'current': 'v1', 'new': 'v2'} or None, 
                               'apps': [{'name': 'app', 'current': 'vA', 'new': 'vB'}, ...]}
        """
        updates = {'scoop': None, 'apps': []}
        added_app_names = set() # Keep track of app names already added
        if not status_output:
            return updates

        lines = status_output.strip().split('\n')
        cleaned_lines = [remove_ansi_codes(line).strip() for line in lines]

        scoop_update_re = re.compile(r"Scoop can be updated from version ([\w.-]+) to ([\w.-]+)\.")
        # Regex for app update line, capturing name, current_version, and new_version from "Update available: X"
        app_update_info_re = re.compile(r"Update available:\s*([\w.+-]+)")

        data_section_started = False # For the table of apps
        for line in cleaned_lines:
            if not line:
                continue

            # Check for Scoop update line (usually at the top)
            scoop_match = scoop_update_re.search(line)
            if scoop_match:
                updates['scoop'] = {'current': scoop_match.group(1), 'new': scoop_match.group(2)}
                continue # Move to next line

            # Detect start of app list (usually after a "----" separator line)
            if "----" in line and "Name" not in line and "Version" not in line: # Avoid matching "Name" in header like "---- Name ----"
                data_section_started = True
                continue

            if not data_section_started:
                continue # Skip lines until the app data section starts

            # Skip header line like "Name Version Source..."
            if line.lower().startswith("name ") and "version" in line.lower():
                continue

            # Process app lines from the table
            parts = line.split() # Simple split by whitespace
            # Expecting at least Name, Installed Version, Latest Version
            if len(parts) >= 3: 
                app_name = parts[0]
                current_version_from_table = parts[1]
                new_version_from_table = parts[2]

                # Default new_version is from the table's "Latest Version" column
                final_new_version = new_version_from_table
                
                # Check if "Update available: X.Y.Z" exists in the *rest* of the line (e.g., Info column).
                # This would override new_version_from_table if found and is more specific.
                # For the typical table output, this regex won't match in parts[3:], 
                # and new_version_from_table will be used.
                if len(parts) > 3:
                    info_string_for_regex = " ".join(parts[3:]) # Check from the 4th part onwards
                    update_match_in_info = app_update_info_re.search(info_string_for_regex)
                    if update_match_in_info:
                        final_new_version = update_match_in_info.group(1)

                # Check if an update is available by comparing versions
                # and ensuring final_new_version is a valid version string
                if current_version_from_table != final_new_version and \
                   final_new_version.lower() not in ["n/a", "-", "unknown", "error", "latest"]:
                    
                    # Avoid adding 'scoop' if it appears in the app list and was already handled
                    # by the dedicated "Scoop can be updated..." line parser, and ensure no duplicates.
                    if app_name.lower() != 'scoop' and app_name not in added_app_names:
                        updates['apps'].append({
                            'name': app_name,
                            'current': current_version_from_table,
                            'new': final_new_version
                        })
                        added_app_names.add(app_name) # Add to set to prevent duplicates
        return updates

    def refresh_manage_apps_list(self): # Renamed
        """
        Refreshes the list of installed apps and available updates.
        Runs 'scoop update' (metadata), 'scoop status' (updates), and 'scoop list' (installed apps).
        """
        # Initial status update on the main thread
        self.status_label.config(text="Refreshing application list...")
        self.status_progress.pack(side=tk.LEFT, padx=5, pady=2)
        self.status_progress.start(10)
        self._clear_manage_apps_list() # Renamed: Clear previous list (UI update, fine on main thread)
        # _setup_manage_apps_list_actions() is called at init and ensures buttons are there

        def _refresh_task_in_thread(): # Renamed: This function will run in a separate thread
            # --- Step 1: Run 'scoop update' to refresh metadata ---
            if not self.root.winfo_exists(): return

            # Schedule status update for 'scoop update' phase
            self.root.after(0, lambda: {
                self.status_label.config(text="Updating Scoop metadata (scoop update)...") if self.root.winfo_exists() else None
            })

            # Run 'scoop update' silently to refresh metadata
            update_stdout, update_stderr, update_returncode = get_scoop_command_output(['update'])

            # Check if the window was closed during the 'scoop update' modal dialog
            if not self.root.winfo_exists(): return

            if update_returncode != 0:
                # Handle 'scoop update' failure
                def _handle_scoop_update_error():
                    if not self.root.winfo_exists(): return
                    self.status_label.config(text="Error during Scoop metadata update.")
                    error_details = update_stderr or update_stdout or "Unknown error during 'scoop update'."
                    # Ensure error_details is a string
                    if not isinstance(error_details, str):
                        error_details = str(error_details)
                    messagebox.showerror("Scoop Update Error",
                                         f"Failed to update Scoop metadata (scoop update).\n"
                                         f"Details: {error_details.strip()}",
                                         parent=self.root)
                    self.status_label.config(text="Ready") # Reset status
                    self._clear_manage_apps_list() # Renamed
                self.root.after(0, _handle_scoop_update_error)
                return

            # --- Step 2: Run 'scoop status' and process ---
            # Set status for the next phase.
            self.root.after(0, lambda: {
                self.status_label.config(text="Fetching app status (scoop status)...") if self.root.winfo_exists() else None
            })

            status_stdout, status_stderr, status_returncode = get_scoop_command_output(['status'])

            if not self.root.winfo_exists(): return # Check again after command

            # --- Helper for UI updates from this thread ---
            def schedule_ui_update(action):
                if self.root.winfo_exists():
                    self.root.after(0, action)

            if status_returncode != 0:
                def _handle_scoop_status_error():
                    if not self.root.winfo_exists(): return
                    self.status_label.config(text="Error fetching status.")
                    error_details = status_stderr or status_stdout or "Unknown error during 'scoop status'."
                    messagebox.showerror("Scoop Status Error",
                                         f"Failed to get app status (scoop status).\n"
                                         f"Details: {error_details.strip()}",
                                         parent=self.root)
                    self.status_label.config(text="Ready") # Reset status
                    self._clear_manage_apps_list() # Renamed
                schedule_ui_update(_handle_scoop_status_error)
                return

            if status_stderr and not status_stdout: # If only errors from status, show them
                schedule_ui_update(lambda: messagebox.showwarning("Scoop Status Warning", f"Scoop status returned warnings/errors:\n{status_stderr}", parent=self.root))
            
            updates_info = self.parse_scoop_updates_info(status_stdout)

            # --- Step 3: Run 'scoop list' and process ---
            schedule_ui_update(lambda: {
                self.status_label.config(text="Fetching installed apps (scoop list)...") if self.root.winfo_exists() else None
            })
            list_stdout, list_stderr, list_returncode = get_scoop_command_output(['list'])

            if not self.root.winfo_exists(): return

            if list_returncode != 0:
                def _handle_scoop_list_error():
                    if not self.root.winfo_exists(): return
                    self.status_label.config(text="Error fetching installed apps.")
                    error_details = list_stderr or list_stdout or "Unknown error during 'scoop list'."
                    messagebox.showerror("Scoop List Error",
                                         f"Failed to get installed apps (scoop list).\n"
                                         f"Details: {error_details.strip()}",
                                         parent=self.root)
                    self.status_label.config(text="Ready")
                    self._clear_manage_apps_list() # Renamed
                schedule_ui_update(_handle_scoop_list_error)
                return
            
            installed_apps_parsed = self.parse_scoop_list_apps(list_stdout)

            # --- Step 4: Combine data ---
            managed_apps_candidates = []
            app_updates_dict = {app['name'].lower(): app for app in updates_info.get('apps', [])}
            scoop_self_update_info = updates_info.get('scoop')

            if scoop_self_update_info:
                managed_apps_candidates.append({
                    'name': 'Scoop (Self-Update)', # Display name for Treeview
                    'original_name': 'scoop', 
                    'current_version': scoop_self_update_info['current'],
                    'new_version': scoop_self_update_info['new'],
                    'status_text': 'Scoop Update Available',
                    'has_update': True,
                    'is_scoop_self': True,
                    'source_bucket': 'Scoop Core' 
                })

            processed_app_names_lower = set(['scoop'] if scoop_self_update_info else [])

            for app_data in installed_apps_parsed:
                original_name = app_data['name']
                original_name_lower = original_name.lower()

                if original_name_lower in processed_app_names_lower: # Already handled (e.g. 'scoop' package by self-update)
                    continue

                current_version_from_list = app_data['version']
                source_bucket = app_data['source']
                update_details = app_updates_dict.get(original_name_lower)

                if update_details:
                    managed_apps_candidates.append({
                        'name': original_name, 'original_name': original_name,
                        'current_version': update_details['current'], 
                        'new_version': update_details['new'],
                        'status_text': 'Update Available', 'has_update': True,
                        'is_scoop_self': False, 'source_bucket': source_bucket
                    })
                else:
                    managed_apps_candidates.append({
                        'name': original_name, 'original_name': original_name,
                        'current_version': current_version_from_list,
                        'new_version': 'N/A', 
                        'status_text': 'Installed', 'has_update': False,
                        'is_scoop_self': False, 'source_bucket': source_bucket
                    })
                processed_app_names_lower.add(original_name_lower)
            
            # Sort: Scoop self-update first, then apps with updates, then other installed, then by name.
            def sort_key(app):
                if app['is_scoop_self']: return (0, app['name'].lower())
                if app['has_update']: return (1, app['name'].lower())
                return (2, app['name'].lower())
            managed_apps_candidates.sort(key=sort_key)

            # --- Step 5: Schedule UI update for populating the list and final status ---
            def _populate_list_and_finalize():
                if not self.root.winfo_exists(): return
                self.current_managed_apps_data = managed_apps_candidates # Renamed
                self.manage_apps_treeview.delete(*self.manage_apps_treeview.get_children()) # Renamed
                
                # Populate the Treeview
                for app_item in managed_apps_candidates:
                    item_tags = ()
                    # Apply bold tag if the app has an update and a new version is specified
                    if app_item.get('has_update', False) and app_item.get('new_version', 'N/A') != 'N/A':
                        item_tags = (self.UPDATED_APP_TAG,)

                    self.manage_apps_treeview.insert('', tk.END, values=( # Renamed
                        app_item['name'],
                        app_item['current_version'],
                        app_item['new_version']
                    ), tags=item_tags)

                self.status_label.config(text="Ready") # Final status
                self.status_progress.stop()
                self.status_progress.pack_forget()
                if not managed_apps_candidates:
                    self.manage_apps_list_title_label.config(text="No applications installed or no updates found.")
                else:
                    self.manage_apps_list_title_label.config(text="Installed Apps & Updates:")
            schedule_ui_update(_populate_list_and_finalize)

        thread = threading.Thread(target=_refresh_task_in_thread) # Renamed
        thread.daemon = True
        thread.start()

    def _handle_update_selected_from_manage_list(self): # Renamed
        if not self.current_managed_apps_data: # Renamed
            messagebox.showwarning("No Items Listed", "No items available in the list to select.", parent=self.root)
            return
        selected_iids = self.manage_apps_treeview.selection() # Renamed
            
        scoop_self_update_selected = False
        apps_to_update_display_names = []
        apps_to_update_original_names = []

        for iid in selected_iids:
            idx = self.manage_apps_treeview.index(iid) # Renamed
            candidate = self.current_managed_apps_data[idx] # Renamed
            
            if candidate['is_scoop_self'] and candidate['has_update']:
                scoop_self_update_selected = True
            elif not candidate['is_scoop_self'] and candidate['has_update']:
                apps_to_update_original_names.append(candidate['original_name'])
                apps_to_update_display_names.append(candidate['name'])
        
        if not scoop_self_update_selected and not apps_to_update_original_names:
            messagebox.showwarning("No Actionable Selection", "Please select Scoop or app(s) with available updates.", parent=self.root)
            return

        confirm_message_parts = []
        if scoop_self_update_selected:
            confirm_message_parts.append("Scoop itself")
        if apps_to_update_display_names:
            confirm_message_parts.append(f"{len(apps_to_update_display_names)} app(s): {', '.join(apps_to_update_display_names)}")

        full_confirm_message = "Are you sure you want to update:\n- " + "\n- ".join(confirm_message_parts)

        if messagebox.askyesno("Confirm Update", full_confirm_message, parent=self.root):
            if scoop_self_update_selected:
                run_scoop_command_threaded(['update'], self.status_label, self.root, self.refresh_manage_apps_list) # This updates scoop itself
            if apps_to_update_original_names:
                # Run updates for apps. Could be one command: scoop update app1 app2 ...
                run_scoop_command_threaded(['update'] + apps_to_update_original_names, self.status_label, self.root, self.refresh_manage_apps_list)
    
    def _handle_uninstall_selected_from_manage_list(self): # Renamed
        if not self.current_managed_apps_data: # Renamed
            messagebox.showwarning("No Items Listed", "No items in the list to select for uninstallation.", parent=self.root)
            return
        
        selected_iids = self.manage_apps_treeview.selection() # Renamed
        if not selected_iids:
            messagebox.showwarning("No Selection", "Please select app(s) to uninstall.", parent=self.root)
            return

        apps_to_uninstall_original_names = []
        apps_to_uninstall_display_names = []
        for iid in selected_iids:
            idx = self.manage_apps_treeview.index(iid) # Renamed
            candidate = self.current_managed_apps_data[idx] # Renamed
            
            if not candidate['is_scoop_self']: # Cannot uninstall "Scoop (Self-Update)" entry
                apps_to_uninstall_original_names.append(candidate['original_name'])
                apps_to_uninstall_display_names.append(candidate['name'])
        
        if not apps_to_uninstall_original_names:
            messagebox.showinfo("No Apps Selected", "No actual applications were selected for uninstallation.\nThe 'Scoop (Self-Update)' entry cannot be uninstalled via this action.", parent=self.root)
            return

        confirm_message = f"Are you sure you want to uninstall the following {len(apps_to_uninstall_display_names)} app(s)?\n- " + "\n- ".join(apps_to_uninstall_display_names)
        if messagebox.askyesno("Confirm Uninstall", confirm_message, parent=self.root):
            run_scoop_command_threaded(['uninstall'] + apps_to_uninstall_original_names, self.status_label, self.root, self.refresh_manage_apps_list)


def main():
    
    # Sets DPI awareness
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    
    root_window = tk.Tk()
    app = ScoopUI(root_window)
    root_window.mainloop()

if __name__ == "__main__":
    main()
