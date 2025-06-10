# Scoop UI Interface

A graphical user interface (GUI) for managing Scoop, the command-line installer for Windows. This application provides an intuitive way to search, install, update, and manage your Scoop applications without needing to use the terminal directly.

![{7075F18D-B871-44EE-A3CD-9174AA2BC714}](https://github.com/user-attachments/assets/75d9fa98-6c22-4960-b40a-b2663984da66)


## Features

*   **Tabbed Interface:**
    *   **Manage Apps:**
        *   View available updates for Scoop itself and installed applications.
        *   Select and update Scoop or individual/multiple applications.
        *   Select and uninstall applications from the list.
        *   Refresh the list of available updates.
        *   Select/Deselect All and Clear List options for managing the update list.
    *   **Search Apps:**
        *   Search for applications available in Scoop buckets.
        *   View search results including app name, version, and source bucket.
        *   Install applications directly from the search results.
        *   Clear search results.
*   **Live Command Output:** For operations like install, uninstall, and update, a modal dialog displays the live output from Scoop, keeping you informed of the progress.
*   **Asynchronous Operations:** Scoop commands are run in separate threads to keep the UI responsive.
*   **Status Bar:** Provides feedback on the current operation (e.g., "Ready", "Searching...", "Running command...").
*   **Error Handling:** Displays informative messages for common issues like Scoop not being found or command failures.
*   **DPI Aware:** Utilizes `hidpi_tk` for better scaling on high-DPI displays.
*   **Modern Look and Feel:** Uses `ttk` themed widgets.

## Prerequisites

*   **Python 3.x**
*   **Scoop:** Must be installed and configured in your system's PATH. You can install Scoop by following the instructions at scoop.sh.
*   **Tkinter:** Usually included with standard Python installations.
*   **hidpi_tk:** A Python package for DPI awareness in Tkinter. You can install it via pip:
    ```bash
    pip install hidpi-tk
    ```

## How to Run

1.  Ensure all prerequisites are met.
2.  Save the script as a Python file (e.g., `scoop_ui.py`).
3.  Run the script from your terminal:
    ```bash
    python scoop_ui.py
    ```
    Or, if your Python launcher is configured:
    ```bash
    py scoop_ui.py
    ```

## Usage

### Main Window

The application opens with a tabbed interface. A status bar at the bottom indicates the current state of the application.

### Manage Apps Tab

*   **Refresh Update List:** Click this button to run `scoop status` and populate the list below with any available updates for Scoop itself or your installed applications.
*   **Updates List:** Displays applications that have pending updates.
    *   You can select one or more applications (or Scoop itself if an update is available).
*   **Action Buttons:**
    *   **Update Selected:** Updates the selected items in the list.
    *   **Select All:** Selects all items in the updates list.
    *   **Uninstall Selected:** Uninstalls the selected applications (Scoop self-update entry cannot be uninstalled this way).
    *   **Deselect All:** Clears all selections in the list.
    *   **Clear List:** Clears the contents of the updates list.

### Search Apps Tab

*   **App Name Entry:** Type the name (or part of the name) of the application you want to search for.
*   **Search Button:** Initiates a `scoop search` command with the provided query.
*   **Search Results List:** Displays applications matching your search query, along with their version and source bucket.
    *   You can select a single application from this list.
*   **Action Buttons:**
    *   **Install Selected:** Installs the application selected in the search results list.
    *   **Clear Results:** Clears the current search results from the list.

### Command Output Dialog

When you initiate an install, uninstall, or update operation, a new window will appear. This window shows the live output from the Scoop command as it executes. It also includes a progress label. Once the command is complete, a "Close" button will appear, allowing you to close this dialog.

## Dependencies

*   Python 3
*   Tkinter (standard library)
*   `ttk` (part of Tkinter)
*   `hidpi_tk` (external library)

## Notes

*   The application relies on the `scoop` command being accessible in your system's PATH.
*   Long-running operations like installing large applications or updating many apps will take time, but the UI should remain responsive. The output dialog will show the progress.

