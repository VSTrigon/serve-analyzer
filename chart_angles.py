import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import sys
import os

def chart_angles(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: Could not find CSV at '{csv_path}'")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    base = os.path.splitext(csv_path)[0]
    output_path = base + "_charts.png"

    # --- Smooth the data slightly so charts aren't too jagged ---
    window = 5
    df["r_elbow_smooth"]    = df["r_elbow_angle"].rolling(window, center=True).mean()
    df["r_shoulder_smooth"] = df["r_shoulder_angle"].rolling(window, center=True).mean()
    df["l_wrist_smooth"]    = df["l_wrist_height"].rolling(window, center=True).mean()
    df["tilt_smooth"]       = df["shoulder_tilt"].rolling(window, center=True).mean()

    t = df["time_sec"]

    # --- Layout: 2x2 grid of charts ---
    fig = plt.figure(figsize=(14, 10))
    fig.suptitle("Serve Analysis — Joint Angles Over Time", fontsize=16, fontweight="bold", y=0.98)
    gs = gridspec.GridSpec(2, 2, hspace=0.45, wspace=0.35)

    # ── Chart 1: Right Elbow Angle ──
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(t, df["r_elbow_smooth"], color="#E63946", linewidth=2)
    ax1.axhline(y=90, color="gray", linestyle="--", linewidth=1, label="90° reference")
    ax1.set_title("Right Elbow Angle", fontweight="bold")
    ax1.set_xlabel("Time (seconds)")
    ax1.set_ylabel("Angle (degrees)")
    ax1.legend(fontsize=8)
    ax1.set_ylim(0, 200)
    ax1.fill_between(t, df["r_elbow_smooth"], alpha=0.1, color="#E63946")
    # Annotate min (most bent = near contact point)
    min_idx = df["r_elbow_smooth"].idxmin()
    if not pd.isna(min_idx):
        ax1.annotate(
            f"Min: {df['r_elbow_smooth'][min_idx]:.0f}°",
            xy=(t[min_idx], df["r_elbow_smooth"][min_idx]),
            xytext=(t[min_idx] + 0.1, df["r_elbow_smooth"][min_idx] + 15),
            arrowprops=dict(arrowstyle="->", color="black"),
            fontsize=8,
        )

    # ── Chart 2: Right Shoulder Angle ──
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(t, df["r_shoulder_smooth"], color="#457B9D", linewidth=2)
    ax2.set_title("Right Shoulder Angle", fontweight="bold")
    ax2.set_xlabel("Time (seconds)")
    ax2.set_ylabel("Angle (degrees)")
    ax2.set_ylim(0, 200)
    ax2.fill_between(t, df["r_shoulder_smooth"], alpha=0.1, color="#457B9D")
    max_idx = df["r_shoulder_smooth"].idxmax()
    if not pd.isna(max_idx):
        ax2.annotate(
            f"Peak: {df['r_shoulder_smooth'][max_idx]:.0f}°",
            xy=(t[max_idx], df["r_shoulder_smooth"][max_idx]),
            xytext=(t[max_idx] + 0.1, df["r_shoulder_smooth"][max_idx] - 20),
            arrowprops=dict(arrowstyle="->", color="black"),
            fontsize=8,
        )

    # ── Chart 3: Toss Arm Height (left wrist Y position) ──
    ax3 = fig.add_subplot(gs[1, 0])
    # Invert Y because MediaPipe Y=0 is top of screen
    ax3.plot(t, 1 - df["l_wrist_smooth"], color="#2A9D8F", linewidth=2)
    ax3.set_title("Toss Arm Height (Left Wrist)", fontweight="bold")
    ax3.set_xlabel("Time (seconds)")
    ax3.set_ylabel("Relative Height (higher = more extended)")
    ax3.fill_between(t, 1 - df["l_wrist_smooth"], alpha=0.1, color="#2A9D8F")
    peak_idx = (1 - df["l_wrist_smooth"]).idxmax()
    if not pd.isna(peak_idx):
        ax3.annotate(
            "Toss peak",
            xy=(t[peak_idx], (1 - df["l_wrist_smooth"])[peak_idx]),
            xytext=(t[peak_idx] + 0.1, (1 - df["l_wrist_smooth"])[peak_idx] - 0.05),
            arrowprops=dict(arrowstyle="->", color="black"),
            fontsize=8,
        )

    # ── Chart 4: Shoulder Tilt ──
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(t, df["tilt_smooth"], color="#E9C46A", linewidth=2)
    ax4.axhline(y=0, color="gray", linestyle="--", linewidth=1)
    ax4.set_title("Shoulder Tilt", fontweight="bold")
    ax4.set_xlabel("Time (seconds)")
    ax4.set_ylabel("Tilt (positive = right shoulder higher)")
    ax4.fill_between(t, df["tilt_smooth"], alpha=0.1, color="#E9C46A")

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nCharts saved to: {output_path}")
    print("Opening charts...")
    os.system(f"open '{output_path}'")

    # --- Print a simple text summary ---
    print("\n── Serve Analysis Summary ──")
    print(f"  Duration analyzed:        {t.max():.1f} seconds")
    print(f"  Right elbow — avg:        {df['r_elbow_angle'].mean():.1f}°")
    print(f"  Right elbow — min:        {df['r_elbow_angle'].min():.1f}°  (most bent)")
    print(f"  Right shoulder — peak:    {df['r_shoulder_angle'].max():.1f}°")
    print(f"  Shoulder tilt — avg:      {df['shoulder_tilt'].mean():.1f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 chart_angles.py <path_to_csv>")
        print("Example: python3 chart_angles.py serve_angles.csv")
        sys.exit(1)

    chart_angles(sys.argv[1])