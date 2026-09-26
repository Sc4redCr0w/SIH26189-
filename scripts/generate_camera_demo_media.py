"""Generate synthetic camera demo media for the Windows prototype.

The generated clips contain animated motion, timestamps, and a moving
rectangular subject. They exist so the capture/evidence/review pipeline can be
demonstrated without physical CCTV hardware.

These clips are synthetic. The face detector may or may not classify the drawn
subject as a face; demo *events* are produced by the timestamp-driven
DEMO SIMULATION timeline, which is explicitly labeled as simulated and is not
biometric identification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


MOVE_SECONDS = 2.0
# Resting subject rectangle in the generated footage. A scripted demo event can
# reference this box so the annotation lines up with the visible subject.
SUBJECT_REST_BOX = {"x": 360, "y": 180, "width": 120, "height": 180}


def build_clip(path: Path, *, seconds: float, fps: int, subject_label: str, hue: int) -> None:
    """Render one synthetic clip.

    The subject walks in during the first `MOVE_SECONDS` and then holds a fixed
    position so a scripted demo event can reference `SUBJECT_REST_BOX`.
    """
    width, height = 960, 540
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():  # pragma: no cover - codec failure is environment specific
        raise RuntimeError(f"Unable to open video writer for {path}")
    total_frames = int(seconds * fps)
    try:
        for index in range(total_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :] = (28, 22, 18)
            # Static scene detail so motion is visible between consecutive frames.
            for column in range(0, width, 120):
                cv2.line(frame, (column, 0), (column, height), (48, 40, 34), 1)
            for row in range(0, height, 90):
                cv2.line(frame, (0, row), (width, row), (48, 40, 34), 1)
            move_frames = max(1, int(MOVE_SECONDS * fps))
            phase = min(1.0, index / move_frames)
            center_x = int(180 + phase * 240)
            center_y = 300
            subject_size = 120
            color = (hue, 150, 220)
            cv2.rectangle(frame, (center_x - subject_size // 2, center_y - subject_size), (center_x + subject_size // 2, center_y + subject_size), color, -1)
            cv2.rectangle(frame, (center_x - subject_size // 2, center_y - subject_size), (center_x + subject_size // 2, center_y + subject_size), (235, 235, 235), 2)
            cv2.circle(frame, (center_x - 22, center_y - 40), 9, (240, 240, 240), -1)
            cv2.circle(frame, (center_x + 22, center_y - 40), 9, (240, 240, 240), -1)
            cv2.line(frame, (center_x - 18, center_y - 8), (center_x + 18, center_y - 8), (240, 240, 240), 3)
            cv2.putText(frame, subject_label, (28, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (235, 235, 235), 2, cv2.LINE_AA)
            cv2.putText(frame, f"t={index / fps:05.2f}s", (width - 190, height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2, cv2.LINE_AA)
            cv2.putText(frame, "SYNTHETIC DEMO FOOTAGE", (28, height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 190, 240), 2, cv2.LINE_AA)
            writer.write(frame)
    finally:
        writer.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic camera demo clips.")
    parser.add_argument("--output", default="datasets/camera_demo", help="Output directory relative to the repository root.")
    parser.add_argument("--fps", type=int, default=10)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    clips = (
        ("demo-parking.mp4", 20.0, "PARKING AREA", 210),
        ("demo-entrance.mp4", 20.0, "BUILDING ENTRANCE", 150),
    )
    for name, seconds, label, hue in clips:
        target = output / name
        build_clip(target, seconds=seconds, fps=args.fps, subject_label=label, hue=hue)
        print(f"Wrote {target} ({target.stat().st_size} bytes)")
    print(f"Resting subject box for scripted events: {json.dumps(SUBJECT_REST_BOX)}")


if __name__ == "__main__":
    main()
