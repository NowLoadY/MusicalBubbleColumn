#!/usr/bin/env python3
"""
Example script to demonstrate the centralized configuration system.
Shows how to load, modify, and save configuration settings.
"""

from MBC_config import get_config, load_config, reload_config

def main():
    """Demonstrate configuration system usage."""
    print("=== Musical Bubble Column Configuration System Demo ===\n")
    
    # Load default configuration
    print("1. Loading default configuration...")
    config = get_config()
    
    print(f"   - Default orientation: {config.visualization.default_orientation}")
    print(f"   - Data height: {config.visualization.data_height_3d}")
    print(f"   - Audio frequency: {config.audio.frequency}")
    print(f"   - Window title: {config.ui.window_title}")
    print(f"   - Max bubble volume (up): {config.physics.max_volume_up}")
    print(f"   - GPU auto-selection: {config.performance.auto_gpu_selection}")
    
    # Demonstrate configuration modification
    print("\n2. Modifying configuration...")
    config.visualization.default_orientation = "down"
    config.physics.max_volume_up = 750
    config.performance.auto_gpu_selection = False
    
    print(f"   - Changed orientation to: {config.visualization.default_orientation}")
    print(f"   - Changed max volume to: {config.physics.max_volume_up}")
    print(f"   - Disabled GPU auto-selection: {config.performance.auto_gpu_selection}")
    
    # Save configuration to file
    print("\n3. Saving configuration to file...")
    config.save_to_file("example_settings.json")
    print("   - Configuration saved to: example_settings.json")
    
    # Load configuration from file
    print("\n4. Loading configuration from file...")
    loaded_config = load_config("example_settings.json")
    print(f"   - Loaded orientation: {loaded_config.visualization.default_orientation}")
    print(f"   - Loaded max volume: {loaded_config.physics.max_volume_up}")
    print(f"   - Loaded GPU setting: {loaded_config.performance.auto_gpu_selection}")
    
    # Demonstrate structured access
    print("\n5. Configuration structure:")
    print("   Config sections:")
    print(f"     - file_paths: {type(config.file_paths).__name__}")
    print(f"     - theme: {type(config.theme).__name__}")
    print(f"     - visualization: {type(config.visualization).__name__}")
    print(f"     - physics: {type(config.physics).__name__}")
    print(f"     - audio: {type(config.audio).__name__}")
    print(f"     - ui: {type(config.ui).__name__}")
    print(f"     - performance: {type(config.performance).__name__}")
    
    # Performance settings example (referencing GPU performance memory)
    print("\n6. Performance optimization settings:")
    print(f"   - GPU threshold elements: {config.performance.gpu_threshold_elements}")
    print(f"   - Performance history size: {config.performance.performance_history_size}")
    print(f"   - Numba cache enabled: {config.performance.numba_cache}")
    
    # Physics settings example (referencing bubble physics memory)
    print("\n7. Physics simulation settings:")
    print(f"   - Base rise speed (up): {config.physics.base_rise_speed_up}")
    print(f"   - Max rise speed: {config.physics.max_rise_speed}")
    print(f"   - Merge interval: {config.physics.merge_interval}")
    print(f"   - Bubble size increase factor: {config.physics.size_increase_factor}")
    
    print("\n=== Configuration Demo Complete ===")

if __name__ == "__main__":
    main()
