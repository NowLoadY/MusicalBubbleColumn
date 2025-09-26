"""
Three.js渲染器实现 - 为Web端提供高性能渲染

这个模块实现了基于Three.js的Web渲染引擎，通过WebSocket
将渲染数据发送到前端，实现：
- 高性能WebGL渲染
- 跨平台Web支持
- 实时交互
- 移动设备兼容

使用方法：
1. 启动WebSocket服务器
2. 在浏览器中打开Three.js前端页面
3. 使用ThreeJSRenderer替换MatplotlibRenderer
"""

import json
import asyncio
import websockets
import threading
from typing import List, Dict, Any, Set
from MBC_RenderInterface import RenderEngineInterface, RenderableParticle, CameraState, RenderSettings
import logging


class ThreeJSRenderer(RenderEngineInterface):
    """
    基于Three.js的Web渲染引擎
    
    通过WebSocket协议将渲染数据实时发送到Three.js前端，
    实现高性能的Web端3D渲染。
    """
    
    def __init__(self, websocket_port: int = 8765, host: str = "localhost"):
        """
        初始化Three.js渲染器
        
        Args:
            websocket_port: WebSocket服务器端口
            host: 服务器主机地址
        """
        self.port = websocket_port
        self.host = host
        self.settings = None
        self.is_initialized = False
        
        # WebSocket相关
        self.websocket_server = None
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server_thread = None
        self.loop = None
        
        # 性能优化
        self.frame_count = 0
        self.max_particles_per_frame = 10000
        
        # 设置日志
        self.logger = logging.getLogger('ThreeJSRenderer')
    
    def initialize(self, settings: RenderSettings) -> bool:
        """初始化Three.js渲染系统和WebSocket服务器"""
        try:
            self.settings = settings
            
            # 启动WebSocket服务器
            self._start_websocket_server()
            
            self.is_initialized = True
            self.logger.info(f"Three.js渲染器初始化成功，WebSocket服务器运行在 ws://{self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Three.js渲染器初始化失败: {e}")
            return False
    
    def _start_websocket_server(self):
        """启动WebSocket服务器"""
        def run_server():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            start_server = websockets.serve(
                self._handle_websocket_connection,
                self.host,
                self.port
            )
            
            self.loop.run_until_complete(start_server)
            self.loop.run_forever()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
    
    async def _handle_websocket_connection(self, websocket, path):
        """处理WebSocket客户端连接"""
        self.connected_clients.add(websocket)
        self.logger.info(f"新的Three.js客户端连接: {websocket.remote_address}")
        
        try:
            # 发送初始设置
            if self.settings:
                await self._send_settings_to_client(websocket)
            
            # 保持连接
            async for message in websocket:
                # 处理客户端消息（相机控制、用户交互等）
                await self._handle_client_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.discard(websocket)
            self.logger.info(f"Three.js客户端断开连接: {websocket.remote_address}")
    
    async def _send_settings_to_client(self, websocket):
        """发送渲染设置到客户端"""
        settings_data = {
            "type": "settings",
            "data": {
                "background_color": self.settings.background_color,
                "antialiasing": self.settings.antialiasing,
                "particle_quality": self.settings.particle_quality,
                "max_particles": self.settings.max_particles
            }
        }
        await websocket.send(json.dumps(settings_data))
    
    async def _handle_client_message(self, websocket, message):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "camera_update":
                # 客户端相机更新（可用于同步）
                pass
            elif msg_type == "interaction":
                # 用户交互事件
                pass
                
        except json.JSONDecodeError:
            self.logger.warning(f"收到无效的JSON消息: {message}")
    
    def render_frame(self, particles: List[RenderableParticle], 
                     camera: CameraState) -> bool:
        """渲染一帧并发送到Three.js客户端"""
        if not self.is_initialized or not self.connected_clients:
            return True  # 没有客户端连接时静默成功
        
        try:
            # 性能优化：限制粒子数量
            if len(particles) > self.max_particles_per_frame:
                particles = particles[:self.max_particles_per_frame]
            
            # 准备渲染数据
            render_data = {
                "type": "render_frame",
                "frame_id": self.frame_count,
                "data": {
                    "particles": self._serialize_particles(particles),
                    "camera": self._serialize_camera(camera),
                    "timestamp": self.frame_count * 16.67  # 假设60fps
                }
            }
            
            # 异步发送到所有连接的客户端
            asyncio.run_coroutine_threadsafe(
                self._broadcast_to_clients(render_data),
                self.loop
            )
            
            self.frame_count += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Three.js渲染失败: {e}")
            return False
    
    def _serialize_particles(self, particles: List[RenderableParticle]) -> List[Dict]:
        """将粒子对象序列化为JSON数据"""
        return [
            {
                "id": p.object_id or i,
                "position": p.position,
                "size": p.size,
                "color": p.color,
                "type": p.particle_type,
                "opacity": p.opacity,
                "blend_factor": p.blend_factor
            }
            for i, p in enumerate(particles)
        ]
    
    def _serialize_camera(self, camera: CameraState) -> Dict:
        """将相机状态序列化为JSON数据"""
        return {
            "position": camera.position,
            "target": camera.target,
            "up": camera.up,
            "elev": camera.elev,
            "azim": camera.azim,
            "x_range": camera.x_range,
            "y_range": camera.y_range,
            "z_range": camera.z_range
        }
    
    async def _broadcast_to_clients(self, data: Dict):
        """广播数据到所有连接的客户端"""
        if not self.connected_clients:
            return
        
        message = json.dumps(data)
        disconnected_clients = []
        
        for client in self.connected_clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.append(client)
        
        # 清理断开的连接
        for client in disconnected_clients:
            self.connected_clients.discard(client)
    
    def set_camera(self, camera: CameraState):
        """设置相机状态（发送到客户端）"""
        if not self.connected_clients:
            return
        
        camera_data = {
            "type": "camera_update",
            "data": self._serialize_camera(camera)
        }
        
        asyncio.run_coroutine_threadsafe(
            self._broadcast_to_clients(camera_data),
            self.loop
        )
    
    def clear_scene(self):
        """清空Three.js场景"""
        if not self.connected_clients:
            return
        
        clear_data = {
            "type": "clear_scene",
            "data": {}
        }
        
        asyncio.run_coroutine_threadsafe(
            self._broadcast_to_clients(clear_data),
            self.loop
        )
    
    def update_settings(self, settings: RenderSettings):
        """更新渲染设置并发送到客户端"""
        self.settings = settings
        
        if not self.connected_clients:
            return
        
        settings_data = {
            "type": "settings_update",
            "data": {
                "background_color": settings.background_color,
                "antialiasing": settings.antialiasing,
                "particle_quality": settings.particle_quality,
                "max_particles": settings.max_particles
            }
        }
        
        asyncio.run_coroutine_threadsafe(
            self._broadcast_to_clients(settings_data),
            self.loop
        )
    
    def cleanup(self):
        """清理Three.js渲染器资源"""
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        if self.server_thread:
            self.server_thread.join(timeout=1.0)
        
        self.connected_clients.clear()
        self.is_initialized = False
        self.logger.info("Three.js渲染器清理完成")
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取Three.js渲染器信息"""
        return {
            "name": "Three.js WebGL Renderer",
            "version": "1.0.0",
            "backend": "three.js",
            "capabilities": [
                "webgl_rendering",
                "real_time_streaming",
                "web_compatible",
                "mobile_support",
                "websocket_communication",
                "interactive_camera",
                "high_performance"
            ],
            "performance": "high",
            "platform": "web",
            "websocket_url": f"ws://{self.host}:{self.port}",
            "connected_clients": len(self.connected_clients)
        }


# 辅助函数：简化Three.js渲染器的使用
def create_threejs_renderer(port: int = 8765) -> ThreeJSRenderer:
    """
    创建Three.js渲染器的便捷函数
    
    Args:
        port: WebSocket服务器端口
        
    Returns:
        ThreeJSRenderer: 配置好的Three.js渲染器实例
    """
    renderer = ThreeJSRenderer(websocket_port=port)
    
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    return renderer


# 示例前端HTML模板
THREE_JS_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Musical Bubble Column - Three.js</title>
    <style>
        body { margin: 0; padding: 0; background: #000; overflow: hidden; }
        canvas { display: block; }
        #info { position: absolute; top: 10px; left: 10px; color: white; font-family: Arial; }
    </style>
</head>
<body>
    <div id="info">
        <div>Musical Bubble Column</div>
        <div id="status">Connecting...</div>
        <div id="fps">FPS: 0</div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // Three.js场景设置
        let scene, camera, renderer, particles = [];
        let ws;
        
        // 初始化Three.js
        function init() {
            scene = new THREE.Scene();
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.body.appendChild(renderer.domElement);
            
            // 连接WebSocket
            connectWebSocket();
            
            // 开始渲染循环
            animate();
        }
        
        // WebSocket连接
        function connectWebSocket() {
            ws = new WebSocket('ws://localhost:8765');
            
            ws.onopen = function() {
                document.getElementById('status').textContent = 'Connected';
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
            
            ws.onclose = function() {
                document.getElementById('status').textContent = 'Disconnected';
                setTimeout(connectWebSocket, 1000); // 重连
            };
        }
        
        // 处理服务器消息
        function handleMessage(data) {
            switch(data.type) {
                case 'render_frame':
                    updateParticles(data.data.particles);
                    updateCamera(data.data.camera);
                    break;
                case 'settings_update':
                    updateSettings(data.data);
                    break;
                case 'clear_scene':
                    clearScene();
                    break;
            }
        }
        
        // 更新粒子
        function updateParticles(particleData) {
            // 清理旧粒子
            particles.forEach(p => scene.remove(p));
            particles = [];
            
            // 创建新粒子
            particleData.forEach(p => {
                const geometry = new THREE.SphereGeometry(p.size * 0.01);
                const material = new THREE.MeshBasicMaterial({
                    color: new THREE.Color(p.color[0], p.color[1], p.color[2]),
                    opacity: p.color[3],
                    transparent: true
                });
                
                const particle = new THREE.Mesh(geometry, material);
                particle.position.set(p.position[0], p.position[1], p.position[2]);
                
                scene.add(particle);
                particles.push(particle);
            });
        }
        
        // 更新相机
        function updateCamera(cameraData) {
            // 简化的相机控制
            camera.position.set(0, 0, 100);
            camera.lookAt(0, 0, 0);
        }
        
        // 更新设置
        function updateSettings(settings) {
            scene.background = new THREE.Color(
                settings.background_color[0],
                settings.background_color[1], 
                settings.background_color[2]
            );
        }
        
        // 清空场景
        function clearScene() {
            particles.forEach(p => scene.remove(p));
            particles = [];
        }
        
        // 渲染循环
        let lastTime = 0;
        let frameCount = 0;
        
        function animate() {
            requestAnimationFrame(animate);
            
            // FPS计算
            const currentTime = performance.now();
            frameCount++;
            if (currentTime - lastTime >= 1000) {
                document.getElementById('fps').textContent = 'FPS: ' + Math.round(frameCount * 1000 / (currentTime - lastTime));
                frameCount = 0;
                lastTime = currentTime;
            }
            
            renderer.render(scene, camera);
        }
        
        // 窗口大小调整
        window.addEventListener('resize', function() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // 启动
        init();
    </script>
</body>
</html>
"""
