import threading
import queue
from flask import Blueprint, request, jsonify, Flask
from printers.floatingbar_module import build_billout_receipt, send_to_printer_registration
from printers.specific_kitchen import build_kitchen_receipt, send_to_printer
import json
from database_modules.db_connector import get_connection_floatingbar
from database_modules.floatingbar_transaction_module import get_floatingbar_transaction

app = Flask(__name__)

# 1. Initialize the Queue
print_queue = queue.Queue()

# 2. The Worker Function: This runs in the background
def printer_worker():
    while True:
        # This will block until an item is available
        job = print_queue.get()
        if job is None: break  # Poison pill to stop thread if needed
        
        try:
            #To simulate multiple requets simulatanously 
            import time
            time.sleep(2)
            data, printer_name = job
            receipt = build_kitchen_receipt(data)
            send_to_printer(receipt, printer_name, logo_path="./BlueOceanBar.jpg")
            print(f"Successfully printed to {printer_name}")
        except Exception as e:
            print(f"Printer Error: {e}")
        finally:
            # Signal that the job is done
            print_queue.task_done()

# 3. Start the background thread
worker_thread = threading.Thread(target=printer_worker, daemon=True)
worker_thread.start()

@app.route("/print/kitchen-order", methods=["POST"])
def print_kitchen_order():
    try:
        data = request.get_json()
        printer_name = data.get("printer_name")

        if not printer_name:
            return jsonify({"success": False, "message": "printer_name is required"}), 400

        # Pre-process data as before
        if isinstance(data.get("services_availed"), list):
            data["services_availed"] = json.dumps(data["services_availed"])

        # 4. Push to Queue instead of printing immediately
        print_queue.put((data, printer_name))

        return jsonify({
            "success": True, 
            "message": f"Order queued for {printer_name}. Current queue size: {print_queue.qsize()}"
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    

@app.route("/split-bill/print/<string:transaction_id>", methods=["GET"])
def split_bill_print(transaction_id):

    try:
        data = get_floatingbar_transaction(transaction_id)

        if not data:
            return jsonify({"error": "Transaction not found"}), 404

        main_guest = data.get("main_guest_information", {})
        add_on_guests = data.get("add_on_guest", [])

        all_guests = [main_guest] + add_on_guests

        printed = 0

        for guest in all_guests:

            print(f" Printing bill for {guest.get('firstName')}")

            # ---------------------------------
            # Convert services format
            # ---------------------------------
            converted_services = []
            subtotal = 0

            for s in guest.get("services_availed", []):
                qty = s.get("qty", 1)
                price = s.get("unit_price", 0)

                converted_services.append({
                    "qty": qty,
                    "item": s.get("item", "Item"),
                    "price": price,
                    "note": s.get("notes", "")
                })

                subtotal += qty * price

            # ---------------------------------
            # APPLY DISCOUNT %
            # ---------------------------------
            discount_percent = guest.get("discount_amount", 0) or 0
            discount_id = guest.get("discountId")

            discount_value = 0
            if discount_id and discount_percent > 0:
                discount_value = subtotal * (discount_percent / 100)

            net_total = subtotal - discount_value
            if net_total < 0:
                net_total = 0

            # ---------------------------------
            # PAYMENT + CHANGE
            # ---------------------------------
            amount_paid = guest.get("amount_paid", 0)

            change = amount_paid - net_total
            if change < 0:
                change = 0

            # ---------------------------------
            # Prepare data for printer
            # ---------------------------------
            receipt_data = data.copy()
            print(receipt_data)

            receipt_data["services_availed"] = json.dumps(converted_services)
            receipt_data["total_net_billing"] = net_total
            receipt_data["total_amount_paid"] = amount_paid
            receipt_data["total_change"] = change

            print(f"  NET TOTAL: {net_total}")

            # ---------------------------------
            # Show amount paid & change
            # ---------------------------------
            amount_paid = guest.get("amount_paid", 0)
            change = max(amount_paid - net_total, 0)
            print(f"  AMOUNT PAID: {amount_paid}")
            print(f"  CHANGE: {change}")
            # ---------------------------------
            # BUILD RECEIPT
            # ---------------------------------
            # receipt = build_billout_receipt(
            #     receipt_data,
            #     json.dumps(guest)
            # )

            # # ---------------------------------
            # # SEND TO PRINTER
            # # ---------------------------------
            # send_to_printer_registration(
            #     receipt,
            #     logo_path="./images/BlueOceanBar.jpg",
            #     qr_path="./images/blueoceanbar_qr.png"
            # )

            printed += 1

        print(f"{printed} receipts printed successfully")

        return jsonify({
            "success": True,
            "printed": printed
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500
    

@app.route("/split-bill/print/<string:transaction_id>/specific", methods=["GET"])
def split_bill_print_specific(transaction_id):

    try:
        data = get_floatingbar_transaction(transaction_id)

        if not data:
            return jsonify({"error": "Transaction not found"}), 404

        # 🎯 Target guest from query params
        target_first = request.args.get("firstName")
        target_last = request.args.get("lastName")

        if not target_first or not target_last:
            return jsonify({"error": "Provide firstName and lastName"}), 400

        main_guest = data.get("main_guest_information", {})
        add_on_guests = data.get("add_on_guest", [])

        all_guests = [main_guest] + add_on_guests

        printed = 0

        for guest in all_guests:

            #  Match only the requested guest
            if not (
                guest.get("firstName", "").lower() == target_first.lower()
                and guest.get("lastName", "").lower() == target_last.lower()
            ):
                continue

            print(f"\n🧾 Printing bill for {guest.get('firstName')} {guest.get('lastName')}")

            # ---------------------------------
            # Convert services format
            # ---------------------------------
            converted_services = []
            subtotal = 0

            for s in guest.get("services_availed", []):
                qty = s.get("qty", 1)
                price = s.get("unit_price", 0)

                converted_services.append({
                    "qty": qty,
                    "item": s.get("item", "Item"),
                    "price": price,
                    "note": s.get("notes", "")
                })

                subtotal += qty * price

                print(f"  {qty} x {s.get('item')} @ {price} = {qty * price}")

            # ---------------------------------
            # APPLY DISCOUNT %
            # ---------------------------------
            discount_percent = guest.get("discount_amount", 0) or 0
            discount_id = guest.get("discountId")

            discount_value = 0
            if discount_id and discount_percent > 0:
                discount_value = subtotal * (discount_percent / 100)

            net_total = max(subtotal - discount_value, 0)

            # ---------------------------------
            # PAYMENT + CHANGE
            # ---------------------------------
            amount_paid = guest.get("amount_paid", 0)
            change = max(amount_paid - net_total, 0)
            print(f"All Data: {data}")
            print(f"  NET TOTAL: {net_total}")
            print(f"  AMOUNT PAID: {amount_paid}")
            print(f"  CHANGE: {change}")

            # ---------------------------------
            # 🧾 PREPARE DATA FOR PRINTER
            # ---------------------------------
            receipt_data = data.copy()

            receipt_data["services_availed"] = json.dumps(converted_services)
            receipt_data["total_net_billing"] = net_total
            receipt_data["total_amount_paid"] = amount_paid
            receipt_data["total_change"] = change

            # ---------------------------------
            #  BUILD RECEIPT (READY)
            # ---------------------------------
            # receipt = build_billout_receipt(
            #     receipt_data,
            #     json.dumps(guest)
            # )

            # ---------------------------------
            #  SEND TO PRINTER (READY)
            # ---------------------------------
            # send_to_printer_registration(
            #     receipt,
            #     logo_path="./images/BlueOceanBar.jpg",
            #     qr_path="./images/blueoceanbar_qr.png"
            # )

            printed += 1
            break  # Only print one guest

        if printed == 0:
            return jsonify({"error": "Guest not found in this transaction"}), 404

        print(f"\n {printed} receipt prepared (console preview)")

        return jsonify({
            "success": True,
            "printed": printed
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500
    

@app.route("/floatingbar/guest-payment", methods=["PUT"])
def update_guest_payment():
    """
    Updates the amount paid for a specific guest in a floatingbar transaction.
    Expects JSON body:
    {
        "transaction_id": "TXN-001",
        "guest_first_name": "customer2",
        "guest_last_name": "Sobrevilla",
        "amount_paid": 2000
    }
    """
    try:
        data = request.get_json()
        transaction_id = data.get("transaction_id")
        first_name = data.get("guest_first_name")
        last_name = data.get("guest_last_name")
        guest_payment = float(data.get("amount_paid") or 0)

        if not transaction_id or not first_name or not last_name:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        conn = get_connection_floatingbar()
        cursor = conn.cursor(dictionary=True)

        # Fetch existing transaction
        cursor.execute("SELECT * FROM floatingbar_transaction WHERE transaction_id = %s", (transaction_id,))
        transaction = cursor.fetchone()

        if not transaction:
            return jsonify({"status": "error", "message": "Transaction not found"}), 404

        # Load JSON fields
        main_guest = json.loads(transaction.get("main_guest_information") or "{}")
        add_on_guests = json.loads(transaction.get("add_on_guest") or "[]")

        guest_found = False

        # Check main guest first
        if main_guest.get("firstName") == first_name and main_guest.get("lastName") == last_name:
            main_guest["amount_paid"] = guest_payment
            guest_found = True

        # Check add-on guests
        for guest in add_on_guests:
            if guest.get("firstName") == first_name and guest.get("lastName") == last_name:
                guest["amount_paid"] = guest_payment
                guest_found = True
                break

        if not guest_found:
            return jsonify({"status": "error", "message": "Guest not found in transaction"}), 404

        # Update the DB
        cursor.execute("""
            UPDATE floatingbar_transaction
            SET main_guest_information = %s, add_on_guest = %s
            WHERE transaction_id = %s
        """, (json.dumps(main_guest), json.dumps(add_on_guests), transaction_id))

        conn.commit()

        return jsonify({
            "status": "success",
            "message": f"Payment updated for {first_name} {last_name}",
            "guest_payment": guest_payment
        })

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    app.run(debug=True, threaded=True)