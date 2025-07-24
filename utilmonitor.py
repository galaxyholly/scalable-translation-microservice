from flask import Flask, jsonify, render_template
import psutil
import time
import os
from errorlogger import error_logger



def create_app(reports):
    """Create Flask app with error handling for monitoring endpoints."""
    try:
        if not reports:
            raise ValueError("Reports parameter cannot be None or empty")
            
        # Validate reports structure
        required_keys = ['cpu', 'ram', 'queues', 'jobs', 'response_time', 'connected_servers']
        missing_keys = [key for key in required_keys if key not in reports]
        if missing_keys:
            raise ValueError(f"Reports missing required keys: {missing_keys}")
            
        app = Flask(__name__)
        
        # Configure Flask error handling
        app.config['PROPAGATE_EXCEPTIONS'] = True
        
        @app.errorhandler(500)
        def internal_error(error):
            error_logger(error, "Flask internal server error")
            return jsonify({'error': 'Internal server error', 'timestamp': time.time()}), 500
            
        @app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'Endpoint not found', 'timestamp': time.time()}), 404
        
        @app.route('/dashboard')
        def dashboard():
            try:
                return render_template('dashboard.html')
            except FileNotFoundError as template_error:
                error_logger(template_error, "Dashboard template not found")
                return jsonify({
                    'error': 'Dashboard template not available',
                    'timestamp': time.time()
                }), 500
            except Exception as e:
                error_logger(e, "Error serving dashboard")
                return jsonify({
                    'error': 'Dashboard unavailable',
                    'timestamp': time.time()
                }), 500

        @app.route('/api/stats')
        def stats():
            try:
                # Safely extract values with defaults
                stats_data = {}
                
                for key, default_value in [
                    ('cpu_percent', 0),
                    ('ram_percent', 0), 
                    ('queue_count', 0),
                    ('active_jobs', 0),
                    ('avg_response_time', 0),
                    ('server_count', 0)
                ]:
                    try:
                        if key == 'cpu_percent':
                            raw_value = reports['cpu'].value
                        elif key == 'ram_percent':
                            raw_value = reports['ram'].value
                        elif key == 'queue_count':
                            raw_value = reports['queues'].value
                        elif key == 'active_jobs':
                            raw_value = reports['jobs'].value
                        elif key == 'avg_response_time':
                            raw_value = reports['response_time'].value
                        elif key == 'server_count':
                            raw_value = reports['connected_servers'].value
                        
                        # Validate and sanitize the value
                        if raw_value is None:
                            stats_data[key] = default_value
                        elif isinstance(raw_value, (int, float)):
                            # Ensure reasonable bounds
                            if key in ['cpu_percent', 'ram_percent']:
                                stats_data[key] = max(0, min(100, raw_value))
                            elif key in ['queue_count', 'active_jobs', 'server_count']:
                                stats_data[key] = max(0, int(raw_value))
                            elif key == 'avg_response_time':
                                stats_data[key] = max(0, raw_value)
                            else:
                                stats_data[key] = raw_value
                        else:
                            error_logger(TypeError(f"Invalid data type for {key}: {type(raw_value)}"), f"Stats API value validation")
                            stats_data[key] = default_value
                            
                    except AttributeError as attr_error:
                        error_logger(attr_error, f"Missing attribute for {key}")
                        stats_data[key] = default_value
                    except Exception as value_error:
                        error_logger(value_error, f"Error getting {key} value")
                        stats_data[key] = default_value
                
                # Add timestamp
                stats_data['timestamp'] = time.time()
                
                response = jsonify(stats_data)
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                response.headers['Access-Control-Allow-Origin'] = '*'  # Enable CORS
                
                return response
                
            except Exception as e:
                error_logger(e, "Critical error in stats endpoint")
                return jsonify({
                    'error': 'Stats temporarily unavailable',
                    'timestamp': time.time()
                }), 500
        
        @app.route('/api/debug')
        def debug():
            try:
                debug_data = {}
                
                # Raw values with error handling
                for key, report_key in [
                    ('cpu_raw', 'cpu'),
                    ('ram_raw', 'ram'),
                    ('queues_raw', 'queues'),
                    ('jobs_raw', 'jobs'),
                    ('response_time_raw', 'response_time'),
                    ('servers_raw', 'connected_servers')
                ]:
                    try:
                        if report_key in reports:
                            debug_data[key] = reports[report_key].value
                        else:
                            debug_data[key] = 'N/A'
                    except Exception as debug_error:
                        error_logger(debug_error, f"Error getting debug value for {key}")
                        debug_data[key] = 'ERROR'
                
                # Add system info for debugging
                try:
                    debug_data['system_cpu'] = psutil.cpu_percent(interval=0.1)
                    debug_data['system_ram'] = psutil.virtual_memory().percent
                    debug_data['system_cores'] = psutil.cpu_count()
                except Exception as system_error:
                    error_logger(system_error, "Error getting system debug info")
                    debug_data['system_info'] = 'ERROR'
                
                debug_data['timestamp'] = time.time()
                debug_data['reports_available'] = bool(reports)
                debug_data['report_keys'] = list(reports.keys()) if reports else []
                
                response = jsonify(debug_data)
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Access-Control-Allow-Origin'] = '*'
                
                return response
                
            except Exception as e:
                error_logger(e, "Critical error in debug endpoint")
                return jsonify({
                    'error': 'Debug info unavailable',
                    'timestamp': time.time()
                }), 500
        
        @app.route('/health')
        def health_check():
            """Simple health check endpoint."""
            try:
                # Basic health indicators
                health_status = {
                    'status': 'healthy',
                    'timestamp': time.time(),
                    'reports_connected': bool(reports),
                    'flask_running': True
                }
                
                # Check if we can access reports
                if reports:
                    try:
                        test_value = reports['cpu'].value
                        health_status['reports_accessible'] = True
                    except Exception:
                        health_status['reports_accessible'] = False
                        health_status['status'] = 'degraded'
                else:
                    health_status['reports_accessible'] = False
                    health_status['status'] = 'degraded'
                
                return jsonify(health_status)
                
            except Exception as e:
                error_logger(e, "Health check failed")
                return jsonify({
                    'status': 'unhealthy',
                    'timestamp': time.time(),
                    'error': 'Health check failed'
                }), 500
        
        return app
        
    except Exception as e:
        error_logger(e, "Failed to create Flask app")
        raise


def start_webserver(reports):
    """Start the Flask web server with error handling."""
    try:
        if not reports:
            raise ValueError("Reports parameter is required")
            
        app = create_app(reports)
        
        # Validate port and host
        host = '0.0.0.0'
        port = int(os.environ.get("PORT", 5000))
        
        try:
            # Check if port is available
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                error_logger(RuntimeError(f"Port {port} already in use"), "Webserver startup")
                # Try alternative port
                port = 5001
                
        except Exception as port_check_error:
            error_logger(port_check_error, "Port availability check failed")
        
        try:
            app.run(host=host, port=port, debug=False, threaded=True)
        except OSError as os_error:
            error_logger(os_error, f"Failed to bind to {host}:{port}")
            raise
        except Exception as run_error:
            error_logger(run_error, "Flask app run failed")
            raise
            
    except Exception as e:
        error_logger(e, "Failed to start web server")
        raise 