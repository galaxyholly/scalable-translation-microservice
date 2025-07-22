import asyncio
import multiprocessing
import os
import time

import psutil

from usagemonitor import get_ram_usage, get_cpu_info, get_core_usage, get_total_cores
from processspawner import spawn_process_on_core
from errorlogger import error_logger
from config import AVG_ELAPSED_SAMPLE_SIZE, MAX_CPU, MAX_RAM


class QueueManager:
    """
    Manages distributed translation workers across CPU cores.
    Handles task delegation, load balancing, and resource monitoring.
    """
    
    def __init__(self):
        try:
            self.queue_max = 10
            self.queues = {}  # {queue_id: [task_count, pid, core_id, pipe]}
            
            # Resource thresholds
            self.ram_usage_max = MAX_RAM  # Percentage
            self.cpu_usage_max = MAX_CPU  # Percentage
            
            # Task tracking
            self.task_counter = 0
            self.pending_tasks = {}  # {task_id: task_info}

            self.times_avg_list = []
            self.avg_time = None
            
            print("🔧 QueueManager initialized")
        except Exception as e:
            error_logger(e, "Failed to initialize QueueManager")
            raise

    async def is_ram_free(self, reply_context):
        """Check if system has enough available RAM."""
        try:
            ram_data = get_ram_usage()
            if not ram_data or 'percentage' not in ram_data:
                error_logger(ValueError("Invalid RAM data returned"), "RAM check validation")
                return True  # Fail open
                
            ram_percentage = float(ram_data['percentage'].replace('%', ''))
            
            if ram_percentage >= self.ram_usage_max:
                try:
                    await reply_context.message.reply(
                        "System overloaded, please try again later."
                    )
                except Exception as reply_error:
                    error_logger(reply_error, f"Failed to send RAM overload message to user")
                return False
            return True
            
        except ValueError as e:
            error_logger(e, "Failed to parse RAM percentage")
            return True  # Fail open
        except Exception as e:
            error_logger(e, "RAM check failed")
            return True  # Fail open

    def cpu_too_high(self, queue_data):
        """Check if CPU usage is too high for this queue."""
        try:
            if not queue_data or len(queue_data) < 3:
                error_logger(ValueError("Invalid queue data structure"), f"Queue data: {queue_data}")
                return False
                
            core_id = queue_data[2]
            task_count = queue_data[0]
            
            try:
                core_usage = get_core_usage(core_id)
            except Exception as usage_error:
                error_logger(usage_error, f"Failed to get usage for core {core_id}")
                return False  # Assume CPU is fine if we can't measure
            
            print(f"🔍 Core {core_id}: {core_usage}% usage, {task_count} tasks")
            
            result = core_usage >= self.cpu_usage_max
            print(f"🔍 CPU too high? {result} (core usage: {core_usage}%, threshold: {self.cpu_usage_max}%)")
            
            return result
            
        except (IndexError, TypeError) as e:
            error_logger(e, f"Invalid queue data structure: {queue_data}")
            return False
        except Exception as e:
            error_logger(e, f"CPU check failed for queue data: {queue_data}")
            return False

    def queue_full(self, queue_data):
        """Check if queue has reached maximum capacity."""
        try:
            if not queue_data or len(queue_data) < 1:
                error_logger(ValueError("Invalid queue data for fullness check"), f"Queue data: {queue_data}")
                return True  # Assume full if we can't check
                
            return queue_data[0] >= self.queue_max
        except Exception as e:
            error_logger(e, f"Queue fullness check failed for data: {queue_data}")
            return True  # Assume full on error

    def make_new_queue(self, core_id):
        """Create a new worker queue on specified core."""
        try:
            if core_id < 0 or core_id >= get_total_cores():
                error_logger(ValueError(f"Invalid core ID: {core_id}"), f"Total cores: {get_total_cores()}")
                return None
                
            pid, actual_core_id, pipe = spawn_process_on_core(core_id)
            
            if not pipe:
                error_logger(RuntimeError("Pipe creation failed"), f"Core {core_id}")
                return None
                
            queue_id = len(self.queues) + 1
            self.queues[queue_id] = [0, pid, actual_core_id, pipe]
            print(f"🆕 Created queue {queue_id} on core {actual_core_id}")
            return queue_id
            
        except Exception as e:
            error_logger(e, f"Failed to create queue on core {core_id}")
            return None

    def queue_check(self):
        """Find an available queue or create a new one."""
        try:
            # Get CPU usage for all cores ONCE
            try:
                all_core_usage = psutil.cpu_percent(interval=0.1, percpu=True)
                if not all_core_usage:
                    raise ValueError("Empty CPU usage data")
            except Exception as e:
                error_logger(e, "Failed to get CPU usage")
                all_core_usage = [0] * get_total_cores()  # Fallback
            
            # Find available queues using pre-measured CPU data
            good_queues = []
            for queue_id, queue_data in self.queues.items():
                try:
                    if not queue_data or len(queue_data) < 3:
                        error_logger(ValueError("Malformed queue data"), f"Queue {queue_id}: {queue_data}")
                        continue
                        
                    core_id = queue_data[2]
                    task_count = queue_data[0]
                    
                    # Use pre-measured CPU data instead of calling get_core_usage()
                    core_usage = all_core_usage[core_id] if core_id < len(all_core_usage) else 0
                    
                    cpu_too_high = core_usage >= self.cpu_usage_max
                    queue_full = task_count >= self.queue_max
                    
                    print(f"🔍 Core {core_id}: {core_usage}% usage, {task_count} tasks")
                    print(f"🔍 CPU too high? {cpu_too_high} (core usage: {core_usage}%, threshold: {self.cpu_usage_max}%)")
                    
                    if not cpu_too_high and not queue_full:
                        good_queues.append(queue_id)
                        
                except Exception as queue_error:
                    error_logger(queue_error, f"Error checking queue {queue_id}")
                    continue

            if good_queues:
                return good_queues[0]
            elif len(self.queues) >= get_total_cores():
                return None  # All cores busy
            else:
                core_id = len(self.queues)
                return self.make_new_queue(core_id)
                
        except Exception as e:
            error_logger(e, "Queue check failed")
            return None

    async def task_sort(self, task, reaction):
        """Main entry point for processing translation requests."""
        try:
            if not task or not reaction:
                error_logger(ValueError("Invalid task or reaction"), f"Task: {task}, Reaction: {reaction}")
                return
                
            # Check system resources
            if not await self.is_ram_free(reaction):
                return

            # Find available queue
            queue_id = self.queue_check()
            if not queue_id:
                try:
                    await reaction.message.reply(
                        "Bot is processing too many requests, please try again later."
                    )
                except Exception as reply_error:
                    error_logger(reply_error, "Failed to send overload message")
                return

            # Create and track task
            self.task_counter += 1
            task_id = self.task_counter

            self.pending_tasks[task_id] = {
                'reaction': reaction,
                'queue_id': queue_id,
                'sent_time': time.time()
            }

            # Send task to worker
            try:
                task_data = {'id': task_id, 'task': task}
                
                if queue_id not in self.queues or len(self.queues[queue_id]) < 4:
                    error_logger(ValueError("Invalid queue structure"), f"Queue {queue_id}: {self.queues.get(queue_id)}")
                    return
                    
                pipe = self.queues[queue_id][3]
                if not pipe:
                    error_logger(RuntimeError("Pipe is None"), f"Queue {queue_id}")
                    return
                    
                pipe.send(task_data)
                self.queues[queue_id][0] += 1
                
            except (BrokenPipeError, ConnectionError) as pipe_error:
                error_logger(pipe_error, f"Pipe communication failed for queue {queue_id}")
                # Clean up broken queue
                try:
                    del self.queues[queue_id]
                    del self.pending_tasks[task_id]
                except:
                    pass
                await reaction.message.reply("❌ Translation service temporarily unavailable")
            
        except Exception as e:
            error_logger(e, "Task sorting failed")
            try:
                await reaction.message.reply("❌ Translation service error")
            except:
                pass  # Don't log Discord reply failures in the main exception handler

    async def handle_completed_task(self, task_id, result, time_of_recv):
        """Handle completed translation and reply to user."""
        try:
            if task_id not in self.pending_tasks:
                error_logger(ValueError(f"Unknown task ID: {task_id}"), "Task completion error")
                return

            task_info = self.pending_tasks[task_id]
            if not task_info:
                error_logger(ValueError("Empty task info"), f"Task ID: {task_id}")
                return
                
            reaction = task_info.get('reaction')
            queue_id = task_info.get('queue_id')
            start_time = task_info.get('sent_time')
            
            if not all([reaction, queue_id is not None, start_time]):
                error_logger(ValueError("Incomplete task info"), f"Task {task_id}: {task_info}")
                return

            # Calculate elapsed time
            try:
                elapsed_time = time_of_recv - start_time
                self.avg_list_calc(elapsed_time)
            except Exception as timing_error:
                error_logger(timing_error, f"Failed to calculate elapsed time for task {task_id}")

            # Reply to user
            try:
                if not result:
                    result = "[Translation failed]"
                await reaction.message.reply(f"🇩🇪➡️🇺🇸 {result}")
            except Exception as reply_error:
                error_logger(reply_error, f"Failed to send translation result for task {task_id}")

            # Clean up
            try:
                del self.pending_tasks[task_id]
                
                if queue_id in self.queues and len(self.queues[queue_id]) > 0:
                    self.queues[queue_id][0] -= 1
                else:
                    error_logger(ValueError("Invalid queue during cleanup"), f"Queue {queue_id}")
            except Exception as cleanup_error:
                error_logger(cleanup_error, f"Failed to clean up task {task_id}")
            
            # Clean up empty queues
            try:
                empty_queues = []
                for q_id, queue_data in self.queues.items():
                    if queue_data and len(queue_data) > 0 and queue_data[0] == 0:
                        empty_queues.append(q_id)
                
                # Close empty queues (keep at least 1)
                for q_id in empty_queues[1:]:  # Skip first empty queue
                    try:
                        if q_id in self.queues and len(self.queues[q_id]) > 3:
                            pipe = self.queues[q_id][3]
                            if pipe:
                                pipe.send("STOP")
                            del self.queues[q_id]
                            print(f"🧹 Closed empty queue {q_id}")
                    except Exception as queue_cleanup_error:
                        error_logger(queue_cleanup_error, f"Failed to close queue {q_id}")

                print(f"✅ Task {task_id} completed, queue {queue_id} now has {self.queues.get(queue_id, [0])[0]} tasks")
                
            except Exception as queue_management_error:
                error_logger(queue_management_error, "Failed to manage empty queues")

        except Exception as e:
            error_logger(e, f"Failed to handle completed task {task_id}")

    async def async_monitor(self):
        """Monitor all worker pipes for completed translations."""
        print("👀 Monitor started...")
        
        while True:
            try:
                # Only process if we have active queues
                if not self.queues:
                    await asyncio.sleep(0.5)  # Longer sleep when no queues
                    continue
                
                any_data_processed = False
                
                # Create a copy of queue items to avoid modification during iteration
                queue_items = list(self.queues.items())
                
                for queue_id, queue_data in queue_items:
                    try:
                        if not queue_data or len(queue_data) < 4:
                            error_logger(ValueError("Invalid queue data in monitor"), f"Queue {queue_id}: {queue_data}")
                            continue
                            
                        pipe = queue_data[3]
                        if not pipe:
                            error_logger(ValueError("Pipe is None"), f"Queue {queue_id}")
                            continue
                        
                        # Check if pipe has data without blocking
                        if pipe.poll():
                            try:
                                result = pipe.recv()
                                if isinstance(result, dict) and 'id' in result and 'result' in result:
                                    task_id = result['id']
                                    translation = result['result']
                                    time_of_recv = result.get('time_finished', time.time())
                                    await self.handle_completed_task(task_id, translation, time_of_recv)
                                    any_data_processed = True
                                else:
                                    error_logger(ValueError("Invalid result format"), f"Queue {queue_id}: {result}")
                                    
                            except (EOFError, BrokenPipeError) as pipe_error:
                                error_logger(pipe_error, f"Pipe broken for queue {queue_id}")
                                # Remove broken queue
                                try:
                                    del self.queues[queue_id]
                                except:
                                    pass
                            except Exception as process_error:
                                error_logger(process_error, f"Error processing queue {queue_id}")
                                
                    except Exception as queue_error:
                        error_logger(queue_error, f"Error monitoring queue {queue_id}")
                        continue
                
                # Adaptive sleep - shorter if we processed data, longer if idle
                if any_data_processed:
                    await asyncio.sleep(0.05)  # 50ms when active
                else:
                    await asyncio.sleep(0.2)   # 200ms when idle
                    
            except Exception as e:
                error_logger(e, "Monitor loop error")
                await asyncio.sleep(1)

    def shutdown_all_queues(self):
        """Gracefully shutdown all worker processes."""
        try:
            for queue_id, queue_data in self.queues.items():
                try:
                    if queue_data and len(queue_data) > 3:
                        pipe = queue_data[3]
                        if pipe:
                            pipe.send("STOP")
                            print(f"🔄 Sent shutdown signal to queue {queue_id}")
                        else:
                            error_logger(ValueError("Pipe is None during shutdown"), f"Queue {queue_id}")
                    else:
                        error_logger(ValueError("Invalid queue data during shutdown"), f"Queue {queue_id}: {queue_data}")
                except Exception as queue_shutdown_error:
                    error_logger(queue_shutdown_error, f"Failed to shutdown queue {queue_id}")
        except Exception as e:
            error_logger(e, "Failed to shutdown all queues")

    def avg_list_calc(self, new_time_elapsed):
        """Calculate running average of translation times."""
        try:
            if not isinstance(new_time_elapsed, (int, float)) or new_time_elapsed < 0:
                error_logger(ValueError(f"Invalid elapsed time: {new_time_elapsed}"), "Average calculation")
                return self.avg_time or 0

            if len(self.times_avg_list) < AVG_ELAPSED_SAMPLE_SIZE:
                self.times_avg_list.append(new_time_elapsed)
            elif len(self.times_avg_list) == AVG_ELAPSED_SAMPLE_SIZE:
                self.times_avg_list.pop(0)  # Remove oldest (FIFO)
                self.times_avg_list.append(new_time_elapsed)
            else:
                # This shouldn't happen, but handle gracefully
                error_logger(ValueError(f"Unexpected list size: {len(self.times_avg_list)}"), "Average calculation")
                self.times_avg_list = [new_time_elapsed]

            # Calculate and store average
            if self.times_avg_list:
                self.avg_time = sum(self.times_avg_list) / len(self.times_avg_list)
                return self.avg_time
            else:
                self.avg_time = 0
                return 0
                
        except Exception as e:
            error_logger(e, f"Failed to calculate average for time: {new_time_elapsed}")
            return self.avg_time or 0