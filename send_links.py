"""
Driver Link Generator
=====================
Generates personalized POD capture links for drivers at drop-off locations.

This can be run as a standalone script or integrated into your dispatch workflow.
It fetches the current AT_DROP_OFF_LOCATION shipments and generates
WhatsApp-compatible links for each driver.

Usage:
    python send_links.py                   # Print all links
    python send_links.py --send-whatsapp   # Open WhatsApp links (desktop)
"""

import requests
import pandas as pd
from io import BytesIO
from urllib.parse import quote
import argparse
import sys

REDASH_API_URL = (
    "https://redash.trella.co/api/queries/4922/results.csv"
    "?api_key=TX9ND3NoDL0xHNFcbFKvWwPMQAnouCXcywp1tAdz"
)

# ── Update this to your deployed Streamlit app URL ──
APP_BASE_URL = "https://your-app.streamlit.app"


# WhatsApp message templates per language
MESSAGES = {
    "ar": (
        "مرحباً {driver_name}،\n\n"
        "أنت الآن في موقع التفريغ للشحنة {shipment_key}.\n"
        "يرجى النقر على الرابط التالي لتحميل إثبات التسليم:\n\n"
        "{link}\n\n"
        "شكراً لك - فريق تريلا 🚛"
    ),
    "en": (
        "Hello {driver_name},\n\n"
        "You have arrived at the drop-off location for shipment {shipment_key}.\n"
        "Please click the link below to upload your Proof of Delivery:\n\n"
        "{link}\n\n"
        "Thank you - Trella Team 🚛"
    ),
    "ur": (
        "السلام علیکم {driver_name}،\n\n"
        "آپ شپمنٹ {shipment_key} کے ڈراپ آف مقام پر پہنچ گئے ہیں۔\n"
        "براہ کرم ڈیلیوری کا ثبوت اپ لوڈ کرنے کے لیے نیچے دیے گئے لنک پر کلک کریں:\n\n"
        "{link}\n\n"
        "شکریہ - ٹریلا ٹیم 🚛"
    ),
}


def fetch_dropoff_shipments() -> pd.DataFrame:
    """Fetch all shipments currently at drop-off status."""
    resp = requests.get(REDASH_API_URL, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(BytesIO(resp.content))
    # Filter for AT_DROP_OFF_LOCATION status
    dropoff = df[df["status"] == "AT_DROP_OFF_LOCATION"].copy()
    return dropoff


def generate_driver_link(shipment_key: str) -> str:
    """Generate the POD capture link for a specific shipment."""
    return f"{APP_BASE_URL}/?shipment={shipment_key}"


def generate_whatsapp_link(phone: str, message: str) -> str:
    """Generate a WhatsApp click-to-chat link."""
    # Clean phone number (remove spaces, dashes, ensure country code)
    clean_phone = "".join(c for c in str(phone) if c.isdigit())
    if clean_phone.startswith("05"):  # Saudi mobile starting with 05
        clean_phone = "966" + clean_phone[1:]
    elif not clean_phone.startswith("966"):
        clean_phone = "966" + clean_phone
    return f"https://wa.me/{clean_phone}?text={quote(message)}"


def main():
    parser = argparse.ArgumentParser(description="Generate POD links for drivers")
    parser.add_argument(
        "--send-whatsapp",
        action="store_true",
        help="Generate WhatsApp click-to-send links",
    )
    parser.add_argument(
        "--lang",
        choices=["ar", "en", "ur"],
        default="ar",
        help="Message language (default: ar)",
    )
    args = parser.parse_args()

    print("Fetching shipments at drop-off locations...")
    df = fetch_dropoff_shipments()

    if df.empty:
        print("No shipments currently at drop-off location.")
        sys.exit(0)

    print(f"\nFound {len(df)} shipment(s) at drop-off:\n")
    print("-" * 80)

    for _, row in df.iterrows():
        shipment_key = row["key"]
        driver_name = row.get("carrier", "Driver")
        phone = row.get("carrier_mobile", "")
        plate = row.get("vehicle_plate", "")
        destination = row.get("destination_city", "")

        pod_link = generate_driver_link(shipment_key)

        print(f"  Driver:      {driver_name}")
        print(f"  Phone:       {phone}")
        print(f"  Plate:       {plate}")
        print(f"  Destination: {destination}")
        print(f"  POD Link:    {pod_link}")

        if args.send_whatsapp and phone:
            msg = MESSAGES[args.lang].format(
                driver_name=driver_name,
                shipment_key=shipment_key,
                link=pod_link,
            )
            wa_link = generate_whatsapp_link(phone, msg)
            print(f"  WhatsApp:    {wa_link}")

        print("-" * 80)


if __name__ == "__main__":
    main()
