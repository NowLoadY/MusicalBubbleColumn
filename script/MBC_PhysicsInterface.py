"""
物理引擎抽象接口 - 为替换物理引擎建立标准化接口

这个模块定义了物理引擎的抽象基类，使得未来可以轻松替换不同的物理引擎
（如从njit实现替换为PyMunk、Bullet等）。
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import Tuple, List, Dict, Any

from MBC_config import get_config


class PhysicsEngineInterface(ABC):
    """
    物理引擎抽象基类
    
    定义了所有物理引擎必须实现的标准接口，
    确保不同物理引擎间的可替换性。
    """
    
    @abstractmethod
    def add_pattern(self, bit_array: np.ndarray, volumes: List[float], 
                   average_volume: float, position_list: List[Tuple[int, int]], 
                   final_volume: np.ndarray, final_volume_index: int, 
                   scaler: float, thickness_list: List[int], 
                   pattern_data: np.ndarray, pattern_data_thickness: np.ndarray, 
                   orientation: str) -> List[float]:
        """
        添加新的气泡模式到物理世界
        
        Args:
            bit_array: MIDI激活状态数组
            volumes: 音量数组
            average_volume: 平均音量
            position_list: 气泡位置列表
            final_volume: 最终音量历史数组
            final_volume_index: 音量索引
            scaler: 缩放因子
            thickness_list: 厚度列表
            pattern_data: 模式数据数组
            pattern_data_thickness: 厚度数据数组
            orientation: 方向 ("up" 或 "down")
            
        Returns:
            List[float]: 方差列表
        """
        pass
    
    @abstractmethod
    def calculate_bubble(self, pattern_data: np.ndarray, 
                        pattern_data_thickness: np.ndarray, 
                        data_height: int, orientation: str = "up") -> Tuple[np.ndarray, np.ndarray]:
        """
        计算气泡物理模拟
        
        Args:
            pattern_data: 模式数据数组
            pattern_data_thickness: 厚度数据数组
            data_height: 数据高度
            orientation: 方向 ("up" 或 "down")
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: 更新后的 (pattern_data, pattern_data_thickness)
        """
        pass
    
    @abstractmethod
    def calculate_render_data(self, pattern_data: np.ndarray, 
                            pattern_data_thickness: np.ndarray,
                            offset: Tuple[float, float],
                            all_positions_x: np.ndarray, all_positions_y: np.ndarray,
                            position_index_keys_x: np.ndarray, position_index_keys_y: np.ndarray,
                            position_index_values: np.ndarray, opacity_values: Dict,
                            data_height: int, orientation_int: int,
                            snow_ttl: np.ndarray, snow_sizes: np.ndarray, max_snow_ttl: int) -> Tuple[np.ndarray, ...]:
        """
        计算渲染数据
        
        Args:
            pattern_data: 模式数据数组
            pattern_data_thickness: 厚度数据数组
            offset: 坐标偏移
            all_positions_x, all_positions_y: 所有位置坐标
            position_index_keys_x, position_index_keys_y: 位置索引键
            position_index_values: 位置索引值
            opacity_values: 透明度值字典
            data_height: 数据高度
            orientation_int: 方向整数 (0=up, 1=down)
            snow_ttl: 雪花TTL数组
            snow_sizes: 积雪尺寸数组
            max_snow_ttl: 最大雪花TTL
            
        Returns:
            Tuple[np.ndarray, ...]: (all_x, all_y, all_z, all_sizes, all_opacity, all_types, all_color_blend_factors)
        """
        pass

    def get_engine_info(self) -> Dict[str, Any]:
        """
        获取物理引擎信息
        
        Returns:
            Dict[str, Any]: 引擎信息（名称、版本、特性等）
        """
        return {
            "name": "Unknown",
            "version": "1.0.0",
            "features": ["basic_physics"]
        }


class NjitPhysicsEngine(PhysicsEngineInterface):
    """
    基于Numba JIT的高性能物理引擎实现
    
    将现有的njit函数包装为标准化的物理引擎接口，
    保持原有的高性能特性。
    """
    
    def __init__(self):
        """初始化njit物理引擎"""
        # 延迟导入避免循环依赖
        import MBC_njit_func
        self.njit_func = MBC_njit_func
        self.config = get_config()
        
    def add_pattern(self, bit_array: np.ndarray, volumes: List[float], 
                   average_volume: float, position_list: List[Tuple[int, int]], 
                   final_volume: np.ndarray, final_volume_index: int, 
                   scaler: float, thickness_list: List[int], 
                   pattern_data: np.ndarray, pattern_data_thickness: np.ndarray, 
                   orientation: str) -> List[float]:
        """使用njit函数添加气泡模式"""
        return self.njit_func.add_pattern(
            bit_array, volumes, average_volume, position_list, 
            final_volume, final_volume_index, scaler, thickness_list, 
            pattern_data,
            pattern_data_thickness,
            orientation,
            self.config.physics.max_volume_up,
            self.config.physics.max_volume_down,
            self.config.physics.birth_curve_up,
            self.config.physics.birth_curve_down,
        )
    
    def calculate_bubble(self, pattern_data: np.ndarray, 
                        pattern_data_thickness: np.ndarray, 
                        data_height: int, orientation: str = "up") -> Tuple[np.ndarray, np.ndarray]:
        """使用njit函数计算气泡物理"""
        scale = self.config.scale
        physics = self.config.physics
        vertical_cell_pitch_m = scale.column_height_m / max(float(data_height - 1), 1.0)
        return self.njit_func.calculate_bubble(
            pattern_data,
            pattern_data_thickness,
            data_height,
            orientation,
            vertical_cell_pitch_m,
            scale.horizontal_cell_pitch_m,
            scale.bubble_area_unit_m2,
            scale.simulation_step_s,
            scale.gravity_m_s2,
            scale.atmospheric_pressure_pa,
            scale.liquid_density_kg_m3,
            scale.gas_density_kg_m3,
            scale.water_kinematic_viscosity_m2_s,
            scale.surface_tension_n_m,
            scale.drag_coefficient,
            scale.min_bubble_radius_m,
            scale.max_bubble_radius_m,
            scale.stable_bubble_radius_m,
            scale.split_weber_number,
            scale.merge_efficiency,
            scale.coalescence_factor,
            physics.max_rise_speed,
            physics.merge_interval,
            physics.grid_cell_size,
            physics.adjacent_grid_threshold,
            physics.max_volume_up,
            physics.max_volume_down,
        )
    
    def calculate_render_data(self, pattern_data: np.ndarray, 
                            pattern_data_thickness: np.ndarray,
                            offset: Tuple[float, float],
                            all_positions_x: np.ndarray, all_positions_y: np.ndarray,
                            position_index_keys_x: np.ndarray, position_index_keys_y: np.ndarray,
                            position_index_values: np.ndarray, opacity_values: Dict,
                            data_height: int, orientation_int: int,
                            snow_ttl: np.ndarray, snow_sizes: np.ndarray, max_snow_ttl: int) -> Tuple[np.ndarray, ...]:
        """使用njit函数计算渲染数据"""
        scale = self.config.scale
        return self.njit_func.calculate_pattern_data_3d(
            pattern_data, pattern_data_thickness, offset,
            all_positions_x, all_positions_y,
            position_index_keys_x, position_index_keys_y, position_index_values,
            opacity_values, data_height, orientation_int, snow_ttl, snow_sizes, max_snow_ttl,
            scale.bubble_area_unit_m2,
            scale.min_bubble_radius_m,
            scale.max_bubble_radius_m,
            scale.bubble_screen_radius_per_meter,
            scale.min_bubble_screen_radius,
            scale.inactive_screen_radius,
            scale.light_particle_screen_radius,
            scale.lampshade_screen_radius,
        )
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取njit引擎信息"""
        return {
            "name": "Numba JIT Physics Engine",
            "version": "1.0.0", 
            "features": [
                "high_performance",
                "bubble_physics",
                "snow_effects",
                "light_effects",
                "njit_compiled"
            ],
            "backend": "numba"
        }
