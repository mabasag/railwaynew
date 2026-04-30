from flask import Flask, Response, request, jsonify, render_template_string,redirect
import subprocess
import threading
import queue
import time
from PIL import ImageGrab
import io
import os
import platform
import requests
import uuid
import json

app = Flask(__name__)

# Queue to handle command outputs
output_queue = queue.Queue()

# Detect OS
IS_WINDOWS = platform.system() == "Windows"

# Start persistent shell
if IS_WINDOWS:
    shell = subprocess.Popen(
        ["cmd.exe"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
else:
    shell = subprocess.Popen(
        ["/bin/bash"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def read_output():
    while True:
        line = shell.stdout.readline()
        if line:
            output_queue.put(line)

# Start reading thread
threading.Thread(target=read_output, daemon=True).start()


# =========================
# SCREENSHOT STREAM
# =========================
def generate_screen():
    while True:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        frame = buf.getvalue()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        time.sleep(0.5)


@app.route('/screen')
def screen():
    return Response(generate_screen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# =========================
# TERMINAL COMMAND
# =========================
@app.route('/command', methods=['POST'])
def command():
    cmd = request.json.get("cmd")

    if not cmd:
        return jsonify({"error": "No command"}), 400

    try:
        shell.stdin.write(cmd + "\n")
        shell.stdin.flush()
        return jsonify({"status": "sent"})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/output')
def output():
    lines = []
    while not output_queue.empty():
        lines.append(output_queue.get())

    return jsonify({"output": "".join(lines)})


# =========================
# WEB UI
# =========================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Remote Control</title>
    <style>
        body { font-family: Arial; background:#111; color:#eee; text-align:center; }
        img { width: 80%; border:2px solid #444; margin-bottom:10px; }
        input { width:60%; padding:10px; font-size:16px; }
        button { padding:10px; font-size:16px; }
        #terminal {
            width:80%;
            height:200px;
            margin:auto;
            background:black;
            color:lime;
            overflow:auto;
            padding:10px;
            text-align:left;
        }
    </style>
</head>
<body>

<h2>🖥 Remote Screen + Terminal</h2>

<img src="/screen">

<br>

<input id="cmd" placeholder="Enter command...">
<button onclick="sendCmd()">Send</button>

<div id="terminal"></div>

<script>
function sendCmd(){
    let cmd = document.getElementById("cmd").value;

    fetch("/command", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({cmd: cmd})
    });

    document.getElementById("cmd").value = "";
}

function fetchOutput(){
    fetch("/output")
    .then(res => res.json())
    .then(data => {
        let term = document.getElementById("terminal");
        term.innerText += data.output;
        term.scrollTop = term.scrollHeight;
    });
}

setInterval(fetchOutput, 1000);
</script>

</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(debug=True)
