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

# MySQL configuration
DB_HOST = os.getenv('DB_HOST', '')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', '')

def get_db_connection():
    """Initialize and return MySQL database connection"""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}", file=sys.stderr)
        return None

def initialize_database():
    """Create necessary tables if they don't exist"""
    connection = get_db_connection()
    if not connection:
        return False
    
    cursor = connection.cursor()
    try:
        # Create the sessions table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Sesiones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                circuit_id VARCHAR(255),
                circuit_name VARCHAR(255),
                session_id VARCHAR(255),
                shortname VARCHAR(50),
                date_start VARCHAR(255),
                date_end VARCHAR(255),
                category_id VARCHAR(255),
                category_name VARCHAR(255)
            )
        ''')
        
        connection.commit()
        print("Database tables verified/created")
        return True
    except Error as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return False
    finally:
        cursor.close()
        connection.close()

def get_circuits_from_db():
    """Fetch circuit data from the database"""
    try:
        connection = get_db_connection()
        if not connection:
            return None
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT event_id, circuit_name FROM Circuitos")
        results = cursor.fetchall()
        
        if not results:
            print("No circuit data found in the database.")
            return []
        
        circuits = []
        for row in results:
            circuits.append({
                "event_id": row["event_id"],
                "circuit_id": row["event_id"],  # Use event_id as circuit_id
                "circuit_name": row["circuit_name"]
            })
        
        cursor.close()
        connection.close()
        return circuits
    except Error as e:
        print(f"Error fetching circuits from database: {e}", file=sys.stderr)
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
        
        # Get the raw date string, MySQL will store it as-is
        date_start = session.get('date', '')
        date_end = ''  # Leave empty as specified
        
        category = session.get('category', {})
        category_id = category.get('id', '')
        category_name = category.get('name', '')
        
        session_data.append((
            circuit_id,
            circuit_name,
            session_id,
            shortname,
            date_start,
            date_end,
            category_id,
            category_name
        ))
    
    return session_data

def save_to_database(session_data):
    """Save the session data to MySQL database"""
    if not session_data:
        print("No session data to save.")
        return False
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM Sesiones")
        
        # Insert new session data
        insert_query = """
        INSERT INTO Sesiones (circuit_id, circuit_name, session_id, shortname, 
                             date_start, date_end, category_id, category_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.executemany(insert_query, session_data)
        connection.commit()
        
        print(f"Successfully saved {len(session_data)} sessions to database")
        cursor.close()
        connection.close()
        return True
    
    except Error as e:
        print(f"Error saving sessions to database: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

def main():
    """Main function to run the script"""
    if not initialize_database():
        print("Failed to initialize database.")
        return
        
    print("Fetching circuit data from database...")
    circuits = get_circuits_from_db()
    
    if not circuits:
        print("Failed to fetch circuit data or no circuits found.")
        return
    
    print(f"Found {len(circuits)} circuits in the database.")
    
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
        save_to_database(all_session_data)
    else:
        print("No session data found for any circuit")

if __name__ == "__main__":
    main()
