import os
from dotenv import load_dotenv
import mysql.connector

# Load environment variables
load_dotenv()

def setup_database():
    """Initialize the MySQL database with the required tables."""
    print("Setting up the database...")
    
    # Get connection parameters from environment variables
    host = os.getenv('MYSQL_HOST')
    user = os.getenv('MYSQL_USER')
    password = os.getenv('MYSQL_PASSWORD')
    database = os.getenv('MYSQL_DATABASE')
    
    # Verify environment variables
    if not all([host, user, password, database]):
        missing = []
        if not host: missing.append('MYSQL_HOST')
        if not user: missing.append('MYSQL_USER')
        if not password: missing.append('MYSQL_PASSWORD')
        if not database: missing.append('MYSQL_DATABASE')
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Please set these variables in the .env file")
        return False

    try:
        # First create the database if it doesn't exist
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
        cursor.close()
        conn.close()
        
        # Now connect to the database
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        
        # Read the schema file
        with open('schema.sql', 'r') as f:
            schema = f.read()
        
        # Split into individual statements
        statements = schema.split(';')
        
        cursor = conn.cursor()
        # Execute each statement
        for statement in statements:
            if statement.strip():
                cursor.execute(statement)
                
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Database setup complete!")
        return True
        
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return False

if __name__ == "__main__":
    setup_database()
