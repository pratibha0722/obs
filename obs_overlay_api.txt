# obs_overlay_api.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from obsws_python import ReqClient
from typing import Optional, Dict, Any, List

# =========================
# CONFIG
# =========================

BASE_URL = "https://nntr.in/api/api/Conference"

# OBS config
OBS_HOST = "192.168.1.8"
OBS_PORT = 4455
OBS_PASSWORD = "29kPOoAi6qZGjFv6"

# OBS scene/source names
OVERLAY_SCENE_NAME = "ConferenceOverlayScene"
ADVERTISEMENT_SCENE_NAME = "AdvertisementScene"
TEXT_SOURCE_NAME = "ConferenceOverlayText"

# Optional: if you create a second text source for next talk only
NEXT_TALK_TEXT_SOURCE_NAME = "ConferenceNextTalkText"

# Flask config
API_HOST = "0.0.0.0"
API_PORT = 5001
DEBUG = True

# API endpoints from your backend
GET_ALL_SESSIONS_ENDPOINT = f"{BASE_URL}/GetSession"
GET_SESSION_BY_ID_ENDPOINT = f"{BASE_URL}/Get-Session"

# =========================
# APP
# =========================

app = Flask(__name__)
CORS(app)

# =========================
# HELPERS
# =========================

def obs_client() -> ReqClient:
    return ReqClient(
        host=OBS_HOST,
        port=OBS_PORT,
        password=OBS_PASSWORD,
        timeout=5
    )

def safe_get(url: str, timeout: int = 15) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def normalize(value: Any) -> str:
    return str(value or "").strip()

def hhmm(value: Optional[str]) -> str:
    """
    Handles:
    - 16:34:00
    - 16:34:00.123456
    - None
    """
    if not value:
        return "—"
    value = str(value).strip()
    if len(value) >= 5:
        return value[:5]
    return value

def duration_to_min(value: Optional[str]) -> str:
    """
    '00:10:00' -> '10 min'
    """
    if not value:
        return "—"
    try:
        parts = str(value).split(":")
        h = int(parts[0]) if len(parts) > 0 else 0
        m = int(parts[1]) if len(parts) > 1 else 0
        total = h * 60 + m
        return f"{total} min"
    except Exception:
        return value

def get_all_sessions() -> List[Dict[str, Any]]:
    data = safe_get(GET_ALL_SESSIONS_ENDPOINT)
    return data.get("data") or []

def get_session_details(session_id: str) -> List[Dict[str, Any]]:
    data = safe_get(f"{GET_SESSION_BY_ID_ENDPOINT}/{session_id}")
    return data.get("data") or []

def find_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    sessions = get_all_sessions()
    for s in sessions:
        if normalize(s.get("id")) == normalize(session_id):
            return s
    return None

def sort_details(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort by:
    1. startTime if present
    2. createdDate fallback
    3. original as-is if values missing
    """
    def sort_key(d: Dict[str, Any]):
        st = normalize(d.get("startTime"))
        cd = normalize(d.get("createdDate"))
        return (st or "99:99:99", cd or "9999-12-31T23:59:59")
    return sorted(details, key=sort_key)

def find_detail_by_id(details: List[Dict[str, Any]], detail_id: str) -> Optional[Dict[str, Any]]:
    for d in details:
        if normalize(d.get("id")) == normalize(detail_id):
            return d
    return None

def find_next_detail(details: List[Dict[str, Any]], current_detail_id: str) -> Optional[Dict[str, Any]]:
    ordered = sort_details(details)
    for i, d in enumerate(ordered):
        if normalize(d.get("id")) == normalize(current_detail_id):
            if i + 1 < len(ordered):
                return ordered[i + 1]
            return None
    return None

def build_overlay_text(
    session: Dict[str, Any],
    current_detail: Dict[str, Any],
    next_detail: Optional[Dict[str, Any]]
) -> str:
    session_name = normalize(session.get("sessionName")) or "—"
    hall_name = normalize(session.get("hallName")) or "—"
    location = normalize(session.get("location")) or "—"
    chair = normalize(session.get("chairPersonName")) or "—"

    topic = normalize(current_detail.get("topic")) or "—"
    speaker = normalize(current_detail.get("nameOfSpeaker")) or "—"
    start_time = hhmm(current_detail.get("startTime"))
    end_time = hhmm(current_detail.get("endTime"))
    duration = duration_to_min(current_detail.get("time"))

    if next_detail:
        next_topic = normalize(next_detail.get("topic")) or "—"
        next_speaker = normalize(next_detail.get("nameOfSpeaker")) or "—"
        next_line = f"Next: {next_topic} | {next_speaker}"
    else:
        next_line = "Next: No further talk in this session"

    text = (
        f"{session_name}\n"
        f"Topic: {topic}\n"
        f"Speaker: {speaker}\n"
        f"Time: {start_time} - {end_time}  |  Duration: {duration}\n"
        f"Hall: {hall_name}\n"
        f"Location: {location}\n"
        f"Chair: {chair}\n"
        f"{next_line}"
    )
    return text

def build_next_talk_text(next_detail: Optional[Dict[str, Any]]) -> str:
    if not next_detail:
        return "No next talk"
    next_topic = normalize(next_detail.get("topic")) or "—"
    next_speaker = normalize(next_detail.get("nameOfSpeaker")) or "—"
    next_start = hhmm(next_detail.get("startTime"))
    next_end = hhmm(next_detail.get("endTime"))
    return f"UP NEXT: {next_topic} | {next_speaker} | {next_start} - {next_end}"

def set_obs_text(source_name: str, text_value: str):
    client = obs_client()
    client.set_input_settings(
        name=source_name,
        settings={"text": text_value},
        overlay=True
    )

def switch_scene(scene_name: str):
    client = obs_client()
    client.set_current_program_scene(scene_name)

def send_overlay_to_obs(overlay_text: str, next_talk_text: Optional[str] = None):
    set_obs_text(TEXT_SOURCE_NAME, overlay_text)

    # Optional second text source
    if next_talk_text:
        try:
            set_obs_text(NEXT_TALK_TEXT_SOURCE_NAME, next_talk_text)
        except Exception:
            # Ignore if source not created yet
            pass

    switch_scene(OVERLAY_SCENE_NAME)

def show_advertisement_scene():
    switch_scene(ADVERTISEMENT_SCENE_NAME)

def get_overlay_payload(session_id: str, detail_id: str) -> Dict[str, Any]:
    session = find_session_by_id(session_id)
    if not session:
        raise ValueError(f"Session not found for sessionId={session_id}")

    details = get_session_details(session_id)
    if not details:
        raise ValueError(f"No session details found for sessionId={session_id}")

    current_detail = find_detail_by_id(details, detail_id)
    if not current_detail:
        raise ValueError(f"Session detail not found for detailId={detail_id}")

    next_detail = find_next_detail(details, detail_id)

    overlay_text = build_overlay_text(session, current_detail, next_detail)
    next_talk_text = build_next_talk_text(next_detail)

    return {
        "session": session,
        "currentDetail": current_detail,
        "nextDetail": next_detail,
        "overlayText": overlay_text,
        "nextTalkText": next_talk_text,
    }

# =========================
# ROUTES
# =========================

@app.get("/health")
def health():
    return jsonify({
        "success": True,
        "message": "OBS overlay API running"
    })

@app.post("/overlay/start")
def overlay_start():
    """
    Expected payload:
    {
      "sessionId": "....",
      "detailId": "...."
    }
    """
    try:
        body = request.get_json(force=True) or {}
        session_id = normalize(body.get("sessionId"))
        detail_id = normalize(body.get("detailId"))

        if not session_id or not detail_id:
            return jsonify({
                "success": False,
                "message": "sessionId and detailId are required"
            }), 400

        payload = get_overlay_payload(session_id, detail_id)
        send_overlay_to_obs(
            overlay_text=payload["overlayText"],
            next_talk_text=payload["nextTalkText"]
        )

        return jsonify({
            "success": True,
            "message": "Overlay sent to OBS and switched to overlay scene",
            "data": {
                "sessionId": session_id,
                "detailId": detail_id,
                "overlayText": payload["overlayText"],
                "nextTalkText": payload["nextTalkText"]
            }
        })

    except requests.HTTPError as e:
        return jsonify({
            "success": False,
            "message": f"Backend API HTTP error: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.post("/overlay/preview")
def overlay_preview():
    """
    Same as start, but useful for testing.
    Sends text to OBS overlay scene.
    """
    try:
        body = request.get_json(force=True) or {}
        session_id = normalize(body.get("sessionId"))
        detail_id = normalize(body.get("detailId"))

        if not session_id or not detail_id:
            return jsonify({
                "success": False,
                "message": "sessionId and detailId are required"
            }), 400

        payload = get_overlay_payload(session_id, detail_id)
        send_overlay_to_obs(
            overlay_text=payload["overlayText"],
            next_talk_text=payload["nextTalkText"]
        )

        return jsonify({
            "success": True,
            "message": "Preview sent to OBS",
            "data": {
                "overlayText": payload["overlayText"],
                "nextTalkText": payload["nextTalkText"]
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.post("/overlay/end")
def overlay_end():
    """
    Expected payload:
    {
      "sessionId": "....",
      "detailId": "...."
    }

    Right now end action only switches to ad scene.
    """
    try:
        show_advertisement_scene()

        return jsonify({
            "success": True,
            "message": "OBS switched to advertisement scene"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.post("/overlay/clear")
def overlay_clear():
    """
    Clears text but does not change scene.
    """
    try:
        set_obs_text(TEXT_SOURCE_NAME, "")
        try:
            set_obs_text(NEXT_TALK_TEXT_SOURCE_NAME, "")
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": "Overlay text cleared"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print("======================================")
    print("OBS Overlay API starting...")
    print(f"API  : http://{API_HOST}:{API_PORT}")
    print(f"OBS  : ws://{OBS_HOST}:{OBS_PORT}")
    print(f"Text : {TEXT_SOURCE_NAME}")
    print("======================================")
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)