"""Out-of-process end-to-end verification for the camera monitoring module.

Runs against a live backend and walks the full acceptance path:

  video file source -> capture worker -> annotated evidence frame
  -> review queue -> human association -> knowledge graph observation
  -> audit trail

Usage (Windows PowerShell):

    .\\.venv\\Scripts\\python.exe scripts\\verify-camera-e2e.py

The script never performs face identification. It only verifies that a human
reviewer action is required before the graph receives a Person association.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "backend").as_uri()  # placeholder to keep linters quiet
API_BASE = "http://127.0.0.1:8000/api/v1"
USERNAME = "admin"
PASSWORD = "ChangeMe-Admin-2026!"

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  PASS  {label}")
    else:
        FAILED.append(f"{label} {detail}".strip())
        print(f"  FAIL  {label} {detail}".strip())


def main() -> int:
    client = httpx.Client(timeout=30.0)
    try:
        print("== Authentication ==")
        login = client.post(f"{API_BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD})
        check("Admin login", login.status_code == 200, login.text[:160])
        if login.status_code != 200:
            return 1
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("== Camera source registration ==")
        clip = "datasets/camera_demo/demo-parking.mp4"
        suffix = uuid.uuid4().hex[:8]
        payload = {
            "camera_name": f"E2E Camera {suffix}",
            "source_type": "VIDEO_FILE",
            "source_uri": clip,
            "location_name": f"E2E Location {suffix}",
            "timezone": "Asia/Kolkata",
            "description": "End-to-end verification camera",
            "metadata": {
                "demo_events": [
                    {
                        "timestamp_seconds": 1.0,
                        "bbox": {"x": 300, "y": 170, "width": 120, "height": 140},
                        "confidence": 0.96,
                        "label": "Potential match event - SIMULATED",
                        "suggested_person_id": "ENT-DEMO-P1001",
                    }
                ]
            },
        }
        created = client.post(f"{API_BASE}/cameras", headers=headers, json=payload)
        check("Admin created camera", created.status_code == 201, created.text[:200])
        if created.status_code != 201:
            return 1
        camera = created.json()
        camera_id = camera["id"]
        check("Source URI is masked in response", camera["source_uri_masked"].endswith("demo-parking.mp4"))

        denied = client.post(
            f"{API_BASE}/cameras",
            headers={**headers, "Authorization": f"Bearer {client.post(f'{API_BASE}/auth/login', json={'username': 'analyst', 'password': 'ChangeMe-Analyst-2026!'}).json()['access_token']}"},
            json=payload,
        )
        check("Analyst cannot create camera", denied.status_code == 403, denied.text[:160])

        print("== Stream start and evidence capture ==")
        started = client.post(f"{API_BASE}/cameras/{camera_id}/start", headers=headers)
        check("Admin started camera", started.status_code == 200, started.text[:200])

        observation: dict | None = None
        deadline = time.time() + 45
        while time.time() < deadline and observation is None:
            listed = client.get(f"{API_BASE}/cameras/observations/all", headers=headers, params={"camera_id": camera_id, "limit": 5})
            if listed.status_code == 200 and listed.json():
                observation = listed.json()[0]
                break
            time.sleep(1.0)
        check("Observation captured from video file", observation is not None)
        if observation is None:
            return 1

        check("Observation is labeled simulated", observation["is_simulated"] is True and "SIMULATED" in observation["simulation_label"].upper())
        check("Observation has camera id and location", observation["camera_id"] == camera_id and bool(observation["location_name"]))
        check("Observation has a timestamp", bool(observation["timestamp"]))
        check("Bounding box is present", observation["bbox"]["width"] > 0 and observation["bbox"]["height"] > 0)
        check("Raw frame evidence stored", bool(observation["evidence_id"]))
        check("Annotated frame evidence stored", bool(observation["annotated_evidence_id"]))

        frame = client.get(f"{API_BASE}/cameras/observations/{observation['id']}/annotated-frame", params={"token": token})
        check("Annotated evidence is downloadable", frame.status_code == 200 and frame.content[:2] == b"\xff\xd8", f"status={frame.status_code} bytes={len(frame.content)}")

        status = client.get(f"{API_BASE}/cameras/{camera_id}/status", headers=headers).json()
        check("Camera reports LIVE status", status["status"] == "LIVE", json.dumps(status)[:200])
        check("Camera reports detection count", status["detection_count"] >= 1)
        check("Demo mode surfaced to the client", status["demo_mode"] is True)

        latest = client.get(f"{API_BASE}/cameras/{camera_id}/latest-frame", params={"token": token})
        check("Live annotated frame endpoint works", latest.status_code == 200 and latest.content[:2] == b"\xff\xd8", f"status={latest.status_code}")

        print("== Cooldown / duplicate throttling ==")
        before = len(client.get(f"{API_BASE}/cameras/observations/all", headers=headers, params={"camera_id": camera_id, "limit": 200}).json())
        time.sleep(6)
        after = len(client.get(f"{API_BASE}/cameras/observations/all", headers=headers, params={"camera_id": camera_id, "limit": 200}).json())
        check("Cooldown limits duplicate observations", after - before <= 1, f"before={before} after={after}")

        print("== Human review and knowledge graph ==")
        detail = client.get(f"{API_BASE}/cameras/observations/{observation['id']}", headers=headers)
        check("Analyst/Admin can open the observation", detail.status_code == 200)
        check("Review starts as PENDING_REVIEW", detail.json()["review_status"] == "PENDING_REVIEW")

        graph_before = client.get(f"{API_BASE}/graph", headers=headers, params={"center_id": "ENT-DEMO-P1001", "depth": 2}).json()
        had_link = any(edge["relationship_type"] == "HUMAN_VERIFIED_OBSERVATION" and edge["target"] == observation["id"] for edge in graph_before["edges"])
        check("No person link exists before human review", not had_link)

        analyst_login = client.post(f"{API_BASE}/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        analyst_headers = {"Authorization": f"Bearer {analyst_login.json()['access_token']}"}
        auditor_login = client.post(f"{API_BASE}/auth/login", json={"username": "auditor", "password": "ChangeMe-Auditor-2026!"})
        auditor_headers = {"Authorization": f"Bearer {auditor_login.json()['access_token']}"}

        auditor_review = client.post(
            f"{API_BASE}/cameras/observations/{observation['id']}/review",
            headers=auditor_headers,
            json={"decision": "VERIFY"},
        )
        check("Auditor cannot review observations", auditor_review.status_code == 403, auditor_review.text[:160])

        rejected = client.post(
            f"{API_BASE}/cameras/observations/{observation['id']}/review",
            headers=analyst_headers,
            json={"decision": "ASSOCIATE", "notes": "Association requires a selected Person"},
        )
        check("Association without a Person is rejected", rejected.status_code == 422, rejected.text[:200])

        associated = client.post(
            f"{API_BASE}/cameras/observations/{observation['id']}/review",
            headers=analyst_headers,
            json={"decision": "ASSOCIATE", "associated_person_id": "ENT-DEMO-P1001", "notes": "Human reviewer confirmed the event."},
        )
        check("Analyst can manually associate a Person", associated.status_code == 200, associated.text[:220])
        if associated.status_code == 200:
            check("Review status becomes ASSOCIATED_WITH_ENTITY", associated.json()["review_status"] == "ASSOCIATED_WITH_ENTITY")
            check("Reviewer identity is recorded", associated.json()["reviews"][0]["reviewer_id"] is not None)

        second_review = client.post(
            f"{API_BASE}/cameras/observations/{observation['id']}/review",
            headers=analyst_headers,
            json={"decision": "REJECT"},
        )
        check("A reviewed observation cannot be silently re-decided", second_review.status_code == 409, second_review.text[:160])

        graph_after = client.get(f"{API_BASE}/graph", headers=headers, params={"center_id": "ENT-DEMO-P1001", "depth": 2}).json()
        person_edge = next((edge for edge in graph_after["edges"] if edge["relationship_type"] == "HUMAN_VERIFIED_OBSERVATION" and edge["target"] == observation["id"]), None)
        check("Graph receives the reviewed association", person_edge is not None)
        check("Graph edge carries evidence provenance", bool(person_edge and person_edge.get("evidence_id")))
        captured_by = any(edge["relationship_type"] == "CAPTURED_BY" and edge["source"] == observation["id"] for edge in graph_after["edges"])
        check("Observation is linked to its camera", captured_by)
        located_at = any(edge["relationship_type"] == "LOCATED_AT" and edge["source"] == observation["id"] for edge in graph_after["edges"])
        check("Observation is linked to its location", located_at)

        print("== Audit trail ==")
        for action in (
            "CAMERA_CREATED",
            "CAMERA_STARTED",
            "CAMERA_OBSERVATION_CREATED",
            "CAMERA_EVIDENCE_VIEWED",
            "OBSERVATION_ASSOCIATED_WITH_PERSON",
        ):
            events = client.get(f"{API_BASE}/audit", headers=headers, params={"action": action, "limit": 20})
            check(f"Audit contains {action}", events.status_code == 200 and any(item["action"] == action for item in events.json()))

        print("== Stream control ==")
        stopped = client.post(f"{API_BASE}/cameras/{camera_id}/stop", headers=headers)
        check("Admin stopped camera", stopped.status_code == 200 and stopped.json()["status"] == "STOPPED", stopped.text[:200])
        analyst_stop = client.post(f"{API_BASE}/cameras/{camera_id}/stop", headers=analyst_headers)
        check("Analyst cannot stop camera", analyst_stop.status_code == 403)
    finally:
        client.close()

    print()
    print(f"Passed: {len(PASSED)}   Failed: {len(FAILED)}")
    for failure in FAILED:
        print(f"  - {failure}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
