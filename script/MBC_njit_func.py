from numba import njit
import numpy as np


@njit
def add_pattern(bit_array, volumes, average_volume, position_list, final_volume, final_volume_index, scaler, thickness_list, pattern_data, pattern_data_thickness, orientation):
    variances = []
    active_indices = np.where(bit_array)[0]  # 获取活动索引
    for i in active_indices:
        x_center, y_center = position_list[i]
        volume_factor = ((volumes[i] - average_volume) / average_volume) if average_volume else 0
        final_volume_piece = min(500, (1 + scaler * volume_factor) ** 5)
        final_volume[final_volume_index] = final_volume_piece
        final_volume_index = (final_volume_index + 1) % 30
        if final_volume_index == 0:
            variance = np.var(final_volume)
            variances.append(variance)

        thickness_list[i] = int(final_volume_piece)
        total_thickness = thickness_list[i] + (1 * (119 - i)) // 119
        pattern_data[-1 if orientation == "down" else 0, x_center, y_center] = 1
        pattern_data_thickness[-1 if orientation == "down" else 0, x_center, y_center] = total_thickness + 1

    return variances

@njit
def calculate_bubble(pattern_data, pattern_data_thickness, data_height):
    pattern_data_temp = np.zeros(pattern_data.shape, dtype=np.float32)
    pattern_data_thickness_temp = np.zeros(pattern_data_thickness.shape, dtype=np.float32)

    # 使用向量化操作处理气泡上升
    for layer in range(0, data_height - 1):
        x, y = np.nonzero(pattern_data[layer])
        if x.size == 0:
            continue
        
        thickness = pattern_data_thickness[layer]
        max_x = pattern_data_temp.shape[1] - 1
        max_y = pattern_data_temp.shape[2] - 1
        
        # 批量计算上升速度
        th_values = np.zeros(x.size, dtype=np.float32)
        for i in range(x.size):
            th_values[i] = thickness[x[i], y[i]]
            
        rise_speeds = 5 + np.minimum(10 * (layer / (3 * data_height / 4)), 10) + np.minimum(th_values * 0.1, 8)
        rise_speeds = np.clip(rise_speeds, 0, 18)
        target_layers = np.minimum(layer + rise_speeds.astype(np.int32), data_height - 1)
        
        # 批量生成抖动
        jitter_x = np.random.randint(-1, 2, size=x.size)
        jitter_y = np.random.randint(-1, 2, size=y.size)
        target_x = np.clip(x + jitter_x, 0, max_x)
        target_y = np.clip(y + jitter_y, 0, max_y)
        
        # 更新气泡位置和厚度
        for i in range(len(x)):
            tl, tx, ty = target_layers[i], target_x[i], target_y[i]
            th = th_values[i]
            
            if pattern_data_temp[tl, tx, ty] == 1:
                pattern_data_thickness_temp[tl, tx, ty] += th
            else:
                pattern_data_thickness_temp[tl, tx, ty] = th
                pattern_data_temp[tl, tx, ty] = 1
            
            # 根据高度调整气泡大小
            size_increase = 1 + (tl / data_height) * 0.05
            pattern_data_thickness_temp[tl, tx, ty] *= size_increase

    # 优化气泡合并逻辑：每隔几层才进行合并检查
    merge_interval = 5  # 每隔5层检查一次合并
    for layer in range(0, data_height, merge_interval):
        x, y = np.nonzero(pattern_data_temp[layer])
        if len(x) < 2:  # 如果气泡数量太少，跳过合并
            continue
            
        # 使用网格法减少需要检查的气泡对
        grid = np.zeros((pattern_data.shape[1] // 3 + 1, pattern_data.shape[2] // 3 + 1), dtype=np.int32)
        grid_points = []
        for i in range(len(x)):
            grid_x = x[i] // 3
            grid_y = y[i] // 3
            grid[grid_x, grid_y] += 1
            grid_points.append((grid_x, grid_y, i))
        
        # 只检查相邻网格中的气泡
        for i in range(len(grid_points)):
            gx, gy, idx = grid_points[i]
            for j in range(i + 1, len(grid_points)):
                gx2, gy2, idx2 = grid_points[j]
                
                # 只检查相邻网格
                if abs(gx - gx2) <= 1 and abs(gy - gy2) <= 1:
                    distance = np.sqrt((x[idx] - x[idx2]) ** 2 + (y[idx] - y[idx2]) ** 2)
                    if 2 * distance < np.sqrt(pattern_data_thickness_temp[layer, x[idx], y[idx]] + 
                                           pattern_data_thickness_temp[layer, x[idx2], y[idx2]]):
                        # 合并气泡
                        new_x = (x[idx] + x[idx2]) // 2
                        new_y = (y[idx] + y[idx2]) // 2
                        pattern_data_temp[layer, new_x, new_y] = 1
                        pattern_data_thickness_temp[layer, new_x, new_y] = np.minimum(
                            500, 
                            pattern_data_thickness_temp[layer, x[idx], y[idx]] + 
                            pattern_data_thickness_temp[layer, x[idx2], y[idx2]]
                        )
                        pattern_data_temp[layer, x[idx], y[idx]] = 0
                        pattern_data_temp[layer, x[idx2], y[idx2]] = 0
                        pattern_data_thickness_temp[layer, x[idx], y[idx]] = 0
                        pattern_data_thickness_temp[layer, x[idx2], y[idx2]] = 0

    return pattern_data_temp, pattern_data_thickness_temp