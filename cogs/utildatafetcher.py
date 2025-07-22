import sys
import psutil
from discord.ext import commands, tasks
from errorlogger import error_logger
import asyncio

# Add higher directory to python modules path
sys.path.append("..")


class Utilities(commands.Cog):
    def __init__(self, bot):
        try:
            if not bot:
                raise ValueError("Bot instance cannot be None")
                
            self.bot = bot
            
            # Verify bot has required reports attribute
            if not hasattr(bot, 'reports'):
                error_logger(AttributeError("Bot missing reports attribute"), "Utilities cog initialization")
                raise AttributeError("Bot must have reports attribute")
                
            # Validate reports structure
            required_keys = ['cpu', 'ram', 'connected_servers', 'queues', 'jobs', 'response_time']
            missing_keys = [key for key in required_keys if key not in bot.reports]
            if missing_keys:
                error_logger(ValueError(f"Missing report keys: {missing_keys}"), "Reports validation")
                raise ValueError(f"Reports missing required keys: {missing_keys}")
                
        except Exception as e:
            error_logger(e, "Failed to initialize Utilities cog")
            raise

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            # Initialize CPU monitoring baseline
            try:
                psutil.cpu_percent(interval=0.1)
            except Exception as cpu_init_error:
                error_logger(cpu_init_error, "Failed to initialize CPU monitoring")
                
            # Start stats collection task
            try:
                self.update_all_stats.start()
            except Exception as task_start_error:
                error_logger(task_start_error, "Failed to start stats collection task")
                raise
                
        except Exception as e:
            error_logger(e, "Error in Utilities cog on_ready")

    async def cog_load(self):
        """Called when the cog is loaded"""
        try:
            await self.bot.wait_until_ready()
            
            try:
                psutil.cpu_percent(interval=0.1)
            except Exception as cpu_init_error:
                error_logger(cpu_init_error, "Failed to initialize CPU monitoring in cog_load")
                
            try:
                self.update_all_stats.start()
            except Exception as task_start_error:
                error_logger(task_start_error, "Failed to start stats task in cog_load")
                
        except Exception as e:
            error_logger(e, "Error in Utilities cog_load")

    @tasks.loop(seconds=0.5)
    async def update_all_stats(self):
        try:
            # Get system metrics with individual error handling
            try:
                cpu_usage = psutil.cpu_percent(interval=None)
                if not isinstance(cpu_usage, (int, float)) or cpu_usage < 0:
                    raise ValueError(f"Invalid CPU usage value: {cpu_usage}")
            except Exception as cpu_error:
                error_logger(cpu_error, "Failed to get CPU usage")
                cpu_usage = 0
                
            try:
                mem_usage = psutil.virtual_memory().percent
                if not isinstance(mem_usage, (int, float)) or mem_usage < 0:
                    raise ValueError(f"Invalid memory usage value: {mem_usage}")
            except Exception as mem_error:
                error_logger(mem_error, "Failed to get memory usage")
                mem_usage = 0
                
            try:
                server_count = len(self.bot.guilds) if self.bot.guilds else 0
                if server_count < 0:
                    raise ValueError(f"Invalid server count: {server_count}")
            except Exception as guild_error:
                error_logger(guild_error, "Failed to get guild count")
                server_count = 0
                
            # Get queue manager metrics
            try:
                if not hasattr(self.bot, 'queue_manager') or not self.bot.queue_manager:
                    queue_count = 0
                    job_count = 0
                    avg_response_time = 0
                else:
                    queue_manager = self.bot.queue_manager
                    
                    try:
                        queue_count = len(queue_manager.queues) if queue_manager.queues else 0
                    except Exception as queue_count_error:
                        error_logger(queue_count_error, "Failed to get queue count")
                        queue_count = 0
                        
                    try:
                        if queue_manager.queues:
                            job_count = sum(queue_data[0] for queue_data in queue_manager.queues.values() 
                                          if queue_data and len(queue_data) > 0)
                        else:
                            job_count = 0
                    except Exception as job_count_error:
                        error_logger(job_count_error, "Failed to calculate job count")
                        job_count = 0
                        
                    try:
                        avg_response_time = getattr(queue_manager, 'avg_time', 0) or 0
                        if not isinstance(avg_response_time, (int, float)) or avg_response_time < 0:
                            avg_response_time = 0
                    except Exception as response_time_error:
                        error_logger(response_time_error, "Failed to get average response time")
                        avg_response_time = 0
                        
            except Exception as queue_manager_error:
                error_logger(queue_manager_error, "Failed to access queue manager")
                queue_count = 0
                job_count = 0
                avg_response_time = 0

            # Update reports with error handling for each metric
            try:
                if hasattr(self.bot, 'reports') and self.bot.reports:
                    metrics = {
                        'cpu': cpu_usage,
                        'ram': mem_usage,
                        'connected_servers': server_count,
                        'queues': queue_count,
                        'jobs': job_count,
                        'response_time': avg_response_time
                    }
                    
                    for metric_name, value in metrics.items():
                        try:
                            if metric_name in self.bot.reports:
                                self.bot.reports[metric_name].value = value
                            else:
                                error_logger(KeyError(f"Missing report key: {metric_name}"), "Report update")
                        except Exception as metric_error:
                            error_logger(metric_error, f"Failed to update {metric_name} metric")
                else:
                    error_logger(AttributeError("Bot reports not available"), "Stats update")
                    
            except Exception as reports_error:
                error_logger(reports_error, "Failed to update reports")
            
        except Exception as e:
            error_logger(e, "Critical error in stats update loop")

    @update_all_stats.before_loop
    async def before_update_stats(self):
        try:
            await self.bot.wait_until_ready()
        except Exception as e:
            error_logger(e, "Error waiting for bot ready in stats task")

    @update_all_stats.error
    async def update_stats_error(self, error):
        """Handle errors in the stats update loop"""
        error_logger(error, "Stats update task error handler")
        
        # Try to restart the task after a delay
        try:
            await asyncio.sleep(5)
            if not self.update_all_stats.is_running():
                self.update_all_stats.start()
        except Exception as restart_error:
            error_logger(restart_error, "Failed to restart stats update task")


async def setup(bot):
    """Setup function for loading the cog."""
    try:
        if not bot:
            raise ValueError("Bot instance cannot be None")
            
        # Verify psutil is working
        try:
            psutil.cpu_percent()
            psutil.virtual_memory()
        except Exception as psutil_error:
            error_logger(psutil_error, "psutil not functioning properly")
            raise
            
        await bot.add_cog(Utilities(bot))
        
    except Exception as e:
        error_logger(e, "Failed to setup Utilities cog")
        raise