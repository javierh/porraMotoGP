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
DB_HOST = os.getenv('MYSQL_HOST')  # Changed from DB_HOST to MYSQL_HOST
DB_USER = os.getenv('MYSQL_USER')  # Changed from DB_USER to MYSQL_USER
DB_PASSWORD = os.getenv('MYSQL_PASSWORD')  # Changed from DB_PASSWORD to MYSQL_PASSWORD
DB_NAME = os.getenv('MYSQL_DATABASE')  # Changed from DB_NAME to MYSQL_DATABASE

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
        # Update the Circuitos table definition to match schema.sql
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Circuitos (
                event_id VARCHAR(255) PRIMARY KEY,
                circuit_name VARCHAR(255) NOT NULL,
                date_start VARCHAR(255),
                date_end VARCHAR(255),
                hashtag VARCHAR(255)
            )
        ''')
        
        connection.commit()
        print("Database table 'circuitos' verified/created")
        return True
    except Error as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return False
    finally:
        cursor.close()
        connection.close()

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
        circuit_name = circuit.get('circuit', {}).get('name', '')
        date_start = circuit.get('date_start', '')
        date_end = circuit.get('date_end', '')
        hashtag = circuit.get('name', '')
        
        # Removed circuit_id from the tuple to match the schema
        circuit_data.append((event_id, circuit_name, date_start, date_end, hashtag))
    
    return circuit_data

def save_to_database(circuit_data):
    """Save the circuit data to MySQL database"""
    if not circuit_data:
        print("No circuit data to save.")
        return False
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # Instead of deleting all records, use an UPSERT approach
        # to handle the foreign key constraints
        insert_query = """
        INSERT INTO Circuitos (event_id, circuit_name, date_start, date_end, hashtag)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            circuit_name = VALUES(circuit_name),
            date_start = VALUES(date_start),
            date_end = VALUES(date_end),
            hashtag = VALUES(hashtag)
        """
        
        # Keep track of all event IDs we're inserting
        event_ids = [item[0] for item in circuit_data]
        
        # Execute the inserts/updates
        cursor.executemany(insert_query, circuit_data)
        
        # Now we can safely delete any circuits that aren't in our new data
        # but only if they aren't referenced in Sesiones
        if event_ids:
            # Construct a parameterized query with the right number of placeholders
            placeholders = ','.join(['%s'] * len(event_ids))
            safe_delete_query = f"""
            DELETE FROM Circuitos 
            WHERE event_id NOT IN ({placeholders})
            AND NOT EXISTS (
                SELECT 1 FROM Sesiones WHERE Sesiones.circuit_id = Circuitos.event_id
            )
            """
            cursor.execute(safe_delete_query, event_ids)
            deleted_count = cursor.rowcount
            print(f"Removed {deleted_count} old circuits that weren't referenced")
            
        connection.commit()
        
        print(f"Successfully saved {len(circuit_data)} circuits to database")
        cursor.close()
        connection.close()
        return True
    
    except Error as e:
        print(f"Error saving circuits to database: {e}", file=sys.stderr)
        print(f"Exception type: {type(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

def main():
    """Main function to run the script"""
    if not initialize_database():
        print("Failed to initialize database.")
        return
        
    print("Fetching MotoGP 2025 circuit data...")
    circuits_json = fetch_circuits()
    
    if circuits_json:
        circuit_data = extract_circuit_data(circuits_json)
        if circuit_data:
            print(f"Found {len(circuit_data)} circuits")
            save_to_database(circuit_data)
        else:
            print("No circuit data found")
    else:
        print("Failed to fetch circuit data")

if __name__ == "__main__":
    main()
