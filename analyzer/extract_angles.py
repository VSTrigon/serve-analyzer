import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import cv2
import mediapipe as mp
import pandas as pd
import numpy as np
import sys
import os

# --- MediaPipe setup ---
mp_pose = mp.solutions.pose

def calculate_angle(a, b, c):
    """
    Calculate the angle at point B, formed by points A-B-C.
    Each point is a [x, y] coordinate.
    Returns angle in degrees.
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
    return round(angle, 2)


def extract_angles(input_path, start_frame=0, end_frame=None):
    if not os.path.exists(input_path):
        print(f"Error: Could not find video at '{input_path}'")
        sys.exit(1)

    base, ext = os.path.splitext(input_path)
    output_csv = base + "_angles.csv"

    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Extracting angles from {total} frames at {fps:.1f}fps...")

    rows = []
    frame_num = 0

    if end_frame is None:
        end_frame = total

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_num += 1
            if frame_num % 30 == 0:
                print(f"  Frame {frame_num}/{total}...")
            if frame_num < start_frame:
                continue
            if frame_num > end_frame:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            if not results.pose_landmarks:
                continue

            lm = results.pose_landmarks.landmark

            # Helper to get [x, y] from a landmark index
            def pt(idx):
                return [lm[idx].x, lm[idx].y]

            # --- MediaPipe landmark indices we care about ---
            # Right side (hitting arm for right-handers)
            R_SHOULDER = 12
            R_ELBOW    = 14
            R_WRIST    = 16
            R_HIP      = 24
            R_KNEE     = 26
            R_ANKLE    = 28

            # Left side (toss arm / non-hitting side)
            L_SHOULDER = 11
            L_ELBOW    = 13
            L_WRIST    = 15
            L_HIP      = 23
            L_KNEE     = 25
            L_ANKLE    = 27

            # Calculate angles
            r_elbow_angle    = calculate_angle(pt(R_SHOULDER), pt(R_ELBOW), pt(R_WRIST))
            l_elbow_angle    = calculate_angle(pt(L_SHOULDER), pt(L_ELBOW), pt(L_WRIST))
            r_shoulder_angle = calculate_angle(pt(R_HIP), pt(R_SHOULDER), pt(R_ELBOW))
            l_shoulder_angle = calculate_angle(pt(L_HIP), pt(L_SHOULDER), pt(L_ELBOW))

            # Shoulder tilt: difference in Y between left and right shoulder
            # (positive = right shoulder higher, negative = left shoulder higher)
            shoulder_tilt = round((lm[L_SHOULDER].y - lm[R_SHOULDER].y) * 100, 2)

            # --- NEW: Knee bend (hip-knee-ankle angle) ---
            # Smaller angle = deeper knee bend (more loaded)
            r_knee_angle = calculate_angle(pt(R_HIP), pt(R_KNEE), pt(R_ANKLE))
            l_knee_angle = calculate_angle(pt(L_HIP), pt(L_KNEE), pt(L_ANKLE))

            # --- NEW: Hip rotation (tilt between hips, same logic as shoulder tilt) ---
            hip_tilt = round((lm[L_HIP].y - lm[R_HIP].y) * 100, 2)

            # --- NEW: Shoulder-hip separation (the "X-factor") ---
            # Angle of the line between shoulders, vs angle of the line between hips,
            # in the horizontal (x) plane — captures rotational coil between upper/lower body
            shoulder_line_angle = np.degrees(np.arctan2(
                lm[R_SHOULDER].y - lm[L_SHOULDER].y,
                lm[R_SHOULDER].x - lm[L_SHOULDER].x
            ))
            hip_line_angle = np.degrees(np.arctan2(
                lm[R_HIP].y - lm[L_HIP].y,
                lm[R_HIP].x - lm[L_HIP].x
            ))
            # Normalize angle difference to 0-180 range to avoid wraparound bugs
            raw_diff = abs(shoulder_line_angle - hip_line_angle)
            x_factor = round(min(raw_diff, 360 - raw_diff), 2)

            # --- NEW: Weight transfer proxy ---
            # Horizontal distance between front and back ankle, normalized
            # Tracks how far weight has shifted forward through the motion
            weight_transfer = round(abs(lm[R_ANKLE].x - lm[L_ANKLE].x), 4)

            # Wrist heights (lower Y value = higher on screen)
            r_wrist_height = round(lm[R_WRIST].y, 4)
            l_wrist_height = round(lm[L_WRIST].y, 4)

            # Visibility scores — how confident MediaPipe is for key joints
            r_wrist_vis = round(lm[R_WRIST].visibility, 2)
            r_elbow_vis = round(lm[R_ELBOW].visibility, 2)

            time_sec = round(frame_num / fps, 3)

            rows.append({
                "frame":            frame_num,
                "time_sec":         time_sec,
                "r_elbow_angle":    r_elbow_angle,
                "l_elbow_angle":    l_elbow_angle,
                "r_shoulder_angle": r_shoulder_angle,
                "l_shoulder_angle": l_shoulder_angle,
                "shoulder_tilt":    shoulder_tilt,
                "r_wrist_height":   r_wrist_height,
                "l_wrist_height":   l_wrist_height,
                "r_wrist_vis":      r_wrist_vis,
                "r_elbow_vis":      r_elbow_vis,
                "r_knee_angle":     r_knee_angle,
                "l_knee_angle":     l_knee_angle,
                "hip_tilt":         hip_tilt,
                "x_factor":         x_factor,
                "weight_transfer":  weight_transfer,
            })

    cap.release()

    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)

    print(f"\nDone! Saved {len(df)} frames of angle data to: {output_csv}")
    print(f"\nQuick summary:")
    print(f"  Avg right elbow angle:    {df['r_elbow_angle'].mean():.1f}°")
    print(f"  Min right elbow angle:    {df['r_elbow_angle'].min():.1f}°  (most bent = near contact)")
    print(f"  Max right elbow angle:    {df['r_elbow_angle'].max():.1f}°  (most extended)")
    print(f"  Avg shoulder tilt:        {df['shoulder_tilt'].mean():.1f}")
    print(f"  Min right wrist height:   {df['r_wrist_height'].min():.3f}  (highest point)")
    print(f"  Frames analyzed:          {len(df)}")


if __name__ == "__main__":
    if len(sys.argv) not in [2, 4]:
        print("Usage: python3 extract_angles.py <path_to_video> [start_frame end_frame]")
        print("Example (full video):  python3 extract_angles.py serve.mov")
        print("Example (trimmed):     python3 extract_angles.py serve.mov 40 200")
        sys.exit(1)

    video = sys.argv[1]
    start = int(sys.argv[2]) if len(sys.argv) == 4 else 0
    end   = int(sys.argv[3]) if len(sys.argv) == 4 else None

    extract_angles(video, start, end)