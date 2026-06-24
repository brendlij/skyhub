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
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import structlog
from PIL import Image

from app.db.database import SessionLocal, create_db_tables, get_db_session
from app.config import get_settings
from app.repositories.node_repository import NodeRepository
from app.repositories.node_camera_settings_repository import NodeCameraSettingsRepository
from app.repositories.node_environment_repository import NodeEnvironmentRepository
from app.repositories.node_overlay_settings_repository import NodeOverlaySettingsRepository
from app.realtime.connection_manager import ConnectionManager
from app.overlays import apply_overlays_to_image

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

if (settings.frontend_dist_dir / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=settings.frontend_dist_dir / "assets"),
        name="frontend-assets",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def frontend_app():
    index_path = settings.frontend_dist_dir / "index.html"

    if index_path.exists():
        return FileResponse(index_path)

    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SkyHub</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f1115; color: #f3f5f7; }
    code { background: #171a21; padding: .2rem .35rem; border-radius: 4px; }
    a { color: #5bbcff; }
  </style>
</head>
<body>
  <h1>SkyHub</h1>
  <p>The Vue frontend has not been built yet.</p>
  <p>For development, run <code>cd frontend && npm install && npm run dev</code>.</p>
  <p>For Python-served static files, run <code>cd frontend && npm run build</code>, then restart the server.</p>
  <p><a href="/docs">API docs</a></p>
</body>
</html>
        """
    )


@app.get("/legacy", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SkyHub</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { min-height: 100vh; }
    .node.active { border-color: var(--bs-info) !important; }
    .node { text-align: left; }
    .preview img {
      width: 100%;
      max-height: 65vh;
      object-fit: contain;
      background: #050608;
    }
  </style>
</head>
<body data-bs-theme="dark" class="bg-body-tertiary">
  <nav class="navbar border-bottom bg-body">
    <div class="container-fluid">
      <span class="navbar-brand mb-0 h1">SkyHub</span>
      <a class="link-info" href="/docs">API docs</a>
    </div>
  </nav>
  <main class="container-fluid py-3">
    <div class="row g-3">
      <aside class="col-12 col-lg-3 col-xxl-2">
        <div class="card">
          <div class="card-header text-uppercase small fw-semibold text-secondary">Nodes</div>
          <div id="nodes" class="card-body row g-2"></div>
        </div>
      </aside>
      <div class="col-12 col-lg-9 col-xxl-10">
        <div class="vstack gap-3">
          <section class="card">
            <div class="card-header text-uppercase small fw-semibold text-secondary">Control</div>
            <div class="card-body">
              <div id="selected" class="text-secondary mb-3">No node selected</div>
              <div class="d-flex flex-wrap gap-2">
                <button id="refresh" class="btn btn-outline-secondary">Refresh</button>
                <button id="start" class="btn btn-primary" disabled>Start</button>
                <button id="stop" class="btn btn-danger" disabled>Stop</button>
              </div>
              <div id="message" class="text-secondary small mt-3"></div>
            </div>
          </section>
          <section class="card">
            <div class="card-header text-uppercase small fw-semibold text-secondary">Settings</div>
            <div class="card-body">
              <div class="row g-3">
                <div class="col-6 col-xl-3">
                  <label class="form-label" for="interval_seconds">Interval seconds</label>
                  <input id="interval_seconds" class="form-control" type="number" min="1">
                </div>
                <div class="col-6 col-xl-3">
                  <label class="form-label" for="width">Width</label>
                  <input id="width" class="form-control" type="number" min="1">
                </div>
                <div class="col-6 col-xl-3">
                  <label class="form-label" for="height">Height</label>
                  <input id="height" class="form-control" type="number" min="1">
                </div>
                <div class="col-6 col-xl-3">
                  <label class="form-label" for="format">Format</label>
                  <input id="format" class="form-control">
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <div class="form-check mt-xl-4">
                    <input id="day_auto_exposure" class="form-check-input" type="checkbox">
                    <label class="form-check-label" for="day_auto_exposure">Day auto exposure</label>
                  </div>
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <label class="form-label" for="day_exposure_ms">Day exposure ms</label>
                  <input id="day_exposure_ms" class="form-control" type="number" min="1">
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <div class="form-check mt-xl-4">
                    <input id="day_auto_gain" class="form-check-input" type="checkbox">
                    <label class="form-check-label" for="day_auto_gain">Day auto gain</label>
                  </div>
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <label class="form-label" for="day_gain">Day gain</label>
                  <input id="day_gain" class="form-control" type="number" step="0.1" min="0">
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <div class="form-check mt-xl-4">
                    <input id="night_auto_exposure" class="form-check-input" type="checkbox">
                    <label class="form-check-label" for="night_auto_exposure">Night auto exposure</label>
                  </div>
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <label class="form-label" for="night_exposure_ms">Night exposure ms</label>
                  <input id="night_exposure_ms" class="form-control" type="number" min="1">
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <div class="form-check mt-xl-4">
                    <input id="night_auto_gain" class="form-check-input" type="checkbox">
                    <label class="form-check-label" for="night_auto_gain">Night auto gain</label>
                  </div>
                </div>
                <div class="col-12 col-md-6 col-xl-3">
                  <label class="form-label" for="night_gain">Night gain</label>
                  <input id="night_gain" class="form-control" type="number" step="0.1" min="0">
                </div>
              </div>
              <button id="save" class="btn btn-primary mt-3" disabled>Save Settings</button>
            </div>
          </section>
          <section class="card preview">
            <div class="card-header text-uppercase small fw-semibold text-secondary">Latest Capture</div>
            <div class="card-body">
              <div id="latestMeta" class="text-secondary small mb-2">No capture loaded</div>
              <img id="latestImage" class="img-fluid rounded border" alt="Latest capture" hidden>
            </div>
          </section>
        </div>
      </div>
    </div>
  </main>
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
        const nodeColumn = document.createElement("div");
        nodeColumn.className = "col-12";
        const button = document.createElement("button");
        button.className = "node btn btn-outline-secondary w-100 p-3" + (node.node_id === selectedNodeId ? " active" : "");
        button.innerHTML = `
          <div class="fw-semibold">${node.node_id}</div>
          <span class="badge ${node.online ? "text-bg-success" : "text-bg-danger"}">${node.online ? "online" : "offline"}</span>
          <div class="small text-secondary mt-1">${node.last_message_type || "no messages yet"}</div>
          ${node.online ? "" : "<div class=\\"small text-secondary\\">Click to select, delete below</div>"}
        `;
        button.onclick = () => selectNode(node.node_id);
        nodeColumn.appendChild(button);
        container.appendChild(nodeColumn);

        if (!node.online) {
          const deleteColumn = document.createElement("div");
          deleteColumn.className = "col-12";
          const deleteButton = document.createElement("button");
          deleteButton.className = "btn btn-outline-danger btn-sm w-100";
          deleteButton.textContent = `Delete ${node.node_id}`;
          deleteButton.onclick = () => deleteNode(node.node_id);
          deleteColumn.appendChild(deleteButton);
          container.appendChild(deleteColumn);
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

    async function refreshDashboard() {
      await loadNodes();

      if (selectedNodeId) {
        await Promise.all([loadSettings(), loadLatest()]);
      }
    }

    document.getElementById("refresh").onclick = () => refreshDashboard().catch(error => setMessage(error.message));
    document.getElementById("save").onclick = () => saveSettings().catch(error => setMessage(error.message));
    document.getElementById("start").onclick = () => startCapture().catch(error => setMessage(error.message));
    document.getElementById("stop").onclick = () => stopCapture().catch(error => setMessage(error.message));

    refreshDashboard().catch(error => setMessage(error.message));
    setInterval(() => {
      refreshDashboard().catch(() => {});
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


@app.get("/api/storage")
async def storage_stats():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(settings.data_dir)
    captures_bytes = directory_size(settings.captures_dir)
    thumbnails_bytes = directory_size(settings.thumbnails_dir)
    database_bytes = settings.database_path.stat().st_size if settings.database_path.exists() else 0
    data_bytes = directory_size(settings.data_dir)

    return {
        "data_dir": str(settings.data_dir),
        "captures_dir": str(settings.captures_dir),
        "thumbnails_dir": str(settings.thumbnails_dir),
        "database_path": str(settings.database_path),
        "data_bytes": data_bytes,
        "captures_bytes": captures_bytes,
        "thumbnails_bytes": thumbnails_bytes,
        "database_bytes": database_bytes,
        "other_data_bytes": max(0, data_bytes - captures_bytes - thumbnails_bytes - database_bytes),
        "disk_total_bytes": usage.total,
        "disk_used_bytes": usage.used,
        "disk_free_bytes": usage.free,
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

    await connections.broadcast_dashboard(
        {
            "type": "node.deleted",
            "node_id": node_id,
        }
    )

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


class OverlayEntity(BaseModel):
    id: str
    type: str
    label: str | None = None
    enabled: bool = True
    x: float = 0
    y: float = 0
    anchor: str = "top-left"
    font_size: int = 28
    color: str = "#ffffff"
    background: str = "#000000"
    background_opacity: float = 0.35
    text: str | None = None


class NodeOverlaySettingsUpdate(BaseModel):
    enabled: bool | None = None
    entities: list[OverlayEntity] | None = None


def safe_path_part(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in ["-", "_", "."] else "_"
        for character in value
    ).strip("._") or "unknown"


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0

    total = 0

    for file_path in path.rglob("*"):
        if file_path.is_file():
            try:
                total += file_path.stat().st_size
            except OSError:
                logger.warning("storage.file_size_failed", path=str(file_path))

    return total


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


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("datetime.invalid", value=value)
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed


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
        "format": camera_settings.format or "jpg",
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
        "capture_enabled": camera_settings.capture_enabled,
        "current_sequence_id": camera_settings.current_sequence_id,
        "updated_at": camera_settings.updated_at.isoformat() if camera_settings.updated_at else None,
    }


def overlay_settings_to_dict(overlay_settings) -> dict:
    return {
        "node_id": overlay_settings.node_id,
        "enabled": overlay_settings.enabled,
        "entities": overlay_settings.entities or [],
        "updated_at": overlay_settings.updated_at.isoformat() if overlay_settings.updated_at else None,
    }


def environment_to_dict(environment) -> dict:
    return {
        "node_id": environment.node_id,
        "sensor": environment.sensor_driver,
        "temperature_c": environment.temperature_c,
        "humidity_percent": environment.humidity_percent,
        "pressure_hpa": environment.pressure_hpa,
        "dew_point_c": environment.dew_point_c,
        "captured_at": environment.captured_at.isoformat() if environment.captured_at else None,
        "updated_at": environment.updated_at.isoformat() if environment.updated_at else None,
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
        "format": camera_settings.format or "jpg",
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
        "capture_enabled": camera_settings.capture_enabled,
        "sequence_id": camera_settings.current_sequence_id,
    }


def capture_record_from_path(file_path: Path) -> dict:
    relative_path = file_path.relative_to(settings.captures_dir)
    node_id = relative_path.parts[0]
    archive_date = relative_path.parts[1]
    period = relative_path.parts[2]
    original_path = settings.originals_dir / relative_path
    thumbnail_path = settings.thumbnails_dir / relative_path

    return {
        "node_id": node_id,
        "archive_date": archive_date,
        "period": period,
        "filename": file_path.name,
        "path": str(file_path),
        "original_available": original_path.is_file(),
        "thumbnail_available": thumbnail_path.is_file(),
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


def create_thumbnail(source_path: Path, thumbnail_path: Path, max_size: tuple[int, int] = (420, 236)) -> None:
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as image:
        image.thumbnail(max_size)
        image.convert("RGB").save(thumbnail_path, format="JPEG", quality=82, optimize=True)


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
    await connections.broadcast_dashboard(
        {
            "type": "settings.updated",
            "node_id": node_id,
            "settings": settings_payload,
            "node_notified": sent,
        }
    )

    return {
        "settings": settings_payload,
        "node_notified": sent,
    }


@app.get("/api/nodes/{node_id}/overlays")
async def get_node_overlays(node_id: str, db: Session = Depends(get_db_session)):
    repo = NodeOverlaySettingsRepository(db)
    overlay_settings = repo.get_or_create(node_id)
    return overlay_settings_to_dict(overlay_settings)


@app.put("/api/nodes/{node_id}/overlays")
async def update_node_overlays(
    node_id: str,
    request: NodeOverlaySettingsUpdate,
    db: Session = Depends(get_db_session),
):
    repo = NodeOverlaySettingsRepository(db)
    values = request.model_dump(exclude_none=True)

    if "entities" in values:
        values["entities"] = [
            entity.model_dump() if hasattr(entity, "model_dump") else entity
            for entity in request.entities or []
        ]

    overlay_settings = repo.update(node_id, values)
    payload = overlay_settings_to_dict(overlay_settings)
    await connections.broadcast_dashboard(
        {
            "type": "overlay.updated",
            "node_id": node_id,
            "overlays": payload,
        }
    )

    return payload


@app.get("/api/nodes/{node_id}/environment")
async def get_node_environment(node_id: str, db: Session = Depends(get_db_session)):
    environment = NodeEnvironmentRepository(db).get(node_id)

    if environment is None:
        raise HTTPException(status_code=404, detail="No environment telemetry for node")

    return environment_to_dict(environment)


@app.post("/api/nodes/{node_id}/sequence/start")
async def start_sequence(
    node_id: str,
    request: SequenceStartRequest | None = None,
    db: Session = Depends(get_db_session),
):
    sequence_id = f"seq_{uuid4().hex}"
    settings_repo = NodeCameraSettingsRepository(db)
    camera_settings = settings_repo.update(
        node_id,
        {
            "capture_enabled": True,
            "current_sequence_id": sequence_id,
        },
    )
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
    await connections.broadcast_dashboard(
        {
            "type": "capture.state.updated",
            "node_id": node_id,
            "capture_enabled": True,
            "sequence_id": sequence_id,
            "sent": sent,
        }
    )

    if not sent:
        return {
            "status": "queued",
            "reason": "node_not_connected",
            "node_id": node_id,
            "sequence_id": sequence_id,
            "message": message,
        }

    return {
        "status": "sent",
        "node_id": node_id,
        "sequence_id": sequence_id,
        "message": message,
    }


@app.post("/api/nodes/{node_id}/sequence/stop")
async def stop_sequence(
    node_id: str,
    request: SequenceStopRequest | None = None,
    db: Session = Depends(get_db_session),
):
    settings_repo = NodeCameraSettingsRepository(db)
    existing_settings = settings_repo.get_or_create(node_id)
    sequence_id = request.sequence_id if request else existing_settings.current_sequence_id
    settings_repo.update(
        node_id,
        {
            "capture_enabled": False,
            "current_sequence_id": None,
        },
    )
    message = {
        "type": "sequence.stop",
        "sequence_id": sequence_id,
    }

    sent = await connections.send_to_node(node_id, message)
    await connections.broadcast_dashboard(
        {
            "type": "capture.state.updated",
            "node_id": node_id,
            "capture_enabled": False,
            "sequence_id": sequence_id,
            "sent": sent,
        }
    )

    if not sent:
        return {
            "status": "queued",
            "reason": "node_not_connected",
            "node_id": node_id,
            "sequence_id": sequence_id,
            "message": message,
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
    raw: bool = False,
    thumb: bool = False,
):
    safe_node_id = safe_path_part(node_id)
    safe_archive_date = safe_path_part(archive_date)
    safe_period = safe_path_part(period)
    safe_filename = safe_path_part(filename)
    rendered_file_path = settings.captures_dir / safe_node_id / safe_archive_date / safe_period / safe_filename
    original_file_path = settings.originals_dir / safe_node_id / safe_archive_date / safe_period / safe_filename
    thumbnail_file_path = settings.thumbnails_dir / safe_node_id / safe_archive_date / safe_period / safe_filename

    if thumb and thumbnail_file_path.is_file():
        file_path = thumbnail_file_path
        root_dir = settings.thumbnails_dir
    elif thumb and rendered_file_path.is_file():
        create_thumbnail(rendered_file_path, thumbnail_file_path)
        file_path = thumbnail_file_path
        root_dir = settings.thumbnails_dir
    elif raw and original_file_path.is_file():
        file_path = original_file_path
        root_dir = settings.originals_dir
    else:
        file_path = rendered_file_path
        root_dir = settings.captures_dir

    try:
        resolved_root_dir = root_dir.resolve()
        resolved_file_path = file_path.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Capture not found")

    if not resolved_file_path.is_relative_to(resolved_root_dir):
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
    db: Session = Depends(get_db_session),
):
    try:
        parsed_metadata = json.loads(metadata)
    except json.JSONDecodeError:
        parsed_metadata = {"raw": metadata}

    upload_node_id = safe_path_part(node_id)
    upload_format = safe_path_part(format.lower())
    original_name = safe_path_part(Path(file.filename or f"capture.{upload_format}").name)
    capture_id = f"cap_{uuid4().hex}"
    captured_at = parse_capture_datetime(parsed_metadata)
    archive_date, period = archive_period(captured_at)
    filename = f"{capture_id}_{original_name}"
    capture_dir = settings.captures_dir / upload_node_id / archive_date / period
    output_path = capture_dir / filename
    original_dir = settings.originals_dir / upload_node_id / archive_date / period
    original_path = original_dir / filename
    thumbnail_dir = settings.thumbnails_dir / upload_node_id / archive_date / period
    thumbnail_path = thumbnail_dir / filename

    capture_dir.mkdir(parents=True, exist_ok=True)
    original_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_dir.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as output_file:
        shutil.copyfileobj(file.file, output_file)

    shutil.copy2(output_path, original_path)

    overlay_settings = NodeOverlaySettingsRepository(db).get_or_create(upload_node_id)
    apply_overlays_to_image(
        output_path,
        overlay_settings,
        node_id=node_id,
        captured_at=captured_at,
        period=period,
        timezone_name=settings.timezone,
    )
    create_thumbnail(output_path, thumbnail_path)

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

    capture_record = capture_record_from_path(output_path)
    await connections.broadcast_dashboard(
        {
            "type": "capture.uploaded",
            "node_id": node_id,
            "capture": capture_record,
        }
    )

    return {
        "status": "stored",
        "capture_id": capture_id,
        "node_id": node_id,
        "sequence_id": sequence_id,
        "path": capture_record["path"],
        "filename": capture_record["filename"],
        "archive_date": capture_record["archive_date"],
        "period": capture_record["period"],
        "format": upload_format,
        "width": width,
        "height": height,
        "metadata": parsed_metadata,
        "size_bytes": capture_record["size_bytes"],
    }


@app.websocket("/ws/nodes/{node_id}")
async def node_websocket(websocket: WebSocket, node_id: str):
    await connections.connect(node_id, websocket)

    db = SessionLocal()
    repo = NodeRepository(db)

    try:
        repo.mark_online(node_id)
        logger.info("node.connected", node_id=node_id)
        await connections.broadcast_dashboard(
            {
                "type": "node.updated",
                "node_id": node_id,
                "online": True,
            }
        )

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
                await connections.broadcast_dashboard(
                    {
                        "type": "node.updated",
                        "node_id": node_id,
                        "online": True,
                        "message_type": message_type,
                    }
                )

            elif message_type == "environment.telemetry":
                environment = NodeEnvironmentRepository(db).upsert(
                    node_id=node_id,
                    sensor_driver=message.get("sensor"),
                    temperature_c=float(message["temperature_c"]),
                    humidity_percent=float(message["humidity_percent"]),
                    pressure_hpa=(
                        float(message["pressure_hpa"])
                        if message.get("pressure_hpa") is not None
                        else None
                    ),
                    dew_point_c=(
                        float(message["dew_point_c"])
                        if message.get("dew_point_c") is not None
                        else None
                    ),
                    captured_at=parse_iso_datetime(message.get("captured_at")),
                )
                await connections.broadcast_dashboard(
                    {
                        "type": "environment.updated",
                        "node_id": node_id,
                        "telemetry": environment_to_dict(environment),
                    }
                )

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
        await connections.broadcast_dashboard(
            {
                "type": "node.updated",
                "node_id": node_id,
                "online": False,
            }
        )

    finally:
        db.close()


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await connections.connect_dashboard(websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        connections.disconnect_dashboard(websocket)


@app.get("/{frontend_path:path}", include_in_schema=False)
async def frontend_route(frontend_path: str):
    first_segment = frontend_path.split("/", 1)[0]

    if first_segment not in {"monitor", "captures", "overlays", "settings", "nodes"}:
        raise HTTPException(status_code=404, detail="Not found")

    index_path = settings.frontend_dist_dir / "index.html"

    if index_path.exists():
        return FileResponse(index_path)

    return await frontend_app()


