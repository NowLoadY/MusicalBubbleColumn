"""
渲染引擎抽象接口 - 实现渲染系统的分离和可替换性

这个模块定义了渲染引擎的标准接口，使得可以轻松替换不同的渲染系统：
- Matplotlib（当前实现）
- Three.js（Web渲染）
- WebGL（高性能渲染）
- Unity（游戏引擎）等

设计目标：
1. 完全解耦渲染逻辑与核心业务逻辑
2. 标准化的渲染对象数据结构
3. 支持多种渲染后端
4. 为Three.js等Web技术奠定基础
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import numpy as np


@dataclass
class RenderableParticle:
    """
    标准化的可渲染粒子对象
    
    这个数据结构是渲染引擎无关的，可以被任何渲染系统使用
    """
    # 基础属性
    position: Tuple[float, float, float]  # (x, y, z) 世界坐标
    size: float                          # 粒子大小
    color: Tuple[float, float, float, float]  # RGBA颜色 [0-1]范围
    opacity: float                       # 透明度 [0-1]范围
    
    # 分类属性
    particle_type: str                   # "bubble", "snow", "light", "lampshade"
    object_id: Optional[int] = None      # 唯一标识符（用于动画追踪）
    
    # 渲染属性
    blend_factor: float = 0.0            # 颜色混合因子
    animation_age: float = 0.0           # 动画年龄（用于效果）
    
    # 扩展属性（供特定渲染器使用）
    extra_data: Dict[str, Any] = None    # 额外数据字典


@dataclass 
class CameraState:
    """相机状态配置"""
    position: Tuple[float, float, float]   # 相机位置
    target: Tuple[float, float, float]     # 观察目标
    up: Tuple[float, float, float]         # 向上向量
    elev: float                           # 仰角
    azim: float                           # 方位角
    
    # 视图范围
    x_range: Tuple[float, float]          # x轴范围
    y_range: Tuple[float, float]          # y轴范围  
    z_range: Tuple[float, float]          # z轴范围


@dataclass
class RenderSettings:
    """渲染设置配置"""
    background_color: Tuple[float, float, float, float] = (0.0, 0.0, 60/255, 1.0)
    window_opacity: float = 1.0
    antialiasing: bool = True
    particle_quality: str = "high"  # "low", "medium", "high"
    
    # 性能设置
    max_particles: int = 50000
    enable_animations: bool = True
    frame_rate_limit: int = 60


class RenderEngineInterface(ABC):
    """
    渲染引擎抽象基类
    
    定义了所有渲染引擎必须实现的标准接口，
    确保不同渲染系统间的可替换性。
    """
    
    @abstractmethod
    def initialize(self, settings: RenderSettings) -> bool:
        """
        初始化渲染引擎
        
        Args:
            settings: 渲染设置
            
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    def render_frame(self, particles: List[RenderableParticle], 
                     camera: CameraState) -> bool:
        """
        渲染一帧
        
        Args:
            particles: 要渲染的粒子列表
            camera: 相机状态
            
        Returns:
            bool: 渲染是否成功
        """
        pass
    
    @abstractmethod
    def set_camera(self, camera: CameraState):
        """
        设置相机状态
        
        Args:
            camera: 新的相机状态
        """
        pass
    
    @abstractmethod
    def clear_scene(self):
        """清空场景中的所有对象"""
        pass
    
    @abstractmethod
    def update_settings(self, settings: RenderSettings):
        """
        更新渲染设置
        
        Args:
            settings: 新的渲染设置
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """清理资源"""
        pass
    
    def get_engine_info(self) -> Dict[str, Any]:
        """
        获取渲染引擎信息
        
        Returns:
            Dict[str, Any]: 引擎信息
        """
        return {
            "name": "Unknown Render Engine",
            "version": "1.0.0",
            "backend": "unknown",
            "capabilities": []
        }


class MatplotlibRenderer(RenderEngineInterface):
    """
    基于Matplotlib的渲染引擎实现
    
    包装现有的matplotlib渲染逻辑，保持向后兼容性
    """
    
    def __init__(self):
        """初始化matplotlib渲染器"""
        self.fig = None
        self.ax = None
        self.settings = None
        self.is_initialized = False
        
        # 导入matplotlib相关模块
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        import MBC_njit_func
        
        self.plt = plt
        self.njit_func = MBC_njit_func
    
    def initialize(self, settings: RenderSettings) -> bool:
        """初始化matplotlib渲染系统"""
        try:
            self.settings = settings
            
            # 这里暂时不创建figure，因为需要与现有MBC_Core集成
            # 在update_core_render阶段会传入现有的fig和ax
            self.is_initialized = True
            return True
            
        except Exception as e:
            print(f"Matplotlib渲染器初始化失败: {e}")
            return False
    
    def set_matplotlib_objects(self, fig, ax):
        """
        设置matplotlib对象（用于与现有代码集成）
        
        Args:
            fig: matplotlib figure对象
            ax: matplotlib 3D axes对象
        """
        self.fig = fig
        self.ax = ax
    
    def render_frame(self, particles: List[RenderableParticle], 
                     camera: CameraState) -> bool:
        """使用matplotlib渲染粒子"""
        if not self.is_initialized or self.ax is None:
            return False
            
        try:
            # 清空当前绘图
            self.ax.cla()
            
            if not particles:
                return True
            
            # 转换粒子数据为numpy数组（保持与原有性能）
            positions = np.array([p.position for p in particles])
            sizes = np.array([p.size for p in particles])
            colors = np.array([p.color for p in particles])
            
            if len(positions) > 0:
                # 设置绘图参数
                scatter_kwargs = {
                    'c': colors,
                    'marker': 'o',
                    's': sizes,
                    'alpha': None,  # 使用颜色中的alpha通道
                    'edgecolors': 'none',
                    'antialiased': self.settings.antialiasing if self.settings else True,
                }
                
                # 绘制散点图
                self.ax.scatter(positions[:, 0], positions[:, 1], positions[:, 2], **scatter_kwargs)
            
            # 设置相机
            self._apply_camera_state(camera)
            
            # 隐藏坐标轴（保持原有外观）
            self._hide_axes()
            
            return True
            
        except Exception as e:
            print(f"Matplotlib渲染失败: {e}")
            return False
    
    def set_camera(self, camera: CameraState):
        """设置matplotlib相机"""
        if self.ax:
            self._apply_camera_state(camera)
    
    def _apply_camera_state(self, camera: CameraState):
        """应用相机状态到matplotlib"""
        if self.ax:
            # 设置视图角度
            self.ax.view_init(elev=camera.elev, azim=camera.azim)
            
            # 设置显示范围
            self.ax.set_xlim(camera.x_range)
            self.ax.set_ylim(camera.y_range)
            self.ax.set_zlim(camera.z_range)
            
            self.ax.margins(0)
    
    def _hide_axes(self):
        """隐藏坐标轴（保持原有外观）"""
        if self.ax:
            for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
                axis.pane.fill = False
                axis.set_pane_color((0, 0, 0, 0))
                axis.set_major_formatter(self.plt.NullFormatter())
                axis.set_visible(False)
                axis.line.set_visible(False)
                axis.set_ticks([])
    
    def clear_scene(self):
        """清空matplotlib场景"""
        if self.ax:
            self.ax.cla()
    
    def update_settings(self, settings: RenderSettings):
        """更新matplotlib渲染设置"""
        self.settings = settings
        
        if self.fig and settings:
            self.fig.set_facecolor(settings.background_color)
            
            # 更新窗口透明度（如果支持）
            try:
                if hasattr(self.fig.canvas.manager, 'window'):
                    self.fig.canvas.manager.window.setWindowOpacity(settings.window_opacity)
            except:
                pass
    
    def cleanup(self):
        """清理matplotlib资源"""
        if self.fig:
            self.plt.close(self.fig)
        self.is_initialized = False
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取matplotlib渲染器信息"""
        return {
            "name": "Matplotlib 3D Renderer",
            "version": "1.0.0",
            "backend": "matplotlib",
            "capabilities": [
                "3d_rendering",
                "scatter_plots", 
                "transparency",
                "color_blending",
                "camera_control"
            ],
            "performance": "medium",
            "platform": "desktop"
        }


# 工具函数：数据转换
def convert_njit_to_particles(all_x: np.ndarray, all_y: np.ndarray, all_z: np.ndarray,
                             all_sizes: np.ndarray, all_opacity: np.ndarray, 
                             all_types: np.ndarray, all_color_blend_factors: np.ndarray,
                             base_color: Tuple[float, float, float]) -> List[RenderableParticle]:
    """
    将njit函数输出转换为标准化的渲染粒子对象
    
    这个函数桥接了现有的njit输出和新的渲染接口
    """
    particles = []
    
    if len(all_x) == 0:
        return particles
    
    # 计算颜色（使用现有的njit颜色计算逻辑）
    import MBC_njit_func
    colors = MBC_njit_func.calculate_particle_colors_njit(
        all_types, all_color_blend_factors, all_opacity,
        base_color[0], base_color[1], base_color[2]
    )
    
    # 类型映射
    type_names = {0: "bubble", 1: "light", 2: "lampshade"}
    
    for i in range(len(all_x)):
        particle = RenderableParticle(
            position=(float(all_x[i]), float(all_y[i]), float(all_z[i])),
            size=float(all_sizes[i]),
            color=(float(colors[i, 0]), float(colors[i, 1]), 
                  float(colors[i, 2]), float(colors[i, 3])),
            opacity=float(all_opacity[i]),
            particle_type=type_names.get(all_types[i], "unknown"),
            blend_factor=float(all_color_blend_factors[i]),
            object_id=i
        )
        particles.append(particle)
    
    return particles
