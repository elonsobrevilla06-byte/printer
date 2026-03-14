# routes_kitchen.py
from flask import Blueprint, request, jsonify, Flask
from specific_kitchen import build_kitchen_receipt, send_to_printer
import json


app = Flask(__name__)

@app.route("/print/kitchen-order", methods=["POST"])
def print_kitchen_order():
    try:
        data = request.get_json()
        printer_name = data.get("printer_name")

        if not printer_name:
            return jsonify({"success": False, "message": "printer_name is required"}), 400

        if isinstance(data.get("services_availed"), list):
            data["services_availed"] = json.dumps(data["services_availed"])

        receipt = build_kitchen_receipt(data)
        send_to_printer(receipt, printer_name, logo_path="./BlueOceanBar.jpg")

        return jsonify({"success": True, "message": f"Printed to {printer_name}"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    

if __name__ == "__main__":
    app.run(debug=True)