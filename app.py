# bot.py
import random
import os
import sys
from dotenv import load_dotenv
import discord
import multiprocessing
import time
import asyncio
from pathlib import Path
from utilmonitor import start_webserver
from flask import Flask, jsonify, render_template
from discord.ext import commands
from config import intents, HEALTH_CHECK_INTERVAL, STARTUP_DELAY
from errorlogger import error_logger
from botdb import status_retrieve

# Loading auth information into variables.
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

def validate_environment():
    required_vars = {
        'DISCORD_TOKEN': TOKEN,
        'DISCORD_GUILD': GUILD
    }
    
    # This says, iterate through required_vars, make the list out of the var variable, which is the key of the key value pair, that is only stored if it checks and finds no value pair. Oof, love list comprehensions.
    missing = [var for var, value in required_vars.items() if not value] 
    if missing:
        error_logger(ValueError(f"Missing required environment variables: {', '.join(missing)}"))
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        

# Check validation first as it's the first potential non-import error.
validate_environment()

app = Flask(__name__)

def start_bot(reports):
    bot = commands.Bot(command_prefix='$', intents=intents) # Self Explanatory
    bot.reports = reports

    @bot.event
    async def on_ready():
        print('...process_starts...')
        try:
            cogs_dir = Path(__file__).parent / "cogs"
            for filename in os.listdir(cogs_dir):
                if filename.endswith('.py'):
                    await bot.load_extension(f'cogs.{filename[:-3]}')
        except FileNotFoundError as e:
            error_logger(e, "Cogs directory not found")
            sys.exit()
        except ImportError as e:
            error_logger(e, "Failed to load cog")
            sys.exit()

        translate_cog = bot.get_cog('Translate')  # Get the cog instance

        if translate_cog:
            # Access the queue_manager through the cog's module
            from cogs.translate import queue_manager
            queue_manager.monitor_task = asyncio.create_task(queue_manager.async_monitor())
            print("🚀 Started async monitor task")
        else:
            error_logger(RuntimeError("Could not load cog"), "Critical startup failure")
            raise RuntimeError("Could not load cog")
            
        # Just sets the bot's presence or status to a random string in the status.txt file
        await bot.change_presence(activity=discord.Game(status_retrieve()))
       
    @bot.event # This is the on_message handler. Every time a message is sent in any channel, this handler will catch it and process it as follows:
    async def on_message(message):
        await bot.process_commands(message) # This tells the bot to send any commands it detects to processing.
        
    
    return bot.run(TOKEN)



def start_gui(reports):
    print("starting webserver...")
    try:
        start_webserver(reports)  # Pass reports here
    except Exception as e:
        error_logger(e, "Flask server error")
        sys.exit()


if __name__=='__main__':
    def start_processes(): # This is just main(). Will probably rename it later. This function will split the discord bot and flask web server into separate processes so Discord.py has more resources.
        """ Initialize and start both Discord bot and monitoring web server processes.
    
            Manages the main application lifecycle with health monitoring and 
            graceful shutdown handling. """
        # Create reports dictionary
        reports = {
            'cpu': multiprocessing.Value('d', 0),
            'ram': multiprocessing.Value('d', 0),
            'queues': multiprocessing.Value('i', 0),
            'jobs': multiprocessing.Value('i', 0),
            'response_time': multiprocessing.Value('d', 0),
            'connected_servers': multiprocessing.Value('d', 0)
        }

        # Pass to processes
        p1 = multiprocessing.Process(target=start_bot, args=(reports,))
        p2 = multiprocessing.Process(target=start_gui, args=(reports,))
   
            
        p1.start()
        p2.start()
        
        time.sleep(STARTUP_DELAY)
        try:
            while p1.is_alive() and p2.is_alive():
                time.sleep(HEALTH_CHECK_INTERVAL)
            
            # If we get here, one process died
            print("One process failed, shutting down...")
        
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            # Clean up any remaining processes
            if p1.is_alive():
                p1.terminate()
            if p2.is_alive():
                p2.terminate()
        
        p1.join()
        p2.join()

        

    start_processes()

