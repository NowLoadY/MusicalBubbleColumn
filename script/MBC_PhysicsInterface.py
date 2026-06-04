"""Physics engine interface and Numba implementation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

import numpy as np

from MBC_config import get_config


class PhysicsEngineInterface(ABC):
    """Standard interface for the simulation kernels."""

    @abstractmethod
    def add_pattern(
        self,
        bit_array: np.ndarray,
        volumes: List[float],
        average_volume: float,
        position_list: List[Tuple[int, int]],
        final_volume: np.ndarray,
        final_volume_index: int,
        scaler: float,
        thickness_list: List[int],
        pattern_data: np.ndarray,
        pattern_data_thickness: np.ndarray,
        orientation: str,
    ) -> List[float]:
        """Write the current MIDI activation into the birth grid."""
        pass

    @abstractmethod
    def advance_bubble_particles(
        self,
        pattern_data: np.ndarray,
        pattern_data_thickness: np.ndarray,
        bubble_particles: np.ndarray,
        particle_grid: np.ndarray,
        snow_ttl: np.ndarray,
        snow_sizes: np.ndarray,
        data_height: int,
        orientation_int: int,
    ) -> None:
        """Advance continuous bubble particles and grid-assisted interactions."""
        pass

    @abstractmethod
    def calculate_render_data(
        self,
        pattern_data: np.ndarray,
        pattern_data_thickness: np.ndarray,
        bubble_particles: np.ndarray,
        offset: Tuple[float, float],
        all_positions_x: np.ndarray,
        all_positions_y: np.ndarray,
        position_index_keys_x: np.ndarray,
        position_index_keys_y: np.ndarray,
        position_index_values: np.ndarray,
        opacity_values: Dict,
        data_height: int,
        orientation_int: int,
        snow_ttl: np.ndarray,
        snow_sizes: np.ndarray,
        max_snow_ttl: int,
    ) -> Tuple[np.ndarray, ...]:
        """Build renderable particle arrays from the simulation state."""
        pass

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "name": "Unknown",
            "version": "1.0.0",
            "features": ["basic_physics"],
        }


class NjitPhysicsEngine(PhysicsEngineInterface):
    """High-performance physics engine backed by Numba kernels."""

    def __init__(self):
        import MBC_njit_func

        self.njit_func = MBC_njit_func
        self.config = get_config()

    def add_pattern(
        self,
        bit_array: np.ndarray,
        volumes: List[float],
        average_volume: float,
        position_list: List[Tuple[int, int]],
        final_volume: np.ndarray,
        final_volume_index: int,
        scaler: float,
        thickness_list: List[int],
        pattern_data: np.ndarray,
        pattern_data_thickness: np.ndarray,
        orientation: str,
    ) -> List[float]:
        return self.njit_func.add_pattern(
            bit_array,
            volumes,
            average_volume,
            position_list,
            final_volume,
            final_volume_index,
            scaler,
            thickness_list,
            pattern_data,
            pattern_data_thickness,
            orientation,
            self.config.physics.max_volume_up,
            self.config.physics.max_volume_down,
            self.config.physics.birth_curve_up,
            self.config.physics.birth_curve_down,
        )

    def advance_bubble_particles(
        self,
        pattern_data: np.ndarray,
        pattern_data_thickness: np.ndarray,
        bubble_particles: np.ndarray,
        particle_grid: np.ndarray,
        snow_ttl: np.ndarray,
        snow_sizes: np.ndarray,
        data_height: int,
        orientation_int: int,
    ) -> None:
        scale = self.config.scale
        physics = self.config.physics
        vertical_cell_pitch_m = scale.column_height_m / max(float(data_height - 1), 1.0)
        self.njit_func.advance_bubble_particles(
            pattern_data,
            pattern_data_thickness,
            bubble_particles,
            particle_grid,
            snow_ttl,
            snow_sizes,
            data_height,
            orientation_int,
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
            physics.adjacent_grid_threshold,
            physics.max_snow_ttl,
            scale.bubble_screen_radius_per_meter,
            scale.min_bubble_screen_radius,
        )

    def calculate_render_data(
        self,
        pattern_data: np.ndarray,
        pattern_data_thickness: np.ndarray,
        bubble_particles: np.ndarray,
        offset: Tuple[float, float],
        all_positions_x: np.ndarray,
        all_positions_y: np.ndarray,
        position_index_keys_x: np.ndarray,
        position_index_keys_y: np.ndarray,
        position_index_values: np.ndarray,
        opacity_values: Dict,
        data_height: int,
        orientation_int: int,
        snow_ttl: np.ndarray,
        snow_sizes: np.ndarray,
        max_snow_ttl: int,
    ) -> Tuple[np.ndarray, ...]:
        scale = self.config.scale
        return self.njit_func.calculate_pattern_data_3d(
            pattern_data,
            pattern_data_thickness,
            bubble_particles,
            offset,
            all_positions_x,
            all_positions_y,
            position_index_keys_x,
            position_index_keys_y,
            position_index_values,
            opacity_values,
            data_height,
            orientation_int,
            snow_ttl,
            snow_sizes,
            max_snow_ttl,
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
        return {
            "name": "Numba JIT Physics Engine",
            "version": "2.0.0",
            "features": [
                "continuous_particles",
                "grid_birth",
                "grid_merge",
                "snow_deposition",
                "njit_compiled",
            ],
            "backend": "numba",
        }
