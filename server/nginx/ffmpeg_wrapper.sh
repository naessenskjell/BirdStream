#!/bin/sh
# ffmpeg wrapper for nginx-rtmp exec to capture stderr to log file
# Usage: ffmpeg_wrapper.sh <stream_name> <ffmpeg-args...>
name="$1"
shift
logdir="/var/log/nginx"
mkdir -p "$logdir"
logfile="$logdir/ffmpeg_${name}.log"
# Print header
printf "===== ffmpeg wrapper start: %s =====\n" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$logfile"
printf "cmd: ffmpeg %s\n" "$*" >> "$logfile"
# Run ffmpeg and append both stdout and stderr to logfile
# Use exec so the wrapper PID is replaced by ffmpeg for signal semantics
exec ffmpeg "$@" >> "$logfile" 2>&1
