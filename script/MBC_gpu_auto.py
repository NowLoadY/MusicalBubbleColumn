"""
Automatic GPU Acceleration Module
Transparently replaces core functions with GPU versions when available
"""

import torch
import numpy as np
import time

# Global variables for GPU state
_gpu_accelerator = None
_original_functions = {}
_gpu_enabled = False

def check_gpu_availability():
    """Check if GPU acceleration is available"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False

def initialize_gpu_acceleration():
    """Initialize GPU acceleration if available"""
    global _gpu_accelerator, _gpu_enabled
    
    if not check_gpu_availability():
        print("⚠️ GPU not available, using CPU")
        return False
    
    try:
        from MBC_gpu_core import GPUPatternProcessor
        _gpu_accelerator = GPUPatternProcessor(use_gpu=True)
        _gpu_enabled = True
        
        print("🚀 GPU Acceleration Initialized")
        print(f"   Device: {torch.cuda.get_device_name(0)}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB")
        return True
    except Exception as e:
        print(f"⚠️ GPU initialization failed: {e}")
        _gpu_enabled = False
        return False

def gpu_calculate_bubble(pattern_data, pattern_data_thickness, data_height, orientation="up"):
    """GPU-accelerated bubble calculation with automatic fallback"""
    global _gpu_accelerator, _gpu_enabled
    
    if _gpu_enabled and _gpu_accelerator is not None:
        try:
            return _gpu_accelerator.calculate_bubble_gpu(
                pattern_data, pattern_data_thickness, data_height, orientation
            )
        except Exception as e:
            print(f"GPU calculation failed, falling back to CPU: {e}")
            _gpu_enabled = False
    
    # Fallback to original CPU function
    import MBC_njit_func
    return MBC_njit_func.calculate_bubble(pattern_data, pattern_data_thickness, data_height, orientation)

def gpu_add_pattern(bit_array, volumes, average_volume, position_list,
                   final_volume, final_volume_index, scaler, thickness_list,
                   pattern_data, pattern_data_thickness, orientation):
    """GPU-accelerated pattern addition with automatic fallback"""
    global _gpu_accelerator, _gpu_enabled
    
    if _gpu_enabled and _gpu_accelerator is not None:
        try:
            return _gpu_accelerator.add_pattern_gpu(
                bit_array, volumes, average_volume, position_list,
                final_volume, final_volume_index, scaler, thickness_list,
                pattern_data, pattern_data_thickness, orientation
            )
        except Exception as e:
            print(f"GPU pattern addition failed, falling back to CPU: {e}")
            _gpu_enabled = False
    
    # Fallback to original CPU function
    import MBC_njit_func
    return MBC_njit_func.add_pattern(
        bit_array, volumes, average_volume, position_list,
        final_volume, final_volume_index, scaler, thickness_list,
        pattern_data, pattern_data_thickness, orientation
    )

def patch_calculation_functions():
    """Transparently patch calculation functions with GPU versions"""
    global _original_functions
    
    try:
        import MBC_njit_func
        
        # Backup original functions
        _original_functions['calculate_bubble'] = MBC_njit_func.calculate_bubble
        _original_functions['add_pattern'] = MBC_njit_func.add_pattern
        
        # Replace with GPU-enabled versions
        MBC_njit_func.calculate_bubble = gpu_calculate_bubble
        MBC_njit_func.add_pattern = gpu_add_pattern
        
        print("✅ Core functions patched with GPU acceleration")
        return True
        
    except Exception as e:
        print(f"⚠️ Failed to patch functions: {e}")
        return False

def restore_original_functions():
    """Restore original CPU functions"""
    global _original_functions
    
    try:
        import MBC_njit_func
        
        if 'calculate_bubble' in _original_functions:
            MBC_njit_func.calculate_bubble = _original_functions['calculate_bubble']
        if 'add_pattern' in _original_functions:
            MBC_njit_func.add_pattern = _original_functions['add_pattern']
            
        print("✅ Original functions restored")
        return True
    except Exception as e:
        print(f"⚠️ Failed to restore functions: {e}")
        return False

def enable_auto_gpu_acceleration():
    """
    Enable automatic GPU acceleration
    Call this once at program start
    """
    print("\n" + "="*50)
    print("Musical Bubble Column - Auto GPU Acceleration")
    print("="*50)
    
    # Initialize GPU
    gpu_success = initialize_gpu_acceleration()
    
    if gpu_success:
        # Patch functions
        patch_success = patch_calculation_functions()
        if patch_success:
            print("🚀 GPU acceleration enabled automatically")
            print("   Bubble calculation: GPU")
            print("   3D rendering: CPU (optimal for current data)")
        else:
            print("⚠️ GPU available but patching failed, using CPU")
    else:
        print("⚠️ GPU not available, using CPU")
    
    print("="*50 + "\n")
    return gpu_success

def get_acceleration_status():
    """Get current acceleration status"""
    global _gpu_enabled
    return {
        'gpu_available': check_gpu_availability(),
        'gpu_enabled': _gpu_enabled,
        'device': torch.cuda.get_device_name(0) if _gpu_enabled else 'CPU'
    }


if __name__ == "__main__":
    # Test the auto GPU acceleration
    print("Testing Auto GPU Acceleration...")
    
    success = enable_auto_gpu_acceleration()
    
    if success:
        print("GPU acceleration test successful!")
        print(get_acceleration_status())
    else:
        print("Running in CPU mode")
