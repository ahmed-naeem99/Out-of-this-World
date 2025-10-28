import time
import sys
import traceback
from datetime import datetime

# Import the functions from your data_pipeline.py
try:
    from data_pipeline import run_pipeline, DEFAULT_BBOX
except ImportError:
    sys.exit(1)


def get_last_bbox():
    """
    Reads the last-used BBOX from the tracking file.
    If the file doesn't exist, it returns the default BBOX.
    """
    try:
        with open("last_bbox.txt", "r") as f:
            bbox_from_file = f.read().strip()
            if bbox_from_file:
                return bbox_from_file
            else:
                return DEFAULT_BBOX
    except FileNotFoundError:
        return DEFAULT_BBOX
    except Exception as e:
        return DEFAULT_BBOX


def main_loop():
    print("--- Smart Loop Service (15 min) Started ---")
    while True:
        bbox_to_run = get_last_bbox()
        
        try:
            run_pipeline(bbox_str=bbox_to_run)
            
        except Exception as e:
            traceback.print_exc()

        time.sleep(900) 

if __name__ == "__main__":
    main_loop()