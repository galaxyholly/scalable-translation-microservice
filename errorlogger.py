import os
from datetime import datetime
import sys


def error_logger(exception_obj, *args):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_type = type(exception_obj).__name__
        error_message = str(exception_obj)
        context = ' | '.join(str(arg) for arg in args)
        
        log_entry = f"[{timestamp}] {error_type}: {error_message}\n"
        if context:
            log_entry += f"Context: {context}\n"
        log_entry += "\n"
        
        with open("log.txt", 'a') as file:
            file.write(log_entry)
            
    except Exception as e:
        print(f"CRITICAL: Logger failed - {e}")
        sys.exit(1)

