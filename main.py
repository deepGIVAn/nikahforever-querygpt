import subprocess
import sys
import time
import os

def main():
    print("Starting backend and frontend...")
    
    # Commands to run
    backend_cmd = ["uv", "run", "uvicorn", "app.main:app", "--port", "8000"]
    frontend_cmd = ["uv", "run", "streamlit", "run", "app/frontend.py"]
    
    # Use shell=True on Windows to ensure executable resolution is reliable
    use_shell = os.name == 'nt'
    
    try:
        # Start backend process
        backend_process = subprocess.Popen(
            backend_cmd,
            shell=use_shell
        )
        
        # Start frontend process
        frontend_process = subprocess.Popen(
            frontend_cmd,
            shell=use_shell
        )
        
        print("Both services are running.")
        print("Press Ctrl+C to terminate both services.")
        
        # Monitor processes
        while True:
            # Check if backend has exited
            backend_status = backend_process.poll()
            if backend_status is not None:
                print(f"Backend exited with status code {backend_status}")
                break
                
            # Check if frontend has exited
            frontend_status = frontend_process.poll()
            if frontend_status is not None:
                print(f"Frontend exited with status code {frontend_status}")
                break
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nCtrl+C detected, shutting down services...")
    finally:
        # Gracefully stop backend
        if 'backend_process' in locals() and backend_process.poll() is None:
            print("Terminating backend...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force killing backend...")
                backend_process.kill()
                
        # Gracefully stop frontend
        if 'frontend_process' in locals() and frontend_process.poll() is None:
            print("Terminating frontend...")
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force killing frontend...")
                frontend_process.kill()
                
    print("Cleanup complete. Goodbye!")

if __name__ == "__main__":
    main()
