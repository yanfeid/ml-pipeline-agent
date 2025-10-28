# run_ui.py

import subprocess
import sys
import os

def main():
    ui_path = os.path.join(os.path.dirname(__file__), "frontend", "ui.py")
    
    # Ensure the path exists
    if not os.path.isfile(ui_path):
        print(f"Error: Could not find UI script at {ui_path}")
        sys.exit(1)
    
    # Run the Streamlit app
    subprocess.run(["python", "-m", "streamlit", "run", ui_path])

if __name__ == "__main__":
    main()
