import time
from collections import deque

import numpy as np

from MBC_BubbleGenerator import BubbleGenerator
from MBC_Calc import calculate_opacity, generate_positions
from MBC_commands import NEXT_THEME, REQUEST_FILE_SELECTION, TOGGLE_ORIENTATION
from MBC_PhysicsHandler import PhysicsHandler
from MBC_PhysicsInterface import NjitPhysicsEngine
from MBC_RenderInterface import CameraState, RenderSettings, build_particle_buffer
from MBC_WebGPURenderer import WebGPURenderer
from MBC_config import get_config


class PatternVisualizer3D:
    def __init__(self, pos_type=None, visualize_piano=None, orientation=None, open_browser=True):
        self.config = get_config()
        self.orientation = orientation or self.config.visualization.default_orientation
        self.visualize_piano = (
            visualize_piano
            if visualize_piano is not None
            else self.config.visualization.visualize_piano
        )
        self.pos_type = pos_type or self.config.visualization.default_pos_type
        self.data_height = self.config.visualization.data_height_3d
        self.total_center = (0, 0, self.data_height // 2)
        self.working = True

        self.theme_index = self.config.theme.default_theme_index
        self.fig_themes_rgba = self.config.theme.fig_themes_rgba
        self.data_themes_rgb = self.config.theme.data_themes_rgb
        self.data_color = self.data_themes_rgb[self.theme_index]
        self.window_opacity = self.config.visualization.window_opacity

        self.elev = self.config.visualization.default_elev
        self.target_elev = self.config.visualization.default_elev
        self.azim_angle = self.config.visualization.default_azim_angle
        self.target_azim_speed = self.config.visualization.default_azim_speed
        self.app_commands = deque()
        self.command_handlers = {
            TOGGLE_ORIENTATION: self.toggle_orientation,
            NEXT_THEME: self._change_theme,
            REQUEST_FILE_SELECTION: self.request_file_selection,
        }

        self.position_list, self.offset = generate_positions(
            self.config.visualization.num_positions,
            self.total_center[0],
            self.total_center[1],
            self.config.visualization.inner_radius,
            self.config.visualization.outer_radius,
            pos_type=self.pos_type,
        )
        self._initialize_data()

        self.bubble_generator = BubbleGenerator(self.position_list, self.orientation)
        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)

        self.physics_handler = PhysicsHandler(
            data_height=self.data_height,
            max_x=max_size,
            max_y=max_size,
            all_positions=self.all_positions_array,
            bubble_positions=self.bubble_positions,
            bubble_indices=self.bubble_indices,
            opacity_dict=self.opacity_dict,
            offset=self.offset,
            orientation=self.orientation,
        )
        self.physics_engine = NjitPhysicsEngine()

        self.render_engine = WebGPURenderer(open_browser=open_browser)
        self.render_settings = RenderSettings(
            background_color=self.fig_themes_rgba[self.theme_index],
            window_opacity=self.window_opacity,
            max_particles=self.config.performance.particle_count_light * self.data_height,
            visualize_piano=self.visualize_piano,
        )
        self.render_engine.initialize(self.render_settings)
        self.physics_handler.set_raw_pattern_data(self.pattern_data, self.pattern_data_thickness)

        self.scaler = self.bubble_generator.scaler
        self.final_volume = self.bubble_generator.final_volume
        self.final_volume_index = self.bubble_generator.final_volume_index
        self.thickness_list = self.bubble_generator.thickness_list

        self.MAX_SNOW_STACK_HEIGHT = self.config.physics.max_snow_stack_height
        self.snow_ttl = self.physics_handler.snow_ttl
        self.snow_sizes = self.physics_handler.snow_sizes
        self.MAX_SNOW_TTL = self.config.physics.max_snow_ttl
        self._last_frame_time = time.perf_counter()

    def _initialize_data(self):
        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)
        self.pattern_data_required_size = (self.data_height, max_size + 1, max_size + 1)
        self.pattern_data = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        self.pattern_data_thickness = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        self.all_positions = set(self.position_list)
        self.all_positions_array = np.array(list(self.all_positions))
        self.bubble_positions = np.array(self.position_list)
        self.bubble_indices = np.arange(len(self.position_list))
        self.opacity_dict = calculate_opacity()

        self.default_xlim, self.default_ylim, self.default_zlim = self._calculate_scene_bounds()
        self.zlim = self.default_zlim
        self.xlim = self.default_xlim
        self.ylim = self.default_ylim

    def _calculate_scene_bounds(self):
        height, rows, cols = self.pattern_data.shape
        x_min = -float(self.offset[0])
        x_max = float(rows - 1 - self.offset[0])
        y_min = -float(self.offset[1])
        y_max = float(cols - 1 - self.offset[1])
        xy_margin = 8.0

        if self.orientation == "down":
            light_center_x = rows / 2 - self.offset[0]
            light_center_y = cols / 2 - self.offset[1]
            light_radius = max(rows, cols) / 1.2
            x_min = min(x_min, light_center_x - light_radius)
            x_max = max(x_max, light_center_x + light_radius)
            y_min = min(y_min, light_center_y - light_radius)
            y_max = max(y_max, light_center_y + light_radius)
            z_min = -float(max(self.config.physics.max_snow_stack_height - 1, 1) * 5)
            z_max = float(height + 50)
        else:
            z_min = 0.0
            z_max = float(height + 2)

        xy_radius = max(abs(x_min), abs(x_max), abs(y_min), abs(y_max)) + xy_margin
        return (
            (-xy_radius, xy_radius),
            (-xy_radius, xy_radius),
            (z_min, z_max),
        )

    def update_pattern(self, new_pattern, volumes, average_volume, key_activation_bytes, volumes_real):
        self._sync_frontend_controls()
        boundary_layer = -1 if self.orientation == "down" else 0
        self.pattern_data[boundary_layer, :, :] = 0
        self.pattern_data_thickness[boundary_layer, :, :] = 0

        self.azim_angle = (self.azim_angle - self.target_azim_speed) % 360
        transition_rate = self.config.visualization.view_transition_rate
        self.elev += (self.target_elev - self.elev) * transition_rate
        if abs(self.elev - self.target_elev) < 0.05:
            self.elev = self.target_elev
        elif self.target_elev >= 89.95 and self.elev > 89.0:
            self.elev = 90.0
        elif self.target_elev <= 0.05 and self.elev < 1.0:
            self.elev = 0.0

        if isinstance(new_pattern, bytes):
            bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
            self._update_data_layer(bit_array, volumes, average_volume)

        self._draw_pattern()
        if self.visualize_piano and key_activation_bytes is not None and volumes_real is not None:
            key_activation_bit_array = np.unpackbits(np.frombuffer(key_activation_bytes, dtype=np.uint8))
            self.render_engine.update_piano(key_activation_bit_array[:88], volumes_real[:88])
        self._pace_frame()

    def _sync_frontend_controls(self):
        controls = self.render_engine.get_control_state()
        if controls.get("target_elev") is not None:
            self.target_elev = float(controls["target_elev"])
        if controls.get("target_azim_speed") is not None:
            self.target_azim_speed = float(controls["target_azim_speed"])

        for command in self.render_engine.pop_commands():
            handler = self.command_handlers.get(command)
            if handler is not None:
                handler()

    def request_file_selection(self):
        self.app_commands.append(REQUEST_FILE_SELECTION)
        self.working = False

    def pop_app_commands(self):
        commands = list(self.app_commands)
        self.app_commands.clear()
        return commands

    def _update_data_layer(self, bit_array, volumes, average_volume):
        boundary_layer = -1 if self.orientation == "down" else 0
        self.pattern_data[boundary_layer, :, :] = 0
        self.pattern_data_thickness[boundary_layer, :, :] = 0

        variances = self.physics_engine.add_pattern(
            bit_array,
            volumes,
            average_volume,
            self.bubble_generator.position_list,
            self.bubble_generator.final_volume,
            self.bubble_generator.final_volume_index,
            self.bubble_generator.scaler,
            self.bubble_generator.thickness_list,
            self.pattern_data,
            self.pattern_data_thickness,
            self.orientation,
        )

        active_indices = np.where(bit_array)[0]
        if len(active_indices) > 0:
            self.bubble_generator.final_volume_index = (
                self.bubble_generator.final_volume_index + len(active_indices)
            ) % self.config.physics.final_volume_history_size

        pattern_data_temp, pattern_data_thickness_temp = self.physics_engine.calculate_bubble(
            self.pattern_data,
            self.pattern_data_thickness,
            self.data_height,
            orientation=self.orientation,
        )
        if self.orientation == "down":
            self.pattern_data[: self.data_height - 1] = pattern_data_temp[: self.data_height - 1]
            self.pattern_data_thickness[: self.data_height - 1] = pattern_data_thickness_temp[: self.data_height - 1]
        else:
            self.pattern_data[1:self.data_height] = pattern_data_temp[1:self.data_height]
            self.pattern_data_thickness[1:self.data_height] = pattern_data_thickness_temp[1:self.data_height]
        self.bubble_generator.update_scaler_from_variances(variances)

        self.scaler = self.bubble_generator.scaler
        self.final_volume = self.bubble_generator.final_volume
        self.final_volume_index = self.bubble_generator.final_volume_index
        self.thickness_list = self.bubble_generator.thickness_list

    def _draw_pattern(self):
        all_positions = self.all_positions_array
        orientation_int = 0 if self.orientation == "up" else 1
        all_x, all_y, all_z, all_sizes, all_opacity, all_types, all_color_blend_factors = (
            self.physics_engine.calculate_render_data(
                self.pattern_data,
                self.pattern_data_thickness,
                self.offset,
                all_positions[:, 0],
                all_positions[:, 1],
                self.bubble_positions[:, 0],
                self.bubble_positions[:, 1],
                self.bubble_indices,
                self.opacity_dict,
                self.data_height,
                orientation_int,
                self.snow_ttl,
                self.snow_sizes,
                self.MAX_SNOW_TTL,
            )
        )

        particles = build_particle_buffer(
            all_x,
            all_y,
            all_z,
            all_sizes,
            all_opacity,
            all_types,
            all_color_blend_factors,
            self.data_color,
        )
        camera = CameraState(
            position=(0, 0, 0),
            target=(0, 0, 0),
            up=(0, 0, 1),
            elev=self.elev,
            azim=self.azim_angle,
            x_range=self.xlim,
            y_range=self.ylim,
            z_range=self.zlim,
        )
        self.render_engine.render_frame(particles, camera)

    def _pace_frame(self):
        frame_rate = max(1, self.render_settings.frame_rate_limit)
        min_interval = 1.0 / frame_rate
        now = time.perf_counter()
        remaining = min_interval - (now - self._last_frame_time)
        if remaining > 0:
            time.sleep(remaining)
            now = time.perf_counter()
        self._last_frame_time = now

    def toggle_orientation(self):
        self.orientation = "down" if self.orientation == "up" else "up"
        self.bubble_generator.toggle_orientation()
        self.physics_handler.toggle_orientation()

        self.default_xlim, self.default_ylim, self.default_zlim = self._calculate_scene_bounds()
        self.xlim = self.default_xlim
        self.ylim = self.default_ylim
        self.zlim = self.default_zlim

    def _change_theme(self):
        self.theme_index = (self.theme_index + 1) % len(self.fig_themes_rgba)
        self.data_color = self.data_themes_rgb[self.theme_index]
        self.render_settings.background_color = self.fig_themes_rgba[self.theme_index]
        self.render_engine.update_settings(self.render_settings)

    def stop(self):
        self.working = False
        self.render_engine.cleanup()


def init_njit_func(visualizer):
    bit_array = np.unpackbits(np.frombuffer(bytes(15), dtype=np.uint8))
    test_volumes = [1] * 120

    visualizer.physics_engine.add_pattern(
        bit_array,
        test_volumes,
        0,
        visualizer.bubble_generator.position_list,
        visualizer.bubble_generator.final_volume,
        visualizer.bubble_generator.final_volume_index,
        visualizer.bubble_generator.scaler,
        visualizer.bubble_generator.thickness_list,
        visualizer.pattern_data,
        visualizer.pattern_data_thickness,
        visualizer.orientation,
    )
    visualizer.physics_engine.calculate_bubble(
        visualizer.pattern_data,
        visualizer.pattern_data_thickness,
        visualizer.data_height,
        visualizer.orientation,
    )

    all_positions = visualizer.all_positions_array
    orientation_int = 0 if visualizer.orientation == "up" else 1
    visualizer.physics_engine.calculate_render_data(
        visualizer.pattern_data,
        visualizer.pattern_data_thickness,
        visualizer.offset,
        all_positions[:, 0],
        all_positions[:, 1],
        visualizer.bubble_positions[:, 0],
        visualizer.bubble_positions[:, 1],
        visualizer.bubble_indices,
        visualizer.opacity_dict,
        visualizer.data_height,
        orientation_int,
        visualizer.snow_ttl,
        visualizer.snow_sizes,
        visualizer.MAX_SNOW_TTL,
    )

    visualizer.pattern_data.fill(0)
    visualizer.pattern_data_thickness.fill(0)
    visualizer.physics_handler.reset_physics()
    visualizer.bubble_generator.reset_generator()
