#!/bin/bash
   case "$1" in
     "holdScreen")
       sed -i 's|-i /overlays/.*\.png|-i /overlays/hold_screen.png|' /home/kjell/youtube-stream/run_ffmpeg.sh
       sed -i "s|enable=[0-1]*|enable=1|" /home/kjell/youtube-stream/run_ffmpeg.sh
       echo "Hold screen enabled"
       docker stop ffmpeg-stream
       /home/kjell/youtube-stream/run_ffmpeg.sh
       ;;
     "tempBreak")
       sed -i 's|-i /overlays/.*\.png|-i /overlays/temporary_break.png|' /home/kjell/youtube-stream/run_ffmpeg.sh
       sed -i "s|enable=[0-1]*|enable=1|" /home/kjell/youtube-stream/run_ffmpeg.sh
       echo "Temporary break screen enabled"
       docker stop ffmpeg-stream
       /home/kjell/youtube-stream/run_ffmpeg.sh
       ;;
     "live")
       sed -i "s|enable=[0-1]*|enable=0|" /home/kjell/youtube-stream/run_ffmpeg.sh
       echo "Live videostream enabled"
       docker stop ffmpeg-stream
       /home/kjell/youtube-stream/run_ffmpeg.sh
       ;;
     "stop")
       sed -i 's|-i /overlays/.*\.png|-i /overlays/hold_screen.png|' /home/kjell/youtube-stream/run_ffmpeg.sh
       sed -i "s|enable=[0-1]*|enable=1|" /home/kjell/youtube-stream/run_ffmpeg.sh
       docker stop ffmpeg-stream
       ;;
     *)
       echo "Usage: $0 {holdScreen|tempBreak|live|stop}"
       exit 1
       ;;
   esac
