import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import cv2
import mediapipe as mp
import sys
import os

# --- MediaPipe setup ---
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

def analyze_serve(input_path):
    # Check the file exists
    if not os.path.exists(input_path):
        print(f"Error: Could not find video at '{input_path}'")
        sys.exit(1)

    # Build output filename: myvideo.mp4 -> myvideo_overlay.mp4
    base, ext = os.path.splitext(input_path)
    output_path = base + "_overlay.mp4"

    cap = cv2.VideoCapture(input_path)

    # Grab video properties so output matches input
    fps    = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Video loaded: {width}x{height} @ {fps:.1f}fps, {total} frames")

    # VideoWriter to save the output
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_num = 0

    with mp_pose.Pose(
        static_image_mode=False,       # video mode (tracks across frames)
        model_complexity=2,            # 0=fast, 1=balanced, 2=accurate — use 2 for analysis
        enable_segmentation=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_num += 1
            if frame_num % 30 == 0:  # progress update every 30 frames
                print(f"  Processing frame {frame_num}/{total}...")

            # MediaPipe expects RGB, OpenCV gives BGR
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            # Draw skeleton if landmarks were detected
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
                )

            out.write(frame)

    cap.release()
    out.release()
    print(f"\nDone! Saved to: {output_path}")


# --- Entry point ---
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 pose_overlay.py <path_to_video>")
        print("Example: python3 pose_overlay.py serve.mp4")
        sys.exit(1)

    analyze_serve(sys.argv[1])