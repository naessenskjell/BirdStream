#!/usr/bin/env python3
"""
BirdStream - Server Application
Main Flask application for receiving streams and serving web interface.
Integrates all Phase 3 backend modules for stream handling, YouTube routing,
static fallback, network resilience, and configuration management.
Phase 4: Advanced dashboard with WebSocket real-time updates.
"""

import logging
import os
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from datetime import datetime
from time import sleep
import socket

# Import Phase 3 modules
from stream_handler import StreamHandler, StreamBuffer
from youtube_rtmp import YouTubeRTMP
from static_image_handler import StaticImageHandler
from network_resilience import NetworkResilience, StreamState
from settings_manager import SettingsManager
from logger import StreamLogger, MetricsCollector, ConnectionStatistics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app with SocketIO
app = Flask(__name__, static_folder='static', template_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'birdstream-dev-key')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize Phase 3 modules
stream_handler = StreamHandler()
youtube_rtmp = YouTubeRTMP()
static_image_handler = StaticImageHandler()
network_resilience = NetworkResilience(
    stream_handler=stream_handler,
    youtube_rtmp=youtube_rtmp,
    static_images=static_image_handler
)
settings_manager = SettingsManager()
stream_logger = StreamLogger()
metrics_collector = MetricsCollector()
connection_stats = ConnectionStatistics()

# Connected clients tracking
connected_clients = set()
broadcast_thread = None
broadcast_active = False

# State callbacks for UI updates
def on_stream_state_changed(old_state: StreamState, new_state: StreamState, reason: str = ""):
    """Handle stream state changes (callback signature: old_state, new_state, reason)."""
    stream_logger.log_event(
        'INFO',
        'state_change',
        f'Stream state changed: {old_state.value} -> {new_state.value} ({reason})',
        {'old_state': old_state.value, 'new_state': new_state.value, 'reason': reason}
    )

    if new_state == StreamState.LIVE:
        connection_stats.record_new_connection()
    elif new_state in [StreamState.RECONNECTING, StreamState.ERROR, StreamState.OFF]:
        connection_stats.record_disconnection()

# Register state change callback (use the name expected by NetworkResilience)
network_resilience.on_state_change = on_stream_state_changed

# Load YouTube key if available
youtube_key = settings_manager.get('youtube_stream_key')
if youtube_key:
    youtube_rtmp.set_stream_key(youtube_key)
    stream_logger.log_event('INFO', 'youtube', 'YouTube stream key loaded from settings')


# ============================================================================
# WebSocket Event Handlers (Phase 4: Real-time updates)
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    client_id = request.sid
    connected_clients.add(client_id)
    stream_logger.log_event('INFO', 'websocket', f'Client connected: {client_id}')
    
    # Send initial state
    emit('stream_state', {
        'state': network_resilience.current_state.value,
        'timestamp': datetime.now().isoformat(),
    })
    
    emit('connection_response', {
        'status': 'connected',
        'client_id': client_id,
        'timestamp': datetime.now().isoformat(),
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    client_id = request.sid
    connected_clients.discard(client_id)
    stream_logger.log_event('INFO', 'websocket', f'Client disconnected: {client_id}')


@socketio.on('request_status')
def handle_status_request():
    """Handle status request from client."""
    current_state = network_resilience.current_state
    stream_info = stream_handler.get_status()
    
    emit('status_update', {
        'timestamp': datetime.now().isoformat(),
        'stream_state': current_state.value,
        'video_ok': stream_info.get('video_ok', False),
        'audio_ok': stream_info.get('audio_ok', False),
        'active_streams': len(stream_info.get('connections', {})),
        'connection_stats': connection_stats.get_stats(),
    })


@socketio.on('request_metrics')
def handle_metrics_request():
    """Handle metrics request from client."""
    metrics = metrics_collector.get_metrics()
    stream_info = stream_handler.get_status()
    
    emit('metrics_update', {
        'timestamp': datetime.now().isoformat(),
        'stream': metrics['stream'],
        'video': metrics['video'],
        'audio': metrics['audio'],
        'connections': connection_stats.get_stats(),
        'active_streams': len(stream_info.get('connections', {})),
    })


@socketio.on('request_logs')
def handle_logs_request(data):
    """Handle logs request from client."""
    count = data.get('count', 50)
    event_type = data.get('type', None)
    
    logs = stream_logger.get_recent_logs(count=count, event_type=event_type)
    
    emit('logs_update', {
        'timestamp': datetime.now().isoformat(),
        'logs': logs,
        'count': len(logs),
    })


@socketio.on('request_images')
def handle_images_request():
    """Handle images request from client."""
    try:
        images = static_image_handler.list_images()
        
        emit('images_update', {
            'timestamp': datetime.now().isoformat(),
            'images': images,
            'count': len(images),
        })
    except Exception as e:
        emit('error', {
            'message': f'Error listing images: {str(e)}',
            'timestamp': datetime.now().isoformat(),
        })


# Real-time broadcast thread
def broadcast_updates():
    """Broadcast real-time updates to all connected clients."""
    global broadcast_active
    broadcast_active = True
    
    while broadcast_active:
        try:
            if connected_clients:
                # Get current status
                current_state = network_resilience.current_state
                stream_info = stream_handler.get_status()
                metrics = metrics_collector.get_metrics()
                
                # Broadcast to all connected clients. Some socket.io installs don't accept
                # the `broadcast` kwarg here, so emit to each client's room instead.
                payload = {
                    'timestamp': datetime.now().isoformat(),
                    'stream_state': current_state.value,
                    'video_ok': stream_info.get('video_ok', False),
                    'audio_ok': stream_info.get('audio_ok', False),
                    'video_bitrate': metrics['video'].get('estimated_bitrate_kbps', 0),
                    'audio_bitrate': metrics['audio'].get('estimated_bitrate_kbps', 0),
                    'video_frames': metrics['video']['frames'],
                    'audio_frames': metrics['audio']['frames'],
                    'active_streams': len(stream_info.get('connections', {})),
                }

                # Emit to each connected client by room (session id)
                for cid in list(connected_clients):
                    try:
                        socketio.emit('realtime_update', payload, room=cid)
                    except Exception as e:
                        stream_logger.log_event('ERROR', 'broadcast', f'Emit to {cid} failed: {e}')
            
            sleep(1)  # Update every 1 second
            
        except Exception as e:
            stream_logger.log_event('ERROR', 'broadcast', f'Broadcast error: {str(e)}')
            sleep(2)


def start_broadcast_thread():
    """Start background broadcast thread."""
    global broadcast_thread, broadcast_active
    
    if broadcast_thread is None or not broadcast_thread.is_alive():
        broadcast_active = True
        broadcast_thread = threading.Thread(target=broadcast_updates, daemon=True)
        broadcast_thread.start()
        stream_logger.log_event('INFO', 'broadcast', 'Broadcast thread started')


def stop_broadcast_thread():
    """Stop background broadcast thread."""
    global broadcast_active, broadcast_thread
    
    broadcast_active = False
    if broadcast_thread and broadcast_thread.is_alive():
        broadcast_thread.join(timeout=2)
        stream_logger.log_event('INFO', 'broadcast', 'Broadcast thread stopped')


@app.route('/api/status', methods=['GET'])
def api_status():
    """Get current stream status."""
    current_state = network_resilience.current_state
    stream_info = stream_handler.get_status()
    
    stream_logger.log_event('INFO', 'api', 'Status request received')
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'stream_state': current_state.value,
        'video_ok': stream_info.get('video_ok', False),
        'audio_ok': stream_info.get('audio_ok', False),
        'active_streams': len(stream_info.get('connections', {})),
        'connection_stats': connection_stats.get_stats(),
    })


@app.route('/api/stream/health', methods=['GET'])
def api_stream_health():
    """Get stream health details."""
    stream_info = stream_handler.get_status()
    metrics = metrics_collector.get_metrics()
    
    stream_logger.log_event('INFO', 'api', 'Health check request received')
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'video_status': 'ok' if stream_info.get('video_ok', False) else 'offline',
        'audio_status': 'ok' if stream_info.get('audio_ok', False) else 'offline',
        'last_video_frame': stream_info.get('last_video_update'),
        'last_audio_frame': stream_info.get('last_audio_update'),
        'overall_status': 'healthy' if stream_info.get('video_ok', False) and stream_info.get('audio_ok', False) else 'degraded',
        'metrics': metrics,
    })


@app.route('/api/logs', methods=['GET'])
def api_logs():
    """Get recent logs."""
    count = request.args.get('count', default=50, type=int)
    event_type = request.args.get('type', default=None, type=str)
    
    logs = stream_logger.get_recent_logs(count=count, event_type=event_type)
    
    return jsonify({
        'logs': logs,
        'count': len(logs),
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/mode', methods=['POST'])
def api_set_mode():
    """Set stream mode (live, static, off)."""
    data = request.get_json()
    mode = data.get('mode', 'off')  # live, static, off
    
    try:
        if mode == 'live':
            stream_logger.log_event('INFO', 'mode', 'Switching to LIVE mode')
            network_resilience.handle_stream_recovery()
        elif mode == 'static':
            stream_logger.log_event('INFO', 'mode', 'Switching to STATIC mode')
            network_resilience.start_static_fallback()
        else:
            stream_logger.log_event('INFO', 'mode', 'Switching to OFF mode')
            network_resilience.stop()
        
        return jsonify({
            'status': 'ok',
            'message': f'Mode changed to {mode}',
            'current_state': network_resilience.current_state.value,
        })
    except Exception as e:
        stream_logger.log_event('ERROR', 'mode', f'Error changing mode: {str(e)}')
        connection_stats.record_error(str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/settings/youtube-key', methods=['POST'])
def api_set_youtube_key():
    """Update YouTube stream key."""
    data = request.get_json()
    youtube_key = data.get('key')
    
    try:
        if not youtube_key:
            return jsonify({'status': 'error', 'message': 'YouTube key required'}), 400
        
        # Validate and save
        if settings_manager.validate_youtube_key(youtube_key):
            settings_manager.set('youtube_stream_key', youtube_key)
            youtube_rtmp.set_stream_key(youtube_key)
            
            stream_logger.log_event('INFO', 'youtube', 'YouTube stream key updated')
            
            return jsonify({
                'status': 'ok',
                'message': 'YouTube key updated successfully',
            })
        else:
            stream_logger.log_event('WARNING', 'youtube', 'Invalid YouTube key provided')
            return jsonify({'status': 'error', 'message': 'Invalid YouTube key format'}), 400
            
    except Exception as e:
        stream_logger.log_event('ERROR', 'youtube', f'Error setting YouTube key: {str(e)}')
        connection_stats.record_error(str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/images/upload', methods=['POST'])
def api_upload_image():
    """Upload static image."""
    try:
        if 'image' not in request.files:
            return jsonify({'status': 'error', 'message': 'No image provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No file selected'}), 400
        
        # Use static_image_handler to store image
        image_id = static_image_handler.upload_image(file)
        
        stream_logger.log_event('INFO', 'images', f'Image uploaded: {image_id}')
        
        return jsonify({
            'status': 'ok',
            'message': 'Image uploaded successfully',
            'image_id': image_id,
        })
    except Exception as e:
        stream_logger.log_event('ERROR', 'images', f'Error uploading image: {str(e)}')
        connection_stats.record_error(str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/images/list', methods=['GET'])
def api_list_images():
    """List available images."""
    try:
        images = static_image_handler.list_images()
        
        return jsonify({
            'images': images,
            'count': len(images),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        stream_logger.log_event('ERROR', 'images', f'Error listing images: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/images/<image_id>', methods=['DELETE'])
def api_delete_image(image_id):
    """Delete image."""
    try:
        success = static_image_handler.delete_image(image_id)
        
        if success:
            stream_logger.log_event('INFO', 'images', f'Image deleted: {image_id}')
            return jsonify({
                'status': 'ok',
                'message': f'Image {image_id} deleted successfully',
            })
        else:
            return jsonify({'status': 'error', 'message': f'Image {image_id} not found'}), 404
            
    except Exception as e:
        stream_logger.log_event('ERROR', 'images', f'Error deleting image: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/metrics', methods=['GET'])
def api_metrics():
    """Get performance metrics."""
    try:
        metrics = metrics_collector.get_metrics()
        stream_info = stream_handler.get_status()
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'stream': metrics['stream'],
            'video': metrics['video'],
            'audio': metrics['audio'],
            'connections': connection_stats.get_stats(),
            'active_streams': len(stream_info.get('connections', {})),
        })
    except Exception as e:
        stream_logger.log_event('ERROR', 'metrics', f'Error getting metrics: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/debug', methods=['GET'])
def api_debug():
    """Return basic server debug information: hostname and IP addresses."""
    try:
        hostname = socket.gethostname()
        try:
            host_info = socket.gethostbyname_ex(hostname)
            ips = host_info[2]
        except Exception:
            # Fallback: try to enumerate interfaces
            ips = []
            try:
                for iface in socket.getaddrinfo(hostname, None):
                    ip = iface[4][0]
                    if ip not in ips:
                        ips.append(ip)
            except Exception:
                pass

        return jsonify({
            'hostname': hostname,
            'ip_addresses': ips,
            'listening_port': 5000,
            'pid': os.getpid(),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        stream_logger.log_event('ERROR', 'debug', f'Error in debug endpoint: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    """Serve main web interface."""
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker."""
    return jsonify({'status': 'ok'}), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    stream_logger.log_event('WARNING', 'api', f'404 error: {request.path}')
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    stream_logger.log_event('ERROR', 'api', f'Server error: {error}')
    connection_stats.record_error(str(error))
    return jsonify({'error': 'Server error'}), 500


@app.before_request
def before_request():
    """Log incoming requests."""
    if request.path.startswith('/api/'):
        stream_logger.log_event(
            'DEBUG',
            'api',
            f'{request.method} {request.path}'
        )


@app.after_request
def after_request(response):
    """Log response status."""
    if request.path.startswith('/api/'):
        stream_logger.log_event(
            'DEBUG',
            'api',
            f'Response: {response.status_code} for {request.method} {request.path}'
        )
    return response


if __name__ == '__main__':
    try:
        stream_logger.log_event('INFO', 'startup', 'BirdStream server starting')
        
        # Start monitoring
        network_resilience.start_monitoring()
        
        # Start broadcast thread for real-time updates
        start_broadcast_thread()
        
        logger.info("Starting Flask-SocketIO server on port 5000...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
        
    except Exception as e:
        stream_logger.log_event('ERROR', 'startup', f'Server startup failed: {str(e)}')
        logger.error(f"Server startup failed: {e}")
    finally:
        stream_logger.log_event('INFO', 'shutdown', 'BirdStream server shutting down')
        stop_broadcast_thread()
        network_resilience.stop()
        stream_handler.close()
        youtube_rtmp.stop()
        static_image_handler.stop_streaming()
