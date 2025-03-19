#!/usr/bin/env python3
import requests
import json
import sys
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MySQL configuration - Fixed to match .env variable names
DB_HOST = os.getenv('MYSQL_HOST')
DB_USER = os.getenv('MYSQL_USER')
DB_PASSWORD = os.getenv('MYSQL_PASSWORD')
DB_NAME = os.getenv('MYSQL_DATABASE')

# Print debug information
print(f"Database connection parameters:")
print(f"Host: {DB_HOST}")
print(f"User: {DB_USER}")
print(f"DB Name: {DB_NAME}")

def get_db_connection():
    """Initialize and return MySQL database connection"""
    try:
        # Use TCP connection instead of socket for Windows compatibility
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            # Explicitly set connection parameters for Windows compatibility
            use_pure=True,
            auth_plugin='mysql_native_password'
        )
        if connection.is_connected():
            print(f"Successfully connected to MySQL database: {DB_NAME}")
            return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}", file=sys.stderr)
        print(f"Connection parameters: host={DB_HOST}, user={DB_USER}, database={DB_NAME}")
        return None

def initialize_database():
    """Create necessary tables if they don't exist"""
    connection = get_db_connection()
    if not connection:
        return False
    
    cursor = connection.cursor()
    try:
        # Create the race results table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resultados (
                id INT AUTO_INCREMENT PRIMARY KEY,
                circuit_id VARCHAR(255),
                circuit_name VARCHAR(255),
                event_id VARCHAR(255),
                event_name VARCHAR(255),
                rider_id VARCHAR(255),
                rider_name VARCHAR(255),
                position VARCHAR(50),
                gap VARCHAR(255)
            )
        ''')
        
        connection.commit()
        print("Database table 'resultados' verified/created")
        return True
    except Error as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return False
    finally:
        cursor.close()
        connection.close()

def get_race_sessions_from_db():
    """Fetch race sessions (SPR or RAC) from the database"""
    try:
        connection = get_db_connection()
        if not connection:
            return None
        
        cursor = connection.cursor(dictionary=True)
        
        # Find race sessions (SPR or RAC)
        query = """
        SELECT circuit_id, circuit_name, session_id, shortname
        FROM sesiones
        WHERE shortname IN ('SPR', 'RAC')
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if not results:
            print("No race sessions found in the database.")
            return []
        
        race_sessions = []
        for row in results:
            race_sessions.append({
                "circuit_id": row["circuit_id"],
                "circuit_name": row["circuit_name"],
                "event_id": row["session_id"],
                "event_name": row["shortname"],
                "session_id": row["session_id"],
                "type": row["shortname"]
            })
            print(f"Found {row['shortname']} session for: {row['circuit_name']}")
        
        cursor.close()
        connection.close()
        return race_sessions
    except Error as e:
        print(f"Error fetching race sessions from database: {e}", file=sys.stderr)
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
                    
                    rider_data.append((
                        circuit_id,
                        circuit_name,
                        event_id,
                        event_name,
                        rider_id,
                        rider_name,
                        position,
                        gap
                    ))
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
                    
                    rider_data.append((
                        circuit_id,
                        circuit_name,
                        event_id,
                        event_name,
                        rider_id,
                        rider_name,
                        position,
                        gap
                    ))
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
                
                rider_data.append((
                    circuit_id,
                    circuit_name,
                    event_id,
                    event_name,
                    rider_id,
                    rider_name,
                    position,
                    gap
                ))
        else:
            print(f"Unexpected API response format: {type(results_json)}")
    except Exception as e:
        print(f"Error extracting rider data: {e}")
        import traceback
        traceback.print_exc()
    
    return rider_data

def save_to_database(rider_data):
    """Save the rider data to MySQL database"""
    if not rider_data:
        print("No rider data to save.")
        return False
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM resultados")
        
        # Insert new rider data
        insert_query = """
        INSERT INTO resultados (circuit_id, circuit_name, event_id, event_name,
                           rider_id, rider_name, position, gap)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.executemany(insert_query, rider_data)
        connection.commit()
        
        print(f"Successfully saved {len(rider_data)} rider results to database")
        cursor.close()
        connection.close()
        return True
    
    except Error as e:
        print(f"Error saving rider data to database: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

def main():
    """Main function to run the script"""
    if not initialize_database():
        print("Failed to initialize database.")
        return
        
    print("Fetching race sessions from database...")
    race_sessions = get_race_sessions_from_db()
    
    if not race_sessions:
        print("Failed to fetch race sessions or no race sessions found.")
        return
    
    print(f"Found {len(race_sessions)} race sessions in the database.")
    
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
        save_to_database(all_rider_data)
    else:
        print("No rider data found for any race session")

if __name__ == "__main__":
    main()
