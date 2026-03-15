import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendesk.utils.qr_generator import generate_session_qr

if __name__ == "__main__":
    print("Testing QR generation...")
    # Mocking ngrok URL just to test the QR print
    generate_session_qr("https://mock123.ngrok.app")
