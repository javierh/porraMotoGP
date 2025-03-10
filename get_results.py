#!/usr/bin/env python3
import requests
import json
import sys
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets configuration
GOOGLE_SHEET_CREDENTIALS_FILE = './google_credentials.json'
GOOGLE_SHEET_URL = 'https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

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

def get_race_sessions_from_sheet():
    """Fetch race sessions (SPR or RAC) from 'Sesiones' sheet"""
    try:
        gc = get_google_sheet_client()
        if not gc:
            return None
        
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        sessions_sheet = spreadsheet.worksheet("Sesiones")
        
        # Get all sessions data (skipping header row)
        all_data = sessions_sheet.get_all_values()
        if len(all_data) <= 1:  # Only header or empty
            print("No session data found in the Sesiones sheet.")
            return []
        
        race_sessions = []

        # Skip header row (index 0)
        for row in all_data[1:]:
            if len(row) >= 4:  # Make sure we have all required columns
                circuit_id = row[0]  # Column A: circuit_id 
                circuit_name = row[1]  # Column B: circuit_name
                session_id = row[2]  # Column C: session_id
                shortname = row[3]  # Column D: shortname
                
                # Use shortname (column D) as event_name
                event_id = session_id
                event_name = shortname  # Use column D value as event_name
                
                # Check if this row has "SPR" or "RAC"
                if shortname in ["SPR", "RAC"]:
                    race_sessions.append({
                        "circuit_id": circuit_id,
                        "circuit_name": circuit_name,
                        "event_id": event_id,
                        "event_name": event_name,
                        "session_id": session_id,
                        "type": shortname
                    })
                    print(f"Found {shortname} session for: {circuit_name}")
        
        return race_sessions
    except Exception as e:
        print(f"Error fetching race sessions from sheet: {e}", file=sys.stderr)
        return None

def fetch_session_results(session_id):
    """Fetch session results from MotoGP API for a specific session"""
    url = f"https://api.pulselive.motogp.com/motogp/v1/results/session/{session_id}/classification?test=false"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching results for session {session_id}: {e}")
        return None

def extract_rider_data(results_json, circuit_id, circuit_name, event_id, event_name):
    """Extract the required rider data from JSON response"""
    rider_data = []
    
    try:
        # Check if the results contain a classification object
        if isinstance(results_json, dict) and 'classification' in results_json:
            classification_data = results_json['classification']
            
            if isinstance(classification_data, list):
                for rider in classification_data:
                    rider_id = rider.get('rider', {}).get('id', '')
                    rider_name = rider.get('rider', {}).get('full_name', '')
                    
                    # Get position (represents finished value)
                    position = rider.get('position', '')
                    
                    # Get gap from gap.first
                    gap = rider.get('gap', {}).get('first', '')
                    
                    rider_data.append([
                        circuit_id,
                        circuit_name,
                        event_id,
                        event_name,
                        rider_id,
                        rider_name,
                        position,
                        gap
                    ])
            else:
                print(f"Classification data is not a list: {type(classification_data)}")
        # Handle other response formats we've seen before
        elif isinstance(results_json, dict):
            # Look for classification data in common fields
            classification_data = None
            
            # Check common field names where classification data might be stored
            possible_fields = ['classification', 'items', 'results', 'riders', 'data']
            
            for field in possible_fields:
                if field in results_json and isinstance(results_json[field], list):
                    classification_data = results_json[field]
                    break
            
            # If we found a suitable list field, process it
            if classification_data:
                for rider in classification_data:
                    rider_id = rider.get('rider', {}).get('id', '')
                    rider_name = rider.get('rider', {}).get('full_name', '')
                    
                    # Get position (represents finished value)
                    position = rider.get('position', '')
                    
                    # Get gap - try the nested structure first, then direct
                    gap = ""
                    if 'gap' in rider and isinstance(rider['gap'], dict):
                        gap = rider['gap'].get('first', '')
                    else:
                        gap = rider.get('gap', '')
                    
                    rider_data.append([
                        circuit_id,
                        circuit_name,
                        event_id,
                        event_name,
                        rider_id,
                        rider_name,
                        position,
                        gap
                    ])
            else:
                print("Could not find rider classification data in the response.")
                print(f"Response keys: {list(results_json.keys())}")
        
        # Handle list response format
        elif isinstance(results_json, list):
            for rider in results_json:
                rider_id = rider.get('rider', {}).get('id', '')
                rider_name = rider.get('rider', {}).get('full_name', '')
                
                # Get position (represents finished value)
                position = rider.get('position', '')
                
                # Get gap - try nested structure first, then direct
                gap = ""
                if 'gap' in rider and isinstance(rider['gap'], dict):
                    gap = rider['gap'].get('first', '')
                else:
                    gap = rider.get('gap', '')
                
                rider_data.append([
                    circuit_id,
                    circuit_name,
                    event_id,
                    event_name,
                    rider_id,
                    rider_name,
                    position,
                    gap
                ])
        else:
            print(f"Unexpected API response format: {type(results_json)}")
    except Exception as e:
        print(f"Error extracting rider data: {e}")
        import traceback
        traceback.print_exc()
    
    return rider_data

def save_to_google_sheets(rider_data):
    """Save the rider data to Google Sheets"""
    if not rider_data:
        print("No rider data to save.")
        return False
    
    try:
        gc = get_google_sheet_client()
        if not gc:
            return False
        
        # Access the Google Sheet
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        
        # Check if "Resultados" worksheet exists, otherwise create it
        try:
            worksheet = spreadsheet.worksheet("Resultados")
            print(f"Found worksheet 'Resultados', updating existing data...")
            # Clear existing data but keep headers
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Worksheet 'Resultados' not found. Creating a new one.")
            worksheet = spreadsheet.add_worksheet(title="Resultados", rows=100, cols=20)
            # Add headers
            headers = [
                'circuit_id', 'circuit_name', 'event_id', 'event_name',
                'rider_id', 'rider_name', 'position', 'gap'
            ]
            worksheet.append_row(headers)
        
        # Add rider data
        print(f"Appending {len(rider_data)} rows of rider data...")
        worksheet.append_rows(rider_data)
        
        print(f"Successfully saved {len(rider_data)} rider results to Google Sheets")
        return True
    
    except Exception as e:
        print(f"Error saving rider data to Google Sheet: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

def main():
    """Main function to run the script"""
    print("Fetching race sessions from Google Sheet...")
    race_sessions = get_race_sessions_from_sheet()
    
    if not race_sessions:
        print("Failed to fetch race sessions or no race sessions found.")
        return
    
    print(f"Found {len(race_sessions)} race sessions in the sheet.")
    
    all_rider_data = []
    
    for session in race_sessions:
        circuit_id = session["circuit_id"]
        circuit_name = session["circuit_name"]
        event_id = session["event_id"]
        event_name = session["event_name"]
        session_id = session["session_id"]
        session_type = session["type"]
        
        print(f"Fetching results for {session_type} at: {circuit_name} (Session ID: {session_id})...")
        results_json = fetch_session_results(session_id)
        
        if results_json:
            rider_data = extract_rider_data(results_json, circuit_id, circuit_name, event_id, event_name)
            if rider_data:
                print(f"Found {len(rider_data)} rider results for {circuit_name}")
                all_rider_data.extend(rider_data)
            else:
                print(f"No rider data found for {circuit_name}")
        else:
            print(f"Failed to fetch rider data for {circuit_name}")
    
    if all_rider_data:
        print(f"Total rider results found: {len(all_rider_data)}")
        save_to_google_sheets(all_rider_data)
    else:
        print("No rider data found for any race session")

if __name__ == "__main__":
    main()
