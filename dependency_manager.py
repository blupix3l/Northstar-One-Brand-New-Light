import sys
import subprocess
import importlib.util
import os

# Mapping of import names to pip package names
LIBRARY_MAPPING = {
    "PyQt6": "PyQt6",
    "PyQt6.QtWebEngineWidgets": "PyQt6-WebEngine",
    "requests": "requests",
    "keyring": "keyring",
    "PIL": "Pillow",
    "duckduckgo_search": "duckduckgo_search",
    "firecrawl": "firecrawl",
}

def is_library_installed(lib_name):
    """Check if a library is installed by its import name."""
    # Special case for PIL (Pillow)
    if lib_name == "PIL":
        spec = importlib.util.find_spec("PIL")
        return spec is not None
    
    spec = importlib.util.find_spec(lib_name)
    return spec is not None

def install_library(package_name):
    """Install a package using pip."""
    print(f"Installing missing dependency: {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"Successfully installed {package_name}.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e}")
        return False

def check_and_install_dependencies():
    """Iterate through the required libraries and install them if missing."""
    print("Checking NorthStar dependencies...")
    missing_libs = []
    
    for import_name, package_name in LIBRARY_MAPPING.items():
        if not is_library_installed(import_name):
            print(f"Library '{import_name}' (package: {package_name}) is missing.")
            missing_libs.append(package_name)
    
    if not missing_libs:
        print("All dependencies are already installed.")
        return True
    
    success = True
    for package in missing_libs:
        if not install_library(package):
            success = False
            
    if success:
        print("All missing dependencies have been installed.")
    else:
        print("Some dependencies could not be installed automatically. Please install them manually.")
        
    return success

if __name__ == "__main__":
    check_and_install_dependencies()
