#!/usr/bin/env python3
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import sys

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
    """Initialize database structure from schema.sql"""
    try:
        # First connect to MySQL server
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            # Explicitly set connection parameters for Windows compatibility
            use_pure=True,
            auth_plugin='mysql_native_password'
        )
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")
        
        # Read and execute schema.sql
        with open('schema.sql', 'r') as file:
            schema = file.read()
            
        # Split statements to execute them one by one
        for statement in schema.split(';'):
            if statement.strip():
                try:
                    cursor.execute(statement)
                except Error as e:
                    print(f"Error executing statement: {statement[:100]}... Error: {e}")
                
        connection.commit()
        print("Database initialized successfully.")
        return True
    except Error as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    print("Initializing database structure from schema.sql...")
    success = initialize_database()
    if success:
        print("Database initialization completed successfully.")
    else:
        print("Failed to initialize database.")
