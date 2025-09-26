"""
物理引擎抽象接口 - 为替换物理引擎建立标准化接口

这个模块定义了物理引擎的抽象基类，使得未来可以轻松替换不同的物理引擎
（如从njit实现替换为PyMunk、Bullet等）。
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import Tuple, List, Dict, Any


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
                            snow_ttl: np.ndarray, max_snow_ttl: int) -> Tuple[np.ndarray, ...]:
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
            pattern_data, pattern_data_thickness, orientation
        )
    
    def calculate_bubble(self, pattern_data: np.ndarray, 
                        pattern_data_thickness: np.ndarray, 
                        data_height: int, orientation: str = "up") -> Tuple[np.ndarray, np.ndarray]:
        """使用njit函数计算气泡物理"""
        return self.njit_func.calculate_bubble(
            pattern_data, pattern_data_thickness, data_height, orientation
        )
    
    def calculate_render_data(self, pattern_data: np.ndarray, 
                            pattern_data_thickness: np.ndarray,
                            offset: Tuple[float, float],
                            all_positions_x: np.ndarray, all_positions_y: np.ndarray,
                            position_index_keys_x: np.ndarray, position_index_keys_y: np.ndarray,
                            position_index_values: np.ndarray, opacity_values: Dict,
                            data_height: int, orientation_int: int,
                            snow_ttl: np.ndarray, max_snow_ttl: int) -> Tuple[np.ndarray, ...]:
        """使用njit函数计算渲染数据"""
        return self.njit_func.calculate_pattern_data_3d(
            pattern_data, pattern_data_thickness, offset,
            all_positions_x, all_positions_y,
            position_index_keys_x, position_index_keys_y, position_index_values,
            opacity_values, data_height, orientation_int, snow_ttl, max_snow_ttl
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
