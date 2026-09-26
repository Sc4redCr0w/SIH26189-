from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FaceBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float | None = None
    label: str = "Face detected"

    def as_dict(self) -> dict[str, int | float | str | None]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "label": self.label,
        }


class FaceDetector:
    """Local binary face detector.

    This class intentionally performs detection only. It does not create
    embeddings, compare identities, or consult a biometric watchlist.
    """

    def __init__(self, cascade: Any | None = None) -> None:
        self.cascade = cascade
        self.name = "opencv-haar-frontalface"
        self.confidence_method = "HAAR_CASCADE_BINARY"
        if self.cascade is None:
            try:
                import cv2  # type: ignore[import-not-found]

                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self.cascade = cv2.CascadeClassifier(cascade_path)
                if self.cascade.empty():
                    self.cascade = None
            except Exception:
                self.cascade = None

    @property
    def available(self) -> bool:
        return self.cascade is not None

    def detect(self, frame: Any) -> list[FaceBox]:
        if self.cascade is None or frame is None:
            return []
        try:
            import cv2  # type: ignore[import-not-found]

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )
        except Exception:
            return []
        return [FaceBox(int(x), int(y), int(width), int(height)) for x, y, width, height in faces]


def is_simulated(detection: FaceBox) -> bool:
    return "SIMULATED" in detection.label.upper()


def box_label(detection: FaceBox) -> str:
    """Return the on-frame label for a detection.

    Simulated events are always labeled as a simulation. Real detections show
    `Face detected` and only include a score when the detector produced one.
    """
    if is_simulated(detection):
        return "DEMO SIMULATION - NOT BIOMETRIC IDENTIFICATION"
    score = f" {detection.confidence:.0%}" if detection.confidence is not None else ""
    return f"{detection.label}{score}"


def annotate_frame(frame: Any, detections: list[FaceBox], demo_mode: bool = False) -> Any:
    """Draw non-identifying face boxes and labels onto a frame.

    The label comes from the individual box, not from the global demo flag, so
    a real detection is never relabeled as a simulation.
    """
    if frame is None or not detections:
        return frame
    try:
        import cv2  # type: ignore[import-not-found]

        annotated = frame.copy()
        for detection in detections:
            simulated = is_simulated(detection)
            top_left = (detection.x, detection.y)
            bottom_right = (detection.x + detection.width, detection.y + detection.height)
            color = (60, 70, 220) if simulated else (90, 230, 190)
            cv2.rectangle(annotated, top_left, bottom_right, color, 2)
            label = box_label(detection)
            font_scale = 0.5 if not simulated else 0.46
            (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            text_x = detection.x
            text_y = max(text_height + 4, detection.y - 6)
            cv2.rectangle(annotated, (text_x, text_y - text_height - 4), (text_x + text_width + 6, text_y + baseline - 2), (8, 12, 16), -1)
            cv2.putText(annotated, label, (text_x + 3, text_y - 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 1, cv2.LINE_AA)
        return annotated
    except Exception:
        return frame
