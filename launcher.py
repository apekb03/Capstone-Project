import os
import sys
import time
import subprocess

def start_game():
    # Starts main.py using the exact same python version running this script
    print("\n[LAUNCHER] Starting game...")
    return subprocess.Popen([sys.executable, "main.py"])

def main():
    target_file = "main.py"
    
    if not os.path.exists(target_file):
        print(f"Error: {target_file} not found in this directory.")
        return

    # Get the initial "last modified" timestamp of main.py
    last_mtime = os.path.getmtime(target_file)
    process = start_game()

    try:
        while True:
            time.sleep(0.5) # Check for changes every half second
            current_mtime = os.path.getmtime(target_file)
            
            # If the file was saved/modified
            if current_mtime != last_mtime:
                print("\n[LAUNCHER] Changes detected! Reloading instantly...")
                last_mtime = current_mtime
                
                # Kill the old game process and start a new one
                process.terminate()
                process.wait() 
                process = start_game()
                
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Stopping...")
        process.terminate()

if __name__ == "__main__":
    main()