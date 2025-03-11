#!/usr/bin/env python3
import subprocess
import time
import logging
import os
import sys
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("MotoGP-Scheduler")

# Base directory where all scripts are located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# List of scripts to execute in order
SCRIPTS = [
    "get_circuits.py",
    "get_sessions.py", 
    "get_q2results.py",
    "get_results.py",
    "get_scores.py"
]

# Required Python packages for the scripts
REQUIRED_PACKAGES = [
    "gspread",
    "google-auth",
    "google-auth-oauthlib", 
    "google-auth-httplib2",
    "pytz"
]

# Interval between execution cycles (30 minutes in seconds)
INTERVAL = 30 * 60

def check_and_install_dependencies():
    """Check if required packages are installed, and install if missing."""
    logger.info("Checking required dependencies...")
    
    for package in REQUIRED_PACKAGES:
        try:
            # Try to import the package to see if it's installed
            __import__(package)
            logger.debug(f"Package {package} is already installed.")
        except ImportError:
            # If package is not installed, install it using pip
            logger.info(f"Package {package} not found. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                logger.info(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {package}: {e}")
                # Continue anyway to check other packages
    
    logger.info("Dependency check completed.")

def execute_script(script_name):
    """Execute a Python script and wait for it to complete."""
    script_path = os.path.join(BASE_DIR, script_name)
    
    if not os.path.exists(script_path):
        logger.error(f"Script not found: {script_path}")
        return False
    
    try:
        logger.info(f"Starting execution of {script_name}")
        start_time = time.time()
        
        # Run the script and wait for it to complete
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Completed {script_name} in {elapsed_time:.2f} seconds")
        
        # Log script output
        if result.stdout:
            logger.debug(f"Output from {script_name}:\n{result.stdout}")
        
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing {script_name}: {str(e)}")
        logger.error(f"Return code: {e.returncode}")
        if e.stdout:
            logger.error(f"Standard output:\n{e.stdout}")
        if e.stderr:
            logger.error(f"Standard error:\n{e.stderr}")
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error executing {script_name}: {str(e)}")
        return False

def run_cycle():
    """Run one complete cycle of all scripts in sequence."""
    logger.info("Starting new execution cycle")
    
    for script in SCRIPTS:
        success = execute_script(script)
        if not success:
            logger.warning(f"Script {script} failed, continuing with next script")
    
    logger.info("Execution cycle completed")

def main():
    """Main function to run the scheduler."""
    logger.info("MotoGP data update scheduler started")
    
    # Check and install required dependencies first
    check_and_install_dependencies()
    
    try:
        while True:
            cycle_start = time.time()
            
            # Run one complete cycle
            run_cycle()
            
            # Calculate sleep time until next cycle
            elapsed = time.time() - cycle_start
            sleep_time = max(0, INTERVAL - elapsed)
            
            next_run = datetime.now().replace(microsecond=0) + timedelta(seconds=sleep_time)
            logger.info(f"Next execution cycle will start at {next_run}")
            
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
