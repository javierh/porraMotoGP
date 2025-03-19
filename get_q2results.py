#!/usr/bin/env python3
import requests
import json
import sys
import datetime
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
            use_pure=True,  # Use the pure Python implementation
            auth_plugin='mysql_native_password'  # Use native password auth
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
        # Create both tables: the legacy q2_results and the new Q2 table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS q2_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                circuit_id VARCHAR(255),
                circuit_name VARCHAR(255),
                event_id VARCHAR(255),
                rider_id VARCHAR(255),
                rider_name VARCHAR(255),
                time VARCHAR(255),
                timestamp DATETIME
            )
        ''')
        
        # Create the Q2 table as per schema.sql
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Q2 (
                circuit_id VARCHAR(36) PRIMARY KEY,
                posicion1 VARCHAR(255) NOT NULL,
                posicion2 VARCHAR(255) NOT NULL,
                posicion3 VARCHAR(255) NOT NULL
            )
        ''')
        
        connection.commit()
        print("Database tables 'q2_results' and 'Q2' verified/created")
        return True
    except Error as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return False
    finally:
        cursor.close()
        connection.close()

def get_q2_sessions_from_db():
    """Fetch Q2 sessions from the database by finding Q2 sessions directly"""
    try:
        connection = get_db_connection()
        if not connection:
            return None
        
        cursor = connection.cursor(dictionary=True)
        
        # Revised query that doesn't depend on the 'id' column
        # Instead, we look for sessions with 'Q2' in the shortname
        # or other identifiers of Q2 sessions
        query = """
        SELECT circuit_id, circuit_name, session_id
        FROM Sesiones
        WHERE shortname = 'Q2' OR shortname LIKE '%Q2%' OR shortname LIKE '%Qualifying 2%'
        """
        
        # If the above query returns no results, try the alternative approach
        # This looks for 'Q' sessions only, then we'll process them afterward
        alternative_query = """
        SELECT circuit_id, circuit_name, session_id, shortname, date_start
        FROM Sesiones
        WHERE shortname = 'Q' OR shortname LIKE '%Q%' OR shortname LIKE '%Qualifying%'
        ORDER BY circuit_id, date_start
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # If no Q2 sessions found directly, try the alternative approach
        if not results:
            print("No explicit Q2 sessions found. Trying to identify Q2 sessions from all qualifying sessions...")
            cursor.execute(alternative_query)
            q_sessions = cursor.fetchall()
            
            # Group qualifying sessions by circuit
            circuits = {}
            for row in q_sessions:
                circuit_id = row['circuit_id']
                if circuit_id not in circuits:
                    circuits[circuit_id] = []
                circuits[circuit_id].append(row)
            
            # For each circuit with multiple Q sessions, take the latest one (assuming it's Q2)
            results = []
            for circuit_id, sessions in circuits.items():
                if len(sessions) >= 1:
                    # Sort by date_start and take the latest
                    sessions.sort(key=lambda x: x['date_start'] if x['date_start'] else '')
                    # If there are at least 2 sessions, take the second one
                    if len(sessions) >= 2:
                        results.append(sessions[1])  # Q2 should be the second qualifying session
                    else:
                        # If only one qualifying session, use it (better than nothing)
                        results.append(sessions[0])
        
        if not results:
            print("No Q2 sessions found in the database.")
            return []
        
        q2_sessions = []
        for row in results:
            q2_sessions.append({
                "circuit_id": row["circuit_id"],
                "circuit_name": row["circuit_name"],
                "session_id": row["session_id"]
            })
            print(f"Found Q2 session for: {row['circuit_name']}")
        
        cursor.close()
        connection.close()
        return q2_sessions
    except Error as e:
        print(f"Error fetching Q2 sessions from database: {e}", file=sys.stderr)
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
    current_timestamp = datetime.datetime.now()
    
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
                    
                    rider_data.append((
                        circuit_id,
                        circuit_name,
                        session_id,
                        rider_id,
                        rider_name,
                        lap_time,
                        current_timestamp
                    ))
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
                
                rider_data.append((
                    circuit_id,
                    circuit_name,
                    session_id,
                    rider_id,
                    rider_name,
                    lap_time,
                    current_timestamp
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
        
        # Clear existing data from both tables
        cursor.execute("DELETE FROM q2_results")
        cursor.execute("DELETE FROM Q2")
        
        # Insert new rider data to q2_results
        insert_query = """
        INSERT INTO q2_results (circuit_id, circuit_name, event_id, rider_id, rider_name, time, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.executemany(insert_query, rider_data)
        
        # Also populate the Q2 table with the top 3 riders for each circuit
        for circuit_id in set(row[0] for row in rider_data):
            # Get top 3 riders for this circuit
            top_riders = [row[5] for row in sorted(
                [r for r in rider_data if r[0] == circuit_id],
                key=lambda x: x[6] if x[6] else "99:99.999"
            )[:3]]
            
            # Make sure we have exactly 3 positions
            while len(top_riders) < 3:
                top_riders.append("")
                
            # Insert into Q2 table
            cursor.execute("""
                INSERT INTO Q2 (circuit_id, posicion1, posicion2, posicion3)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    posicion1 = VALUES(posicion1),
                    posicion2 = VALUES(posicion2),
                    posicion3 = VALUES(posicion3)
            """, (circuit_id, top_riders[0], top_riders[1], top_riders[2]))
            
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
        
    print("Fetching Q2 sessions from database...")
    q2_sessions = get_q2_sessions_from_db()
    
    if not q2_sessions:
        print("Failed to fetch Q2 sessions or no Q2 sessions found.")
        return
    
    print(f"Found {len(q2_sessions)} Q2 sessions in the database.")
    
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
        save_to_database(all_rider_data)
    else:
        print("No rider data found for any Q2 session")

if __name__ == "__main__":
    main()
