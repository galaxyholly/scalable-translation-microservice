import os

import discord
from discord import Intents

from botdb import find_project_root


# Setting intents into variables
intents = discord.Intents().all()  # Create intents object
intents.message_content = True  # Discord.py treats message content as privileged

PROJECT_ROOT = find_project_root()

STARTUP_DELAY = 25
HEALTH_CHECK_INTERVAL = 1

AVG_ELAPSED_SAMPLE_SIZE = 10

MAX_CPU = 85
MAX_RAM = 85
