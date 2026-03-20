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



# --------------------------------------------------
# Updated Receipt Builder with footer improvements
# --------------------------------------------------
def build_billout_receipt(data, reservation_json):
    receipt = bytearray()

    guest = json.loads(reservation_json or "{}")
    services = json.loads(data["services_availed"] or "[]")

    # -------------------------
    # HEADER
    # -------------------------
    receipt += ESC + b'@'
    receipt += ESC + b'a\x01'
    receipt += ESC + b'E\x01'
    receipt += b"BLUE OCEAN BAR\n"
    receipt += ESC + b'E\x00'
    receipt += ESC + b'a\x00'

    receipt += double_line()

    # -------------------------
    # TRANSACTION INFO
    # -------------------------
    receipt += f"Transaction ID : {data['transaction_id']}\n".encode()
    receipt += f"Date           : {guest.get('formatted_date','')}\n".encode()
    receipt += f"Day            : {guest.get('weekday','')}\n".encode()

    receipt += line()
    receipt += f"Guest          : {guest.get('firstName','')} {guest.get('lastName','')}\n".encode()
    receipt += f"Pax            : {guest.get('pax','')}\n".encode()
    receipt += f"Phone          : {guest.get('phone','')}\n".encode()
    receipt += line()
    receipt += f"Deck           : {data['deck_assigned']}\n".encode()
    receipt += f"Table          : {data['table_assigned']}\n".encode()
    receipt += f"Card Number    : {data['assigned_card_number']}\n".encode()
    receipt += f"Access Type    : {data['access_type']}\n".encode()
    receipt += f"Attended By    : {data['attended_by']}\n".encode()

    receipt += double_line()

    # -------------------------
    # ORDERED ITEMS
    # -------------------------
    receipt += ESC + b'E\x01'
    receipt += b"ORDER DETAILS\n"
    receipt += ESC + b'E\x00'
    receipt += line()

    subtotal = 0
    for s in services:
        qty = s.get("qty", 1)
        item = s.get("item", "Item")
        price = s.get("price", 0)
        note = s.get("note", "")

        total_price = qty * price
        subtotal += total_price

        receipt += f"{qty} x {item}\n".encode()
        receipt += f"   PHP {money(price)}  = PHP {money(total_price)}\n".encode()
        if note:
            receipt += f"   NOTE: {note}\n".encode()

    receipt += line()

    # -------------------------
    # BILLING SUMMARY
    # -------------------------
    vat = subtotal * 0.12
    discount = subtotal + vat - data["total_net_billing"]

    receipt += item_row("Subtotal", f"PHP {money(subtotal)}")
    receipt += item_row("VAT (12%)", f"PHP {money(vat)}")
    receipt += item_row("Discount", f"PHP {money(discount)}")

    receipt += ESC + b'E\x01'
    receipt += item_row("TOTAL BILL", f"PHP {money(data['total_net_billing'])}")
    receipt += ESC + b'E\x00'

    receipt += double_line()

    # -------------------------
    # PAYMENT SUMMARY
    # -------------------------
    receipt += ESC + b'a\x01'
    receipt += ESC + b'E\x01'
    receipt += b"PAYMENT SUMMARY\n"
    receipt += ESC + b'E\x00'
    receipt += ESC + b'a\x00'

    receipt += item_row("Mode of Payment", data["mode_of_payment"])
    receipt += item_row("Reference No.", data["reference_number"] or "N/A")
    receipt += item_row("Amount Paid", f"PHP {money(data['total_amount_paid'])}")

    receipt += ESC + b'E\x01'
    receipt += GS + b'!\x11'  # BIG TEXT
    receipt += item_row("CHANGE", f"PHP {money(data['total_change'])}")
    receipt += GS + b'!\x00'
    receipt += ESC + b'E\x00'

    receipt += double_line()

    # -------------------------
    # FOOTER + Thank you + QR info
    # -------------------------
    receipt += ESC + b'a\x01'
    receipt += b"Thank you for visiting Blue Ocean Bar!\n"
    receipt += b"Please come again and enjoy our menu.\n"
    receipt += b"Follow us: www.blueoceanbar.com | +63 912 345 6789\n"
    receipt += b"Scan the QR code below for promotions & menu\n"
    receipt += ESC + b'a\x00'

    return receipt
# --------------------------------------------------
# Printer Sender
# --------------------------------------------------
# --------------------------------------------------
# Updated Printer Sender keeping the original name
# --------------------------------------------------
def send_to_printer_registration(receipt_bytes, logo_path=None, qr_path=None):
    output = bytearray()

    printer_width = 576  # ⭐ 80mm printer width


    # ---------------------
    # Add Logo (CENTERED)
    # ---------------------
    if logo_path:
        image = Image.open(logo_path).convert('1')

        # Resize if too wide
        if image.width > printer_width:
            ratio = printer_width / image.width
            image = image.resize(
                (printer_width, int(image.height * ratio)),
                Image.NEAREST
            )

        width, height = image.size
        pixels = image.load()

        left_padding = (printer_width - width) // 2

        image_data = bytearray()
        image_data += b'\x1d\x76\x30\x00'

        w = (printer_width + 7) // 8

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


    # ---------------------
    # Add Receipt Text
    # ---------------------
    output += receipt_bytes


    # ---------------------
    # Add QR (CENTERED)
    # ---------------------
    if qr_path:
        qr_image = Image.open(qr_path).convert('1')

        # Resize only if too big
        if qr_image.width > printer_width:
            ratio = printer_width / qr_image.width
            qr_image = qr_image.resize(
                (printer_width, int(qr_image.height * ratio)),
                Image.NEAREST
            )

        width, height = qr_image.size
        pixels = qr_image.load()

        left_padding = (printer_width - width) // 2

        image_data = bytearray()
        image_data += b'\x1d\x76\x30\x00'

        w = (printer_width + 7) // 8

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
        # ---------------------
    # Cut
    # ---------------------
    output += CUT_SAFE

    # ---------------------
    # Send to Printer
    # ---------------------
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((printer_ip, port))
    sock.sendall(output)
    sock.close()
if __name__ == "__main__":

    # ----------------------------------------
    # DB-LIKE DATA (matches your table columns)
    # ----------------------------------------
    data = {
        "transaction_id": "TRX-9001",
        "type_of_transaction": "walkin",

        "services_availed": '[{"qty":1,"item":"Mojito","note":"","price":250,"waiter":"Anthony"},'
                            '{"qty":8,"item":"Mojito","note":"","price":250,"waiter":"Anthony"}]',

        "total_net_billing": 2520,
        "available_consumables": 0,
        "total_amount_paid": 3000,
        "total_change": 480,

        "mode_of_payment": "CASH",
        "reference_number": None,

        "status": "billout",
        "notes": "",

        "deck_assigned": "Main Deck",
        "table_assigned": "T1 - FRONT FACADE",
        "access_type": "Night Access",
        "assigned_card_number": "card3",
        "attended_by": "Anthony"
    }

    # ----------------------------------------
    # Reservation JSON (guest info)
    # ----------------------------------------
    reservation_json = '''
    {
        "pax":"2",
        "email":"elonsobrevilla06@gmail.com",
        "notes":"asdasdasd",
        "phone":"+63",
        "country":"Philippines",
        "weekday":"Friday",
        "lastName":"Sobrevilla",
        "firstName":"Elon",
        "discountId":"123",
        "formatted_date":"Mar 27, 2026",
        "reservationDate":"2026-03-27"
    }
    '''

    # ----------------------------------------
    # Build + Print
    # ----------------------------------------
    receipt = build_billout_receipt(data, reservation_json)

    send_to_printer_registration(
        receipt,
        logo_path="./images/BlueOceanBar.jpg",
         qr_path="./images/blueoceanbar_qr.png"
    )