# Project overview

Birdhouse: Raspberry Pi 3 B+ + Camera Module 3 Wide + Mono USB Microphone at 192.168.0.22

Server: Docker on Headless Ubuntu at 192.168.0.21 on the same network, but only lightweight processor.

Connection: WiFi 2.4 GHz with tendency to drop connection, but good enough for HD video streaming.

# Requirements

- [ ] Stream video from the Raspberry Pi over the network to the server. Account for occasional WiFi drops without this being visible at the end point. Quality is 1080p at 30 fps.
- [ ] Record audio from the Mono USB Microphone on the Raspberry Pi and stream it along with the video to the server. Audio should be in sync with the video.
- [ ] On the server, receive the video and audio streams.
- [ ] On the server, have a web interface to choose between transmitting the live stream to YouTube or transmitting different static pictures instead. Also include an option to simply turn off the stream.
- [ ] When streaming to YouTube, the stream should be in 1080p at 30 fps with audio in sync.
- [ ] When transmitting static pictures, the pictures should be in 1080p resolution with silent audio.
- [ ] The web interface should be accessible from other devices on the same network.
- [ ] The system should be robust and able to recover from temporary network issues without manual intervention.
- [ ] The solution should be containerized using Docker for easy deployment and management on the server.
- [ ] Documentation on how to set up and run the system, including any dependencies and configuration steps.
- [ ] On the web interface, include a status indicator showing the current state of the stream (live, static image, off) and any connection issues.
- [ ] On the web interface, include an option to upload new static images to be used in the stream.
- [ ] Ensure that the audio quality is clear and free from significant latency or distortion when streamed alongside the video.
- [ ] Implement logging on both the Raspberry Pi and server sides to monitor performance, connection stability, and any errors that occur during streaming.
- [ ] Optimize the system for low CPU and memory usage on the server, considering its lightweight processor.
- [ ] Include a feature on the web interface to change the YouTube stream key and other relevant streaming settings without needing to modify the code directly.
- [ ] If the server stops receiving the stream for any reason (video, audio, or both), it should automatically fall back to a 'reconnecting' state and attempt to recover without manual intervention.

