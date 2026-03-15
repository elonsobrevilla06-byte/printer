import threading
import queue
from flask import Blueprint, request, jsonify, Flask
from printer_utils import build_kitchen_receipt, send_to_printer
import json

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

if __name__ == "__main__":
    app.run(debug=True, threaded=True)