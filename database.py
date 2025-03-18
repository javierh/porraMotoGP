import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host='192.168.86.83',
        user='root',
        password='',
        database='porramotogp'
    )
    return connection

def fetch_data(query, params=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, params)
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return result

def insert_data(query, params):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(query, params)
    connection.commit()
    cursor.close()
    connection.close()
