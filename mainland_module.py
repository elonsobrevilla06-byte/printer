from PIL import Image
import socket
import json

printer_ip = "192.168.1.221"
#192.168.1.220
port = 9100

ESC = b'\x1b'
GS = b'\x1d'
CUT_SAFE = b'\n\n\n\x1d\x56\x00'


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def money(val):
    return f"{val:,.2f}"

def line():
    return b"------------------------------------------------\n"

def double_line():
    return b"================================================\n"

def item_row(label, value):
    return f"{label:<32}{value:>16}\n".encode()


# --------------------------------------------------
# Receipt Builder
# --------------------------------------------------

def build_receipt(data):
    receipt = bytearray()

    # -------------------------
    # Parse NEW JSON format
    # -------------------------
    main_guest = json.loads(data["main_guest_information"] or "{}")
    add_on = json.loads(data["add_on_guest"] or "[]")

    guest_list = []

    # -------------------------
    # Main Guest
    # -------------------------
    if main_guest:
        name = f"{main_guest.get('firstName','')} {main_guest.get('lastName','')}".strip()

        pax = int(main_guest.get("pax", 1))

        guest_list.append({
            "name": name if name else "Main Guest",
            "qty": pax
        })

    # -------------------------
    # Add-On Guests
    # -------------------------
    for g in add_on:
        name = f"{g.get('firstName','')} {g.get('lastName','')}".strip()

        qty = int(g.get("accommodations", 1))

        guest_list.append({
            "name": name if name else "Guest",
            "qty": qty
        })

    # -------------------------
    # Totals
    # -------------------------
    subtotal = data["total_net_billing"]
    vat = subtotal * 0.12
    discount = 0
    total = data["total_net_billing"]

    total_pax = sum(g["qty"] for g in guest_list)

    # price per pax (simple distribution)
    price_per_pax = subtotal / total_pax if total_pax else 0

    # -------------------------
    # Header
    # -------------------------
    receipt += ESC + b'@'
    receipt += ESC + b'a\x01'
    receipt += ESC + b'E\x01'
    receipt += ESC + b'E\x00'
    receipt += ESC + b'a\x00'

    receipt += double_line()

    receipt += item_row("Access Type", data["access_type"])
    receipt += item_row("Deck", data["deck_assigned"])
    receipt += item_row("Table", data["table_assigned"])
    receipt += item_row("Card Number", data["assigned_card_number"])
    receipt += item_row("Guests (Pax)", str(total_pax))

    receipt += line()
    receipt += b"GUEST BREAKDOWN\n"
    receipt += line()

    # -------------------------
    # Guests Breakdown
    # -------------------------
    for guest in guest_list:
        amount = guest["qty"] * price_per_pax

        receipt += item_row(
            f"{guest['name']} x{guest['qty']}",
            f"PHP {money(amount)}"
        )

    receipt += line()

    # -------------------------
    # Billing
    # -------------------------
    receipt += item_row("Subtotal", f"PHP {money(subtotal)}")
    receipt += item_row("VAT (12%)", f"PHP {money(vat)}")
    receipt += item_row("Discount Applied", f"PHP {money(discount)}")

    receipt += ESC + b'E\x01'
    receipt += item_row("TOTAL", f"PHP {money(total)}")
    receipt += ESC + b'E\x00'

    receipt += double_line()

    # -------------------------
    # Payment Summary
    # -------------------------
    receipt += ESC + b'a\x01'
    receipt += ESC + b'E\x01'
    receipt += b"PAYMENT SUMMARY\n"
    receipt += ESC + b'E\x00'
    receipt += ESC + b'a\x00'

    receipt += item_row("Mode of Payment", data["mode_of_payment"])
    receipt += item_row("Reference Number", data["reference_number"] or "N/A")

    receipt += item_row(
        "Total Amount Paid",
        f"PHP {money(data['total_amount_paid'])}"
    )

    receipt += item_row(
        "Change",
        f"PHP {money(data['total_change'])}"
    )

    receipt += double_line()

    receipt += ESC + b'a\x01'
    receipt += b"Thank you for choosing\n"
    receipt += b"BLUE OCEAN BAR\n"
    receipt += ESC + b'a\x00'

    return receipt
# --------------------------------------------------
# Printer Sender
# --------------------------------------------------
def send_to_printer_registration(receipt_bytes, logo_path=None):
    output = bytearray()

    if logo_path:
        image = Image.open(logo_path).convert('1')

        if image.width > 384:
            ratio = 384 / image.width
            new_height = int(image.height * ratio)
            image = image.resize((384, new_height))

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
            for x in range(0, w * 8, 8):
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
    sock.connect((printer_ip, port))
    sock.sendall(output)
    sock.close()

if __name__ == "__main__":
    data = {
    "transaction_id": "TRX-9001",

    "main_guest_information": '''
{
    "country": "Philippines",
    "email": "elonsobrevilla06@gmail.com",
    "firstName": "Elon Ybrahim",
    "lastName": "Sobrevilla",
    "formatted_date": "Mar 12, 2026",
    "notes": "",
    "pax": "6",
    "phone": "+63",
    "transactiondate": "2026-03-12",
    "weekday": "Thursday"
}
''',
   "add_on_guest": '''
[
    {
        "accommodations": 1,
        "country": "",
        "discountId": "",
        "email": "",
        "firstName": "Guest 2",
        "fullName": "",
        "id": "17732801719972",
        "isDiscountApplied": false,
        "lastName": "",
        "phone": "",
        "transaction_id": "TXN-00001"
    }
]
''',

    "total_net_billing": 5000,
    "total_amount_paid": 5000,
    "total_change": 0,

    "mode_of_payment": "CASH",
    "reference_number": None,

    "deck_assigned": "Maindeck",
    "table_assigned": "T1 - FRONT FACADE",
    "access_type": "Night Access",
    "assigned_card_number": "card3"
}

    receipt = build_receipt(data)
    send_to_printer_registration(receipt, logo_path="./BlueOceanBar.jpg")