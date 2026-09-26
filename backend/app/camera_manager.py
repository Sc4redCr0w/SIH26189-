from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from .camera_detection import FaceBox, FaceDetector, annotate_frame
from .camera_service import create_camera_observation
from .camera_sources import CameraSource, FramePacket, create_camera_source
from .config import get_settings
from .db import SessionLocal
from .models import Camera, CameraObservation
from .services import record_audit

logger = logging.getLogger("cni.camera")
settings = get_settings()


class DetectionCooldown:
    def __init__(self, seconds: float) -> None:
        self.seconds = max(0.0, seconds)
        self.last_emit = 0.0

    def should_emit(self, now: float) -> bool:
        if self.seconds <= 0 or now - self.last_emit >= self.seconds:
            self.last_emit = now
            return True
        return False


@dataclass
class CameraRuntime:
    camera_id: str
    source_type: str
    status: str = "STOPPED"
    last_frame_at: datetime | None = None
    last_detection_at: datetime | None = None
    detection_count: int = 0
    active_detections: int = 0
    last_error: str = ""
    latest_frame: bytes | None = None
    latest_annotated_frame: bytes | None = None
    last_boxes: list[dict[str, Any]] = field(default_factory=list)
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    source: CameraSource | None = None
    last_detection_monotonic: float = 0.0
    cooldown: DetectionCooldown = field(default_factory=lambda: DetectionCooldown(settings.camera_detection_cooldown_seconds))
    demo_events_seen: set[int] = field(default_factory=set)
    demo_overlay: FaceBox | None = None
    demo_overlay_until: float = 0.0
    buffer: deque[Any] = field(default_factory=lambda: deque(maxlen=max(2, settings.camera_evidence_pre_event_frames + settings.camera_evidence_post_event_frames + 1)))


class CameraManager:
    def __init__(
        self,
        *,
        source_factory: Callable[[Camera], CameraSource] = create_camera_source,
        detector_factory: Callable[[], FaceDetector] = FaceDetector,
    ) -> None:
        self._source_factory = source_factory
        self._detector_factory = detector_factory
        self._runtimes: dict[str, CameraRuntime] = {}
        self._lock = threading.RLock()
        self._subscribers: set[queue.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        subscriber: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, event_type: str, camera_id: str, payload: dict[str, Any]) -> None:
        event = {"event": event_type, "camera_id": camera_id, "timestamp": datetime.now(UTC).isoformat(), "payload": payload}
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                pass

    def runtime(self, camera_id: str) -> CameraRuntime | None:
        with self._lock:
            return self._runtimes.get(camera_id)

    def is_running(self, camera_id: str) -> bool:
        runtime = self.runtime(camera_id)
        return bool(runtime and runtime.thread and runtime.thread.is_alive())

    def start_camera(self, camera_id: str, *, actor_id: str | None = None) -> CameraRuntime:
        with self._lock:
            existing = self._runtimes.get(camera_id)
            if existing and existing.thread and existing.thread.is_alive():
                return existing
        with SessionLocal() as db:
            camera = db.get(Camera, camera_id)
            if camera is None:
                raise ValueError("Camera not found")
            if not camera.enabled:
                raise ValueError("Camera is disabled")
            config = camera
        runtime = CameraRuntime(camera_id=camera_id, source_type=config.source_type, status="STARTING")
        with self._lock:
            self._runtimes[camera_id] = runtime
        thread = threading.Thread(target=self._run_camera, args=(runtime, config, actor_id), name=f"camera-{camera_id}", daemon=True)
        runtime.thread = thread
        thread.start()
        self._persist_camera_state(camera_id, status="STARTING", last_error="")
        self.publish("CAMERA_STARTING", camera_id, {"status": "STARTING"})
        return runtime

    def stop_camera(self, camera_id: str, *, actor_id: str | None = None) -> None:
        runtime = self.runtime(camera_id)
        if runtime:
            runtime.stop_event.set()
            if runtime.source:
                runtime.source.stop()
            if runtime.thread and runtime.thread.is_alive() and runtime.thread is not threading.current_thread():
                runtime.thread.join(timeout=4)
            runtime.status = "STOPPED"
        self._persist_camera_state(camera_id, status="STOPPED")
        self.publish("CAMERA_STOPPED", camera_id, {"status": "STOPPED"})
        with SessionLocal() as db:
            camera = db.get(Camera, camera_id)
            if camera:
                record_audit(db, action="CAMERA_STOPPED", user_id=actor_id, resource_type="CAMERA", resource_id=camera_id)
                db.commit()

    def start_all(self, *, actor_id: str | None = None) -> None:
        with SessionLocal() as db:
            camera_ids = [camera.id for camera in db.query(Camera).filter(Camera.enabled.is_(True)).all()]
        for camera_id in camera_ids:
            try:
                self.start_camera(camera_id, actor_id=actor_id)
            except Exception as exc:  # pragma: no cover - hardware dependent
                logger.warning("Could not start camera %s: %s", camera_id, exc)

    def stop_all(self) -> None:
        with self._lock:
            camera_ids = list(self._runtimes)
        for camera_id in camera_ids:
            try:
                self.stop_camera(camera_id)
            except Exception:  # pragma: no cover - shutdown best effort
                logger.exception("Could not stop camera %s", camera_id)

    def status(self, camera_id: str) -> dict[str, Any]:
        runtime = self.runtime(camera_id)
        with SessionLocal() as db:
            camera = db.get(Camera, camera_id)
            if camera is None:
                raise ValueError("Camera not found")
            return {
                "camera_id": camera_id,
                "status": runtime.status if runtime else camera.status,
                "source_type": camera.source_type,
                "last_frame_at": runtime.last_frame_at if runtime else camera.last_frame_at,
                "last_detection_at": runtime.last_detection_at if runtime else camera.last_detection_at,
                "detection_count": runtime.detection_count if runtime else camera.detection_count,
                "active_detections": runtime.active_detections if runtime else 0,
                "last_error": runtime.last_error if runtime else camera.last_error,
                "demo_mode": settings.camera_demo_mode,
            }

    def latest_frame(self, camera_id: str, *, annotated: bool = True) -> bytes | None:
        runtime = self.runtime(camera_id)
        if runtime is None:
            return None
        return runtime.latest_annotated_frame if annotated else runtime.latest_frame

    def _persist_camera_state(self, camera_id: str, *, status: str | None = None, last_error: str | None = None, last_frame_at: datetime | None = None) -> None:
        with SessionLocal() as db:
            camera = db.get(Camera, camera_id)
            if camera is None:
                return
            if status is not None:
                camera.status = status
            if last_error is not None:
                camera.last_error = last_error
            if last_frame_at is not None:
                camera.last_frame_at = last_frame_at
            db.commit()

    @staticmethod
    def _encode_jpeg(frame: Any) -> bytes | None:
        try:
            import cv2  # type: ignore[import-not-found]

            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            return encoded.tobytes() if ok else None
        except Exception:
            return None

    def _persist_observation(
        self,
        camera: Camera,
        frame: Any,
        annotated: Any,
        detection: FaceBox,
        packet: FramePacket,
        *,
        actor_id: str | None,
        is_simulated: bool = False,
        simulation_label: str = "",
        suggested_person_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        clip_frames: list[Any] | None = None,
    ) -> CameraObservation:
        with SessionLocal() as db:
            current = db.get(Camera, camera.id)
            if current is None:
                raise RuntimeError("Camera was removed while worker was running")
            observation = create_camera_observation(
                db,
                current,
                frame=frame,
                annotated_frame=annotated,
                detection=detection,
                frame_number=packet.frame_number,
                timestamp=datetime.now(UTC),
                created_by_id=actor_id,
                is_simulated=is_simulated,
                simulation_label=simulation_label,
                suggested_person_id=suggested_person_id,
                metadata=metadata,
                clip_frames=clip_frames,
            )
            record_audit(db, action="CAMERA_OBSERVATION_CREATED", user_id=actor_id, resource_type="CAMERA_OBSERVATION", resource_id=observation.id, details={"camera_id": camera.id, "is_simulated": is_simulated, "detection_only": True})
            db.commit()
            db.refresh(observation)
            return observation

    def _run_camera(self, runtime: CameraRuntime, camera: Camera, actor_id: str | None) -> None:
        detector = self._detector_factory()
        if not detector.available:
            runtime.status = "OFFLINE"
            runtime.last_error = "Face detector is unavailable; install opencv-python to enable detection."
            self._persist_camera_state(camera.id, status="OFFLINE", last_error=runtime.last_error)
            self.publish("CAMERA_DISCONNECTED", camera.id, {"error": runtime.last_error})
            return
        try:
            source = self._source_factory(camera)
            runtime.source = source
            source.connect()
        except Exception as exc:
            runtime.status = "OFFLINE"
            runtime.last_error = str(exc)
            self._persist_camera_state(camera.id, status="OFFLINE", last_error=runtime.last_error)
            self.publish("CAMERA_DISCONNECTED", camera.id, {"error": runtime.last_error})
            return

        runtime.status = "LIVE"
        runtime.last_error = ""
        self._persist_camera_state(camera.id, status="LIVE", last_error="")
        with SessionLocal() as db:
            record_audit(db, action="CAMERA_STARTED", user_id=actor_id, resource_type="CAMERA", resource_id=camera.id)
            db.commit()
        self.publish("CAMERA_CONNECTED", camera.id, {"status": "LIVE", "source_type": camera.source_type})

        last_status_publish = 0.0
        while not runtime.stop_event.is_set():
            try:
                packet = source.read_frame()
                if packet is None:
                    if not source.is_alive():
                        raise RuntimeError("Camera source ended or disconnected")
                    runtime.stop_event.wait(settings.camera_frame_interval_seconds)
                    continue
                runtime.last_frame_at = datetime.now(UTC)
                runtime.buffer.append(packet.frame)
                raw_bytes = self._encode_jpeg(packet.frame)
                if raw_bytes:
                    runtime.latest_frame = raw_bytes
                now_monotonic = time.monotonic()
                detections = detector.detect(packet.frame)
                demo_event = self._demo_event_for(camera, runtime, packet)
                if demo_event is not None:
                    # Keep the simulated box on the live overlay for a few
                    # seconds so the reviewer can see the event window.
                    runtime.demo_overlay = demo_event[0]
                    runtime.demo_overlay_until = now_monotonic + max(3.0, settings.camera_evidence_post_event_frames * 1.5)
                overlay_detections = list(detections)
                if runtime.demo_overlay is not None and now_monotonic <= runtime.demo_overlay_until:
                    overlay_detections.append(runtime.demo_overlay)
                annotated = annotate_frame(packet.frame, overlay_detections, demo_mode=settings.camera_demo_mode)
                annotated_bytes = self._encode_jpeg(annotated)
                if annotated_bytes:
                    runtime.latest_annotated_frame = annotated_bytes
                runtime.active_detections = len(detections)
                runtime.last_boxes = [detection.as_dict() for detection in overlay_detections]
                self._persist_camera_state(camera.id, status="LIVE", last_error="", last_frame_at=runtime.last_frame_at)

                should_capture = bool(detections) and runtime.cooldown.should_emit(now_monotonic)
                if demo_event is not None:
                    should_capture = True
                if should_capture:
                    runtime.last_detection_monotonic = now_monotonic
                    event_detections = [demo_event[0]] if demo_event is not None else detections[:1]
                    for index, detection in enumerate(event_detections[:5]):
                        simulated = demo_event is not None
                        observation = self._persist_observation(
                            camera,
                            packet.frame,
                            annotated,
                            detection,
                            packet,
                            actor_id=actor_id,
                            is_simulated=simulated,
                            simulation_label=demo_event[2] if demo_event else "",
                            suggested_person_id=demo_event[3] if demo_event else None,
                            metadata={
                                "detector_available": detector.available,
                                "detector_confidence_method": detector.confidence_method,
                                "cooldown_seconds": settings.camera_detection_cooldown_seconds,
                                "demo_simulation_not_biometric_identification": simulated,
                            },
                            clip_frames=list(runtime.buffer) if settings.camera_evidence_clip_enabled else None,
                        )
                        runtime.detection_count += 1
                        runtime.last_detection_at = datetime.now(UTC)
                        self.publish("FACE_DETECTED", camera.id, {"observation_id": observation.id, "bbox": detection.as_dict(), "detection_confidence": detection.confidence, "is_simulated": simulated})
                        self.publish("EVIDENCE_CREATED", camera.id, {"observation_id": observation.id, "evidence_id": observation.evidence_id, "annotated_evidence_id": observation.annotated_evidence_id})
                        self.publish("REVIEW_REQUIRED", camera.id, {"observation_id": observation.id, "review_status": observation.review_status, "is_simulated": simulated})
                    if demo_event is not None:
                        runtime.demo_events_seen.add(demo_event[4])
                if now_monotonic - last_status_publish >= 0.5:
                    last_status_publish = now_monotonic
                    self.publish("CAMERA_STATUS", camera.id, {"status": runtime.status, "active_detections": runtime.active_detections, "detection_count": runtime.detection_count, "last_frame_at": runtime.last_frame_at.isoformat() if runtime.last_frame_at else None})
                runtime.stop_event.wait(settings.camera_frame_interval_seconds)
            except Exception as exc:  # keep other workers alive
                runtime.status = "OFFLINE"
                runtime.last_error = str(exc)
                self._persist_camera_state(camera.id, status="OFFLINE", last_error=runtime.last_error)
                self.publish("CAMERA_DISCONNECTED", camera.id, {"error": runtime.last_error})
                if runtime.stop_event.wait(1.0):
                    break
                try:
                    source.reconnect()
                    runtime.status = "LIVE"
                    runtime.last_error = ""
                    self.publish("CAMERA_CONNECTED", camera.id, {"status": "LIVE", "reconnected": True})
                except Exception as reconnect_error:
                    runtime.last_error = str(reconnect_error)
                    self._persist_camera_state(camera.id, status="OFFLINE", last_error=runtime.last_error)
        try:
            source.stop()
        except Exception:
            pass
        runtime.status = "STOPPED"
        self._persist_camera_state(camera.id, status="STOPPED")

    def _demo_event_for(self, camera: Camera, runtime: CameraRuntime, packet: FramePacket) -> tuple[FaceBox, str, str, str | None, int] | None:
        if not settings.camera_demo_mode:
            return None
        metadata = camera.metadata_json if isinstance(camera.metadata_json, dict) else {}
        events = metadata.get("demo_events")
        if not isinstance(events, list):
            return None
        for index, event in enumerate(events):
            if index in runtime.demo_events_seen or not isinstance(event, dict):
                continue
            try:
                event_time = float(event.get("timestamp_seconds", event.get("timestamp", 0)))
            except (TypeError, ValueError):
                continue
            if packet.timestamp_seconds + 0.001 < event_time:
                continue
            bbox = event.get("bbox")
            if not isinstance(bbox, dict):
                bbox = {}
            try:
                box = FaceBox(
                    int(bbox.get("x", 100)),
                    int(bbox.get("y", 80)),
                    int(bbox.get("width", 90)),
                    int(bbox.get("height", 110)),
                    confidence=event.get("confidence"),
                    label="Potential match event — SIMULATED",
                )
            except (TypeError, ValueError):
                continue
            label = str(event.get("label") or "Potential match event — SIMULATED")
            suggested = event.get("suggested_person_id")
            return box, label, label, str(suggested) if isinstance(suggested, str) and suggested else None, index
        return None


camera_manager = CameraManager()
