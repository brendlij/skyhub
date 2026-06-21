from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo

from uuid import uuid4
from astral import LocationInfo
from astral.sun import sun
from pydantic import BaseModel
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
import structlog

from app.db.database import SessionLocal, create_db_tables, get_db_session
from app.config import get_settings
from app.repositories.node_repository import NodeRepository
from app.repositories.node_camera_settings_repository import NodeCameraSettingsRepository
from app.realtime.connection_manager import ConnectionManager

logger = structlog.get_logger()
connections = ConnectionManager()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_tables()
    db = SessionLocal()
    try:
        offline_count = NodeRepository(db).mark_all_offline()
        logger.info("nodes.marked_offline", count=offline_count)
    finally:
        db.close()

    logger.info("database.ready")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SkyHub</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #0f1115;
      --panel: #171a21;
      --panel-2: #1f2430;
      --text: #f3f5f7;
      --muted: #9aa4b2;
      --line: #2b3240;
      --accent: #5bbcff;
      --ok: #61d394;
      --bad: #ff6b6b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid var(--line);
      background: #12151b;
    }
    h1 { margin: 0; font-size: 20px; }
    main {
      display: grid;
      grid-template-columns: 340px minmax(0, 1fr);
      gap: 16px;
      padding: 16px;
    }
    section {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      overflow: hidden;
    }
    h2 {
      margin: 0;
      padding: 12px 14px;
      font-size: 14px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    .nodes { display: grid; gap: 8px; padding: 10px; }
    .node {
      width: 100%;
      text-align: left;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--panel-2);
      color: var(--text);
      cursor: pointer;
    }
    .node.active { border-color: var(--accent); }
    .node strong { display: block; margin-bottom: 4px; }
    .status { color: var(--bad); font-size: 13px; }
    .status.online { color: var(--ok); }
    .content { padding: 14px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    label { display: grid; gap: 6px; font-size: 13px; color: var(--muted); }
    input {
      width: 100%;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: #10131a;
      color: var(--text);
    }
    input[type="checkbox"] { width: auto; }
    .check { display: flex; align-items: center; gap: 8px; padding-top: 23px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 11px;
      background: var(--panel-2);
      color: var(--text);
      cursor: pointer;
    }
    button.primary { background: #12324a; border-color: #285f86; }
    button.danger { background: #3a171a; border-color: #793036; }
    button:disabled { opacity: .5; cursor: not-allowed; }
    .preview {
      display: grid;
      gap: 10px;
    }
    .preview img {
      width: 100%;
      max-height: 65vh;
      object-fit: contain;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #050608;
    }
    .meta, .message { color: var(--muted); font-size: 13px; }
    .message { min-height: 18px; }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>SkyHub</h1>
    <a href="/docs" style="color: var(--accent)">API docs</a>
  </header>
  <main>
    <section>
      <h2>Nodes</h2>
      <div id="nodes" class="nodes"></div>
    </section>
    <div class="preview">
      <section>
        <h2>Control</h2>
        <div class="content">
          <div id="selected" class="meta">No node selected</div>
          <div class="actions">
            <button id="refresh">Refresh</button>
            <button id="start" class="primary" disabled>Start</button>
            <button id="stop" class="danger" disabled>Stop</button>
          </div>
          <div id="message" class="message"></div>
        </div>
      </section>
      <section>
        <h2>Settings</h2>
        <div class="content">
          <div class="grid">
            <label>Interval seconds<input id="interval_seconds" type="number" min="1"></label>
            <label>Width<input id="width" type="number" min="1"></label>
            <label>Height<input id="height" type="number" min="1"></label>
            <label>Format<input id="format"></label>
            <label class="check"><input id="day_auto_exposure" type="checkbox"> Day auto exposure</label>
            <label>Day exposure ms<input id="day_exposure_ms" type="number" min="1"></label>
            <label class="check"><input id="day_auto_gain" type="checkbox"> Day auto gain</label>
            <label>Day gain<input id="day_gain" type="number" step="0.1" min="0"></label>
            <label class="check"><input id="night_auto_exposure" type="checkbox"> Night auto exposure</label>
            <label>Night exposure ms<input id="night_exposure_ms" type="number" min="1"></label>
            <label class="check"><input id="night_auto_gain" type="checkbox"> Night auto gain</label>
            <label>Night gain<input id="night_gain" type="number" step="0.1" min="0"></label>
          </div>
          <div class="actions">
            <button id="save" class="primary" disabled>Save Settings</button>
          </div>
        </div>
      </section>
      <section>
        <h2>Latest Capture</h2>
        <div class="content">
          <div id="latestMeta" class="meta">No capture loaded</div>
          <img id="latestImage" alt="Latest capture" hidden>
        </div>
      </section>
    </div>
  </main>
  <script>
    let selectedNodeId = null;

    const fields = [
      "interval_seconds", "width", "height", "format",
      "day_auto_exposure", "day_exposure_ms", "day_auto_gain", "day_gain",
      "night_auto_exposure", "night_exposure_ms", "night_auto_gain", "night_gain"
    ];

    function setMessage(text) {
      document.getElementById("message").textContent = text || "";
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || response.statusText);
      }
      return response.json();
    }

    async function loadNodes() {
      const data = await requestJson("/api/nodes");
      const container = document.getElementById("nodes");
      container.innerHTML = "";
      const onlineNode = data.nodes.find(node => node.online);
      const selectedNode = data.nodes.find(node => node.node_id === selectedNodeId);

      if ((!selectedNodeId || !selectedNode || (!selectedNode.online && onlineNode)) && (onlineNode || data.nodes.length)) {
        selectedNodeId = (onlineNode || data.nodes[0]).node_id;
      }

      for (const node of data.nodes) {
        const button = document.createElement("button");
        button.className = "node" + (node.node_id === selectedNodeId ? " active" : "");
        button.innerHTML = `
          <strong>${node.node_id}</strong>
          <span class="status ${node.online ? "online" : ""}">${node.online ? "online" : "offline"}</span>
          <div class="meta">${node.last_message_type || "no messages yet"}</div>
          ${node.online ? "" : "<div class=\\"meta\\">Click to select, delete below</div>"}
        `;
        button.onclick = () => selectNode(node.node_id);
        container.appendChild(button);

        if (!node.online) {
          const deleteButton = document.createElement("button");
          deleteButton.className = "node";
          deleteButton.textContent = `Delete ${node.node_id}`;
          deleteButton.onclick = () => deleteNode(node.node_id);
          container.appendChild(deleteButton);
        }
      }

      if (selectedNodeId) {
        document.getElementById("selected").textContent = `Selected: ${selectedNodeId}`;
        document.getElementById("start").disabled = false;
        document.getElementById("stop").disabled = false;
        document.getElementById("save").disabled = false;
      }
    }

    async function selectNode(nodeId) {
      selectedNodeId = nodeId;
      document.getElementById("selected").textContent = `Selected: ${nodeId}`;
      document.getElementById("start").disabled = false;
      document.getElementById("stop").disabled = false;
      document.getElementById("save").disabled = false;
      await Promise.all([loadNodes(), loadSettings(), loadLatest()]);
    }

    async function deleteNode(nodeId) {
      await requestJson(`/api/nodes/${nodeId}`, { method: "DELETE" });
      if (selectedNodeId === nodeId) selectedNodeId = null;
      setMessage(`Deleted ${nodeId}`);
      await loadNodes();
    }

    async function loadSettings() {
      if (!selectedNodeId) return;
      const settings = await requestJson(`/api/nodes/${selectedNodeId}/settings`);
      document.getElementById("interval_seconds").value = settings.interval_seconds;
      document.getElementById("width").value = settings.width;
      document.getElementById("height").value = settings.height;
      document.getElementById("format").value = settings.format;
      document.getElementById("day_auto_exposure").checked = settings.day.auto_exposure;
      document.getElementById("day_exposure_ms").value = settings.day.exposure_ms || "";
      document.getElementById("day_auto_gain").checked = settings.day.auto_gain;
      document.getElementById("day_gain").value = settings.day.gain || "";
      document.getElementById("night_auto_exposure").checked = settings.night.auto_exposure;
      document.getElementById("night_exposure_ms").value = settings.night.exposure_ms || "";
      document.getElementById("night_auto_gain").checked = settings.night.auto_gain;
      document.getElementById("night_gain").value = settings.night.gain || "";
    }

    function value(id) {
      const element = document.getElementById(id);
      if (element.type === "checkbox") return element.checked;
      if (element.type === "number") return element.value === "" ? null : Number(element.value);
      return element.value;
    }

    async function saveSettings() {
      if (!selectedNodeId) return;
      const body = {};
      for (const field of fields) body[field] = value(field);
      await requestJson(`/api/nodes/${selectedNodeId}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      setMessage("Settings saved");
    }

    async function startCapture() {
      if (!selectedNodeId) return;
      const result = await requestJson(`/api/nodes/${selectedNodeId}/sequence/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}"
      });
      setMessage(`Started ${result.sequence_id}`);
    }

    async function stopCapture() {
      if (!selectedNodeId) return;
      await requestJson(`/api/nodes/${selectedNodeId}/sequence/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}"
      });
      setMessage("Stop sent");
      setTimeout(loadLatest, 1000);
    }

    async function loadLatest() {
      if (!selectedNodeId) return;
      const image = document.getElementById("latestImage");
      const meta = document.getElementById("latestMeta");
      try {
        const latest = await requestJson(`/api/captures/latest?node_id=${encodeURIComponent(selectedNodeId)}`);
        const url = `/api/captures/${latest.node_id}/${latest.archive_date}/${latest.period}/${latest.filename}`;
        image.src = `${url}?t=${Date.now()}`;
        image.hidden = false;
        meta.textContent = `${latest.archive_date}/${latest.period} - ${latest.filename} - ${latest.size_bytes} bytes`;
      } catch (error) {
        image.hidden = true;
        meta.textContent = "No captures for this node yet";
      }
    }

    document.getElementById("refresh").onclick = () => Promise.all([loadNodes(), loadLatest()]);
    document.getElementById("save").onclick = () => saveSettings().catch(error => setMessage(error.message));
    document.getElementById("start").onclick = () => startCapture().catch(error => setMessage(error.message));
    document.getElementById("stop").onclick = () => stopCapture().catch(error => setMessage(error.message));

    loadNodes().catch(error => setMessage(error.message));
    setInterval(() => {
      loadNodes().catch(() => {});
      loadLatest().catch(() => {});
    }, 10000);
  </script>
</body>
</html>
"""


@app.get("/api/nodes")
async def list_nodes(db: Session = Depends(get_db_session)):
    repo = NodeRepository(db)
    nodes = repo.list_all()

    return {
        "nodes": [
            {
                "node_id": node.node_id,
                "online": node.online,
                "version": node.version,
                "capabilities": node.capabilities,
                "connected_at": node.connected_at.isoformat() if node.connected_at else None,
                "disconnected_at": node.disconnected_at.isoformat() if node.disconnected_at else None,
                "last_seen_at": node.last_seen_at.isoformat() if node.last_seen_at else None,
                "last_message_type": node.last_message_type,
            }
            for node in nodes
        ]
    }


@app.delete("/api/nodes/{node_id}")
async def delete_node(node_id: str, db: Session = Depends(get_db_session)):
    managed_node = connections.get_node(node_id)

    if managed_node is not None and managed_node.online:
        raise HTTPException(status_code=409, detail="Cannot delete an online node")

    settings_repo = NodeCameraSettingsRepository(db)
    node_repo = NodeRepository(db)
    settings_deleted = settings_repo.delete(node_id)
    node_deleted = node_repo.delete(node_id)

    if not node_deleted and not settings_deleted:
        raise HTTPException(status_code=404, detail="Node not found")

    return {
        "status": "deleted",
        "node_id": node_id,
        "node_deleted": node_deleted,
        "settings_deleted": settings_deleted,
    }


class SequenceStartRequest(BaseModel):
    interval_seconds: int | None = None
    exposure_ms: int | None = None
    gain: float | None = None
    auto_exposure: bool | None = None
    auto_gain: bool | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None


class SequenceStopRequest(BaseModel):
    sequence_id: str | None = None


class NodeCameraSettingsUpdate(BaseModel):
    interval_seconds: int | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    day_auto_exposure: bool | None = None
    day_exposure_ms: int | None = None
    day_auto_gain: bool | None = None
    day_gain: float | None = None
    night_auto_exposure: bool | None = None
    night_exposure_ms: int | None = None
    night_auto_gain: bool | None = None
    night_gain: float | None = None


def safe_path_part(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in ["-", "_", "."] else "_"
        for character in value
    ).strip("._") or "unknown"


def parse_capture_datetime(parsed_metadata: dict) -> datetime:
    captured_at = parsed_metadata.get("captured_at")

    if isinstance(captured_at, str):
        try:
            parsed = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            logger.warning("capture.timestamp.invalid", captured_at=captured_at)

    return datetime.now(timezone.utc)


def archive_period(captured_at: datetime) -> tuple[str, str]:
    local_timezone = ZoneInfo(settings.timezone)
    local_time = captured_at.astimezone(local_timezone)
    location = LocationInfo(
        name="SkyHub",
        region="",
        timezone=settings.timezone,
        latitude=settings.latitude,
        longitude=settings.longitude,
    )

    today_sun = sun(location.observer, date=local_time.date(), tzinfo=local_timezone)
    sunrise = today_sun["sunrise"]
    sunset = today_sun["sunset"]

    if sunrise <= local_time < sunset:
        return local_time.date().isoformat(), "day"

    if local_time >= sunset:
        return local_time.date().isoformat(), "night"

    previous_day = local_time.date()
    previous_day = previous_day.fromordinal(previous_day.toordinal() - 1)
    return previous_day.isoformat(), "night"


def camera_settings_to_dict(camera_settings) -> dict:
    return {
        "node_id": camera_settings.node_id,
        "interval_seconds": camera_settings.interval_seconds,
        "width": camera_settings.width,
        "height": camera_settings.height,
        "format": camera_settings.format,
        "day": {
            "auto_exposure": camera_settings.day_auto_exposure,
            "exposure_ms": camera_settings.day_exposure_ms,
            "auto_gain": camera_settings.day_auto_gain,
            "gain": camera_settings.day_gain,
        },
        "night": {
            "auto_exposure": camera_settings.night_auto_exposure,
            "exposure_ms": camera_settings.night_exposure_ms,
            "auto_gain": camera_settings.night_auto_gain,
            "gain": camera_settings.night_gain,
        },
        "updated_at": camera_settings.updated_at.isoformat() if camera_settings.updated_at else None,
    }


def current_period() -> str:
    return archive_period(datetime.now(timezone.utc))[1]


def capture_settings_for_period(camera_settings, period: str) -> dict:
    profile = getattr(camera_settings, "day" if period == "day" else "night", None)

    if profile is None:
        if period == "day":
            auto_exposure = camera_settings.day_auto_exposure
            exposure_ms = camera_settings.day_exposure_ms
            auto_gain = camera_settings.day_auto_gain
            gain = camera_settings.day_gain
        else:
            auto_exposure = camera_settings.night_auto_exposure
            exposure_ms = camera_settings.night_exposure_ms
            auto_gain = camera_settings.night_auto_gain
            gain = camera_settings.night_gain
    else:
        auto_exposure = profile["auto_exposure"]
        exposure_ms = profile["exposure_ms"]
        auto_gain = profile["auto_gain"]
        gain = profile["gain"]

    return {
        "interval_seconds": camera_settings.interval_seconds,
        "width": camera_settings.width,
        "height": camera_settings.height,
        "format": camera_settings.format,
        "period": period,
        "auto_exposure": auto_exposure,
        "exposure_ms": exposure_ms,
        "auto_gain": auto_gain,
        "gain": gain,
    }


def apply_sequence_overrides(capture_settings: dict, request: SequenceStartRequest | None) -> dict:
    if request is None:
        return capture_settings

    overrides = request.model_dump(exclude_none=True)
    return {
        **capture_settings,
        **overrides,
    }


def config_update_message(camera_settings) -> dict:
    period = current_period()
    return {
        "type": "config.update",
        "settings": camera_settings_to_dict(camera_settings),
        "current_period": period,
        "active_settings": capture_settings_for_period(camera_settings, period),
    }


def capture_record_from_path(file_path: Path) -> dict:
    relative_path = file_path.relative_to(settings.captures_dir)
    node_id = relative_path.parts[0]
    archive_date = relative_path.parts[1]
    period = relative_path.parts[2]

    return {
        "node_id": node_id,
        "archive_date": archive_date,
        "period": period,
        "filename": file_path.name,
        "path": str(file_path),
        "size_bytes": file_path.stat().st_size,
        "modified_at": datetime.fromtimestamp(
            file_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat(),
    }


def iter_capture_files():
    if not settings.captures_dir.exists():
        return

    for file_path in settings.captures_dir.glob("*/*/*/*"):
        if file_path.is_file():
            yield file_path


@app.get("/api/nodes/{node_id}/settings")
async def get_node_settings(node_id: str, db: Session = Depends(get_db_session)):
    repo = NodeCameraSettingsRepository(db)
    camera_settings = repo.get_or_create(node_id)
    return camera_settings_to_dict(camera_settings)


@app.put("/api/nodes/{node_id}/settings")
async def update_node_settings(
    node_id: str,
    request: NodeCameraSettingsUpdate,
    db: Session = Depends(get_db_session),
):
    repo = NodeCameraSettingsRepository(db)
    camera_settings = repo.update(node_id, request.model_dump(exclude_none=True))
    settings_payload = camera_settings_to_dict(camera_settings)
    sent = await connections.send_to_node(node_id, config_update_message(camera_settings))

    return {
        "settings": settings_payload,
        "node_notified": sent,
    }


@app.post("/api/nodes/{node_id}/sequence/start")
async def start_sequence(
    node_id: str,
    request: SequenceStartRequest | None = None,
    db: Session = Depends(get_db_session),
):
    sequence_id = f"seq_{uuid4().hex}"
    settings_repo = NodeCameraSettingsRepository(db)
    camera_settings = settings_repo.get_or_create(node_id)
    period = current_period()
    effective_settings = apply_sequence_overrides(
        capture_settings_for_period(camera_settings, period),
        request,
    )

    message = {
        "type": "sequence.start",
        "sequence_id": sequence_id,
        "settings": effective_settings,
    }

    sent = await connections.send_to_node(node_id, message)

    if not sent:
        return {
            "status": "failed",
            "reason": "node_not_connected",
            "node_id": node_id,
        }

    return {
        "status": "sent",
        "node_id": node_id,
        "sequence_id": sequence_id,
        "message": message,
    }


@app.post("/api/nodes/{node_id}/sequence/stop")
async def stop_sequence(node_id: str, request: SequenceStopRequest | None = None):
    message = {
        "type": "sequence.stop",
        "sequence_id": request.sequence_id if request else None,
    }

    sent = await connections.send_to_node(node_id, message)

    if not sent:
        return {
            "status": "failed",
            "reason": "node_not_connected",
            "node_id": node_id,
        }

    return {
        "status": "sent",
        "node_id": node_id,
        "sequence_id": message["sequence_id"],
        "message": message,
    }


@app.get("/api/captures")
async def list_captures(
    node_id: str | None = None,
    archive_date: str | None = None,
    period: str | None = None,
    limit: int = 100,
):
    records = []

    for file_path in iter_capture_files() or []:
        record = capture_record_from_path(file_path)

        if node_id is not None and record["node_id"] != node_id:
            continue

        if archive_date is not None and record["archive_date"] != archive_date:
            continue

        if period is not None and record["period"] != period:
            continue

        records.append(record)

    records.sort(key=lambda record: record["modified_at"], reverse=True)

    return {
        "captures": records[:limit],
        "count": min(len(records), limit),
        "total": len(records),
    }


@app.get("/api/captures/latest")
async def latest_capture(node_id: str | None = None):
    records = []

    for file_path in iter_capture_files() or []:
        record = capture_record_from_path(file_path)

        if node_id is not None and record["node_id"] != node_id:
            continue

        records.append(record)

    if not records:
        raise HTTPException(status_code=404, detail="No captures found")

    records.sort(key=lambda record: record["modified_at"], reverse=True)
    return records[0]


@app.get("/api/captures/{node_id}/{archive_date}/{period}/{filename}")
async def get_capture_file(
    node_id: str,
    archive_date: str,
    period: str,
    filename: str,
):
    safe_node_id = safe_path_part(node_id)
    safe_archive_date = safe_path_part(archive_date)
    safe_period = safe_path_part(period)
    safe_filename = safe_path_part(filename)
    file_path = settings.captures_dir / safe_node_id / safe_archive_date / safe_period / safe_filename

    try:
        resolved_captures_dir = settings.captures_dir.resolve()
        resolved_file_path = file_path.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Capture not found")

    if not resolved_file_path.is_relative_to(resolved_captures_dir):
        raise HTTPException(status_code=400, detail="Invalid capture path")

    if not resolved_file_path.is_file():
        raise HTTPException(status_code=404, detail="Capture not found")

    return FileResponse(
        resolved_file_path,
        media_type="image/jpeg",
        filename=resolved_file_path.name,
    )


@app.post("/api/captures/upload")
async def upload_capture(
    node_id: str = Form(...),
    sequence_id: str | None = Form(default=None),
    format: str = Form(default="jpg"),
    width: int | None = Form(default=None),
    height: int | None = Form(default=None),
    metadata: str = Form(default="{}"),
    file: UploadFile = File(...),
):
    try:
        parsed_metadata = json.loads(metadata)
    except json.JSONDecodeError:
        parsed_metadata = {"raw": metadata}

    upload_node_id = safe_path_part(node_id)
    upload_format = safe_path_part(format.lower())
    original_name = safe_path_part(Path(file.filename or f"capture.{upload_format}").name)
    capture_id = f"cap_{uuid4().hex}"
    archive_date, period = archive_period(parse_capture_datetime(parsed_metadata))
    filename = f"{capture_id}_{original_name}"
    capture_dir = settings.captures_dir / upload_node_id / archive_date / period
    output_path = capture_dir / filename

    capture_dir.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as output_file:
        shutil.copyfileobj(file.file, output_file)

    logger.info(
        "capture.uploaded",
        node_id=node_id,
        sequence_id=sequence_id,
        capture_id=capture_id,
        archive_date=archive_date,
        period=period,
        path=str(output_path),
        size_bytes=output_path.stat().st_size,
    )

    return {
        "status": "stored",
        "capture_id": capture_id,
        "node_id": node_id,
        "sequence_id": sequence_id,
        "path": str(output_path),
        "filename": filename,
        "archive_date": archive_date,
        "period": period,
        "format": upload_format,
        "width": width,
        "height": height,
        "metadata": parsed_metadata,
        "size_bytes": output_path.stat().st_size,
    }


@app.websocket("/ws/nodes/{node_id}")
async def node_websocket(websocket: WebSocket, node_id: str):
    await connections.connect(node_id, websocket)

    db = SessionLocal()
    repo = NodeRepository(db)

    try:
        repo.mark_online(node_id)
        logger.info("node.connected", node_id=node_id)

        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            version = None
            capabilities = None

            if message_type == "node.hello":
                version = message.get("version")
                capabilities = message.get("capabilities", {})

            repo.update_last_seen(
                node_id=node_id,
                message_type=message_type,
                version=version,
                capabilities=capabilities,
            )

            connections.update_last_seen(
                node_id=node_id,
                message_type=message_type,
                metadata={
                    "version": version,
                    "capabilities": capabilities,
                }
                if message_type == "node.hello"
                else None,
            )

            logger.info(
                "node.message.received",
                node_id=node_id,
                message_type=message_type,
            )

            if message_type == "node.hello":
                settings_repo = NodeCameraSettingsRepository(db)
                camera_settings = settings_repo.get_or_create(node_id)
                await websocket.send_json(config_update_message(camera_settings))

            await websocket.send_json(
                {
                    "type": "server.ack",
                    "received_type": message_type,
                }
            )

    except WebSocketDisconnect:
        connections.disconnect(node_id)
        repo.mark_offline(node_id)
        logger.warning("node.disconnected", node_id=node_id)

    finally:
        db.close()
