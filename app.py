import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import os
import sys
import json
import uuid
import subprocess
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ── Config ──
UPLOAD_FOLDER    = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"mov", "mp4", "avi", "m4v"}
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max upload

app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ── ATP Benchmark Data ──
# Sources: published biomechanics research on professional serve mechanics
ATP_BENCHMARKS = {
    "r_elbow_angle": {
        "avg": 172,
        "range_low": 160,
        "range_high": 180,
        "label": "Right Elbow Angle at Contact",
        "unit": "°",
        "description": "ATP pros average 172° — nearly full extension at contact."
    },
    "r_shoulder_angle": {
        "avg": 175,
        "range_low": 165,
        "range_high": 185,
        "label": "Right Shoulder Angle",
        "unit": "°",
        "description": "Full arm elevation through the kinetic chain."
    },
    "shoulder_tilt": {
        "avg": 3.5,
        "range_low": 1,
        "range_high": 6,
        "label": "Shoulder Tilt",
        "unit": "",
        "description": "Slight positive tilt (right shoulder higher) is ideal at contact."
    },
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ──

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/preview/<filename>")
def preview(filename):
    from flask import send_from_directory
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/upload_preview", methods=["POST"])
def upload_preview():
    if "video" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["video"]
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"preview_{uuid.uuid4().hex}.{ext}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    return jsonify({
        "filename": filename,
        "preview_url": f"/preview/{filename}"
    })

@app.route("/analyze", methods=["POST"])
def analyze():
    # -- Use preview file if already uploaded, otherwise handle new upload --
    preview_filename = request.form.get("preview_filename")
    if preview_filename:
        video_path = os.path.join(app.config["UPLOAD_FOLDER"], preview_filename)
        if not os.path.exists(video_path):
            return jsonify({"error": "Preview file not found. Please re-upload."}), 400
    else:
        if "video" not in request.files:
            return jsonify({"error": "No video file provided."}), 400
        file = request.files["video"]
        if file.filename == "":
            return jsonify({"error": "No file selected."}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Please upload a .mov, .mp4, .avi, or .m4v file."}), 400
        ext = file.filename.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        video_path  = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(video_path)

    # -- Get optional frame trim params --
    start_frame = request.form.get("start_frame", "0")
    end_frame   = request.form.get("end_frame",   None)

    # -- Run extract_angles.py --
    analyzer_dir  = os.path.join(os.path.dirname(__file__), "analyzer")
    extract_script = os.path.join(analyzer_dir, "extract_angles.py")

    cmd = [sys.executable, extract_script, video_path, start_frame]
    if end_frame:
        cmd.append(end_frame)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        os.remove(video_path)
        return jsonify({"error": f"Analysis failed: {result.stderr}"}), 500

    # -- Read the CSV output --
    csv_path = video_path.rsplit(".", 1)[0] + "_angles.csv"
    if not os.path.exists(csv_path):
        os.remove(video_path)
        return jsonify({"error": "Analysis produced no output."}), 500

    import pandas as pd
    df = pd.read_csv(csv_path)

    # -- Build response payload --
    # Send time series data for charts
    chart_data = {
        "time":             df["time_sec"].tolist(),
        "r_elbow_angle":    df["r_elbow_angle"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "r_shoulder_angle": df["r_shoulder_angle"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "shoulder_tilt":    df["shoulder_tilt"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "l_wrist_height":   (1 - df["l_wrist_height"].rolling(5, center=True, min_periods=1).mean()).round(4).tolist(),
    }

    # Summary stats
    summary = {
        "r_elbow_avg":        round(df["r_elbow_angle"].mean(), 1),
        "r_elbow_min":        round(df["r_elbow_angle"].min(), 1),
        "r_elbow_max":        round(df["r_elbow_angle"].max(), 1),
        "r_shoulder_avg":     round(df["r_shoulder_angle"].mean(), 1),
        "r_shoulder_max":     round(df["r_shoulder_angle"].max(), 1),
        "shoulder_tilt_avg":  round(df["shoulder_tilt"].mean(), 1),
        "toss_peak":          round((1 - df["l_wrist_height"]).max(), 3),
        "frames_analyzed":    len(df),
        "duration_sec":       round(df["time_sec"].max(), 2),
    }

   # -- Cleanup temp files --
    os.remove(csv_path)
    # Video deleted after preview no longer needed
    if os.path.exists(video_path):
        os.remove(video_path)

    return jsonify({
        "chart_data":    chart_data,
        "summary":       summary,
        "atp_benchmarks": ATP_BENCHMARKS,
    })


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)