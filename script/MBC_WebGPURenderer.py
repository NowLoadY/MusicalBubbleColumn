"""WebGPU renderer bridge.

The Python side owns simulation and audio timing. The browser owns rendering.
Frames are sent as compact binary WebSocket messages:

    uint32 magic, uint32 version, uint32 frame_id, uint32 particle_count
    float32 elev, azim, x_min, x_max, y_min, y_max, z_min, z_max
    particle_count * 10 float32 values

Particle layout:
    x, y, z, size, r, g, b, a, type, blend_factor
"""

import asyncio
import json
import logging
from collections import deque
import struct
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Set

import numpy as np
import websockets

from MBC_RenderInterface import CameraState, RenderSettings


FRAME_MAGIC = 0x3143424D
FRAME_VERSION = 1


class _FrontendHandler(SimpleHTTPRequestHandler):
    frontend_path: Path

    def translate_path(self, path):
        if path in ("", "/", "/webgpu_frontend.html"):
            return str(self.frontend_path)
        return str(self.frontend_path)

    def log_message(self, format, *args):
        return


class WebGPURenderer:
    def __init__(
        self,
        websocket_port: int = 0,
        http_port: int = 0,
        host: str = "127.0.0.1",
        open_browser: bool = True,
    ):
        self.websocket_port = websocket_port
        self.http_port = http_port
        self.host = host
        self.open_browser = open_browser
        self.settings = None
        self.is_initialized = False

        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.websocket_server = None
        self.http_server = None
        self.server_thread = None
        self.http_thread = None
        self.loop = None
        self.pending_send = None
        self.websocket_ready = threading.Event()
        self.websocket_error = None

        self.frame_count = 0
        self.logger = logging.getLogger("WebGPURenderer")
        app_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        self.frontend_path = app_root / "webgpu_frontend.html"
        self.control_state = {
            "target_elev": None,
            "target_azim_speed": None,
        }
        self.commands = deque()

    def initialize(self, settings: RenderSettings) -> bool:
        self.settings = settings
        self._start_http_server()
        self._start_websocket_server()
        self.is_initialized = True

        url = f"http://{self.host}:{self.http_port}/webgpu_frontend.html?ws={self.websocket_port}"
        self.logger.info("WebGPU renderer available at %s", url)
        if self.open_browser:
            webbrowser.open(url)
        return True

    def _start_http_server(self):
        _FrontendHandler.frontend_path = self.frontend_path
        self.http_server = ThreadingHTTPServer((self.host, self.http_port), _FrontendHandler)
        self.http_port = self.http_server.server_address[1]
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()

    def _start_websocket_server(self):
        self.websocket_ready.clear()
        self.websocket_error = None

        def run_server():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            async def start_server():
                self.websocket_server = await websockets.serve(
                    self._handle_websocket_connection,
                    self.host,
                    self.websocket_port,
                    max_size=None,
                    compression=None,
                )
                sockets = getattr(self.websocket_server, "sockets", None)
                if sockets:
                    self.websocket_port = sockets[0].getsockname()[1]

            try:
                self.loop.run_until_complete(start_server())
                self.websocket_ready.set()
                self.loop.run_forever()
            except Exception as exc:
                self.websocket_error = exc
                self.websocket_ready.set()
            finally:
                self.loop.close()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        if not self.websocket_ready.wait(timeout=3.0):
            raise RuntimeError("Timed out while starting WebGPU WebSocket server.")
        if self.websocket_error is not None:
            raise RuntimeError("Could not start WebGPU WebSocket server.") from self.websocket_error

    async def _handle_websocket_connection(self, websocket, path=None):
        self.connected_clients.add(websocket)
        self.logger.info("WebGPU client connected: %s", websocket.remote_address)
        try:
            await self._send_settings_to_client(websocket)
            async for message in websocket:
                self._handle_client_message(message)
        finally:
            self.connected_clients.discard(websocket)
            self.logger.info("WebGPU client disconnected: %s", websocket.remote_address)

    async def _send_settings_to_client(self, websocket):
        if self.settings is None:
            return
        await websocket.send(
            json.dumps(
                {
                    "type": "settings",
                    "background_color": self.settings.background_color,
                    "max_particles": self.settings.max_particles,
                    "visualize_piano": self.settings.visualize_piano,
                }
            )
        )

    def _handle_client_message(self, message):
        if not isinstance(message, str):
            return
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        if data.get("type") == "ready":
            self.logger.info("WebGPU frontend ready")
        elif data.get("type") == "controls":
            self.control_state.update(
                {
                    "target_elev": data.get("target_elev"),
                    "target_azim_speed": data.get("target_azim_speed"),
                }
            )
        elif data.get("type") == "command":
            command = data.get("command")
            if command:
                self.commands.append(command)

    def get_control_state(self) -> Dict:
        return dict(self.control_state)

    def pop_commands(self):
        commands = list(self.commands)
        self.commands.clear()
        return commands

    def render_frame(self, particles: np.ndarray, camera: CameraState) -> bool:
        if not self.is_initialized or not self.connected_clients or self.loop is None:
            return True
        if self.pending_send is not None and not self.pending_send.done():
            return True

        payload = self._pack_frame(particles, camera)
        self.pending_send = asyncio.run_coroutine_threadsafe(
            self._broadcast_binary(payload),
            self.loop,
        )
        self.frame_count += 1
        return True

    def _pack_frame(self, particles: np.ndarray, camera: CameraState) -> bytes:
        if particles.size == 0:
            particle_bytes = b""
            particle_count = 0
        else:
            contiguous_particles = np.ascontiguousarray(particles, dtype="<f4")
            particle_count = contiguous_particles.shape[0]
            particle_bytes = contiguous_particles.tobytes()

        header = struct.pack(
            "<IIII",
            FRAME_MAGIC,
            FRAME_VERSION,
            self.frame_count,
            particle_count,
        )
        camera_data = np.array(
            [
                camera.elev,
                camera.azim,
                camera.x_range[0],
                camera.x_range[1],
                camera.y_range[0],
                camera.y_range[1],
                camera.z_range[0],
                camera.z_range[1],
            ],
            dtype="<f4",
        )
        return header + camera_data.tobytes() + particle_bytes

    async def _broadcast_binary(self, payload: bytes):
        if not self.connected_clients:
            return
        disconnected = []
        for client in self.connected_clients:
            try:
                await client.send(payload)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client)
        for client in disconnected:
            self.connected_clients.discard(client)

    def set_camera(self, camera: CameraState):
        if not self.connected_clients or self.loop is None:
            return
        message = json.dumps(
            {
                "type": "camera",
                "elev": camera.elev,
                "azim": camera.azim,
                "x_range": camera.x_range,
                "y_range": camera.y_range,
                "z_range": camera.z_range,
            }
        )
        asyncio.run_coroutine_threadsafe(self._broadcast_text(message), self.loop)

    async def _broadcast_text(self, message: str):
        for client in list(self.connected_clients):
            await client.send(message)

    async def _close_websocket_server(self):
        if self.websocket_server is None:
            return
        self.websocket_server.close()
        await self.websocket_server.wait_closed()
        self.websocket_server = None

    def clear_scene(self):
        if not self.connected_clients or self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._broadcast_text(json.dumps({"type": "clear"})),
            self.loop,
        )

    def update_settings(self, settings: RenderSettings):
        self.settings = settings
        if not self.connected_clients or self.loop is None:
            return
        message = json.dumps(
            {
                "type": "settings",
                "background_color": settings.background_color,
                "max_particles": settings.max_particles,
                "visualize_piano": settings.visualize_piano,
            }
        )
        asyncio.run_coroutine_threadsafe(self._broadcast_text(message), self.loop)

    def update_piano(self, key_activation: np.ndarray, volumes: np.ndarray):
        if not self.connected_clients or self.loop is None:
            return
        message = json.dumps(
            {
                "type": "piano",
                "active": np.asarray(key_activation, dtype=np.uint8).tolist(),
                "volumes": np.asarray(volumes, dtype=np.uint8).tolist(),
            }
        )
        asyncio.run_coroutine_threadsafe(self._broadcast_text(message), self.loop)

    def cleanup(self):
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
        if self.loop:
            if self.websocket_server:
                future = asyncio.run_coroutine_threadsafe(self._close_websocket_server(), self.loop)
                future.result(timeout=2.0)
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.http_thread:
            self.http_thread.join(timeout=1.0)
        if self.server_thread:
            self.server_thread.join(timeout=1.0)
        self.connected_clients.clear()
        self.is_initialized = False

    def get_engine_info(self) -> Dict:
        return {
            "name": "WebGPU Renderer",
            "version": "2.0.0",
            "backend": "webgpu",
            "websocket_url": f"ws://{self.host}:{self.websocket_port}",
            "frontend_url": f"http://{self.host}:{self.http_port}/webgpu_frontend.html",
            "connected_clients": len(self.connected_clients),
        }
