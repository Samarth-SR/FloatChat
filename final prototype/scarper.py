# scraper.py

import requests
from bs4 import BeautifulSoup
import re
import json
import sqlite3
import time
from datetime import datetime

# --- Configuration ---
BASE_URL = "https://incois.gov.in/OON/"
DATABASE_FILE = "ocean_data.db" # This MUST be the same database file your backend uses

# --- Step 1: Get the list of all available buoys ---
def get_buoy_list():
    """Scrapes the main page to get a list of all buoy IDs."""
    print("Fetching the list of all available buoys...")
    try:
        response = requests.get(f"{BASE_URL}/index.jsp")
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        
        # Find the dropdown menu (select element) named 'buoy'
        buoy_select = soup.find('select', {'name': 'buoy'})
        if not buoy_select:
            print("Error: Could not find the buoy dropdown menu on the main page.")
            return []
            
        # Extract all option values, skipping the first "Select Buoy" option
        buoys = [option['value'] for option in buoy_select.find_all('option') if option.get('value')]
        print(f"Found {len(buoys)} buoys: {buoys}")
        return buoys
    except requests.exceptions.RequestException as e:
        print(f"Error fetching buoy list: {e}")
        return []

# --- Step 2: For a given buoy, get its available parameters ---
def get_parameters_for_buoy(buoy_id):
    """Visits a buoy's page to find what parameters it measures."""
    print(f"  - Getting parameters for buoy '{buoy_id}'...")
    try:
        url = f"{BASE_URL}/line-graph.jsp?buoy={buoy_id}"
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        
        param_select = soup.find('select', {'name': 'parameter'})
        if not param_select:
            return []
            
        params = [option['value'] for option in param_select.find_all('option') if option.get('value')]
        return params
    except requests.exceptions.RequestException:
        return [] # Silently fail if a buoy page doesn't load

# --- Step 3 & 4: Get data for a specific buoy and parameter ---
def get_data_for_parameter(buoy_id, parameter_name):
    """Submits the form to get the data page and parses the chart data."""
    print(f"    - Fetching data for parameter '{parameter_name}'...")
    try:
        url = f"{BASE_URL}/line-graph.jsp"
        # This payload mimics the form submission
        payload = {
            'buoy': buoy_id,
            'parameter': parameter_name,
            'period': '1', # '1' seems to correspond to the last 10 days
            'submit': 'Submit'
        }
        
        response = requests.post(url, data=payload)
        response.raise_for_status()
        
        # The data is in a JavaScript variable, so we use regex to find it
        match = re.search(r"var chartData\s*=\s*(\[.*?\]);", response.text, re.DOTALL)
        if not match:
            return []
            
        # The regex captures the JSON part of the string
        json_data_string = match.group(1)
        chart_data = json.loads(json_data_string)
        return chart_data
        
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return []

# --- Step 5: Main Orchestration and Database Insertion ---
def main():
    """Main function to run the scraper and populate the database."""
    
    # Connect to the SQLite database
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Optional: Clear old data from the table before inserting new data
    print(f"Clearing old data from 'sensor_data' table in {DATABASE_FILE}...")
    cursor.execute("DELETE FROM sensor_data")
    conn.commit()

    buoys = get_buoy_list()
    if not buoys:
        print("Could not retrieve buoy list. Exiting.")
        return

    for buoy in buoys:
        print(f"\nProcessing Buoy: {buoy}")
        # Be respectful to their server
        time.sleep(2)
        
        parameters = get_parameters_for_buoy(buoy)
        if not parameters:
            print(f"  - No parameters found for {buoy}. Skipping.")
            continue
        
        print(f"  - Found {len(parameters)} parameters: {parameters}")
        
        for param in parameters:
            time.sleep(2) # Another delay before the final data request
            
            data_points = get_data_for_parameter(buoy, param)
            if not data_points:
                print(f"    - No data found for '{param}'.")
                continue
                
            print(f"    - Found {len(data_points)} data points for '{param}'. Inserting into database...")
            
            records_to_insert = []
            for point in data_points:
                # The website provides timestamps in milliseconds
                ts_ms = int(point['date'])
                dt_object = datetime.fromtimestamp(ts_ms / 1000)
                
                # The website provides depth in the parameter name itself
                depth = None
                if '@' in param:
                    try:
                        # Attempt to parse depth like 'Water Temperature @ 050m'
                        depth_str = param.split('@')[1].strip().replace('m', '')
                        depth = int(depth_str)
                    except (ValueError, IndexError):
                        depth = None # Handle cases where parsing fails

                records_to_insert.append((
                    dt_object.isoformat(),
                    buoy,
                    param,
                    depth,
                    float(point['value'])
                ))
            
            # Insert all records for this parameter in a single transaction
            cursor.executemany(
                "INSERT INTO sensor_data (timestamp, sensor_id, parameter_name, depth_m, value) VALUES (?, ?, ?, ?, ?)",
                records_to_insert
            )
            conn.commit()

    print("\nScraping complete. Database has been populated with fresh data.")
    conn.close()

if __name__ == '__main__':
    main()