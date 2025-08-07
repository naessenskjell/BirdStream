#!/bin/bash
   docker run -it --rm \
	 --name ffmpeg-stream \
	-v /home/kjell/youtube-stream/overlays:/overlays:ro \
         jrottenberg/ffmpeg:4.4-ubuntu \
	 -rtsp_transport tcp \
	 -i rtsp://<RASPBERRY_PI_IP_ADDRESS>:8554/cam \
         -i /overlays/hold_screen.png \
         -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
         -filter_complex "[0:v]setpts=PTS-STARTPTS[video];[video][1:v]overlay=0:0:enable=1[out]" \
         -map "[out]" -map 2:a:0 \
	 -c:v libx264 -preset veryfast -crf 22 -g 60 -b:v 4000k \
         -c:a aac -b:a 128k \
	 -f flv -bufsize 4000k -max_delay 10000 \
	 rtmp://a.rtmp.youtube.com/live2/<SECRET_YOUTUBE_LIVE_KEY>
