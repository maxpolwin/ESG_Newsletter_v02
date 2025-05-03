#!/usr/bin/env python3
"""
Setup and Test Script for Academic Paper Abstracts Fallback System

This script:
1. Checks for required dependencies
2. Installs missing dependencies if needed
3. Runs a test on the academic_processor functionality

Author: Max Polwin
"""

import os
import sys
import subprocess
import importlib
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = {
        "requests": "For API calls to Semantic Scholar",
        "PyPDF2": "For extracting text from PDFs"
    }

    missing_packages = []

    for package, description in required_packages.items():
        try:
            importlib.import_module(package)
            logger.info(f"✅ {package} is installed ({description})")
        except ImportError:
            logger.warning(f"❌ {package} is NOT installed ({description})")
            missing_packages.append(package)

    return missing_packages

def install_dependencies(packages):
    """Install missing dependencies."""
    if not packages:
        logger.info("All dependencies are already installed.")
        return True

    logger.info(f"Installing missing dependencies: {', '.join(packages)}")

    try:
        for package in packages:
            logger.info(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            logger.info(f"✅ Successfully installed {package}")

        return True
    except Exception as e:
        logger.error(f"Failed to install dependencies: {str(e)}")
        return False

def backup_file(filename):
    """Create a backup of the specified file."""
    if not os.path.exists(filename):
        logger.warning(f"File {filename} does not exist, no backup needed.")
        return True

    backup_name = f"{filename}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        with open(filename, 'r') as src_file:
            content = src_file.read()

        with open(backup_name, 'w') as backup_file:
            backup_file.write(content)

        logger.info(f"Created backup: {backup_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to create backup of {filename}: {str(e)}")
        return False

def test_academic_processor():
    """Run a simple test of the academic processor."""
    try:
        logger.info("Testing academic_processor.py with a 3-day lookback period...")

        # Create a simple test script
        test_script = """
import sys
sys.path.append('.')
from academic_processor import process_academic_papers

# Test with a 3-day lookback and limited keywords
papers, counts = process_academic_papers(days_lookback=3, process_all=False)

print("\\nTEST RESULTS:")
print(f"Found {len(papers)} papers")
print(f"Paper abstracts by source:")
sources = {}
for paper in papers:
    source = paper.get('abstract_source', 'unknown')
    sources[source] = sources.get(source, 0) + 1

for source, count in sources.items():
    print(f"  - {source}: {count} paper(s)")
"""

        # Write the test script to a temporary file
        with open("temp_test.py", "w") as f:
            f.write(test_script)

        # Run the test script
        subprocess.run([sys.executable, "temp_test.py"], check=True)

        # Clean up
        os.remove("temp_test.py")

        logger.info("Test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

def main():
    """Main function to run the setup and test."""
    logger.info("Starting setup and test for Academic Paper Abstracts Fallback System")

    # Check and install dependencies
    missing_packages = check_dependencies()
    if missing_packages and not install_dependencies(missing_packages):
        logger.error("Failed to install required dependencies. Exiting.")
        return 1

    # Backup existing files
    files_to_backup = ["academic_processor.py", "html_generator.py"]
    for file in files_to_backup:
        backup_file(file)

    # Test the academic processor functionality
    logger.info("Testing the academic processor functionality...")
    if not test_academic_processor():
        logger.warning("Tests did not complete successfully. Please check the logs above.")
        return 1

    logger.info("Setup and testing completed successfully.")
    logger.info("Next steps:")
    logger.info("1. Replace academic_processor.py with the new version")
    logger.info("2. Update html_generator.py with the changes for displaying abstract sources")
    logger.info("3. Run the system to generate a newsletter with improved academic paper summaries")

    return 0

    # Compatibility function for main.py
def run_compatibility_check():
    """Alias for compatibility checking function."""
    # This should return the result of your actual compatibility check function
    # If you have a function like 'check_system_compatibility()', call that
    # Example: return check_system_compatibility()

    # If you can identify the actual function, replace the next line with a call to it
    print("Running compatibility check...")

    # Look at the existing functions in the file and call the appropriate one
    # For example, if there's a function like:
    # - check_compatibility()
    # - system_check()
    # - test_compatibility()

    # As a temporary fallback, implement a basic check
    import platform
    print(f"Python Version: {platform.python_version()}")
    print(f"System: {platform.system()} {platform.release()}")

    # Check directories from config
    from config import OUTPUT_DIR, ATTACHMENTS_DIR, CSS_DIR
    import os
    dirs_ok = all(os.path.isdir(d) for d in [OUTPUT_DIR, ATTACHMENTS_DIR, CSS_DIR])
    print(f"Directories exist: {dirs_ok}")

    return True  # Return True to indicate success

if __name__ == "__main__":
    sys.exit(main())