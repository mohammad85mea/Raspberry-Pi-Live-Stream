from flask import Flask, Response, render_template, request
from picamera2 import Picamera2
import cv2
import numpy as np
import threading

app = Flask(__name__)
streaming = False
lock = threading.Lock()
picam2 = None

def initialize_camera():
    global picam2
    if picam2 is None:
        picam2 = Picamera2()
        # Create the video configuration without fps argument
        picam2.configure(picam2.create_video_configuration(main={"format": "YUV420", "size": (1280, 720)}))
        picam2.start()

def release_camera():
    global picam2
    if picam2 is not None:
        picam2.stop()
        picam2.close()
        picam2 = None

def generate_frames():
    global streaming
    while streaming:
        buffer = picam2.capture_buffer("main")
        frame = np.frombuffer(buffer, dtype=np.uint8)

        y_len = 1280 * 720
        u_len = v_len = (1280 // 2) * (720 // 2)
        y = frame[:y_len].reshape((720, 1280))
        u = frame[y_len:y_len + u_len].reshape((720 // 2, 1280 // 2)).repeat(2, axis=0).repeat(2, axis=1)
        v = frame[y_len + u_len:].reshape((720 // 2, 1280 // 2)).repeat(2, axis=0).repeat(2, axis=1)

        frame = np.dstack((y, u, v)).astype(np.uint8)
        frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def frame_generator():
        global streaming
        while streaming:
            try:
                frame = next(generate_frames())
                yield frame
            except StopIteration:
                break

    return Response(frame_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start', methods=['POST'])
def start_stream():
    global streaming
    with lock:
        if not streaming:
            streaming = True
            initialize_camera()
    return 'Stream started', 200

@app.route('/stop', methods=['POST'])
def stop_stream():
    global streaming
    with lock:
        if streaming:
            streaming = False
            release_camera()
    return 'Stream stopped', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
