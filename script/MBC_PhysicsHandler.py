"""
物理处理器模块 - 轻量级状态管理和接口框架

重构后的职责：
- 管理物理相关的状态和数组引用
- 提供统计信息接口
- 为未来物理引擎替换保留框架

注意：实际的物理计算由高性能的njit函数处理，
这个模块专注于状态管理和接口提供。
"""

import numpy as np
from typing import Tuple, List, Dict
from MBC_config import get_config


class PhysicsHandler:
    """
    物理处理器状态管理器
    
    轻量级设计，专注于：
    1. 物理状态管理（pattern_data等）
    2. 统计信息接口  
    3. 未来物理引擎替换的基础框架
    """
    
    def __init__(self, data_height: int, max_x: int, max_y: int, 
                 all_positions: np.ndarray, bubble_positions: np.ndarray, 
                 bubble_indices: np.ndarray, opacity_dict: Dict,
                 offset: Tuple[float, float], orientation="up"):
        """
        初始化状态管理器
        
        Args:
            data_height: 数据高度
            max_x, max_y: 最大坐标范围  
            all_positions: 所有位置数组
            bubble_positions: 气泡位置数组
            bubble_indices: 气泡索引数组
            opacity_dict: 透明度字典
            offset: 坐标偏移
            orientation: 方向 ("up" 或 "down")
        """
        self.config = get_config()
        self.data_height = data_height
        self.orientation = orientation
        
        # 物理世界状态（与njit函数共享的数组引用）
        self.pattern_data_required_size = (data_height, max_x + 1, max_y + 1)
        self.pattern_data = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        self.pattern_data_thickness = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        
        # 渲染相关数据引用
        self.all_positions = all_positions
        self.bubble_positions = bubble_positions
        self.bubble_indices = bubble_indices
        self.opacity_dict = opacity_dict
        self.offset = offset
        
        # 雪花效果相关 (用于down模式)
        self.MAX_SNOW_STACK_HEIGHT = self.config.physics.max_snow_stack_height
        self.snow_ttl = np.zeros((self.MAX_SNOW_STACK_HEIGHT, self.pattern_data.shape[1], self.pattern_data.shape[2]), dtype=np.int32)
        self.MAX_SNOW_TTL = self.config.physics.max_snow_ttl
    
    def toggle_orientation(self):
        """切换物理方向"""
        self.orientation = "down" if self.orientation == "up" else "up"
    
    def reset_physics(self):
        """重置物理状态"""
        self.pattern_data.fill(0)
        self.pattern_data_thickness.fill(0) 
        if hasattr(self, 'snow_ttl'):
            self.snow_ttl.fill(0)
    
    def get_physics_statistics(self) -> Dict:
        """获取物理统计信息"""
        active_bubbles = np.sum(self.pattern_data > 0)
        total_energy = np.sum(self.pattern_data_thickness)
        
        return {
            "orientation": self.orientation,
            "active_bubbles": int(active_bubbles),
            "total_energy": float(total_energy),
            "data_shape": self.pattern_data.shape,
            "snow_active": int(np.sum(self.snow_ttl > 0)) if hasattr(self, 'snow_ttl') else 0
        }
    
    def get_raw_pattern_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        获取原始模式数据 - 保持与现有代码的兼容性
        
        Returns:
            Tuple[np.ndarray, np.ndarray]: (pattern_data, pattern_data_thickness)
        """
        return self.pattern_data, self.pattern_data_thickness
    
    def set_raw_pattern_data(self, pattern_data: np.ndarray, pattern_data_thickness: np.ndarray):
        """
        设置原始模式数据 - 保持与现有代码的兼容性
        
        Args:
            pattern_data: 模式数据数组
            pattern_data_thickness: 厚度数据数组
        """
        if pattern_data.shape == self.pattern_data.shape:
            self.pattern_data = pattern_data.copy()
        if pattern_data_thickness.shape == self.pattern_data_thickness.shape:
            self.pattern_data_thickness = pattern_data_thickness.copy()
