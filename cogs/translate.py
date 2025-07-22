import asyncio
import sys

from discord.ext import commands
import discord

import argosetup
from argosetup import german_to_english
from cmdqueue import QueueManager
from errorlogger import error_logger

# Add higher directory to python modules path
sys.path.append("..")

# Initialize queue manager with error handling
try:
    queue_manager = QueueManager()
except Exception as e:
    error_logger(e, "Failed to initialize QueueManager")
    raise


class Translate(commands.Cog):
    """Discord cog for handling German to English translation via reactions."""
    
    def __init__(self, bot):
        try:
            if not bot:
                raise ValueError("Bot instance cannot be None")
                
            self.bot = bot
            self.bot.queue_manager = queue_manager
            print("🔧 Translate cog initialized")
            
        except Exception as e:
            error_logger(e, "Failed to initialize Translate cog")
            raise
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready."""
        try:
            print("🔥 Translate cog ready")
            
            # Verify queue manager is still accessible
            if not hasattr(self.bot, 'queue_manager') or not self.bot.queue_manager:
                error_logger(RuntimeError("Queue manager not available"), "Cog ready check")
                
        except Exception as e:
            error_logger(e, "Error in Translate cog on_ready")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reaction additions for translation requests."""
        try:
            # Validate inputs
            if not reaction:
                error_logger(ValueError("Reaction is None"), "Reaction validation")
                return
                
            if not user:
                error_logger(ValueError("User is None"), "User validation")
                return
            
            # Don't respond to bot's own reactions
            if user.bot:
                return
            
            # Check if reaction has valid message
            if not hasattr(reaction, 'message') or not reaction.message:
                error_logger(ValueError("Reaction has no valid message"), f"Reaction: {reaction}")
                return
                
            # Check if message has content
            if not hasattr(reaction.message, 'content'):
                error_logger(ValueError("Message has no content attribute"), f"Message: {reaction.message}")
                return
                
            message_content = reaction.message.content
            if not message_content or not message_content.strip():
                try:
                    await reaction.message.reply("❌ Cannot translate empty message")
                except Exception as reply_error:
                    error_logger(reply_error, "Failed to send empty message error")
                return
            
            # Check message length (prevent extremely long translations)
            if len(message_content) > 2000:  # Discord's message limit
                try:
                    await reaction.message.reply("❌ Message too long to translate (max 2000 characters)")
                except Exception as reply_error:
                    error_logger(reply_error, "Failed to send message too long error")
                return
                
            # Check for German flag emoji
            if str(reaction.emoji) == '🇩🇪':
                try:
                    # Verify queue manager is available
                    if not hasattr(self.bot, 'queue_manager') or not self.bot.queue_manager:
                        error_logger(RuntimeError("Queue manager not available"), "Translation request")
                        try:
                            await reaction.message.reply("❌ Translation service temporarily unavailable")
                        except Exception as reply_error:
                            error_logger(reply_error, "Failed to send service unavailable message")
                        return
                    
                    # Send to queue manager for processing
                    await self.bot.queue_manager.task_sort(message_content, reaction)
                    
                except AttributeError as attr_error:
                    error_logger(attr_error, f"Missing attribute during translation: {attr_error}")
                    try:
                        await reaction.message.reply("❌ Translation service error")
                    except Exception as reply_error:
                        error_logger(reply_error, "Failed to send service error message")
                        
                except Exception as translation_error:
                    error_logger(translation_error, f"Translation processing failed for message: {message_content[:50]}...")
                    try:
                        await reaction.message.reply("❌ Translation failed, please try again")
                    except Exception as reply_error:
                        error_logger(reply_error, "Failed to send translation failed message")
            
        except discord.errors.NotFound as not_found_error:
            # Message or reaction was deleted - this is normal, don't log as error
            pass
            
        except discord.errors.Forbidden as forbidden_error:
            error_logger(forbidden_error, "Bot lacks permissions to respond to reaction")
            
        except discord.errors.HTTPException as http_error:
            error_logger(http_error, "Discord API error during reaction handling")
            
        except Exception as e:
            error_logger(e, f"Unexpected error in reaction handler - User: {user}, Emoji: {getattr(reaction, 'emoji', 'unknown')}")


async def setup(bot):
    """Setup function for loading the cog."""
    try:
        if not bot:
            raise ValueError("Bot instance cannot be None")
            
        # Verify required imports are available
        try:
            from argosetup import german_to_english
        except ImportError as import_error:
            error_logger(import_error, "Failed to import german_to_english function")
            raise
            
        # Verify queue manager is initialized
        if not queue_manager:
            raise RuntimeError("Queue manager failed to initialize")
            
        await bot.add_cog(Translate(bot))
        print("✅ Translate cog loaded successfully")
        
    except Exception as e:
        error_logger(e, "Failed to setup Translate cog")
        raise