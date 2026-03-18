from flask import Flask, request, render_template_string, redirect
import threading
import time
import requests
import uuid
import json
import os

app = Flask(__name__)

jobs = {}
SAVE_FILE = "jobs.json"


# =========================
# SAVE / LOAD FUNCTIONS
# =========================
def save_jobs():
    data = []
    for job in jobs.values():
        data.append({
            "url": job.url,
            "interval": job.interval
        })

    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)


def load_jobs():
    if not os.path.exists(SAVE_FILE):
        return

    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)

        for item in data:
            job = PingJob(item["url"], item["interval"])
            jobs[job.id] = job

    except Exception as e:
        print("Load error:", e)


# =========================
# JOB CLASS
# =========================
class PingJob:
    def __init__(self, url, interval_seconds):
        self.id = str(uuid.uuid4())[:8]
        self.url = url
        self.interval = interval_seconds
        self.running = True
        self.logs = []
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while self.running:
            try:
                start = time.time()
                r = requests.get(self.url, timeout=10)
                duration = round(time.time() - start, 2)

                preview = r.text[:200].replace("\n", " ")

                if r.status_code == 200:
                    color = "lime"
                elif r.status_code < 400:
                    color = "orange"
                else:
                    color = "red"

                log = f"""
                <span style='color:{color}'>
                ✅ {self.url} | {r.status_code} | {duration}s | {len(r.text)} bytes
                </span>
                <br><small style='color:#ccc'>{preview}</small>
                """

                self.logs.append(log)

            except Exception as e:
                self.logs.append(f"<span style='color:red'>❌ {self.url} -> {str(e)}</span>")

            self.logs = self.logs[-30:]
            time.sleep(self.interval)

    def stop(self):
        self.running = False


# =========================
# MAIN PAGE
# =========================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        interval_value = int(request.form.get("interval", 5))
        unit = request.form.get("unit")

        if unit == "minutes":
            interval_seconds = interval_value * 60
        else:
            interval_seconds = interval_value

        job = PingJob(url, interval_seconds)
        jobs[job.id] = job

        save_jobs()

        return redirect("/")

    return render_template_string("""
    <html>
    <head>
        <title>Persistent Multi URL Pinger</title>
    </head>
    <body style="font-family:Arial; background:#0f172a; color:white; padding:20px;">

    <h2>🌐 Multi-URL Pinger (Persistent)</h2>

    <form method="POST">
        URL:<br>
        <input type="text" name="url" style="width:300px" required><br><br>

        Interval:<br>
        <input type="number" name="interval" value="5" min="1">

        <select name="unit">
            <option value="seconds">Seconds</option>
            <option value="minutes">Minutes</option>
        </select>

        <br><br>
        <button type="submit">➕ Add URL</button>
    </form>

    <hr>

    <h3>Active Jobs:</h3>
    <div id="jobs-container">Loading...</div>

    <script>
    async function loadJobs() {
        const res = await fetch("/jobs");
        const html = await res.text();
        document.getElementById("jobs-container").innerHTML = html;
    }

    loadJobs();
    setInterval(loadJobs, 3000);
    </script>

    </body>
    </html>
    """)


# =========================
# JOBS VIEW
# =========================
@app.route("/jobs")
def get_jobs():
    return render_template_string("""
    {% for id, job in jobs.items() %}
        <div style="border:1px solid #334155; padding:15px; margin-bottom:15px; border-radius:8px;">
            <b style="color:#38bdf8">{{ job.url }}</b><br>
            Interval: {{ job.interval }} seconds<br>
            <a href="/stop/{{ id }}" style="color:red;">🛑 Stop</a>

            <div style="background:#020617; padding:10px; margin-top:10px; height:180px; overflow:auto;">
                {% for log in job.logs %}
                    {{ log|safe }}<br>
                {% endfor %}
            </div>
        </div>
    {% endfor %}
    """, jobs=jobs)


# =========================
# STOP JOB
# =========================
@app.route("/stop/<job_id>")
def stop(job_id):
    if job_id in jobs:
        jobs[job_id].stop()
        del jobs[job_id]
        save_jobs()

    return redirect("/")


# =========================
# STARTUP LOAD
# =========================
load_jobs()


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
