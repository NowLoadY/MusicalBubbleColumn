"""
气泡生成器模块 - 轻量级状态管理器

重构后的职责：
- 管理气泡生成相关的状态（scaler, final_volume等）
- 提供配置接口供物理引擎使用
- 提供统计信息接口
- 为未来的模块化扩展保留框架

注意：实际的气泡生成逻辑由高性能的njit函数处理，
这个模块专注于状态管理和接口提供。
"""

import numpy as np
from typing import Tuple, List, Dict
from MBC_config import get_config


class BubbleGenerator:
    """
    气泡生成器状态管理器
    
    轻量级设计，专注于：
    1. 状态管理（scaler, final_volume, thickness_list等）
    2. 配置提供（供物理引擎使用）
    3. 统计信息接口
    4. 未来扩展的基础框架
    """
    
    def __init__(self, position_list, orientation="up"):
        """
        初始化状态管理器
        
        Args:
            position_list: 气泡位置列表
            orientation: 方向 ("up" 或 "down")
        """
        self.config = get_config()
        self.position_list = position_list
        self.orientation = orientation
        
        # 状态管理属性（与njit函数共享）
        self.scaler = 1
        self.final_volume = np.zeros(self.config.physics.final_volume_history_size)
        self.final_volume_index = 0
        self.thickness_list = [0] * 120
        
    def update_scaler_from_variances(self, variances: List[float]):
        """
        根据方差更新缩放器（由外部调用）
        
        Args:
            variances: 从njit函数返回的方差列表
        """
        if variances:
            variances_threshold = self.config.physics.variance_threshold
            if np.mean(variances) < variances_threshold:
                self.scaler += self.config.physics.scaler_increment
            else:
                self.scaler = max(0, self.scaler - self.config.physics.scaler_increment)
    
    def get_physics_config(self) -> Dict:
        """
        获取物理引擎配置参数
        
        Returns:
            Dict: 物理配置参数，供物理引擎使用
        """
        return {
            "max_volume_up": self.config.physics.max_volume_up,
            "max_volume_down": self.config.physics.max_volume_down,
            "variance_threshold": self.config.physics.variance_threshold,
            "scaler_increment": self.config.physics.scaler_increment,
            "final_volume_history_size": self.config.physics.final_volume_history_size,
        }
    
    def reset_generator(self):
        """重置生成器状态"""
        self.scaler = 1
        self.final_volume = np.zeros(self.config.physics.final_volume_history_size)
        self.final_volume_index = 0
        self.thickness_list = [0] * 120
    
    def toggle_orientation(self):
        """切换方向"""
        self.orientation = "down" if self.orientation == "up" else "up"
    
    def get_statistics(self) -> Dict:
        """获取生成器统计信息"""
        return {
            "scaler": self.scaler,
            "orientation": self.orientation,
            "active_thickness_count": sum(1 for t in self.thickness_list if t > 0),
            "average_thickness": np.mean([t for t in self.thickness_list if t > 0]) if any(self.thickness_list) else 0
        }
