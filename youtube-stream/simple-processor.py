import os
import subprocess
import threading
import time
from flask import Flask, request, render_template_string, jsonify
from werkzeug.utils import secure_filename

# --- Configuration ---
HOLD_IMAGE = '/app/overlays/hold_screen.png'
BREAK_IMAGE = '/app/overlays/temporary_break.png'
RECONNECT_IMAGE = '/app/overlays/reconnecting_screen.png'
RTSP_URL = os.getenv('RTSP_URL', 'rtsp://192.168.0.22:8554/cam')
WIDTH, HEIGHT, FPS = 1920, 1080, 30
UPLOAD_FOLDER = '/app/overlays'
CUSTOM_IMAGE = os.path.join(UPLOAD_FOLDER, 'custom_screen.png')

# --- State management ---
state_lock = threading.Lock()
current_state = 'hold'

youtube_key_lock = threading.Lock()
youtube_key = os.getenv('YOUTUBE_STREAM_KEY')

def get_youtube_url():
	# Build the YouTube RTMP URL from the current key
	with youtube_key_lock:
		return f'rtmp://a.rtmp.youtube.com/live2/{youtube_key}'

# --- Flask UI ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
	<title>Stream Control</title>
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<style>
		body {
			font-family: Arial, sans-serif;
			text-align: center;
			margin: 0;
			padding: 0;
			background: #f7f7f7;
		}
		.container {
			max-width: 400px;
			margin: 40px auto;
			background: #fff;
			border-radius: 12px;
			box-shadow: 0 2px 8px rgba(0,0,0,0.08);
			padding: 24px 16px 32px 16px;
		}
		h1 {
			font-size: 2em;
			margin-bottom: 18px;
			color: #333;
		}
		.section-title {
			font-size: 1.1em;
			font-weight: bold;
			margin: 24px 0 10px 0;
			color: #1976d2;
			text-align: left;
		}
		#currentState {
			font-size: 1.1em;
			margin: 18px 0 24px 0;
			color: #555;
		}
		.button-row {
			display: flex;
			flex-wrap: wrap;
			justify-content: center;
			gap: 12px;
			margin-bottom: 18px;
		}
		.primary-actions {
			display: flex;
			justify-content: center;
			gap: 12px;
			margin-bottom: 18px;
		}
		.secondary-actions {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 12px;
			margin-bottom: 18px;
		}
		.live-btn {
			background: #d32f2f;
			color: #fff;
			border: none;
			border-radius: 6px;
			padding: 14px 28px;
			font-size: 1.1em;
			font-weight: bold;
			cursor: pointer;
			box-shadow: 0 1px 4px rgba(0,0,0,0.07);
			transition: background 0.2s;
		}
		.live-btn:hover, .live-btn:active {
			background: #b71c1c;
		}
		.break-btn {
			background: #388e3c;
			color: #fff;
			border: none;
			border-radius: 6px;
			padding: 14px 28px;
			font-size: 1.1em;
			font-weight: bold;
			cursor: pointer;
			box-shadow: 0 1px 4px rgba(0,0,0,0.07);
			transition: background 0.2s;
		}
		.break-btn:hover, .break-btn:active {
			background: #1b5e20;
		}
		button {
			padding: 12px 20px;
			font-size: 1em;
			border: none;
			border-radius: 6px;
			background: #1976d2;
			color: #fff;
			cursor: pointer;
			transition: background 0.2s;
			box-shadow: 0 1px 4px rgba(0,0,0,0.07);
		}
		button:hover, button:active {
			background: #1565c0;
		}
		form {
			margin-top: 10px;
		}
		label {
			display: block;
			margin-bottom: 8px;
			font-size: 1em;
			color: #333;
		}
		input[type=text] {
			padding: 10px;
			font-size: 1em;
			width: 100%;
			max-width: 300px;
			border: 1px solid #ccc;
			border-radius: 6px;
			margin-bottom: 12px;
			box-sizing: border-box;
		}
		@media (max-width: 600px) {
			.container {
				max-width: 98vw;
				padding: 12px 4vw 24px 4vw;
			}
			h1 {
				font-size: 1.3em;
			}
			.live-btn, .break-btn {
				font-size: 1em;
				padding: 10px 12px;
			}
			button {
				font-size: 0.95em;
				padding: 10px 12px;
			}
			input[type=text] {
				font-size: 0.95em;
			}
		}
	</style>
</head>
<body>
	<div class="container">
		<h1>Stream Overlay Control</h1>
        <hr>
		<div id="currentState">Huidige status: <span id="stateValue">...</span></div>

		<div class="section-title">Vlugge acties</div>
		<div class="primary-actions">
			<button class="live-btn" onclick="sendState('live')">Live Camera</button>
			<button class="break-btn" onclick="sendState('break')">Pauzescherm</button>
		</div>
        <hr>

		<div class="section-title">Andere acties</div>
		<div class="secondary-actions">
			<button onclick="sendState('hold')">Wachtscherm</button>
			<button onclick="sendState('custom')">Custom Afbeelding</button>
			<button onclick="sendState('reconnecting')">Reconnect Scherm</button>
			<button onclick="sendState('stopped')">Stop Stream</button>
		</div>
        
        <div class="section-title">Upload Custom Overlay Afbeelding</div>
		<form id="uploadForm" enctype="multipart/form-data" method="post" action="/upload_image">
			<input type="file" id="customImage" name="customImage" accept="image/png,image/jpeg" required>
			<button type="submit">Upload</button>
		</form>
		<div id="uploadStatus" style="margin-top:10px;color:#1976d2;"></div>
        <hr>

		<div class="section-title">YouTube Stream Key</div>
		<form id="keyForm" onsubmit="updateKey(event)">
			<label for="streamKey">Update Stream Key:</label>
			<input type="text" id="streamKey" name="streamKey" required>
			<button type="submit">Update Key</button>
		</form>		
	</div>
	<script>
		function sendState(state) {
			fetch('/set_state', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ state: state })
			})
			.then(response => response.json())
			.then(data => {
				updateStateDisplay();
			})
			.catch(error => alert('Error: ' + error));
		}
		function updateKey(event) {
			event.preventDefault();
			const key = document.getElementById('streamKey').value;
			fetch('/set_key', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ key: key })
			})
			.then(response => response.json())
			.then(data => {
			})
			.catch(error => alert('Error: ' + error));
		}
		function updateStateDisplay() {
			fetch('/get_state')
			.then(response => response.json())
			.then(data => {
				document.getElementById('stateValue').textContent = data.state;
			});
		}
		setInterval(updateStateDisplay, 1000);
		window.onload = updateStateDisplay;

		document.getElementById('uploadForm').onsubmit = function(e) {
			e.preventDefault();
			const formData = new FormData(document.getElementById('uploadForm'));
			fetch('/upload_image', {
				method: 'POST',
				body: formData
			})
			.then(response => response.json())
			.then(data => {
				document.getElementById('uploadStatus').textContent = data.message;
			})
			.catch(error => {
				document.getElementById('uploadStatus').textContent = 'Upload mislukt';
			});
		};
	</script>
</body>
</html>
"""

@app.route('/')
def index():
	return render_template_string(INDEX_HTML)

@app.route('/upload_image', methods=['POST'])
def upload_image():
	# Handle custom image upload (no resolution check, robust PIL usage)
	if 'customImage' not in request.files:
		return jsonify({'status': 'error', 'message': 'Fout bij het uploaden van de afbeelding'}), 400
	file = request.files['customImage']
	if file.filename == '':
		return jsonify({'status': 'error', 'message': 'Geen bestand geselecteerd'}), 400
	if file and allowed_file(file.filename):
		try:
			# Save file directly, then verify it's a valid image
			save_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename('custom_screen.png'))
			file.save(save_path)
			# Use PIL to open and immediately close the image (do not use .verify())
			from PIL import Image
			img = Image.open(save_path)
			img.close()
			return jsonify({'status': 'ok', 'message': 'Afbeelding geüpload!'})
		except Exception as e:
			return jsonify({'status': 'error', 'message': 'Ongeldige afbeelding'}), 400
	return jsonify({'status': 'error', 'message': 'Ongeldig bestandstype, alleen PNG en JPEG zijn toegestaan'}), 400

@app.route('/set_state', methods=['POST'])
def set_state():
	# Change the stream state (hold/break/live/stopped/custom/reconnecting)
	data = request.get_json()
	state = data.get('state')
	if state in ['hold', 'break', 'live', 'stopped', 'custom', 'reconnecting']:
		with state_lock:
			global current_state
			current_state = state
		print(f"State set to: {state}")
		return jsonify({'status': 'ok', 'state': state})
	return jsonify({'status': 'error', 'message': 'Invalid state'}), 400

@app.route('/set_key', methods=['POST'])
def set_key():
	# Update the YouTube stream key
	data = request.get_json()
	key = data.get('key')
	if key and isinstance(key, str) and len(key) > 0:
		with youtube_key_lock:
			global youtube_key
			youtube_key = key
		print(f"YouTube stream key updated: {key}")
		# Force ffmpeg restart by setting last_state to None
		with state_lock:
			pass  # No-op, triggers restart in main_loop
		return jsonify({'status': 'ok', 'key': key})
	return jsonify({'status': 'error', 'message': 'Invalid key'}), 400

@app.route('/get_state')
def get_state():
	# Return the current state as JSON
	with state_lock:
		return jsonify({'state': current_state})

def run_flask():
	# Run the Flask web server
	app.run(host='0.0.0.0', port=3000)

# --- FFmpeg process management ---

def ffmpeg_cmd_for_state(state):
	# Build the ffmpeg command for the current state
	if state == 'stopped':
		return None  # No ffmpeg process should run
	youtube_url = get_youtube_url()
	if state == 'live':
		# Pass through RTSP video/audio to YouTube (copy video, encode audio)
		return [
			'ffmpeg',
			'-rtsp_transport', 'tcp',
			'-thread_queue_size', '512',
			'-fflags', '+nobuffer',
			'-i', RTSP_URL,
			'-c:v', 'copy',
			'-b:v', '8000k',
			'-bufsize', '512k',
			'-c:a', 'aac',
			'-ar', '44100',
			'-b:a', '128k',
			'-f', 'flv',
			youtube_url
		]
	elif state == 'custom':
		img = CUSTOM_IMAGE
		return [
			'ffmpeg',
			'-loop', '1',
			'-re',
			'-i', img,
			'-f', 'lavfi',
			'-t', '3600',
			'-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
			'-vf', f'scale={WIDTH}:{HEIGHT},format=yuv420p',
			'-r', str(FPS),
			'-c:v', 'libx264',
			'-preset', 'veryfast',
			'-b:v', '8000k',
			'-bufsize', '512k',
			'-pix_fmt', 'yuv420p',
			'-c:a', 'aac',
			'-ar', '44100',
			'-b:a', '128k',
			'-shortest',
			'-f', 'flv',
			youtube_url
		]
	elif state == 'reconnecting':
		img = RECONNECT_IMAGE
		return [
			'ffmpeg',
			'-loop', '1',
			'-re',
			'-i', img,
			'-f', 'lavfi',
			'-t', '3600',
			'-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
			'-vf', f'scale={WIDTH}:{HEIGHT},format=yuv420p',
			'-r', str(FPS),
			'-c:v', 'libx264',
			'-preset', 'veryfast',
			'-b:v', '8000k',
			'-bufsize', '512k',
			'-pix_fmt', 'yuv420p',
			'-c:a', 'aac',
			'-ar', '44100',
			'-b:a', '128k',
			'-shortest',
			'-f', 'flv',
			youtube_url
		]
	else:
		img = HOLD_IMAGE if state == 'hold' else BREAK_IMAGE
		return [
			'ffmpeg',
			'-loop', '1',
			'-re',
			'-i', img,
			'-f', 'lavfi',
			'-t', '3600',
			'-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
			'-vf', f'scale={WIDTH}:{HEIGHT},format=yuv420p',
			'-r', str(FPS),
			'-c:v', 'libx264',
			'-preset', 'veryfast',
			'-b:v', '8000k',
			'-bufsize', '512k',
			'-pix_fmt', 'yuv420p',
			'-c:a', 'aac',
			'-ar', '44100',
			'-b:a', '128k',
			'-shortest',
			'-f', 'flv',
			youtube_url
		]

def start_ffmpeg(state):
	# Start ffmpeg with the given state, or return None if stopped
	cmd = ffmpeg_cmd_for_state(state)
	if not cmd:
		print('Stream stopped, no ffmpeg running.')
		return None
	print('Starting ffmpeg:', ' '.join(cmd))
	return subprocess.Popen(cmd)

def try_rtsp_connection():
	# Try to open RTSP stream for a short time to check if it's available
	try:
		test_cmd = [
			'ffmpeg',
			'-rtsp_transport', 'tcp',
			'-t', '2',
			'-i', RTSP_URL,
			'-f', 'null',
			'-'
		]
		result = subprocess.run(test_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
		return result.returncode == 0
	except Exception:
		return False

def main_loop():
	global current_state
	ffmpeg_proc = None
	last_state = None
	last_key = None
	reconnect_attempt_interval = 5  # seconds between reconnect attempts
	last_reconnect_attempt = 0
	live_check_interval = 2  # seconds between RTSP checks in live mode
	last_live_check = 0
	try:
		while True:
			with state_lock:
				state = current_state
			with youtube_key_lock:
				key = youtube_key

			# Proactively check RTSP connection in live mode
			if state == 'live':
				now = time.time()
				if now - last_live_check > live_check_interval:
					last_live_check = now
					if not try_rtsp_connection():
						print('RTSP connection lost during live, switching to reconnecting.')
						with state_lock:
							current_state = 'reconnecting'
						state = 'reconnecting'
						# Stop live ffmpeg and start reconnecting overlay
						if ffmpeg_proc:
							ffmpeg_proc.terminate()
							try:
								ffmpeg_proc.wait(timeout=5)
							except subprocess.TimeoutExpired:
								ffmpeg_proc.kill()
							ffmpeg_proc = None
						ffmpeg_proc = start_ffmpeg('reconnecting')
						last_state = 'reconnecting'
						last_key = key
						time.sleep(1)
						continue

			# If in reconnecting state, only try to reconnect periodically
			if state == 'reconnecting':
				now = time.time()
				# Only try to reconnect every interval
				if now - last_reconnect_attempt > reconnect_attempt_interval:
					last_reconnect_attempt = now
					print('Attempting to reconnect to RTSP...')
					if try_rtsp_connection():
						print('RTSP connection restored, switching to live.')
						with state_lock:
							current_state = 'live'
						state = 'live'
						# Stop reconnecting ffmpeg and start live ffmpeg
						if ffmpeg_proc:
							ffmpeg_proc.terminate()
							try:
								ffmpeg_proc.wait(timeout=5)
							except subprocess.TimeoutExpired:
								ffmpeg_proc.kill()
							ffmpeg_proc = None
						ffmpeg_proc = start_ffmpeg('live')
						last_state = 'live'
						last_key = key
					else:
						# Only start reconnecting overlay if not already running
						if not ffmpeg_proc or ffmpeg_proc.poll() is not None or last_state != 'reconnecting':
							if ffmpeg_proc:
								ffmpeg_proc.terminate()
								try:
									ffmpeg_proc.wait(timeout=5)
								except subprocess.TimeoutExpired:
									ffmpeg_proc.kill()
								ffmpeg_proc = None
							ffmpeg_proc = start_ffmpeg('reconnecting')
							last_state = 'reconnecting'
							last_key = key
				# Sleep and continue loop
				time.sleep(1)
				continue

			# Normal state handling
			# Restart ffmpeg if state or key changed
			if state != last_state or key != last_key:
				if ffmpeg_proc:
					print('Stopping previous ffmpeg...')
					ffmpeg_proc.terminate()
					try:
						ffmpeg_proc.wait(timeout=5)
					except subprocess.TimeoutExpired:
						ffmpeg_proc.kill()
					ffmpeg_proc = None
				ffmpeg_proc = start_ffmpeg(state)
				last_state = state
				last_key = key

			# If ffmpeg dies, handle fallback for live mode
			if ffmpeg_proc and ffmpeg_proc.poll() is not None:
				print('ffmpeg exited, restarting...')
				with state_lock:
					if current_state == 'live':
						print('RTSP input failed, switching to reconnecting screen.')
						current_state = 'reconnecting'
						last_state = None  # Force restart with reconnecting screen

			time.sleep(1)
	except KeyboardInterrupt:
		print('Exiting...')
	finally:
		if ffmpeg_proc:
			ffmpeg_proc.terminate()
			try:
				ffmpeg_proc.wait(timeout=5)
			except subprocess.TimeoutExpired:
				ffmpeg_proc.kill()

if __name__ == '__main__':
	# Start Flask UI and main loop
	with youtube_key_lock:
		if not youtube_key:
			print("Error: YOUTUBE_STREAM_KEY not set")
			exit(1)
	flask_thread = threading.Thread(target=run_flask, daemon=True)
	flask_thread.start()
	main_loop()