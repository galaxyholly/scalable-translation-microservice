# Scalable Translation Microservice

A high-performance Discord bot that demonstrates distributed systems architecture and real-time resource management using Python multiprocessing.

## Architecture Highlights

- **Distributed Worker System**: Spawns translation workers across multiple CPU cores with automatic load balancing
- **Real-time Monitoring**: Live CPU, RAM, and queue monitoring with web dashboard
- **Resource-Aware Scaling**: Automatically creates/destroys workers based on system load and demand
- **Process Isolation**: Each translation task runs in isolated processes for stability and performance
- **Inter-Process Communication**: Uses multiprocessing pipes for efficient task distribution

## Technical Features

- CPU core affinity for optimal performance
- Adaptive queue management with overflow protection
- Comprehensive error handling and logging
- RESTful monitoring API with JSON endpoints
- Async/await patterns for concurrent operations
- Flask web interface for real-time system metrics

## Use Case
Currently optimized for German-to-English translation via Discord reactions, but the architecture easily extends to any CPU-intensive task requiring distributed processing.

## Setup

### Prerequisites
- Python 3.12 - (Required - argostranslate compatibility)
- Discord Bot Token

### Installation

1. Clone the repository:
```bash
git clone https://github.com/galaxyholly/scalable-translation-microservice.git
cd scalable-translation-microservice
```

2. Install Dependencies:
```bash
pip install -r requirements.txt
```

3. Create environment file
```bash
cp .env.example .env
```

4. Edit .env with your actual token.

5. Run the bot.
```bash
python galaxybot.py
```

## Usage

React to any message with 🇩🇪 to translate it from German to English. 

**Live Monitoring**: While the bot is running, visit http://127.0.0.1:5000/dashboard to view real-time system metrics and performance data.
