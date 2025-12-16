import time
import sys
import traceback
from datetime import datetime

# Import the functions from your data_pipeline.py
try:
    from data_pipeline import run_pipeline, DEFAULT_BBOX
except ImportError:
    sys.exit(1)


def main_loop():
    print("--- Smart Loop Service (15 min) Started ---")
    while True:
        # Always use DEFAULT_BBOX from .env file
        bbox_to_run = DEFAULT_BBOX
        
        try:
            run_pipeline(bbox_str=bbox_to_run)
            
        except Exception as e:
            traceback.print_exc()

        time.sleep(900) 

if __name__ == "__main__":
    main_loop()