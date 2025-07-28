from data_pipeline import run_pipeline
import time

while True:
    run_pipeline()
    time.sleep(900)  # Run every 15 mins 
