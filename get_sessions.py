#!/usr/bin/env python3
import requests
import json
import sys
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets configuration
GOOGLE_SHEET_CREDENTIALS_FILE = './google_credentials.json'
GOOGLE_SHEET_URL = 'https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

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

def get_circuits_from_sheet():
    """Fetch circuit data from 'Circuitos' sheet"""
    try:
        gc = get_google_sheet_client()
        if not gc:
            return None
        
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        circuits_sheet = spreadsheet.worksheet("Circuitos")
        
        # Get all circuits data (skipping header row)
        all_data = circuits_sheet.get_all_values()
        if len(all_data) <= 1:  # Only header or empty
            print("No circuit data found in the Circuitos sheet.")
            return []
        
        circuits = []
        # Skip header row (index 0)
        for row in all_data[1:]:
            if len(row) >= 3:  # Make sure we have all required columns
                event_id = row[0]  # Column A: event_id
                circuit_id = row[1]  # Column B: circuit_id
                circuit_name = row[2]  # Column C: circuit_name
                
                circuits.append({
                    "event_id": event_id,
                    "circuit_id": circuit_id,
                    "circuit_name": circuit_name
                })
        
        return circuits
    except Exception as e:
        print(f"Error fetching circuits from sheet: {e}", file=sys.stderr)
        return None

def fetch_sessions(event_uuid):
    """Fetch session data from MotoGP API for a specific event"""
    url = f"https://api.pulselive.motogp.com/motogp/v1/results/sessions?eventUuid={event_uuid}&categoryUuid=e8c110ad-64aa-4e8e-8a86-f2f152f6a942"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching sessions for event {event_uuid}: {e}")
        return None

def extract_session_data(sessions_json, circuit_id, circuit_name):
    """Extract the required session data from JSON response"""
    session_data = []
    
    for session in sessions_json:
        session_id = session.get('id', '')
        shortname = session.get('type', '')
        date_start = session.get('date', '')
        date_end = ''  # Leave empty as specified
        category = session.get('category', {})
        category_id = category.get('id', '')
        category_name = category.get('name', '')
        
        session_data.append([
            circuit_id,
            circuit_name,
            session_id,
            shortname,
            date_start,
            date_end,
            category_id,
            category_name
        ])
    
    return session_data

def save_to_google_sheets(session_data):
    """Save the session data to Google Sheets"""
    if not session_data:
        print("No session data to save.")
        return False
    
    try:
        gc = get_google_sheet_client()
        if not gc:
            return False
        
        # Access the Google Sheet
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        
        # Check if "Sesiones" worksheet exists, otherwise create it
        try:
            worksheet = spreadsheet.worksheet("Sesiones")
            print(f"Found worksheet 'Sesiones', updating existing data...")
            # Clear existing data but keep headers
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Worksheet 'Sesiones' not found. Creating a new one.")
            worksheet = spreadsheet.add_worksheet(title="Sesiones", rows=100, cols=20)
            # Add headers
            headers = [
                'circuit_id', 'circuit_name', 'session_id', 'shortname',
                'date_start', 'date_end', 'category_id', 'category_name'
            ]
            worksheet.append_row(headers)
        
        # Add session data
        print(f"Appending {len(session_data)} rows of session data...")
        worksheet.append_rows(session_data)
        
        print(f"Successfully saved {len(session_data)} sessions to Google Sheets")
        return True
    
    except Exception as e:
        print(f"Error saving sessions to Google Sheet: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

def main():
    """Main function to run the script"""
    print("Fetching circuit data from Google Sheet...")
    circuits = get_circuits_from_sheet()
    
    if not circuits:
        print("Failed to fetch circuit data or no circuits found.")
        return
    
    print(f"Found {len(circuits)} circuits in the sheet.")
    
    all_session_data = []
    
    for circuit in circuits:
        event_id = circuit["event_id"]
        circuit_id = circuit["circuit_id"]
        circuit_name = circuit["circuit_name"]
        
        print(f"Fetching sessions for circuit: {circuit_name} (Event ID: {event_id})...")
        sessions_json = fetch_sessions(event_id)
        
        if sessions_json:
            session_data = extract_session_data(sessions_json, circuit_id, circuit_name)
            if session_data:
                print(f"Found {len(session_data)} sessions for {circuit_name}")
                all_session_data.extend(session_data)
            else:
                print(f"No session data found for {circuit_name}")
        else:
            print(f"Failed to fetch session data for {circuit_name}")
    
    if all_session_data:
        print(f"Total sessions found: {len(all_session_data)}")
        save_to_google_sheets(all_session_data)
    else:
        print("No session data found for any circuit")

if __name__ == "__main__":
    main()
 