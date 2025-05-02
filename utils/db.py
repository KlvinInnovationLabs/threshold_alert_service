import json
from os import environ, path
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

# Specificy a `.env` file containing key/value config values
load_dotenv("../config/.env")
# Keys match the parameters for psycopg2.connect()

SERVER_HOST =  f"{environ.get("SERVER_URL")}:{environ.get("SERVER_PORT")}"
db_connection_dict = {
    "dbname": environ.get("DATABASE_NAME"),
    "user": environ.get("DATABASE_USER"),
    "password": environ.get("DATABASE_PASSWORD"),
    "port": environ.get("DATABASE_PORT"),
    "host": environ.get("DATABASE_HOST"),
}


# Database functions to process and ingest
def unwrap(option):
    if option is None:
        raise ValueError("Called unwrap on a None value")
    return option


def get_connection_pool():
    connection_pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        **db_connection_dict,
        options="-c search_path=sentinel",
    )
    return connection_pool


# Insert a new device reading and get the returned id
def insert_data(device_id, time, readings):
    conn = get_connection_pool().getconn("dataInsertion")
    cur = conn.cursor()
    if cur:
        print("Got Cursor")

    query = "INSERT INTO sentinel.device_readings (device_id, time,sensor_readings) VALUES (%s, %s,%s);"
    cur.execute(query, (device_id, time, json.dumps(readings)))

    # Commit the transaction
    conn.commit()

    # Close the connection
    cur.close()
    conn.close()


# Fetch email addresses based on threshold level
# def get_emails(device_id, threshold_type):
#     conn = get_connection_pool().getconn()
#     cursor = conn.cursor()
#     cursor.execute(
#         "SELECT yellow_email, orange_email, red_email FROM devices WHERE device_id = %s",
#         (device_id,),
#     )
#
#     result = cursor.fetchall()[0]
#     result = list(list(single_result[1:-1].split(",")) for single_result in result)
#     if threshold_type == "yellow":
#         return [result[0]]  # Yellow (Threshold 1)
#     elif threshold_type == "orange":
#         return result[:2]  # Orange (Threshold 2)
#     else:
#         return result  # Red (Threshold 3)
#

def get_emails(device_id, threshold_type):
    return "sudhamshusuri.2015@gmail.com"

# Fetch factory, zone, and machine names
def get_entity_names(device_id):
    conn = get_connection_pool().getconn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT factorys.factory_name, zones.zone_name, machines.machine_name
        FROM devices AS devices
        JOIN machines AS machines ON devices.machine_entity_id = machines.machine_entity_id
        JOIN entitys AS entity ON machines.machine_entity_id = entity.entity_id
        JOIN zones as zones ON entity.parent_entity_id = zones.zone_entity_id
        JOIN entitys as e ON zones.zone_entity_id = e.entity_id
        JOIN factorys AS factorys ON e.parent_entity_id = factorys.factory_entity_id
        WHERE devices.device_id = %s;
    """,
        (device_id,),
    )

    result = cursor.fetchall()

    return (
        result[0] if result else ("Unknown Factory", "Unknown Zone", "Unknown Machine")
    )


# Fetch thresholds from the `sensors` table
def get_thresholds(device_id, sensor_id):
    conn = get_connection_pool().getconn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT threshold_yellow, threshold_orange, threshold_red FROM sensors WHERE sensor_id = %s AND device_id = %s",
        (sensor_id, device_id),
    )
    result = cursor.fetchone()
    if result:
        return result
    else:
        raise DataNotSetError(
            {
                "device_id": device_id,
                "sensor_id": sensor_id,
                "datatype": "Thresholds",
                "extras": sensor_id,
            }
        )


def get_sensor_IDs(device_id):
    conn = get_connection_pool().getconn()
    cursor = conn.cursor()
    cursor.execute(f"SELECT sensor_id FROM sensors WHERE device_id = '{device_id}'")
    result = cursor.fetchall()

    # Unwraps result from 2 dimensions to 1 dimension - [(1,),(2,),(3,)] -> [1,2,3,]
    sensorIDs = list(map(lambda x: x[0], result))

    if sensorIDs:
        return sensorIDs
    else:
        raise DataNotSetError({"device_id": device_id, "datatype": "sensors"})


def get_all_company_ids():
    conn = get_connection_pool().getconn()
    cursor = conn.cursor()
    cursor.execute("SELECT company_entity_id FROM companys")
    result = cursor.fetchall()
    # Unwraps result from 2 dimensions to 1 dimension - [(1,),(2,),(3,)] -> [1,2,3,]
    company_ids = list(map(lambda x: str(x[0]), result))

    if company_ids:
        return company_ids
    else:
        raise DataNotSetError({"extras": "Company"})


def get_company_from_device_id(device_id):
    conn = get_connection_pool().getconn()
    cursor = conn.cursor()

    try:
        query = """WITH RECURSIVE ParentEntity AS (
        SELECT e.entity_id, e.parent_entity_id
        FROM devices d
        INNER JOIN Machines m ON d.machine_entity_id = m.machine_entity_id
        INNER JOIN entitys e ON e.entity_id = m.machine_entity_id
        WHERE d.device_id = %s
        
        UNION ALL
        
        SELECT e.entity_id, e.parent_entity_id
        FROM entitys e
        INNER JOIN ParentEntity pe ON e.entity_id = pe.parent_entity_id
        )
        SELECT entity_id
        FROM ParentEntity
        WHERE parent_entity_id IS NULL;
        """
        cursor.execute(query, (device_id,))
        company = cursor.fetchone()

        return str(company[0])
    except Exception as e:
        print(e)
        return None
    finally:
        cursor.close()
        conn.close()


class DataNotSetError(Exception):
    """Raises an exception if data was not defined for a device's sensor"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self):

        if self.message["device_id"]:
            return f"{self.message['device_id']} has no\
            {self.message['datatype']} defined - {self.message['extras']}"

        return f"{self.message['extras']} not defined"
