"""Centralized configuration for Musical Bubble Column application."""

import os.path as os_path
from dataclasses import dataclass, field
from typing import Tuple, List
import json

# Base paths
base_path = os_path.dirname(os_path.abspath(__file__))


@dataclass
class FilePathsConfig:
    """File paths and resource locations."""
    icon_path: str = field(default_factory=lambda: os_path.join(base_path, "rounded_icon.png"))
    default_midi_path: str = field(default_factory=lambda: os_path.join(base_path, "City_Of_Stars.mid"))
    default_wav_path: str = field(default_factory=lambda: os_path.join(base_path, "City_Of_Stars_vocal.wav"))
    config_file: str = field(default_factory=lambda: os_path.join(base_path, "mbc_settings.json"))


@dataclass
class ThemeConfig:
    """Visual themes and colors."""
    fig_themes_rgba: List[Tuple[float, float, float, float]] = field(default_factory=lambda: [
        (0., 0., 60/255, 1.),           # 深蓝
        (0., 0., 0., 1.),               # 黑色
        (1., 1., 1., 1.),               # 白色
        (47/255, 0., 80/255, 1.),       # 深紫
        (0., 0., 60/255, 1.),           # 深蓝
    ])
    data_themes_rgb: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (229/255, 248/255, 1.),         # 亮蓝
        (1., 1., 1.),                   # 白色
        (0., 0., 0.),                   # 黑色
        (255/255, 192/255, 203/255),    # 粉色
        (255/255, 192/255, 203/255),    # 粉色
    ])
    default_theme_index: int = 0


@dataclass
class VisualizationConfig:
    """3D visualization and rendering settings."""
    data_height_3d: int = 400
    default_orientation: str = "up"  # "up" or "down"
    default_pos_type: str = "Fibonacci"  # "Fibonacci", "circle", "arc"
    visualize_piano: bool = True
    
    # View settings
    default_elev: float = 37.0
    default_azim_angle: float = 30.0
    default_azim_speed: float = 1.0
    window_opacity: float = 1.0
    
    # Bubble position generation
    num_positions: int = 120
    inner_radius: float = 2.0
    outer_radius: float = 36.0
    
    # Animation settings
    pause_duration: float = 0.002
    view_transition_rate: float = 0.1
    

@dataclass
class PhysicsConfig:
    """Bubble physics and simulation parameters."""
    # Volume and scaling
    max_volume_up: int = 500
    max_volume_down: int = 200
    scaler_increment: float = 0.01
    variance_threshold: float = 6.0
    final_volume_history_size: int = 30
    
    # Bubble movement
    base_rise_speed_up: float = 5.0
    max_progress_bonus: float = 10.0
    thickness_speed_factor: float = 0.1
    max_thickness_bonus: float = 8.0
    base_rise_speed_down: float = 6.0
    jitter_range: int = 3  # -3 to +4 for down mode
    max_rise_speed: float = 18.0
    
    # Size adjustments
    size_increase_factor: float = 0.05
    
    # Bubble merging
    merge_interval: int = 5  # Check merging every N layers
    grid_cell_size: int = 3
    adjacent_grid_threshold: int = 1
    merge_distance_factor: float = 2.0
    
    # Snow effects (for down orientation)
    max_snow_stack_height: int = 5
    max_snow_ttl: int = 400
    snow_size_min: float = 10.0
    snow_size_max: float = 40.0
    snow_opacity_min: float = 0.2
    snow_opacity_max: float = 0.8
    

@dataclass
class AudioConfig:
    """Audio playback and MIDI processing settings."""
    # Pygame mixer settings
    frequency: int = 44100
    size: int = -16
    channels: int = 2
    mixer_channels: int = 2
    
    # Timing and delays
    wav_delay_ms: int = 300
    mp3_delay_ms: int = 100
    
    # MIDI processing
    piano_key_count: int = 88  # Standard piano keys
    midi_note_min: int = 21   # A0
    midi_note_max: int = 108  # C8
    pattern_key_count: int = 120  # For pattern generation
    
    # Volume processing
    total_volumes_maxlen: int = 240
    zero_pattern_interval: int = 2
    

@dataclass
class UIConfig:
    """User interface settings."""
    # Window dimensions
    default_figure_size: Tuple[float, float] = (5.0, 6.0)
    window_title: str = "🎼Musical Bubble Column!🎹"
    
    # Loading dialog
    loading_dialog_size: Tuple[int, int] = (600, 150)
    loading_smooth_fps: int = 30
    loading_transition_duration: float = 1.0
    
    # File dialog
    file_dialog_size: Tuple[int, int] = (800, 800)
    file_dialog_offset_x: int = 50
    
    # Progress bar and UI effects
    icon_y_offset: int = 20
    shadow_offset: int = 3
    shadow_blur_radius: int = 10
    corner_radius_factor: float = 0.2
    
    # Slider settings
    elev_slider_pos: List[float] = field(default_factory=lambda: [0.9, 0.1, 0.03, 0.8])
    azim_slider_pos: List[float] = field(default_factory=lambda: [0.2, 0.02, 0.6, 0.03])
    azim_slider_pos_no_piano: List[float] = field(default_factory=lambda: [0.2, 0.0, 0.6, 0.03])
    
    # Piano visualization
    piano_xlim: Tuple[int, int] = (0, 52)  # 52 white keys
    piano_ylim: Tuple[int, int] = (0, 1)
    white_key_width: float = 1.0
    black_key_width: float = 0.55
    black_key_height: float = 0.6
    black_key_y_offset: float = 0.4
    black_key_x_offset: float = 0.275
    

@dataclass
class PerformanceConfig:
    """Performance optimization settings."""
    # GPU/CPU selection (from memory about GPU performance)
    auto_gpu_selection: bool = True
    gpu_threshold_elements: int = 1000  # Switch to GPU above this threshold
    performance_history_size: int = 10
    
    # Rendering optimization
    particle_count_light: int = 200  # For light effects
    emphasis_bubble_layers: int = 3  # Number of emphasis layers
    emphasis_bubble_opacities: List[float] = field(default_factory=lambda: [0.8, 0.3, 0.1])
    emphasis_bubble_sizes: List[float] = field(default_factory=lambda: [100.0, 250.0, 500.0])
    
    # Memory and caching
    numba_cache: bool = True
    numba_nogil: bool = True
    numba_fastmath: bool = True
    

@dataclass
class AppConfig:
    """Complete application configuration."""
    file_paths: FilePathsConfig = field(default_factory=FilePathsConfig)
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    physics: PhysicsConfig = field(default_factory=PhysicsConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    def save_to_file(self, filepath: str = None) -> None:
        """Save configuration to JSON file."""
        if filepath is None:
            filepath = self.file_paths.config_file
        
        config_dict = self._to_dict()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
    
    def _to_dict(self) -> dict:
        """Convert config to dictionary for JSON serialization."""
        result = {}
        for field_name, field_value in self.__dict__.items():
            if hasattr(field_value, '__dict__'):
                result[field_name] = field_value.__dict__
            else:
                result[field_name] = field_value
        return result
    
    @classmethod
    def load_from_file(cls, filepath: str = None) -> 'AppConfig':
        """Load configuration from JSON file."""
        config = cls()  # Start with defaults
        
        if filepath is None:
            filepath = config.file_paths.config_file
        
        if os_path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)
                
                # Update config with loaded values
                config._from_dict(config_dict)
            except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                print(f"Warning: Could not load config from {filepath}: {e}")
                print("Using default configuration.")
        
        return config
    
    def _from_dict(self, config_dict: dict) -> None:
        """Update config from dictionary."""
        for section_name, section_data in config_dict.items():
            if hasattr(self, section_name) and isinstance(section_data, dict):
                section_obj = getattr(self, section_name)
                for key, value in section_data.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)


# Global configuration instance
_global_config: AppConfig = None


def load_config(filepath: str = None) -> AppConfig:
    """Load and return the global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = AppConfig.load_from_file(filepath)
    return _global_config


def get_config() -> AppConfig:
    """Get the current global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = load_config()
    return _global_config


def reload_config(filepath: str = None) -> AppConfig:
    """Force reload the global configuration."""
    global _global_config
    _global_config = AppConfig.load_from_file(filepath)
    return _global_config


# Backward compatibility - expose commonly used values at module level
def _get_compat_values():
    """Get backward compatibility values from current config."""
    config = get_config()
    return {
        'PATH_TO_ICON': config.file_paths.icon_path,
        'DEFAULT_MIDI_PATH': config.file_paths.default_midi_path,
        'WAV_FILE_PATH': config.file_paths.default_wav_path,
        'fig_themes_rgba': config.theme.fig_themes_rgba,
        'data_themes_rgb': config.theme.data_themes_rgb,
        'data_height_3d': config.visualization.data_height_3d,
    }

# Set up backward compatibility
_compat = _get_compat_values()
PATH_TO_ICON = _compat['PATH_TO_ICON']
DEFAULT_MIDI_PATH = _compat['DEFAULT_MIDI_PATH']
WAV_FILE_PATH = _compat['WAV_FILE_PATH']
fig_themes_rgba = _compat['fig_themes_rgba']
data_themes_rgb = _compat['data_themes_rgb']
data_height_3d = _compat['data_height_3d']
