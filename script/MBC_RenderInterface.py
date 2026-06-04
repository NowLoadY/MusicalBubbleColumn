"""Render data contract for the WebGPU renderer."""

from dataclasses import dataclass
from typing import Tuple

import numpy as np


PARTICLE_FLOAT_COUNT = 10


@dataclass
class CameraState:
    position: Tuple[float, float, float]
    target: Tuple[float, float, float]
    up: Tuple[float, float, float]
    elev: float
    azim: float
    x_range: Tuple[float, float]
    y_range: Tuple[float, float]
    z_range: Tuple[float, float]


@dataclass
class RenderSettings:
    background_color: Tuple[float, float, float, float] = (0.0, 0.0, 60 / 255, 1.0)
    window_opacity: float = 1.0
    particle_quality: str = "webgpu"
    max_particles: int = 100000
    frame_rate_limit: int = 120
    visualize_piano: bool = True


def build_particle_buffer(
    all_x: np.ndarray,
    all_y: np.ndarray,
    all_z: np.ndarray,
    all_sizes: np.ndarray,
    all_opacity: np.ndarray,
    all_types: np.ndarray,
    all_color_blend_factors: np.ndarray,
    base_color: Tuple[float, float, float],
) -> np.ndarray:
    """Pack njit output into a contiguous float32 instance buffer.

    Layout per particle:
    x, y, z, size, r, g, b, a, type, blend_factor
    """
    count = len(all_x)
    if count == 0:
        return np.empty((0, PARTICLE_FLOAT_COUNT), dtype=np.float32)

    import MBC_njit_func

    colors = MBC_njit_func.calculate_particle_colors_njit(
        all_types,
        all_color_blend_factors,
        all_opacity,
        base_color[0],
        base_color[1],
        base_color[2],
    )

    particle_buffer = np.empty((count, PARTICLE_FLOAT_COUNT), dtype=np.float32)
    particle_buffer[:, 0] = all_x
    particle_buffer[:, 1] = all_y
    particle_buffer[:, 2] = all_z
    particle_buffer[:, 3] = all_sizes
    particle_buffer[:, 4:8] = colors
    particle_buffer[:, 8] = all_types
    particle_buffer[:, 9] = all_color_blend_factors
    return np.ascontiguousarray(particle_buffer, dtype=np.float32)
