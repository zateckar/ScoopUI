import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk # Added ttk
from hidpi_tk import DPIAwareTk
import subprocess
import re # For removing ANSI escape codes
import threading

# Removed: run_scoop_command (functionality integrated into _execute_scoop_action_with_modal_output
# and run_scoop_command_threaded)

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


def _execute_scoop_action_with_modal_output(command_parts, parent_window, status_label):
    """
    Executes a Scoop command (install, uninstall, update) and shows its output
    in a new modal Toplevel dialog with live updates.
    This function is intended to be run in a separate thread.
    """
    dialog_title = f"Scoop: {' '.join(command_parts)}"
    dialog = tk.Toplevel(parent_window)
    dialog.title(dialog_title)
    dialog.geometry("700x450")
    dialog.transient(parent_window)
    dialog.configure(bg=parent_window.cget('bg')) # Match parent background
    
    output_display = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, height=20, state=tk.DISABLED)
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
        progress_label = ttk.Label(progress_frame, text="Running...")
        progress_label.pack(side=tk.LEFT, padx=(0,5))
        # progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=200) # Optional: if you want a visual bar
        # progress_bar.pack(side=tk.LEFT, expand=True, fill=tk.X)
        # progress_bar.start(10)

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
        # if 'progress_bar' in locals() and progress_bar.winfo_exists():
        #     progress_bar.stop()
        #     progress_bar.pack_forget() # Clean up progress bar
        # if 'progress_label' in locals() and progress_label.winfo_exists() and not (process.returncode == 0 or "Error" in progress_label.cget("text")):
        #     # If no specific status was set (e.g. early exit), set a generic one or hide
        #      progress_label.config(text="Operation ended.")

        if dialog.winfo_exists():
            output_display.config(state=tk.DISABLED) # Make text read-only
            # Add close button if not already there
            has_close_button = any(isinstance(child, tk.Button) and child.cget("text") == "Close" for child in dialog.winfo_children())
            if not has_close_button:
                tk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=5)
        
        # Update main status bar after the modal operation is essentially complete
        if status_label and status_label.winfo_exists():
            parent_window.after(0, lambda: status_label.config(text="Ready"))
        
        if dialog.winfo_exists():
            dialog.wait_window() # Blocks until the dialog is destroyed

def run_scoop_command_threaded(command_parts, status_label, parent_window):
    """
    Runs a Scoop action (install, uninstall, update) in a separate thread,
    displaying its output in a modal dialog.
    """
    status_label.config(text=f"Running 'scoop {' '.join(command_parts)}'...")
    thread = threading.Thread(target=_execute_scoop_action_with_modal_output,
                              args=(command_parts, parent_window, status_label))
    thread.daemon = True # Allows main program to exit even if thread is running
    thread.start()

class ScoopUI:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Scoop UI Interface")
        self.root.geometry("850x750") # Increased height for listbox

        # Apply a theme
        style = ttk.Style()
        # print(style.theme_names()) # To see available themes
        style.theme_use('xpnative') # Or 'xpnative', 'clam', 'alt', 'default', 'classic' - 'vista' or 'xpnative' often good on Windows
        
        # --- Main Tabbed Interface ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # --- Updates Tab ---
        self.updates_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.updates_tab, text='Manage Apps')
        self._create_updates_tab_widgets(self.updates_tab)
        
        # --- Search Tab ---
        self.search_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.search_tab, text='Search Apps')
        self._create_search_tab_widgets(self.search_tab)

        # --- Status Bar ---
        self.status_label = ttk.Label(self.root, text="Ready", anchor=tk.W, padding=(5, 2))
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Optionally, load updates when the app starts or when tab is first selected
        # self.manage_updates() # To load updates on startup
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

        self.search_results_scrollbar = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL)
        self.search_results_listbox = tk.Listbox(listbox_container,
                                                 yscrollcommand=self.search_results_scrollbar.set,
                                                 exportselection=False,
                                                 activestyle='none',
                                                 selectmode=tk.SINGLE)
        self.search_results_scrollbar.config(command=self.search_results_listbox.yview)
        self.search_results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0,2)) # Small adjustment for scrollbar
        self.search_results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.search_action_buttons_frame = ttk.Frame(list_display_frame)
        self.search_action_buttons_frame.pack(fill=tk.X, pady=(5,0))
        self.current_search_results_data = []
        self._setup_search_list_actions()

    def _create_updates_tab_widgets(self, parent_frame):
        # Action Frame for Updates
        updates_top_actions_frame = ttk.Frame(parent_frame, padding=(0,10,0,5))
        updates_top_actions_frame.pack(fill=tk.X, padx=10, pady=(10,0), anchor=tk.N)
        self.refresh_updates_button = ttk.Button(updates_top_actions_frame, text="Refresh Update List", command=self.manage_updates)
        self.refresh_updates_button.pack(side=tk.LEFT, pady=5)

        # List Display Frame for Updates
        list_display_frame = ttk.Frame(parent_frame, padding=5)
        list_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.updates_list_title_label = ttk.Label(list_display_frame, text="Available Updates:")
        self.updates_list_title_label.pack(anchor=tk.W, pady=(0,5))

        listbox_container = ttk.Frame(list_display_frame) # Using ttk.Frame for consistency
        listbox_container.pack(fill=tk.BOTH, expand=True)

        self.updates_list_scrollbar = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL)
        self.updates_listbox = tk.Listbox(listbox_container,
                                          yscrollcommand=self.updates_list_scrollbar.set,
                                          exportselection=False,
                                          activestyle='none',
                                          selectmode=tk.MULTIPLE)
        self.updates_list_scrollbar.config(command=self.updates_listbox.yview)
        self.updates_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0,2)) # Small adjustment
        self.updates_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.updates_action_buttons_frame = ttk.Frame(list_display_frame)
        self.updates_action_buttons_frame.pack(fill=tk.X, pady=(5,0))
        self.current_updates_data = []
        self._setup_updates_list_actions()

    def _setup_search_list_actions(self):
        for widget in self.search_action_buttons_frame.winfo_children():
            widget.destroy()
        # self.search_results_listbox.delete(0, tk.END) # Clearing data is handled by _clear_search_results
        # self.current_search_results_data = []
        self.search_list_title_label.config(text="Search Results:")
        ttk.Button(self.search_action_buttons_frame, text="Install Selected", command=self._handle_install_selected_from_list).pack(side=tk.LEFT, padx=(0,5), pady=5)
        ttk.Button(self.search_action_buttons_frame, text="Clear Results", command=self._clear_search_results).pack(side=tk.LEFT, padx=(0,5), pady=5)



    def _clear_search_results(self):
        self.search_results_listbox.delete(0, tk.END)
        self.current_search_results_data = []
        self.search_list_title_label.config(text="Search Results:") # Keep title consistent

    def _setup_updates_list_actions(self):
        for widget in self.updates_action_buttons_frame.winfo_children():
            widget.destroy()
        # self.updates_listbox.delete(0, tk.END) # Clearing data is handled by _clear_updates_list
        # self.current_updates_data = []
        self.updates_list_title_label.config(text="Available Updates:")
        ttk.Button(self.updates_action_buttons_frame, text="Update Selected", command=self._handle_update_selected_from_list).pack(side=tk.LEFT, padx=(0,5), pady=5)
        ttk.Button(self.updates_action_buttons_frame, text="Select All", command=lambda: self.updates_listbox.select_set(0, tk.END)).pack(side=tk.LEFT, padx=(0,5), pady=5)
        ttk.Button(self.updates_action_buttons_frame, text="Uninstall Selected", command=self._handle_uninstall_selected_from_updates_list).pack(side=tk.LEFT, padx=(0,5), pady=5)
        ttk.Button(self.updates_action_buttons_frame, text="Deselect All", command=lambda: self.updates_listbox.select_clear(0, tk.END)).pack(side=tk.LEFT, padx=(0,5), pady=5)
        ttk.Button(self.updates_action_buttons_frame, text="Clear List", command=self._clear_updates_list).pack(side=tk.LEFT, padx=(0,5), pady=5)

    def _clear_updates_list(self):
        self.updates_listbox.delete(0, tk.END)
        self.current_updates_data = []
        self.updates_list_title_label.config(text="Available Updates:") # Keep title consistent

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
            # _setup_search_list_actions() is already called at init and ensures buttons are there
            
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
                    self.current_results_data = search_results
                    self.search_results_listbox.delete(0, tk.END)
                    for item in search_results:
                        self.search_results_listbox.insert(tk.END, f"{item['name']} (Version: {item['version']}, Source: {item['source']})")

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

    # Removed: _show_search_results_dialog (functionality integrated into search_app and main UI)

    def _handle_install_selected_from_list(self):
        if not self.current_search_results_data: # Check if there's data to select from
            messagebox.showwarning("No Results", "No search results to select from.", parent=self.root)
            return

        selected_indices = self.search_results_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select an app to install.", parent=self.root)
            return
        
        selected_app_info = self.current_search_results_data[selected_indices[0]] # Single selection for search
        app_to_install = selected_app_info['name']
        if messagebox.askyesno("Confirm Install", f"Are you sure you want to install '{app_to_install}'?", parent=self.root):
            run_scoop_command_threaded(['install', app_to_install], self.status_label, self.root)

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

    def manage_updates(self):
        """
        Fetches scoop status, parses for updates (Scoop & apps), and shows a dialog to manage them.
        """
        self.status_label.config(text="Fetching update status...")
        self._clear_updates_list() # Clear previous update list
        # _setup_updates_list_actions() is already called at init and ensures buttons are there

        def fetch_and_show_dialog():
            # Run 'scoop status' to get update information
            stdout, stderr, returncode = get_scoop_command_output(['status'])

            if not self.root.winfo_exists():
                return

            if returncode != 0:
                self.status_label.config(text="Error fetching status.")
                messagebox.showerror("Error", f"Failed to get app status: {stderr or stdout or 'Unknown error'}", parent=self.root)
                if self.root.winfo_exists():
                    self.status_label.config(text="Ready") # Reset status
                    self._clear_updates_list() # Clear list area on error
                return

            if stderr and not stdout: # If only errors, show them
                messagebox.showwarning("Scoop Status Warning", f"Scoop status returned errors:\n{stderr}", parent=self.root)
            
            updates_info = self.parse_scoop_updates_info(stdout)

            if not self.root.winfo_exists(): return

            if not updates_info['scoop'] and not updates_info['apps']:
                self.status_label.config(text="Ready")
                messagebox.showinfo("Manage Apps", "No pending updates found for Scoop or applications.", parent=self.root)
                if self.root.winfo_exists(): self._clear_updates_list()
                return

            self.status_label.config(text="Ready")  # Reset status before showing dialog
            
            if self.root.winfo_exists():
                update_candidates = []
                if updates_info['scoop']:
                    s_info = updates_info['scoop']
                    display_text = f"Scoop (Self-Update) (Current: {s_info['current']} -> New: {s_info['new']})"
                    update_candidates.append({'type': 'scoop', 'name': 'scoop', 'text': display_text, 'cmd_parts': ['update']})

                for app_info in sorted(updates_info['apps'], key=lambda x: x['name']): # Sort apps by name
                    display_text = f"{app_info['name']} (Current: {app_info['current']} -> New: {app_info['new']})"
                    update_candidates.append({'type': 'app', 'name': app_info['name'], 'text': display_text, 'cmd_parts': ['update', app_info['name']]})

                self.current_updates_data = update_candidates
                self.updates_listbox.delete(0, tk.END)
                for candidate in update_candidates:
                    self.updates_listbox.insert(tk.END, candidate['text'])

        thread = threading.Thread(target=fetch_and_show_dialog)
        thread.daemon = True
        thread.start()

    def _handle_update_selected_from_list(self):
        if not self.current_updates_data: # Check if there's data to select from
            messagebox.showwarning("No Updates Listed", "No updates available in the list to select.", parent=self.root)
            return
        selected_indices = self.updates_listbox.curselection()
            
        scoop_self_update_selected = False
        selected_app_names_for_message = []

        for i in selected_indices:
            candidate = self.current_updates_data[i]
            if candidate['type'] == 'scoop':
                scoop_self_update_selected = True
            elif candidate['type'] == 'app':
                selected_app_names_for_message.append(candidate['name'])
        
        if not scoop_self_update_selected and not selected_app_names_for_message:
            messagebox.showwarning("No Selection", "Please select Scoop or at least one app to update.", parent=self.root)
            return

        confirm_message_parts = []
        if scoop_self_update_selected:
            confirm_message_parts.append("Scoop itself")
        if selected_app_names_for_message:
            confirm_message_parts.append(f"{len(selected_app_names_for_message)} app(s): {', '.join(selected_app_names_for_message)}")

        full_confirm_message = "Are you sure you want to update:\n- " + "\n- ".join(confirm_message_parts)

        if messagebox.askyesno("Confirm Update", full_confirm_message, parent=self.root):
            if scoop_self_update_selected:
                run_scoop_command_threaded(['update'], self.status_label, self.root) # This updates scoop itself
            if selected_app_names_for_message:
                # Run updates for apps. Could be one command: scoop update app1 app2 ...
                run_scoop_command_threaded(['update'] + selected_app_names_for_message, self.status_label, self.root)
    
    def _handle_uninstall_selected_from_updates_list(self):
        if not self.current_updates_data: # Check if there's data to select from
            messagebox.showwarning("No Updates Listed", "No items in the list to select for uninstallation.", parent=self.root)
            return
        
        selected_indices = self.updates_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select app(s) to uninstall.", parent=self.root)
            return

        apps_to_uninstall = []
        for i in selected_indices:
            candidate = self.current_updates_data[i]
            # Only allow uninstalling actual apps, not 'scoop' self-update entry
            if candidate['type'] == 'app':
                apps_to_uninstall.append(candidate['name'])
        
        if not apps_to_uninstall:
            messagebox.showinfo("No Apps Selected", "No actual applications were selected for uninstallation (Scoop self-update cannot be uninstalled this way).", parent=self.root)
            return

        confirm_message = f"Are you sure you want to uninstall the following {len(apps_to_uninstall)} app(s)?\n- " + "\n- ".join(apps_to_uninstall)
        if messagebox.askyesno("Confirm Uninstall", confirm_message, parent=self.root):
            run_scoop_command_threaded(['uninstall'] + apps_to_uninstall, self.status_label, self.root)


def main():
    root_window = DPIAwareTk()
    app = ScoopUI(root_window)
    root_window.mainloop()

if __name__ == "__main__":
    main()
