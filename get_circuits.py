#!/usr/bin/env python3
import requests
import json
import sys
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets configuration - using the same as in get_sessions.py
GOOGLE_SHEET_CREDENTIALS_FILE = './google_credentials.json'
GOOGLE_SHEET_URL = 'https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXXXXXXXXXXX'

def get_google_sheet_client():
    """Initialize and return Google Sheets client"""
    try:
        scopes = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(GOOGLE_SHEET_CREDENTIALS_FILE, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Error initializing Google Sheets client: {e}", file=sys.stderr)
        return None

def fetch_circuits():
    """Fetch circuit data from MotoGP API for 2025 season"""
    url = "https://api.motogp.pulselive.com/motogp/v1/results/events?seasonUuid=ae6c6f0d-c652-44f8-94aa-420fc5b3dab4&test=false"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def extract_circuit_data(circuits_json):
    """Extract the required circuit data from JSON response"""
    circuit_data = []
    
    for circuit in circuits_json:
        event_id = circuit.get('id', '')
        circuit_id = circuit.get('circuit', {}).get('id', '')
        circuit_name = circuit.get('circuit', {}).get('name', '')
        date_start = circuit.get('date_start', '')
        date_end = circuit.get('date_end', '')
        hashtag = circuit.get('name', '')
        
        circuit_data.append([event_id, circuit_id, circuit_name, date_start, date_end, hashtag])
    
    return circuit_data

def save_to_google_sheets(circuit_data):
    """Save the circuit data to Google Sheets"""
    if not circuit_data:
        print("No circuit data to save.")
        return False
    
    try:
        gc = get_google_sheet_client()
        if not gc:
            return False
        
        # Access the Google Sheet using URL instead of name
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        
        # First get all worksheet names to check what's available
        all_worksheets = [ws.title for ws in spreadsheet.worksheets()]
        print(f"Available worksheets: {all_worksheets}")
        
        # Use 'Circuitos' with capital C as shown in the worksheet list
        worksheet_name = 'Circuitos'
        
        # Get the existing worksheet without trying to create a new one
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            print(f"Found worksheet '{worksheet_name}', updating existing data...")
            # Clear existing data but keep headers
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Worksheet '{worksheet_name}' not found. Creating a new one.")
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=100, cols=20)
            # Add headers
            headers = ['event_id', 'id', 'circuit_name', 'date_start', 'date_end', 'hashtag']
            worksheet.append_row(headers)
        
        # Add circuit data
        print(f"Appending {len(circuit_data)} rows of circuit data...")
        worksheet.append_rows(circuit_data)
        
        print(f"Successfully saved {len(circuit_data)} circuits to Google Sheets")
        return True
    
    except Exception as e:
        print(f"Error saving circuits to Google Sheet: {e}", file=sys.stderr)
        print(f"Exception type: {type(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

def main():
    """Main function to run the script"""
    print("Fetching MotoGP 2025 circuit data...")
    circuits_json = fetch_circuits()
    
    if circuits_json:
        circuit_data = extract_circuit_data(circuits_json)
        if circuit_data:
            print(f"Found {len(circuit_data)} circuits")
            save_to_google_sheets(circuit_data)
        else:
            print("No circuit data found")
    else:
        print("Failed to fetch circuit data")

if __name__ == "__main__":
    main()
