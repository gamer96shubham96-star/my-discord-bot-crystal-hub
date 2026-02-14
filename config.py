import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

# Brand Colors
BRAND_COLOR = 0xAA78FF
SUCCESS_COLOR = 0x2ECC71
ERROR_COLOR = 0xE74C3C
GOLD_COLOR = 0xF1C40F

# System Settings
AUTO_CLOSE_SECONDS = 1800
APPLICATION_COOLDOWN = 86400
