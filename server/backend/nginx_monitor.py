"""
BirdStream - Nginx RTMP Monitor

Polls the nginx-rtmp status endpoint and updates the StreamHandler/NetworkResilience
about active streams. This is a lightweight fallback when nginx is used for ingest
but no direct webhook is configured.
"""
import threading
import time
import logging
import os
import requests
from network_resilience import StreamState

logger = logging.getLogger(__name__)


class NginxMonitor:
    def __init__(self, stream_handler, network_resilience, stat_urls=None, poll_interval=2, metrics_collector=None):
        self.stream_handler = stream_handler
        self.network_resilience = network_resilience
        self.poll_interval = poll_interval
        self._running = False
        self._thread = None

        # Candidate URLs to try if not provided
        if stat_urls is None:
            stat_urls = []
            env = os.environ.get('NGINX_STAT_URL')
            if env:
                stat_urls.append(env)
            # Docker Compose service name
            stat_urls.append('http://nginx-rtmp/stat')
            # Host bindings commonly used
            stat_urls.append('http://localhost:8080/stat')
            stat_urls.append('http://127.0.0.1:8080/stat')

        self.stat_urls = stat_urls
        self.active_url = None
        self.metrics_collector = metrics_collector

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("NginxMonitor started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("NginxMonitor stopped")

    def _find_working_url(self):
        for url in self.stat_urls:
            try:
                r = requests.get(url, timeout=1)
                if r.status_code == 200:
                    logger.info(f"Using nginx stat URL: {url}")
                    self.active_url = url
                    return True
            except Exception:
                continue
        logger.debug("No reachable nginx stat URL found yet")
        return False

    def _parse_stat_for_live(self, text):
        # Very simple heuristic: look for the application 'live' and 'publishing' or 'playing'
        lower = text.lower()
        live_present = 'application live' in lower or '/live' in lower
        publishing = 'publishing' in lower or 'play' in lower or 'playing' in lower
        return live_present and publishing

    def _run(self):
        while self._running:
            try:
                if not self.active_url:
                    self._find_working_url()

                if not self.active_url:
                    time.sleep(self.poll_interval)
                    continue

                try:
                    r = requests.get(self.active_url, timeout=2)
                except Exception:
                    # lost connection, clear and retry discovery
                    self.active_url = None
                    time.sleep(self.poll_interval)
                    continue

                if r.status_code != 200:
                    time.sleep(self.poll_interval)
                    continue

                is_live = self._parse_stat_for_live(r.text)

                if is_live:
                    # Ensure a connection is registered in stream_handler
                    conn_id = 'nginx-live0'
                    conn = self.stream_handler.get_connection(conn_id)
                    if not conn:
                        conn = self.stream_handler.register_connection(conn_id)
                        logger.info(f"Registered stream from nginx as {conn_id}")

                    # Mark as active/live
                    conn.is_active = True
                    conn.video_ok = True
                    conn.audio_ok = True
                    conn.update_activity()
                    # Notify resilience manager
                    # Notify resilience manager about live state
                    try:
                        self.network_resilience.set_state(StreamState.LIVE, 'nginx detected live')
                    except Exception as e:
                        logger.debug(f"Failed to set network resilience state: {e}")
                    # Update simple metrics (best-effort)
                    try:
                        if self.metrics_collector:
                            # Record a small frame to reflect activity
                            self.metrics_collector.record_video_frame(1024)
                            self.metrics_collector.record_audio_frame(256)
                    except Exception:
                        pass
                else:
                    # No live streams detected; mark nginx connection inactive
                    conn = self.stream_handler.get_connection('nginx-live0')
                    if conn:
                        conn.video_ok = False
                        conn.audio_ok = False
                        conn.is_active = False
                        # Let NetworkResilience handle transitions

                time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in NginxMonitor loop: {e}")
                time.sleep(self.poll_interval)
