# Camera Monitoring and Visual Evidence Module

This module adds multi-source camera monitoring, local face **detection**, automatic
evidence-frame capture, a human review queue, and manual Person association.

## Safety and product boundary

| Capability | Status |
| --- | --- |
| Multi-source live capture (webcam, video file, HTTP/MJPEG, RTSP) | Implemented |
| Local face **detection** (OpenCV Haar cascade) | Implemented |
| Bounding-box overlay with detection metadata | Implemented |
| Automatic raw + annotated evidence capture | Implemented |
| Human review queue (verify / reject / associate) | Implemented |
| Manual association of an observation with an existing Person | Implemented |
| Demo simulation mode for scripted "match" events | Implemented |
| Face embeddings / face recognition / biometric matching | **Not implemented, by design** |
| Biometric watchlists / automatic identification | **Not implemented, by design** |

The module never computes embeddings, never compares faces, and never assigns an
identity automatically. A `CameraObservation` is an *observation*. A
`HUMAN_VERIFIED_OBSERVATION` edge to a `Person` is created only after an
authorized human reviewer explicitly selects a Person in the review queue.

## Architecture

```
Camera source (WEBCAM | VIDEO_FILE | HTTP_STREAM | RTSP)
        |
        v
CameraWorker thread  (one independent thread per camera)
  - capture loop, reconnect, OFFLINE handling
  - FaceDetector.detect(frame)          <- detection only
  - annotate_frame(frame, boxes)        <- non-identifying overlay
  - DetectionCooldown                   <- debounce duplicate events
        |
        +--> runtime.latest_annotated_frame  --> GET /cameras/{id}/latest-frame  --> Live monitoring grid
        |
        v
create_camera_observation()
  - raw frame JPEG           -> Evidence (CAMERA_FRAME)
  - annotated frame JPEG     -> Evidence (CAMERA_FRAME_ANNOTATED)
  - optional short clip      -> Evidence (CAMERA_CLIP)
  - CameraObservation row    -> review_status = PENDING_REVIEW
        |
        v
WebSocket /api/v1/cameras/ws
  CAMERA_CONNECTED, CAMERA_DISCONNECTED, CAMERA_STATUS,
  FACE_DETECTED, EVIDENCE_CREATED, REVIEW_REQUIRED, REVIEW_COMPLETED
        |
        v
Review queue -> human decision -> knowledge graph
  Person -[HUMAN_VERIFIED_OBSERVATION]-> CameraObservation
  CameraObservation -[CAPTURED_BY]-> Camera
  CameraObservation -[LOCATED_AT]-> Location
```

Key modules:

| File | Responsibility |
| --- | --- |
| `backend/app/camera_sources.py` | `CameraSource` abstraction and source implementations |
| `backend/app/camera_detection.py` | Face detection and bounding-box annotation |
| `backend/app/camera_manager.py` | Per-camera workers, runtime status, event broker, cooldown |
| `backend/app/camera_service.py` | Evidence capture, observation persistence, URI masking |
| `backend/app/camera_graph.py` | Projection into the existing relational graph |
| `backend/app/routers/cameras.py` | REST + WebSocket API surface |

Each camera runs in its own daemon thread with its own source handle and its own
`SessionLocal` scope, so a failing camera marks only itself `OFFLINE` and never
stops the other workers.

## Data model

| Table | Purpose |
| --- | --- |
| `cameras` | Source configuration, status, last frame, last detection, counters |
| `camera_observations` | One row per detection event (bbox, confidence, evidence links, review status) |
| `camera_evidence` | Links an observation to its raw / annotated / clip evidence records |
| `observation_reviews` | Human decision, reviewer, optional associated Person, notes |
| `person_reference_photos` | Profile photos for human review only (never used for matching) |

Review statuses: `PENDING_REVIEW`, `VERIFIED_OBSERVATION`, `REJECTED`,
`ASSOCIATED_WITH_ENTITY`. A reviewed observation cannot be silently re-decided;
the API returns `409`.

Graph projection reuses the existing `entities` / `relationships` tables:

- `CAMERA` entity, one per source.
- `LOCATION` entity, created from the configured location name when needed.
- `CAMERA_OBSERVATION` entity, one per observation, carrying
  `detection_only: true` and `no_biometric_matching: true` metadata.

## Detection model and confidence

The prototype uses the OpenCV Haar cascade frontal-face detector
(`opencv-haar-frontalface`). It is a **binary** classifier: it reports whether a
face is present, not a probability. `detection_confidence` is therefore stored as
`null` with `confidence_method = HAAR_CASCADE_BINARY`, and the UI shows
"Not scored by binary detector" instead of inventing a percentage.

Demo simulation events may carry an explicit scripted confidence, which is
labeled as simulated event metadata.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `CNI_CAMERA_DETECTION_ENABLED` | `true` | Enables the detection worker |
| `CNI_CAMERA_DEMO_MODE` | `false` | Enables scripted simulated events |
| `CNI_CAMERA_DETECTION_COOLDOWN_SECONDS` | `10` | Debounce for a continuously visible face |
| `CNI_CAMERA_FRAME_INTERVAL_SECONDS` | `0.08` | Worker loop pacing |
| `CNI_CAMERA_EVIDENCE_PRE_EVENT_FRAMES` | `2` | Ring-buffer depth before the event |
| `CNI_CAMERA_EVIDENCE_POST_EVENT_FRAMES` | `2` | Ring-buffer depth after the event |
| `CNI_CAMERA_EVIDENCE_CLIP_ENABLED` | `false` | Also write a short MP4 clip |
| `CNI_CAMERA_AUTO_START` | `false` | Start all enabled cameras on backend boot |

## API surface

| Method | Route | Role |
| --- | --- | --- |
| `GET` | `/api/v1/cameras` | any authenticated user |
| `POST` | `/api/v1/cameras` | Admin |
| `GET` | `/api/v1/cameras/{id}` | any authenticated user |
| `PATCH` | `/api/v1/cameras/{id}` | Admin |
| `DELETE` | `/api/v1/cameras/{id}` (archive) | Admin |
| `POST` | `/api/v1/cameras/{id}/start` | Admin |
| `POST` | `/api/v1/cameras/{id}/stop` | Admin |
| `GET` | `/api/v1/cameras/{id}/status` | any authenticated user |
| `GET` | `/api/v1/cameras/{id}/latest-frame?token=` | any authenticated user |
| `GET` | `/api/v1/cameras/observations/all` | any authenticated user |
| `GET` | `/api/v1/cameras/observations/{id}` | any authenticated user (audits the view) |
| `GET` | `/api/v1/cameras/observations/{id}/annotated-frame?token=` | any authenticated user |
| `POST` | `/api/v1/cameras/observations/{id}/review` | Admin, Analyst |
| `POST` | `/api/v1/cameras/entities/{id}/reference-photo` | Admin |
| `GET` | `/api/v1/cameras/entities/{id}/reference-photos` | any authenticated user |
| `WS` | `/api/v1/cameras/ws?token=` | any authenticated user |

Auditor is read-only everywhere. Analyst cannot create, edit, start, stop, or
archive a camera and cannot delete evidence.

Frame and evidence image endpoints accept the JWT as a query parameter because
`<img>` elements cannot send an `Authorization` header. The token is validated on
every request, responses are `Cache-Control: no-store`, and camera responses mask
credentials embedded in stream URLs.

## Privacy and consent

- A `WEBCAM` source captures **real imagery from the machine it runs on**. Do not
  point a demo camera at other people, screens, or rooms without their consent.
- Captured frames are written to `backend/storage/uploads/camera/<camera id>/`.
  To discard demo imagery, stop the streams, delete that directory, and remove
  the camera rows.
- `scripts/cleanup-camera-test-data.py` removes synthetic camera test rows and
  their evidence files.
- Never enable a camera source for a real deployment without a lawful basis,
  signage, a retention policy, and access control.

## Running the demo on Windows

```powershell
# 1. Install dependencies (adds opencv-python)
.\scripts\setup.ps1

# 2. Start the backend and frontend
.\scripts\start-backend.ps1
.\scripts\start-frontend.ps1

# 3. Register the three demo cameras and optionally start them
.\scripts\setup-camera-demo.ps1 -DemoMode -Start

# 4. Open the monitoring grid and the review queue
#    http://127.0.0.1:5173/monitoring
#    http://127.0.0.1:5173/monitoring/review
#    http://127.0.0.1:5173/admin/cameras
```

`scripts/setup-camera-demo.ps1` registers:

| Camera | Source | Location |
| --- | --- | --- |
| Demo Camera 01 - Main Gate | `WEBCAM` index 0 | Main Gate |
| Demo Camera 02 - Parking | `VIDEO_FILE` `datasets/camera_demo/demo-parking.mp4` | Parking Area |
| Demo Camera 03 - Entrance | `VIDEO_FILE` `datasets/camera_demo/demo-entrance.mp4` | Building Entrance |

The two clips are generated by `scripts/generate_camera_demo_media.py` and are
clearly watermarked synthetic footage.

**Important demo caveat:** the bundled synthetic clips contain a drawn subject
that a Haar cascade does not classify as a face, so they do not produce real
detections. Real detection requires a real face: point the webcam at a person, or
set a `VIDEO_FILE` camera to an MP4 that contains a person. The synthetic clips
demonstrate independent multi-source capture, evidence storage, cooldown, review,
and graph integration through **demo simulation events**.

## Demo simulation mode

With `CNI_CAMERA_DEMO_MODE=true`, a camera may declare a scripted timeline in its
`metadata.demo_events` array:

```json
{
  "demo_events": [
    {
      "timestamp_seconds": 4.0,
      "bbox": { "x": 300, "y": 170, "width": 120, "height": 140 },
      "confidence": 0.97,
      "label": "Potential match event - SIMULATED",
      "suggested_person_id": "ENT-DEMO-P1001"
    }
  ]
}
```

When the clip timeline crosses the timestamp, the worker emits a simulated
observation. The UI shows a persistent
`DEMO SIMULATION MODE — NOT BIOMETRIC IDENTIFICATION` banner, the observation is
flagged `is_simulated`, and `suggested_person_id` is only a hint: the reviewer
must still pick a Person to create the graph edge.

## Verification

```powershell
# Unit + integration suite (isolated temporary database)
& .\.venv\Scripts\python.exe -m pytest backend\tests

# Live end-to-end walkthrough against a running backend with demo mode enabled
$env:CNI_CAMERA_DEMO_MODE = "true"
.\.venv\Scripts\python.exe scripts\verify-camera-e2e.py
```

Coverage includes camera creation authorization, start/stop, invalid source
handling, video-file streaming, face detection, bounding-box generation, evidence
frame creation, cooldown throttling, review flow, manual association, audit
events, Analyst/Admin/Auditor permissions, and simultaneous camera workers.

## Known limitations

- Haar cascade is a prototype detector: it is fast, local, and license-friendly,
  but it is not accurate and it produces no confidence score.
- The 10-second cooldown is per camera, not per tracked face. Without a tracker,
  two different faces appearing together can share one event window.
- Video files loop; HTTP and RTSP sources depend on the network and on OpenCV
  being able to open the URL.
- Evidence is stored under `backend/storage/uploads/camera/<camera id>/`.
  Retention is not yet automated; only event frames are stored, never continuous
  video.
- Frame and evidence image delivery uses short-lived polling endpoints rather
  than an MJPEG multipart stream.
