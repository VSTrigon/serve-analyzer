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
    "x_factor": {
        "avg": 35,
        "range_low": 25,
        "range_high": 45,
        "label": "Shoulder-Hip Separation (X-Factor)",
        "unit": "°",
        "description": "The 'coil' between hips and shoulders. Elite servers generate 25-45° of separation, storing energy that releases into racket speed."
    },
    "r_knee_angle": {
        "avg": 145,
        "range_low": 120,
        "range_high": 160,
        "label": "Knee Bend at Load",
        "unit": "°",
        "description": "Deeper knee bend (lower angle) generally means more leg drive feeding into the kinetic chain."
    },
    "weight_transfer": {
        "avg": 0.08,
        "range_low": 0.05,
        "range_high": 0.12,
        "label": "Weight Transfer",
        "unit": "",
        "description": "Horizontal distance between front and back foot — tracks how far your weight shifts forward through the serve."
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
        "time":             df["frame"].tolist(),
        "r_elbow_angle":    df["r_elbow_angle"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "r_shoulder_angle": df["r_shoulder_angle"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "shoulder_tilt":    df["shoulder_tilt"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "l_wrist_height":   (1 - df["l_wrist_height"].rolling(5, center=True, min_periods=1).mean()).round(4).tolist(),
        "r_knee_angle":     df["r_knee_angle"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "x_factor":         df["x_factor"].rolling(5, center=True, min_periods=1).mean().round(2).tolist(),
        "weight_transfer":  df["weight_transfer"].rolling(5, center=True, min_periods=1).mean().round(4).tolist(),
    }

    # Summary stats
    # Elbow extension at peak (not the whole-window min, which includes follow-through)
    # Find peak extension as the max in the first 70% of the window — i.e. up to contact
    cutoff = int(len(df) * 0.7)
    r_elbow_at_contact = round(df["r_elbow_angle"].iloc[:cutoff].max(), 1)

    summary = {
        "r_elbow_avg":        round(df["r_elbow_angle"].mean(), 1),
        "r_elbow_contact":    r_elbow_at_contact,
        "r_elbow_max":        round(df["r_elbow_angle"].max(), 1),
        "r_shoulder_avg":     round(df["r_shoulder_angle"].mean(), 1),
        "r_shoulder_max":     round(df["r_shoulder_angle"].max(), 1),
        "shoulder_tilt_avg":  round(df["shoulder_tilt"].mean(), 1),
        "toss_peak":          round((1 - df["l_wrist_height"]).max(), 3),
        "frames_analyzed":    len(df),
        "duration_frames":    len(df),
        "x_factor_max":       round(df["x_factor"].max(), 1),
        "x_factor_avg":       round(df["x_factor"].mean(), 1),
        "r_knee_min":         round(df["r_knee_angle"].min(), 1),
        "weight_transfer_max": round(df["weight_transfer"].max(), 4),
    }

    # -- Generate feedback --
    feedback = []

    # Elbow at contact
    if summary["r_elbow_contact"] >= 170:
        feedback.append({
            "metric": "Elbow Extension",
            "status": "good",
            "message": f"Strong arm extension at contact ({summary['r_elbow_contact']}°). You're generating good racket head speed through the hitting zone."
        })
    elif summary["r_elbow_contact"] >= 155:
        feedback.append({
            "metric": "Elbow Extension",
            "status": "ok",
            "message": f"Decent arm extension at contact ({summary['r_elbow_contact']}°). Try to fully extend your hitting arm — even a few more degrees translates to measurable added power."
        })
    else:
        feedback.append({
            "metric": "Elbow Extension",
            "status": "improve",
            "message": f"Your arm isn't fully extending at contact ({summary['r_elbow_contact']}°). Focus on reaching up and out toward the ball, like you're trying to hit the highest possible point."
        })

    # X-factor
    if summary["x_factor_max"] >= 30:
        feedback.append({
            "metric": "X-Factor (Coil)",
            "status": "good",
            "message": f"Excellent shoulder-hip separation ({summary['x_factor_max']}° peak). You're generating a strong rotational coil that feeds power through the kinetic chain."
        })
    elif summary["x_factor_max"] >= 20:
        feedback.append({
            "metric": "X-Factor (Coil)",
            "status": "ok",
            "message": f"Moderate coil ({summary['x_factor_max']}° peak). Try initiating your hip rotation slightly earlier in the load-up — let the hips lead the shoulders to build more separation."
        })
    else:
        feedback.append({
            "metric": "X-Factor (Coil)",
            "status": "improve",
            "message": f"Low shoulder-hip separation ({summary['x_factor_max']}°). This is a significant power leak. Work on turning your hips into the court while keeping your shoulders back longer during the load-up."
        })

    # Knee bend
    if summary["r_knee_min"] <= 145:
        feedback.append({
            "metric": "Knee Bend",
            "status": "good",
            "message": f"Good knee bend in your load-up ({summary['r_knee_min']}°). Your legs are contributing to the kinetic chain effectively."
        })
    elif summary["r_knee_min"] <= 160:
        feedback.append({
            "metric": "Knee Bend",
            "status": "ok",
            "message": f"Moderate knee bend ({summary['r_knee_min']}°). Dropping a little lower in your load-up will give your legs more to push off from, adding free power to the serve."
        })
    else:
        feedback.append({
            "metric": "Knee Bend",
            "status": "improve",
            "message": f"Minimal knee bend detected ({summary['r_knee_min']}°). Try consciously bending your knees more during the toss — think of loading a spring before releasing upward into the ball."
        })

    # Shoulder tilt
    if 1 <= summary["shoulder_tilt_avg"] <= 6:
        feedback.append({
            "metric": "Shoulder Tilt",
            "status": "good",
            "message": f"Good shoulder tilt at contact ({summary['shoulder_tilt_avg']}). Your hitting shoulder is slightly higher than your toss shoulder — that's ideal."
        })
    else:
        feedback.append({
            "metric": "Shoulder Tilt",
            "status": "ok",
            "message": f"Shoulder tilt is outside the typical range ({summary['shoulder_tilt_avg']}). Ideally your hitting shoulder should be slightly higher at contact — check your trophy pose alignment."
        })

   # -- Cleanup temp files --
    os.remove(csv_path)
    # Video deleted after preview no longer needed
    if os.path.exists(video_path):
        os.remove(video_path)

    return jsonify({
        "chart_data":     chart_data,
        "summary":        summary,
        "atp_benchmarks": ATP_BENCHMARKS,
        "feedback":       feedback,
    })


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)