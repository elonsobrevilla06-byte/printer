from database_modules.db_connector import get_connection_floatingbar, get_connection_mainland
import json

def get_floatingbar_transaction(transaction_id=None):
    conn = get_connection_floatingbar()
    cursor = conn.cursor(dictionary=True)

    try:
        if transaction_id:
            cursor.execute(
                "SELECT * FROM floatingbar_transaction WHERE transaction_id = %s",
                (transaction_id,)
            )
            row = cursor.fetchone()

            if row:
                if row["main_guest_information"]:
                    row["main_guest_information"] = json.loads(row["main_guest_information"])
                if row["add_on_guest"]:
                    row["add_on_guest"] = json.loads(row["add_on_guest"])

            return row
        else:
            cursor.execute("SELECT * FROM floatingbar_transaction")
            result = cursor.fetchall()

            for row in result:
                if row["main_guest_information"]:
                    row["main_guest_information"] = json.loads(row["main_guest_information"])
                if row["add_on_guest"]:
                    row["add_on_guest"] = json.loads(row["add_on_guest"])

            return result

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        cursor.close()
        conn.close()