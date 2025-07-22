import os
import random
import sys
from pathlib import Path

from errorlogger import error_logger


def status_retrieve():
    """
    Opens status.txt and picks a random line to set as the bot's presence.
    
    Returns:
        str: Random status line from status.txt
    """
    try:
        with open(find_file_in_dir("status.txt"), "r") as status:
            current_status = [line.strip() for line in status.readlines()]
            return random.choice(current_status)
    except Exception as e:
        error_logger(e, "Issue retrieving status")
        sys.exit(1)


def find_project_root():
    """Walk up from current file until we find project markers."""
    current = Path(__file__).parent
    markers = ['.git', 'requirements.txt', 'galaxybot.py']
    
    while current != current.parent:
        if any((current / marker).exists() for marker in markers):
            return current
        current = current.parent
    return Path(__file__).parent


def find_file_in_dir(file_name_glob_search):
    """
    Find a file in the project directory using glob search.
    
    Args:
        file_name_glob_search (str): Filename to search for
        
    Returns:
        Path: Path to the found file
        
    Raises:
        ValueError: If multiple files found or none found
    """
    root_path = Path(find_project_root())
    found_files = list(root_path.glob(f"**/{file_name_glob_search}"))
    
    if len(found_files) > 1:
        error_obj = ValueError(f"Multiple {file_name_glob_search} files found")
        error_logger(error_obj, "File search error")
        sys.exit(1)
    elif len(found_files) == 0:
        error_obj = FileNotFoundError(f"{file_name_glob_search} not found")
        error_logger(error_obj, "File search error")
        sys.exit(1)
    else:
        return found_files[0]  # Return Path object directly

    
          
