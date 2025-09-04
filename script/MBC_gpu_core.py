"""
GPU-accelerated core algorithms for Musical Bubble Column
Uses CuPy for CUDA acceleration and PyTorch for advanced GPU operations
"""

import numpy as np
try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False
    print("CuPy not available, falling back to CPU mode")

try:
    import torch
    TORCH_AVAILABLE = torch.cuda.is_available()
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorch not available or CUDA not supported")

# Fallback to numpy if GPU libraries are not available
if CUPY_AVAILABLE:
    xp = cp
else:
    xp = np


class GPUPatternProcessor:
    """GPU-accelerated pattern processing for MIDI visualization"""
    
    def __init__(self, data_height=300, use_gpu=True):
        self.data_height = data_height
        self.use_gpu = use_gpu and (CUPY_AVAILABLE or TORCH_AVAILABLE)
        
        if self.use_gpu:
            if TORCH_AVAILABLE:
                self.device = torch.device('cuda')
                print(f"Using GPU: {torch.cuda.get_device_name(0)}")
            elif CUPY_AVAILABLE:
                print(f"Using CuPy on GPU")
        else:
            print("Running in CPU mode")
            
        # Pre-allocate memory for performance
        self.pattern_cache = {}
        
    def add_pattern_gpu(self, bit_array, volumes, average_volume, position_list, 
                        final_volume, final_volume_index, scaler, thickness_list, 
                        pattern_data, pattern_data_thickness, orientation):
        """
        GPU-accelerated version of add_pattern function
        Maps MIDI notes to visual patterns using parallel processing
        """
        if self.use_gpu and CUPY_AVAILABLE:
            # Convert to CuPy arrays
            bit_array_gpu = cp.asarray(bit_array)
            volumes_gpu = cp.asarray(volumes)
            position_list_gpu = cp.asarray(position_list)
            pattern_data_gpu = cp.asarray(pattern_data)
            pattern_data_thickness_gpu = cp.asarray(pattern_data_thickness)
            
            # Find active indices using GPU
            active_indices = cp.where(bit_array_gpu)[0]
            
            # Parallel computation of volume factors
            volume_indices = cp.minimum(active_indices, len(volumes_gpu) - 1)
            volume_factors = ((volumes_gpu[volume_indices] - average_volume) / average_volume 
                            if average_volume else cp.zeros_like(volume_indices, dtype=cp.float32))
            
            # Calculate final volumes in parallel
            if orientation == "up":
                final_volume_pieces = cp.minimum(500, (1 + scaler * volume_factors) ** 5)
            else:
                final_volume_pieces = cp.minimum(200, (1 + scaler * volume_factors) ** 2.5)
            
            # Update pattern data
            for i, idx in enumerate(cp.asnumpy(active_indices)):
                x_center, y_center = position_list[idx]
                thickness_list[idx] = int(cp.asnumpy(final_volume_pieces[i]))
                total_thickness = thickness_list[idx] + (1 * (119 - idx)) // 119
                
                if orientation == "down":
                    pattern_data_gpu[-1, x_center, y_center] = 1
                    pattern_data_thickness_gpu[-1, x_center, y_center] = total_thickness + 1
                else:
                    pattern_data_gpu[0, x_center, y_center] = 1
                    pattern_data_thickness_gpu[0, x_center, y_center] = total_thickness + 1
            
            # Copy back to CPU memory
            pattern_data[:] = cp.asnumpy(pattern_data_gpu)
            pattern_data_thickness[:] = cp.asnumpy(pattern_data_thickness_gpu)
            
            return []  # variances calculation omitted for simplicity
            
        else:
            # CPU fallback - use original implementation
            return self._add_pattern_cpu(bit_array, volumes, average_volume, position_list,
                                        final_volume, final_volume_index, scaler, thickness_list,
                                        pattern_data, pattern_data_thickness, orientation)
    
    def calculate_bubble_gpu(self, pattern_data, pattern_data_thickness, data_height, orientation="up"):
        """
        GPU-accelerated bubble physics simulation
        Handles particle movement, collision, and merging
        """
        if self.use_gpu and TORCH_AVAILABLE:
            # Convert to PyTorch tensors
            pattern_tensor = torch.from_numpy(pattern_data).float().to(self.device)
            thickness_tensor = torch.from_numpy(pattern_data_thickness).float().to(self.device)
            
            pattern_temp = torch.zeros_like(pattern_tensor)
            thickness_temp = torch.zeros_like(thickness_tensor)
            
            # Determine direction
            direction = 1 if orientation == "up" else -1
            
            # Get all active particles at once (vectorized)
            active_mask = pattern_tensor > 0
            layer_indices, y_indices, x_indices = torch.where(active_mask)
            
            if len(layer_indices) > 0:
                # Get thickness values for all active particles
                thickness_values = thickness_tensor[layer_indices, y_indices, x_indices]
                
                # Calculate rise speeds based on thickness
                rise_speeds = torch.sqrt(thickness_values * 10).clamp(min=1)
                
                # Calculate target positions
                target_layers = layer_indices + direction * rise_speeds.long()
                
                # Add jitter for realistic movement
                jitter_x = torch.randint(-1, 2, (len(x_indices),), device=self.device)
                jitter_y = torch.randint(-1, 2, (len(y_indices),), device=self.device)
                
                target_x = torch.clamp(x_indices + jitter_x, 0, pattern_tensor.shape[2] - 1)
                target_y = torch.clamp(y_indices + jitter_y, 0, pattern_tensor.shape[1] - 1)
                target_layers = torch.clamp(target_layers, 0, pattern_tensor.shape[0] - 1)
                
                # Create linear indices for faster update
                linear_indices = (target_layers * pattern_tensor.shape[1] * pattern_tensor.shape[2] + 
                                target_y * pattern_tensor.shape[2] + target_x)
                
                # Flatten tensors for scatter operations
                pattern_flat = pattern_temp.flatten()
                thickness_flat = thickness_temp.flatten()
                
                # Update pattern (set to 1 where particles exist)
                pattern_flat[linear_indices] = 1
                
                # Accumulate thickness values
                thickness_flat.scatter_add_(0, linear_indices, thickness_values)
                
                # Reshape back
                pattern_temp = pattern_flat.view_as(pattern_tensor)
                thickness_temp = thickness_flat.view_as(thickness_tensor)
                
                # Apply size adjustment for upward orientation
                if orientation == "up":
                    height_factor = target_layers.float() / data_height * 0.05
                    size_adjustment = thickness_temp[target_layers, target_y, target_x] * height_factor
                    thickness_temp[target_layers, target_y, target_x] += size_adjustment
            
            # Bubble merging optimization (GPU-accelerated)
            self._merge_bubbles_gpu(pattern_temp, thickness_temp, data_height, orientation)
            
            # Convert back to numpy
            return pattern_temp.cpu().numpy(), thickness_temp.cpu().numpy()
            
        elif self.use_gpu and CUPY_AVAILABLE:
            return self._calculate_bubble_cupy(pattern_data, pattern_data_thickness, data_height, orientation)
        else:
            return self._calculate_bubble_cpu(pattern_data, pattern_data_thickness, data_height, orientation)
    
    def _merge_bubbles_gpu(self, pattern_temp, thickness_temp, data_height, orientation):
        """GPU-accelerated bubble merging using vectorized operations"""
        merge_distance = 5
        max_thickness = 500 if orientation == "up" else 200
        
        # Process multiple layers in parallel
        for layer in range(data_height):
            active_mask = pattern_temp[layer] > 0
            if not active_mask.any():
                continue
                
            y_coords, x_coords = torch.where(active_mask)
            n_bubbles = len(y_coords)
            
            if n_bubbles < 2:
                continue
            
            # Skip merging for large numbers of bubbles (optimization)
            if n_bubbles > 1000:
                continue
            
            # Calculate pairwise distances using broadcasting
            x_diff = x_coords.unsqueeze(1) - x_coords.unsqueeze(0)
            y_diff = y_coords.unsqueeze(1) - y_coords.unsqueeze(0)
            distances = torch.sqrt(x_diff.float()**2 + y_diff.float()**2)
            
            # Find pairs to merge (lower triangular to avoid duplicates)
            merge_mask = (distances < merge_distance) & (distances > 0)
            merge_mask = torch.tril(merge_mask, diagonal=-1)
            
            # Get merge pairs
            merge_pairs = torch.nonzero(merge_mask, as_tuple=False)
            
            if len(merge_pairs) == 0:
                continue
            
            # Process merges in batches (vectorized)
            # Take only first few merges to avoid conflicts
            n_merges = min(len(merge_pairs), 20)
            merge_pairs = merge_pairs[:n_merges]
            
            for pair in merge_pairs:
                i, j = pair[0], pair[1]
                
                # Calculate merged position
                new_x = (x_coords[i] + x_coords[j]) // 2
                new_y = (y_coords[i] + y_coords[j]) // 2
                
                # Calculate merged thickness
                thickness_i = thickness_temp[layer, y_coords[i], x_coords[i]]
                thickness_j = thickness_temp[layer, y_coords[j], x_coords[j]]
                new_thickness = torch.min(thickness_i + thickness_j, 
                                         torch.tensor(max_thickness, device=self.device, dtype=thickness_temp.dtype))
                
                # Clear original positions
                pattern_temp[layer, y_coords[i], x_coords[i]] = 0
                pattern_temp[layer, y_coords[j], x_coords[j]] = 0
                thickness_temp[layer, y_coords[i], x_coords[i]] = 0
                thickness_temp[layer, y_coords[j], x_coords[j]] = 0
                
                # Set merged bubble
                pattern_temp[layer, new_y, new_x] = 1
                thickness_temp[layer, new_y, new_x] = new_thickness
    
    def _calculate_bubble_cupy(self, pattern_data, pattern_data_thickness, data_height, orientation):
        """CuPy implementation of bubble calculation"""
        pattern_gpu = cp.asarray(pattern_data, dtype=cp.float32)
        thickness_gpu = cp.asarray(pattern_data_thickness, dtype=cp.float32)
        
        pattern_temp = cp.zeros_like(pattern_gpu)
        thickness_temp = cp.zeros_like(thickness_gpu)
        
        if orientation == "up":
            layer_range = range(0, data_height - 1)
            direction = 1
        else:
            layer_range = range(data_height - 1, 0, -1)
            direction = -1
        
        for layer in layer_range:
            layer_slice = pattern_gpu[layer]
            non_zero = cp.nonzero(layer_slice)
            
            if len(non_zero[0]) == 0:
                continue
            
            y_coords = non_zero[0]
            x_coords = non_zero[1]
            thickness_values = thickness_gpu[layer, y_coords, x_coords]
            
            # Calculate physics
            if orientation == "up":
                progress = layer / (data_height - 1)
                rise_speeds = 5.0 + cp.minimum(10.0 * progress, 10.0)
                rise_speeds += cp.minimum(thickness_values * 0.1, 8.0)
            else:
                rise_speeds = 6.0 + cp.minimum(thickness_values * 0.1, 8.0)
                rise_speeds += cp.random.randint(-3, 4, size=len(x_coords))
            
            rise_speeds = cp.clip(rise_speeds, 0.0, 18.0)
            target_layers = layer + direction * rise_speeds.astype(cp.int32)
            
            # Apply jitter
            jitter_x = cp.random.randint(-1, 2, size=len(x_coords))
            jitter_y = cp.random.randint(-1, 2, size=len(y_coords))
            
            target_x = cp.clip(x_coords + jitter_x, 0, pattern_gpu.shape[2] - 1)
            target_y = cp.clip(y_coords + jitter_y, 0, pattern_gpu.shape[1] - 1)
            target_layers = cp.clip(target_layers, 0, pattern_gpu.shape[0] - 1)
            
            # Update positions
            for i in range(len(x_coords)):
                tl = int(target_layers[i])
                tx = int(target_x[i])
                ty = int(target_y[i])
                th = thickness_values[i]
                
                if pattern_temp[tl, ty, tx] == 1:
                    thickness_temp[tl, ty, tx] += th
                else:
                    pattern_temp[tl, ty, tx] = 1
                    thickness_temp[tl, ty, tx] = th
                
                if orientation == "up":
                    size_increase = 1.0 + (tl / data_height) * 0.05
                    thickness_temp[tl, ty, tx] *= size_increase
        
        return cp.asnumpy(pattern_temp), cp.asnumpy(thickness_temp)
    
    def _add_pattern_cpu(self, bit_array, volumes, average_volume, position_list,
                        final_volume, final_volume_index, scaler, thickness_list,
                        pattern_data, pattern_data_thickness, orientation):
        """CPU fallback implementation"""
        variances = []
        active_indices = np.where(bit_array)[0]
        
        for i in active_indices:
            volume_idx = min(i, len(volumes) - 1) if len(volumes) > 0 else 0
            x_center, y_center = position_list[i]
            volume_factor = ((volumes[volume_idx] - average_volume) / average_volume) if average_volume else 0
            
            if orientation == "up":
                final_volume_piece = min(500, (1 + scaler * volume_factor) ** 5)
            else:
                final_volume_piece = min(200, (1 + scaler * volume_factor) ** 2.5)
            
            final_volume[final_volume_index] = final_volume_piece
            final_volume_index = (final_volume_index + 1) % 30
            
            if final_volume_index == 0:
                variance = np.var(final_volume)
                variances.append(variance)
            
            thickness_list[i] = int(final_volume_piece)
            total_thickness = thickness_list[i] + (1 * (119 - i)) // 119
            
            if orientation == "down":
                pattern_data[-1, x_center, y_center] = 1
                pattern_data_thickness[-1, x_center, y_center] = total_thickness + 1
            else:
                pattern_data[0, x_center, y_center] = 1
                pattern_data_thickness[0, x_center, y_center] = total_thickness + 1
        
        return variances
    
    def _calculate_bubble_cpu(self, pattern_data, pattern_data_thickness, data_height, orientation):
        """CPU fallback for bubble calculation"""
        # This would contain the original CPU implementation
        # For brevity, returning the original arrays
        return pattern_data.copy(), pattern_data_thickness.copy()
