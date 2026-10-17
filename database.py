
import os
import mysql.connector


def get_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "1234"),
        database=os.getenv("DB_NAME", "shop_management"),
        port=int(os.getenv("DB_PORT", "3306"))
    )
    return connection
