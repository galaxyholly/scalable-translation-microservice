import multiprocessing
import os
import sys
import time
import psutil

from errorlogger import error_logger


def worker_process(core_id, pipe):
    try:
        process = psutil.Process(os.getpid())
        process.cpu_affinity([core_id])
        
        print(f"🔧 Worker {os.getpid()} started on core {core_id}")
        
        while True:
            try:
                # Check for work
                if pipe.poll():
                    task_data = pipe.recv()
                    print(f"📥 Worker {os.getpid()} received: {task_data}")
                    
                    if isinstance(task_data, dict) and 'id' in task_data:
                        task_id = task_data['id']
                        text = task_data['task']
                        
                        print(f"🔄 Worker {os.getpid()} translating: {text[:50]}...")
                        
                        # In the worker_process function, change the import:
                        from argosetup import german_to_english  # Changed import
                        result = german_to_english(text)  # Changed function call
                        
                        response = {'id': task_id, 'result': result, 'time_finished': int(time.time())}
                        
                        pipe.send(response)
                        
                    elif task_data == "STOP":
                        print(f"🔄 Worker {os.getpid()} shutting down")
                        break
                else:
                    # CRITICAL: Sleep when no work available
                    time.sleep(0.1)  # 100ms idle sleep
                        
            except (EOFError, BrokenPipeError):
                print(f"📡 Worker {os.getpid()}: Pipe closed, shutting down")
                break
            except Exception as e:
                error_logger(e, f"Worker {os.getpid()} task error")
                time.sleep(0.1)  # Sleep on error too
                
    except Exception as e:
        error_logger(e, f"Worker {os.getpid()} fatal error")
    finally:
        try:
            pipe.close()
        except:
            pass


def spawn_process_on_core(core_id):
    """
    Spawn a translation worker and pin it to a specific CPU core.
    
    Args:
        core_id (int): CPU core ID to pin the worker to
        
    Returns:
        tuple: (process_id, core_id, parent_pipe)
        
    Raises:
        Exception: If process spawning fails
    """
    try:
        # Create bidirectional pipes
        parent_conn, child_conn = multiprocessing.Pipe()
        
        # Create the process
        process = multiprocessing.Process(
            target=worker_process, 
            args=(core_id, child_conn)
        )
        
        # Start it
        process.start()
        
        # Return process info and parent's end of the pipe
        return process.pid, core_id, parent_conn
        
    except Exception as e:
        error_logger(e, f"Failed to spawn worker on core {core_id}")
        raise