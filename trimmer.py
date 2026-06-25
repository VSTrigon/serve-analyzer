import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import sys
import os
from PIL import Image, ImageTk
import threading

# Install Pillow if needed
try:
    from PIL import Image, ImageTk
except ImportError:
    print("Installing Pillow...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageTk


class ServeTrimmmer:
    def __init__(self, root):
        self.root = root
        self.root.title("Serve Analyzer — Video Trimmer")
        self.root.configure(bg="#1a1a2e")
        self.root.geometry("900x680")

        self.cap = None
        self.total_frames = 0
        self.fps = 0
        self.video_path = None
        self.start_frame = 0
        self.end_frame = 0
        self.current_frame = 0
        self.playing = False
        self.play_thread = None

        self._build_ui()

    def _build_ui(self):
        # ── Title ──
        tk.Label(
            self.root, text="🎾 Serve Trimmer", font=("Helvetica", 18, "bold"),
            bg="#1a1a2e", fg="#e0e0e0"
        ).pack(pady=(16, 4))

        tk.Label(
            self.root, text="Set start and end points, then run analysis on just that window.",
            font=("Helvetica", 11), bg="#1a1a2e", fg="#888"
        ).pack()

        # ── Load button ──
        tk.Button(
            self.root, text="📂  Load Video", command=self.load_video,
            bg="#457B9D", fg="white", font=("Helvetica", 12, "bold"),
            relief="flat", padx=20, pady=8, cursor="hand2"
        ).pack(pady=12)

        # ── Video canvas ──
        self.canvas = tk.Canvas(self.root, width=720, height=360, bg="#0d0d1a", highlightthickness=0)
        self.canvas.pack()

        # ── Scrub slider ──
        slider_frame = tk.Frame(self.root, bg="#1a1a2e")
        slider_frame.pack(fill="x", padx=40, pady=(10, 0))

        tk.Label(slider_frame, text="Scrub", bg="#1a1a2e", fg="#888", font=("Helvetica", 9)).pack(side="left")
        self.scrub_var = tk.IntVar()
        self.scrub = ttk.Scale(
            slider_frame, from_=0, to=100, orient="horizontal",
            variable=self.scrub_var, command=self.on_scrub
        )
        self.scrub.pack(side="left", fill="x", expand=True, padx=8)
        self.time_label = tk.Label(slider_frame, text="0.00s", bg="#1a1a2e", fg="#e0e0e0", font=("Helvetica", 9), width=6)
        self.time_label.pack(side="left")

        # ── Play/Pause ──
        self.play_btn = tk.Button(
            self.root, text="▶  Play", command=self.toggle_play,
            bg="#2a9d8f", fg="white", font=("Helvetica", 11, "bold"),
            relief="flat", padx=16, pady=6, cursor="hand2"
        )
        self.play_btn.pack(pady=6)

        # ── Start / End setters ──
        trim_frame = tk.Frame(self.root, bg="#1a1a2e")
        trim_frame.pack(pady=4)

        # Start
        start_col = tk.Frame(trim_frame, bg="#1a1a2e")
        start_col.pack(side="left", padx=20)
        tk.Label(start_col, text="START FRAME", bg="#1a1a2e", fg="#2a9d8f", font=("Helvetica", 9, "bold")).pack()
        self.start_label = tk.Label(start_col, text="0", bg="#1a1a2e", fg="#e0e0e0", font=("Helvetica", 14, "bold"))
        self.start_label.pack()
        tk.Button(
            start_col, text="Set Start Here", command=self.set_start,
            bg="#2a9d8f", fg="white", font=("Helvetica", 10), relief="flat", padx=10, pady=4, cursor="hand2"
        ).pack(pady=2)

        # End
        end_col = tk.Frame(trim_frame, bg="#1a1a2e")
        end_col.pack(side="left", padx=20)
        tk.Label(end_col, text="END FRAME", bg="#1a1a2e", fg="#E63946", font=("Helvetica", 9, "bold")).pack()
        self.end_label = tk.Label(end_col, text="—", bg="#1a1a2e", fg="#e0e0e0", font=("Helvetica", 14, "bold"))
        self.end_label.pack()
        tk.Button(
            end_col, text="Set End Here", command=self.set_end,
            bg="#E63946", fg="white", font=("Helvetica", 10), relief="flat", padx=10, pady=4, cursor="hand2"
        ).pack(pady=2)

        # ── Run Analysis button ──
        tk.Button(
            self.root, text="⚡  Run Analysis on Selection",
            command=self.run_analysis,
            bg="#e9c46a", fg="#1a1a2e", font=("Helvetica", 12, "bold"),
            relief="flat", padx=24, pady=8, cursor="hand2"
        ).pack(pady=10)

        self.status = tk.Label(
            self.root, text="Load a video to get started.",
            bg="#1a1a2e", fg="#666", font=("Helvetica", 10)
        )
        self.status.pack()

    # ── Load video ──
    def load_video(self):
        path = filedialog.askopenfilename(
            title="Select your serve video",
            filetypes=[("Video files", "*.mov *.mp4 *.avi *.m4v")]
        )
        if not path:
            return

        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.start_frame = 0
        self.end_frame = self.total_frames

        self.scrub.configure(to=self.total_frames - 1)
        self.scrub_var.set(0)
        self.end_label.config(text=str(self.total_frames))
        self.status.config(text=f"Loaded: {os.path.basename(path)}  |  {self.total_frames} frames @ {self.fps:.0f}fps")
        self.show_frame(0)

    # ── Show a specific frame on canvas ──
    def show_frame(self, frame_num):
        if self.cap is None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        if not ret:
            return

        self.current_frame = frame_num
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Scale to fit canvas
        h, w = frame.shape[:2]
        scale = min(720 / w, 360 / h)
        new_w, new_h = int(w * scale), int(h * scale)
        frame = cv2.resize(frame, (new_w, new_h))

        img = ImageTk.PhotoImage(Image.fromarray(frame))
        self.canvas.config(width=new_w, height=new_h)
        self.canvas.create_image(0, 0, anchor="nw", image=img)
        self.canvas.image = img  # prevent garbage collection

        # Update time label
        secs = frame_num / self.fps if self.fps else 0
        self.time_label.config(text=f"{secs:.2f}s")

    # ── Scrub slider moved ──
    def on_scrub(self, val):
        if self.cap is None:
            return
        frame_num = int(float(val))
        self.show_frame(frame_num)

    # ── Play/Pause ──
    def toggle_play(self):
        if self.playing:
            self.playing = False
            self.play_btn.config(text="▶  Play")
        else:
            self.playing = True
            self.play_btn.config(text="⏸  Pause")
            self.play_thread = threading.Thread(target=self._play_loop, daemon=True)
            self.play_thread.start()

    def _play_loop(self):
        import time
        delay = 1.0 / self.fps if self.fps else 0.033
        frame = self.current_frame
        while self.playing and frame < self.total_frames:
            self.root.after(0, self.show_frame, frame)
            self.root.after(0, self.scrub_var.set, frame)
            frame += 1
            time.sleep(delay)
        self.playing = False
        self.root.after(0, self.play_btn.config, {"text": "▶  Play"})

    # ── Set start/end ──
    def set_start(self):
        self.start_frame = self.current_frame
        self.start_label.config(text=str(self.start_frame))
        self.status.config(text=f"Start set at frame {self.start_frame}  ({self.start_frame/self.fps:.2f}s)")

    def set_end(self):
        self.end_frame = self.current_frame
        self.end_label.config(text=str(self.end_frame))
        self.status.config(text=f"End set at frame {self.end_frame}  ({self.end_frame/self.fps:.2f}s)")

    # ── Run analysis ──
    def run_analysis(self):
        if self.video_path is None:
            messagebox.showwarning("No video", "Please load a video first.")
            return
        if self.start_frame >= self.end_frame:
            messagebox.showwarning("Bad range", "Start frame must be before end frame.")
            return

        self.status.config(text=f"Running analysis on frames {self.start_frame}–{self.end_frame}...")
        self.root.update()

        script_dir = os.path.dirname(os.path.abspath(__file__))
        extract_script = os.path.join(script_dir, "extract_angles.py")
        chart_script   = os.path.join(script_dir, "chart_angles.py")

        base = os.path.splitext(self.video_path)[0]
        csv_path = base + "_angles.csv"

        # Run extract_angles with frame range
        result = subprocess.run(
            [sys.executable, extract_script, self.video_path,
             str(self.start_frame), str(self.end_frame)],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            messagebox.showerror("Error in extract_angles", result.stderr)
            return

        # Run chart_angles
        result2 = subprocess.run(
            [sys.executable, chart_script, csv_path],
            capture_output=True, text=True
        )
        print(result2.stdout)
        if result2.returncode != 0:
            messagebox.showerror("Error in chart_angles", result2.stderr)
            return

        self.status.config(text="✅ Done! Charts saved and opened.")
        messagebox.showinfo("Done!", f"Analysis complete!\nCSV: {csv_path}\nCharts opened automatically.")


# ── Entry point ──
if __name__ == "__main__":
    root = tk.Tk()
    app = ServeTrimmmer(root)
    root.mainloop()