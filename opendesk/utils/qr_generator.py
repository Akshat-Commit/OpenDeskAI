import qrcode # type: ignore
from loguru import logger
import sys

from opendesk.config import BOT_USERNAME
from opendesk.utils.session_manager import create_session



def generate_session_qr(ngrok_url: str) -> str:
    """
    Generates a new session and prints a QR code to the terminal.
    Returns the generated session token.
    """
    if not BOT_USERNAME:
        logger.error("BOT_USERNAME is required in .env for QR code generation.")
        print("\n[!] ERROR: Please set BOT_USERNAME in your .env file to use the session linking feature.")
        sys.exit(1)
        
    token = create_session(ngrok_url)
    
    # Construct the deep link URL for Telegram
    bot_url = f"https://t.me/{BOT_USERNAME}?start={token}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(bot_url)
    qr.make(fit=True)
    
    # Print inverted for terminal readability
    qr.print_ascii(invert=True)
    
    print("\n" + "─"*50)
    print("  SCAN WITH PHONE CAMERA TO CONNECT")
    print("  Link expires in 60 seconds.")
    print("─"*50 + "\n")
    
    return token
