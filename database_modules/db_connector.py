import mysql.connector

def get_connection_mainland():
    return mysql.connector.connect(
        host = "localhost",
        user = "root",
        password = "masteryimain31",
        database = "blue_ocean_mainland_db"
    ) 
def get_connection_floatingbar():
    return mysql.connector.connect(
        host = "localhost",
        user = "root",
        password = "masteryimain31",
        database = "blue_ocean_floatingbar_db"
    ) 