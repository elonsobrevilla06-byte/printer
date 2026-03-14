# printer_utils.py
from PIL import Image
import socket
import json
from datetime import datetime

ESC = b'\x1b'
GS = b'\x1d'
CUT_SAFE = b'\n\n\n\x1d\x56\x00'

# Printer mapping
PRINTERS = {
    "kitchen_printer_1": "192.168.1.221",
    "kitchen_printer_2": "192.168.1.222",
    "bar_printer_1": "192.168.1.223"
}

def money(val):
    return f"{val:,.2f}"

def line():
    return b"------------------------------------------------\n"

def double_line():
    return b"================================================\n"

def item_row(label, value):
    return f"{label:<32}{value:>16}\n".encode()

def build_kitchen_receipt(data):
    receipt = bytearray()
    services = json.loads(data.get("services_availed") or "[]")

    # HEADER
    receipt += ESC + b'@'
    receipt += ESC + b'a\x01'
    receipt += ESC + b'E\x01'
    receipt += b"KITCHEN ORDER\n"
    receipt += ESC + b'E\x00'
    receipt += ESC + b'a\x00'
    receipt += double_line()

    receipt += f"TRX ID : {data['transaction_id']}\n".encode()
    receipt += f"Deck   : {data['deck_assigned']}\n".encode()
    receipt += f"Table  : {data['table_assigned']}\n".encode()
    receipt += f"Card   : {data['assigned_card_number']}\n".encode()
    receipt += f"Time   : {datetime.now().strftime('%I:%M %p')}\n".encode()
    receipt += double_line()

    # ITEMS
    receipt += ESC + b'E\x01'
    receipt += b"ITEMS\n"
    receipt += ESC + b'E\x00'
    receipt += line()

    for s in services:
        qty = s.get("qty", 1)
        item = s.get("item", "Item")
        note = s.get("note", "")
        waiter = s.get("waiter", "N/A")
        purchased_at = s.get("purchased_at", "")

        # BIG QTY + ITEM
        receipt += GS + b'!\x11'
        receipt += f"{qty}x {item}\n".encode()
        receipt += GS + b'!\x00'

        # Notes & purchased at
        if note:
            receipt += f"  NOTE: {note}\n".encode()
        if purchased_at:
            receipt += f"  FROM: {purchased_at}\n".encode()

        receipt += f"  WAITER: {waiter}\n\n".encode()

    receipt += double_line()
    receipt += ESC + b'a\x01'
    receipt += b"*** PREPARE IMMEDIATELY ***\n"
    receipt += ESC + b'a\x00'

    return receipt

def send_to_printer(receipt_bytes, printer_name, logo_path=None):
    if printer_name not in PRINTERS:
        raise ValueError(f"Unknown printer: {printer_name}")

    printer_ip = PRINTERS[printer_name]
    output = bytearray()

    if logo_path:
        image = Image.open(logo_path).convert('1')
        if image.width > 384:
            ratio = 384 / image.width
            image = image.resize((384, int(image.height * ratio)))

        width, height = image.size
        pixels = image.load()
        total_width = 400
        left_padding = 90

        image_data = bytearray()
        image_data += b'\x1d\x76\x30\x00'
        w = (total_width + 7) // 8
        image_data += (w % 256).to_bytes(1, 'little')
        image_data += (w // 256).to_bytes(1, 'little')
        image_data += (height % 256).to_bytes(1, 'little')
        image_data += (height // 256).to_bytes(1, 'little')

        for y in range(height):
            row_bytes = bytearray()
            for x in range(0, w*8, 8):
                byte = 0
                for bit in range(8):
                    img_x = x - left_padding + bit
                    if 0 <= img_x < width and pixels[img_x, y] == 0:
                        byte |= 1 << (7 - bit)
                row_bytes.append(byte)
            image_data += row_bytes

        output += image_data

    output += receipt_bytes + CUT_SAFE

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((printer_ip, 9100))
    sock.sendall(output)
    sock.close()