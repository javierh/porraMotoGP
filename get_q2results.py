#!/usr/bin/env python3
import requests
import json
import sys
import gspread
import datetime
from google.oauth2.service_account import Credentials

# Google Sheets configuration
GOOGLE_SHEET_CREDENTIALS_FILE = './google_credentials.json'
GOOGLE_SHEET_URL = 'https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXXXXXXXXXXXX'

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

def get_q2_sessions_from_sheet():
    """Fetch Q2 sessions from 'Sesiones' sheet by finding consecutive Q entries"""
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
        
        q2_sessions = []
        prev_row = None

        # Skip header row (index 0)
        for i, row in enumerate(all_data[1:], 1):
            if len(row) >= 4:  # Make sure we have all required columns
                circuit_id = row[0]  # Column A: circuit_id 
                circuit_name = row[1]  # Column B: circuit_name
                session_id = row[2]  # Column C: session_id
                shortname = row[3]  # Column D: shortname
                
                # Check if this row has "Q" and previous row also had "Q"
                if shortname == "Q" and prev_row is not None and prev_row[3] == "Q":
                    q2_sessions.append({
                        "circuit_id": circuit_id,
                        "circuit_name": circuit_name,
                        "session_id": session_id
                    })
                    print(f"Found Q2 session for: {circuit_name}")
                
                prev_row = row
        
        return q2_sessions
    except Exception as e:
        print(f"Error fetching Q2 sessions from sheet: {e}", file=sys.stderr)
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

def extract_rider_data(results_json, circuit_id, circuit_name, session_id):
    """Extract the required rider data from JSON response"""
    rider_data = []
    current_timestamp = datetime.datetime.now().isoformat()
    
    try:
        # Handle dictionary response format
        if isinstance(results_json, dict):
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
                    lap_time = rider.get('best_lap', {}).get('time', '')
                    
                    rider_data.append([
                        circuit_id,
                        circuit_name,
                        session_id,
                        rider_id,
                        rider_name,
                        lap_time,
                        current_timestamp
                    ])
            else:
                # If we couldn't find a suitable field, log the structure for debugging
                print("Could not find rider classification data in the response.")
                print(f"Response keys: {list(results_json.keys())}")
        
        # Handle list response format (existing code)
        elif isinstance(results_json, list):
            for rider in results_json:
                rider_id = rider.get('rider', {}).get('id', '')
                rider_name = rider.get('rider', {}).get('full_name', '')
                lap_time = rider.get('best_lap', {}).get('time', '')
                
                rider_data.append([
                    circuit_id,
                    circuit_name,
                    session_id,
                    rider_id,
                    rider_name,
                    lap_time,
                    current_timestamp
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
        
        # Check if "Q2" worksheet exists, otherwise create it
        try:
            worksheet = spreadsheet.worksheet("Q2")
            print(f"Found worksheet 'Q2', updating existing data...")
            # Clear existing data but keep headers
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Worksheet 'Q2' not found. Creating a new one.")
            worksheet = spreadsheet.add_worksheet(title="Q2", rows=100, cols=20)
            # Add headers
            headers = [
                'circuit_id', 'circuit_name', 'event_id', 'rider_id', 
                'rider_name', 'time', 'timestamp'
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
    print("Fetching Q2 sessions from Google Sheet...")
    q2_sessions = get_q2_sessions_from_sheet()
    
    if not q2_sessions:
        print("Failed to fetch Q2 sessions or no Q2 sessions found.")
        return
    
    print(f"Found {len(q2_sessions)} Q2 sessions in the sheet.")
    
    all_rider_data = []
    
    for session in q2_sessions:
        circuit_id = session["circuit_id"]
        circuit_name = session["circuit_name"]
        session_id = session["session_id"]
        
        print(f"Fetching results for Q2 session at: {circuit_name} (Session ID: {session_id})...")
        results_json = fetch_session_results(session_id)
        
        if results_json:
            rider_data = extract_rider_data(results_json, circuit_id, circuit_name, session_id)
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
        print("No rider data found for any Q2 session")

if __name__ == "__main__":
    main()
