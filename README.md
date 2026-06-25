# 🎾 Serve Analyzer

A computer vision tool that analyzes tennis serve mechanics from video footage using MediaPipe Pose. Built in Python, no GPU or paid APIs required — runs entirely on your local machine.

---

## What It Does

Upload a video of your serve and get back:
- **Skeleton overlay video** — MediaPipe tracks 33 body landmarks frame by frame
- **Joint angle extraction** — elbow angle, shoulder angle, shoulder tilt, and toss arm height saved to CSV
- **Analysis charts** — 4-chart breakdown of your mechanics over time
- **Visual trimmer** — scrub through your video and select exactly the window you want analyzed (trophy pose → contact)

---

## How It Works

```
Phone video → MediaPipe Pose → Per-frame landmark CSV → Angle charts
```

MediaPipe detects 33 body landmarks on every frame. From those coordinates we compute joint angles using vector math, then chart them over time to reveal patterns in your mechanics.

---

## Setup

**Requirements:** Python 3.8+, Mac/Windows/Linux

```bash
git clone https://github.com/YOURUSERNAME/serve-analyzer.git
cd serve-analyzer
pip3 install mediapipe opencv-python matplotlib pandas Pillow
```

---

## Usage

### 1. Skeleton overlay
```bash
python3 pose_overlay.py your_serve.mov
```
Outputs `your_serve_overlay.mp4` with joints and bones drawn on every frame.

### 2. Extract angles (full video)
```bash
python3 extract_angles.py your_serve.mov
```

### 3. Extract angles (trimmed window)
```bash
python3 extract_angles.py your_serve.mov 50 200
```
Only analyzes frames 50–200. Use the trimmer UI to find the right frame range.

### 4. Chart the angles
```bash
python3 chart_angles.py your_serve_angles.csv
```
Opens a 4-chart PNG showing elbow angle, shoulder angle, toss arm height, and shoulder tilt over time.

### 5. Visual trimmer (recommended)
```bash
python3 trimmer.py
```
Load your video, scrub to find trophy pose and contact point, set start/end, and hit **Run Analysis** — runs steps 2–4 automatically.

---

## Metrics Tracked

| Metric | What It Tells You |
|---|---|
| Right elbow angle | Arm extension at contact — pros average 160–175° |
| Right shoulder angle | How much your arm loads up and extends |
| Toss arm height | Consistency of your ball toss peak |
| Shoulder tilt | Body rotation through the kinetic chain |

---

## Recording Tips

- Film in **landscape (horizontal)** mode
- **Side-on** angle facing your hitting arm
- **240fps slow motion** gives the cleanest tracking
- Full body in frame — head to feet
- Good lighting, avoid backlighting

---

## Tech Stack

- [MediaPipe Pose](https://google.github.io/mediapipe/solutions/pose) — pose landmark detection
- [OpenCV](https://opencv.org/) — video I/O and frame processing
- [pandas](https://pandas.pydata.org/) — angle data storage and analysis
- [matplotlib](https://matplotlib.org/) — charting
- [tkinter](https://docs.python.org/3/library/tkinter.html) + [Pillow](https://pillow.readthedocs.io/) — trimmer UI

---

## Roadmap

- [ ] Web app — upload video, get analysis back in browser
- [ ] ATP benchmark data — compare your metrics to tour averages
- [ ] Multi-serve comparison — overlay multiple serves on one chart
- [ ] Automatic serve detection — no manual trimming needed

---

## Author

Built by Varun Sivakumar — rising sophomore studying Computer Science at The University of Maryland, College Park.  


---

*Note: Add your own serve videos locally — video files are excluded from this repo via .gitignore.*