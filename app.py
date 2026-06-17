#!/usr/bin/env python3
"""
AdEdit — AI-Powered Advertising Video Editor
============================================
Web UI: upload a demo video → get a polished advertising video.
"""

import os
import uuid
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, Response
from werkzeug.utils import secure_filename

from core.ad_pipeline import AdPipeline
from utils.job_store import JobStore
from utils.ad_config import AdConfig

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2GB

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

job_store = JobStore()

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm", "m4v"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    file = request.files["video"]
    if not file or not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"Unsupported format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    job_id = str(uuid.uuid4())[:8]
    safe   = secure_filename(file.filename)
    input_path  = UPLOAD_DIR / f"{job_id}_{safe}"
    output_path = OUTPUT_DIR / f"{job_id}_ad_output.mp4"

    file.save(str(input_path))

    # Parse config from form
    cfg = AdConfig(
        brand_name      = request.form.get("brand_name", "Your Brand"),
        tagline         = request.form.get("tagline", ""),
        primary_color   = request.form.get("primary_color", "#00D4FF"),
        secondary_color = request.form.get("secondary_color", "#FF6B35"),
        style           = request.form.get("style", "modern"),
        music_style     = request.form.get("music_style", "corporate"),
        add_voiceover   = request.form.get("add_voiceover", "false").lower() == "true",
        voiceover_text  = request.form.get("voiceover_text", ""),
        speed_boost     = float(request.form.get("speed_boost", "1.0")),
        output_duration = request.form.get("output_duration", "auto"),
        add_logo        = request.form.get("add_logo", "false").lower() == "true",
        color_grade     = request.form.get("color_grade", "cinematic"),
        add_captions    = request.form.get("add_captions", "false").lower() == "true",
    )

    job_store.create(job_id, str(input_path), str(output_path), cfg)

    def run_job():
        try:
            job_store.update(job_id, status="processing", progress=0,
                             message="Initializing pipeline…")
            pipeline = AdPipeline(cfg, job_store, job_id)
            pipeline.run(Path(input_path), Path(output_path))
            job_store.update(job_id, status="done", progress=100,
                             message="Complete!", output=str(output_path))
        except Exception as e:
            job_store.update(job_id, status="error", progress=0,
                             message=str(e))

    t = threading.Thread(target=run_job, daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = job_store.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/stream/<job_id>")
def stream(job_id):
    """SSE stream for real-time progress."""
    def generate():
        last_msg = None
        timeout  = 600  # 10 min max
        start    = time.time()
        while time.time() - start < timeout:
            job = job_store.get(job_id)
            if not job:
                yield "data: {\"error\": \"not found\"}\n\n"
                break
            msg = f"data: {__import__('json').dumps(job)}\n\n"
            if msg != last_msg:
                yield msg
                last_msg = msg
            if job.get("status") in ("done", "error"):
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/api/download/<job_id>")
def download(job_id):
    job = job_store.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Not ready"}), 404
    out = Path(job["output"])
    if not out.exists():
        return jsonify({"error": "Output file missing"}), 404
    return send_file(str(out), as_attachment=True,
                     download_name="ad_video.mp4",
                     mimetype="video/mp4")


@app.route("/api/preview/<job_id>")
def preview(job_id):
    job = job_store.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Not ready"}), 404
    out = Path(job["output"])
    if not out.exists():
        return jsonify({"error": "Output file missing"}), 404
    return send_file(str(out), mimetype="video/mp4")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
