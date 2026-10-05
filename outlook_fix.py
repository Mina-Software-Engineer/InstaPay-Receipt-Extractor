import os
import sys
import subprocess


def fix():
    print("--- Starting pywin32 Clean Repair ---")

    # 1. Uninstall existing
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "pywin32"], check=False)

    # 2. Install fresh
    subprocess.run([sys.executable, "-m", "pip", "install", "pywin32"], check=True)

    # 3. Find the post-install script location
    import site
    packages = site.getsitepackages()
    script_found = False

    for p in packages:
        script_path = os.path.join(p, "pywin32_postinstall.py")
        if os.path.exists(script_path):
            print(f"Found script at: {script_path}")
            subprocess.run([sys.executable, script_path, "-install"], check=True)
            script_found = True
            break

    if not script_found:
        # Try Scripts folder in venv
        scripts_path = os.path.join(sys.prefix, "Scripts", "pywin32_postinstall.py")
        if os.path.exists(scripts_path):
            print(f"Found script at: {scripts_path}")
            subprocess.run([sys.executable, scripts_path, "-install"], check=True)
            script_found = True

    if script_found:
        print("\n--- Repair Complete! ---")
        try:
            import win32com.client
            print("Verification: SUCCESS! win32com is now working.")
        except Exception as e:
            print(f"Verification: FAILED. Error: {e}")
    else:
        print("\n--- ERROR: Could not find pywin32_postinstall.py ---")


if __name__ == "__main__":
    fix()
