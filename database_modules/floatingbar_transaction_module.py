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

def put_floatingbar_transaction(transaction_id, data):
    floating_conn = None

    try:
        floating_conn = get_connection_floatingbar()
        cursor = floating_conn.cursor(dictionary=True)

        # -----------------------------
        # Fetch existing transaction
        # -----------------------------
        cursor.execute("SELECT * FROM floatingbar_transaction WHERE transaction_id = %s", (transaction_id,))
        existing_row = cursor.fetchone()

        if not existing_row:
            return {"status": "error", "message": "Transaction not found"}

        # -----------------------------
        # Merge services
        # -----------------------------
        existing_services = json.loads(existing_row["services_availed"]) if existing_row["services_availed"] else []
        new_services = data.get("services_availed") or []
        merged_services = existing_services + new_services

        additional_total = sum(float(s.get("price", 0)) for s in new_services)
        current_net = float(existing_row.get("total_net_billing") or 0)
        updated_total_net = current_net + additional_total

        current_consumables = float(existing_row.get("available_consumables") or 0)
        updated_consumables = current_consumables - additional_total

        existing_paid = float(existing_row.get("total_amount_paid") or 0)
        new_payment = float(data.get("total_amount_paid") or 0)
        total_amount_paid = existing_paid + new_payment

        if updated_consumables < 0:
            updated_consumables += new_payment
            total_change = max(updated_consumables, 0)
            updated_consumables = 0 if updated_consumables >= 0 else updated_consumables
        else:
            total_change = max(total_amount_paid - updated_total_net, 0)

        # -----------------------------
        # Determine status
        # -----------------------------
        new_status = data.get("status") if data.get("status") is not None else existing_row["status"]

        # -----------------------------
        # Build UPDATE query
        # -----------------------------
        update_query = """
        UPDATE floatingbar_transaction
        SET
            services_availed = %s,
            add_on_guest = %s,
            total_net_billing = %s,
            total_amount_paid = %s,
            total_change = %s,
            available_consumables = %s,
            mode_of_payment = %s,
            reference_number = %s,
            status = %s,
            notes = %s,
            deck_assigned = %s,
            table_assigned = %s,
            access_type = %s,
            assigned_card_number = %s,
            attended_by = %s
        WHERE transaction_id = %s
        """

        values = [
            json.dumps(merged_services),
            json.dumps(data.get("add_on_guest") or json.loads(existing_row.get("add_on_guest") or "[]")),
            updated_total_net,
            total_amount_paid,
            total_change,
            updated_consumables,
            data.get("mode_of_payment") or existing_row.get("mode_of_payment"),
            data.get("reference_number") or existing_row.get("reference_number"),
            new_status,
            data.get("notes") or existing_row.get("notes"),
            data.get("deck_assigned") or existing_row.get("deck_assigned"),
            data.get("table_assigned") or existing_row.get("table_assigned"),
            data.get("access_type") or existing_row.get("access_type"),
            data.get("assigned_card_number") or existing_row.get("assigned_card_number"),
            data.get("attended_by") or existing_row.get("attended_by"),
            transaction_id
        ]

        cursor.execute(update_query, values)
        floating_conn.commit()

        return {
            "status": "success",
            "updated_rows": cursor.rowcount,
            "computed": {
                "total_net_billing": updated_total_net,
                "available_consumables": updated_consumables,
                "total_amount_paid": total_amount_paid,
                "total_change": total_change,
                "status": new_status
            }
        }

    except Exception as e:
        if floating_conn: floating_conn.rollback()
        return {"status": "error", "message": str(e)}

    finally:
        if floating_conn: cursor.close(); floating_conn.close()