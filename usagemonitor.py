import psutil


def get_ram_usage():
    """
    Returns RAM usage as a dictionary with human-readable values.
    
    Returns:
        dict: RAM usage with total, used, available (in GB) and percentage
    """
    memory = psutil.virtual_memory()
    
    return {
        'total': f"{memory.total / (1024**3):.2f} GB",
        'used': f"{memory.used / (1024**3):.2f} GB", 
        'available': f"{memory.available / (1024**3):.2f} GB",
        'percentage': f"{memory.percent}%"
    }


def get_cpu_info():
    """
    Get CPU core count and individual core usage.
    
    Returns:
        dict: CPU information including core counts and usage percentages
    """
    # Get core counts
    physical_cores = psutil.cpu_count(logical=False)
    logical_cores = psutil.cpu_count(logical=True)
    
    # Get per-core usage (need a brief interval for accurate reading)
    per_core_usage = psutil.cpu_percent(interval=1, percpu=True)
    
    # Overall CPU usage
    overall_usage = psutil.cpu_percent(interval=1)
    
    return {
        'physical_cores': physical_cores,
        'logical_cores': logical_cores,
        'per_core_usage': per_core_usage,
        'overall_usage': overall_usage
    }


def get_core_usage(core_id):
    """Debug version to see what's happening with CPU measurements"""
    import time
    
    print(f"🔧 Measuring CPU for core {core_id}")
    
    # Try multiple measurement approaches
    print("Method 1 - Single measurement with 0.1s interval:")
    per_core_1 = psutil.cpu_percent(interval=0.1, percpu=True)
    print(f"  Core {core_id}: {per_core_1[core_id]}%")
    
    print("Method 2 - Non-blocking after brief pause:")
    psutil.cpu_percent(percpu=True)  # Reset baseline
    time.sleep(0.2)
    per_core_2 = psutil.cpu_percent(interval=None, percpu=True)
    print(f"  Core {core_id}: {per_core_2[core_id]}%")
    
    print("Method 3 - Overall system CPU:")
    overall = psutil.cpu_percent(interval=0.1)
    print(f"  Overall system: {overall}%")
    
    print("Method 4 - All cores at once:")
    all_cores = psutil.cpu_percent(interval=0.1, percpu=True)
    for i, usage in enumerate(all_cores):
        print(f"  Core {i}: {usage}%")
    
    return per_core_1[core_id]


def get_total_cores():
    """
    Get total number of CPU cores.
    
    Returns:
        int: Total number of CPU cores
    """
    return psutil.cpu_count()

