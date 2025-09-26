from numba import njit, prange
import numpy as np


@njit
def add_pattern(bit_array, volumes, average_volume, position_list, final_volume, final_volume_index, scaler, thickness_list, pattern_data, pattern_data_thickness, orientation):
    variances = []
    active_indices = np.where(bit_array)[0]  # 获取活动索引
    for i in active_indices:
        # Handle case when volumes array has a different size than bit_array
        volume_idx = min(i, len(volumes) - 1) if len(volumes) > 0 else 0
        x_center, y_center = position_list[i]
        volume_factor = ((volumes[volume_idx] - average_volume) / average_volume) if average_volume else 0
        final_volume_piece = min((500 if orientation == "up" else 200), (1 + scaler * volume_factor) ** (5 if orientation == "up" else 2.5))
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
def calculate_bubble(pattern_data, pattern_data_thickness, data_height, orientation="up"):
    pattern_data_temp = np.zeros(pattern_data.shape, dtype=np.float32)
    pattern_data_thickness_temp = np.zeros(pattern_data_thickness.shape, dtype=np.float32)

    # 遍历方向
    if orientation == "up":
        layer_range = range(0, data_height - 1)
        direction = 1
    else:
        layer_range = range(data_height - 1, 0, -1)
        direction = -1

    for layer in layer_range:
        x, y = np.nonzero(pattern_data[layer])
        if x.size == 0:
            continue

        thickness = pattern_data_thickness[layer]
        max_x = pattern_data_temp.shape[1] - 1
        max_y = pattern_data_temp.shape[2] - 1

        # 厚度值
        th_values = np.empty(x.size, dtype=np.float32)
        for i in range(x.size):
            th_values[i] = thickness[x[i], y[i]]

        # 进度因子
        if orientation == "up":
            progress = layer / (data_height - 1)
            rise_speeds = 5.0 + np.minimum(10.0 * progress, 10.0) + np.minimum(th_values * 0.1, 8.0)
        else:
            rise_speeds = 6.0 + np.minimum(th_values * 0.1, 8.0) + np.random.randint(-3,4,size=x.size)

        # 计算上升（或下降）速度
        rise_speeds = np.maximum(0.0, np.minimum(rise_speeds, 18.0))

        # 目标层
        target_layers = layer + direction * rise_speeds.astype(np.int32)

        # 抖动
        jitter_x = np.random.randint(-1, 2, size=x.size)
        jitter_y = np.random.randint(-1, 2, size=y.size)
        target_x = np.maximum(0, np.minimum(x + jitter_x, max_x))
        target_y = np.maximum(0, np.minimum(y + jitter_y, max_y))

        # 写入目标层
        for i in range(len(x)):
            tl = target_layers[i]
            tx = target_x[i]
            ty = target_y[i]
            th = th_values[i]

            # 向下方向：越界气泡强制落在最后一层
            if orientation == "down" and tl < 0:
                tl = pattern_data.shape[0] - 1

            # 边界保护
            tl = max(0, min(tl, pattern_data.shape[0] - 1))

            # 写入
            if pattern_data_temp[tl, tx, ty] == 1:
                pattern_data_thickness_temp[tl, tx, ty] += th
            else:
                pattern_data_temp[tl, tx, ty] = 1
                pattern_data_thickness_temp[tl, tx, ty] = th

            # 随高度调整气泡大小
            if orientation == "up":
                size_increase = 1.0 + (tl / data_height) * 0.05
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
                            (500 if orientation == "up" else 200), 
                            pattern_data_thickness_temp[layer, x[idx], y[idx]] + 
                            pattern_data_thickness_temp[layer, x[idx2], y[idx2]]
                        )
                        pattern_data_temp[layer, x[idx], y[idx]] = 0
                        pattern_data_temp[layer, x[idx2], y[idx2]] = 0
                        pattern_data_thickness_temp[layer, x[idx], y[idx]] = 0
                        pattern_data_thickness_temp[layer, x[idx2], y[idx2]] = 0

    return pattern_data_temp, pattern_data_thickness_temp


@njit('int32[:,:](int32[:,:], int32)', cache=True, nogil=True)
def _unique_2d(arr, width):
    """
    arr: (N,2) int32  坐标 (x,y)
    width: int32      图像宽度，用于 key = y*width + x
    返回: (M,2) int32 去重后的坐标
    """
    n = arr.shape[0]
    if n == 0:
        return arr

    max_key = np.int32(0)
    for i in range(n):
        key = arr[i, 1] * width + arr[i, 0]
        if key > max_key:
            max_key = key

    # 用布尔数组做哈希表
    seen = np.zeros(max_key + 1, dtype=np.bool_)
    tmp_x = np.empty(n, dtype=np.int32)
    tmp_y = np.empty(n, dtype=np.int32)
    k = 0
    for i in range(n):
        x = arr[i, 0]
        y = arr[i, 1]
        key = y * width + x
        if not seen[key]:
            seen[key] = True
            tmp_x[k] = x
            tmp_y[k] = y
            k += 1
    out = np.empty((k, 2), dtype=np.int32)
    for j in range(k):
        out[j, 0] = tmp_x[j]
        out[j, 1] = tmp_y[j]
    return out


@njit('bool_(int32,int32,int32[:,:])', cache=True, nogil=True)
def _is_active(px, py, active):
    lo, hi = 0, active.shape[0]
    while lo < hi:
        mid = (lo + hi) // 2
        if (active[mid, 0] < px) or \
           (active[mid, 0] == px and active[mid, 1] < py):
            lo = mid + 1
        else:
            hi = mid
    return lo < active.shape[0] and active[lo, 0] == px and active[lo, 1] == py


@njit(cache=True, nogil=True, fastmath=True)
def calculate_pattern_data_3d(#down 模式下才有积雪
        pattern_data,
        pattern_data_thickness,
        offset,
        all_positions_x,
        all_positions_y,
        position_index_keys_x,
        position_index_keys_y,
        position_index_values,
        opacity_values,
        data_height,
        orientation_int,          # 0=up, 1=down
        snow_ttl,                # (H, W) int32
        max_snow_ttl,            # int32
    ):
    H, W = pattern_data.shape[1], pattern_data.shape[2]

    # ---------- 1. 第一层点集 ----------
    if orientation_int == 0:
        first_layer = 0
    else:
        first_layer = pattern_data.shape[0] - 1

    p0 = pattern_data[first_layer]
    h, w = p0.shape
    mask0 = p0.ravel() != 0
    idx = np.arange(h * w, dtype=np.int32)[mask0]
    x0 = (idx % w).astype(np.float32)
    y0 = (idx // w).astype(np.float32)
    len0 = len(x0)

    # ---------- 2. 强调气泡 ----------
    if orientation_int == 0:  # 只在 orientation="up" 时计算和渲染强调气泡
        active_x = np.empty(3 * len0, dtype=np.float32)
        active_y = np.empty(3 * len0, dtype=np.float32)
        active_op = np.empty(3 * len0, dtype=np.float32)
        active_sz = np.empty(3 * len0, dtype=np.float32)
        for i in range(3):
            off = i * len0
            active_x[off:off + len0] = x0
            active_y[off:off + len0] = y0
            active_op[off:off + len0] = np.float32([0.8, 0.3, 0.1][i])
            active_sz[off:off + len0] = np.float32([100.0, 250.0, 500.0][i])
    else:
        # 在 orientation="down" 时，创建空数组以避免后续代码出错
        active_x = np.empty(0, dtype=np.float32)
        active_y = np.empty(0, dtype=np.float32)
        active_op = np.empty(0, dtype=np.float32)
        active_sz = np.empty(0, dtype=np.float32)

    # ---------- 3. 去重 ----------
    active_xy_raw = np.empty((len0, 2), dtype=np.int32)
    if len0 > 0:
        active_xy_raw[:, 0] = x0.astype(np.int32)
        active_xy_raw[:, 1] = y0.astype(np.int32)
    active_xy = _unique_2d(active_xy_raw, np.int32(w))

    # ---------- 4. all_positions的可视化 (Optimized) ----------
    if orientation_int == 0:
        n_all = len(all_positions_x)
        # --- 优化: 创建查找表 ---
        # 假设 all_positions_x/y 的最大值不超过 W, H
        lookup_table = np.full((H, W), -1, dtype=np.int32)
        for i in range(len(position_index_keys_x)):
            lookup_table[position_index_keys_y[i], position_index_keys_x[i]] = position_index_values[i]
        
        inactive_flags = np.ones(n_all, dtype=np.bool_)
        for i in prange(n_all):
            if _is_active(all_positions_x[i], all_positions_y[i], active_xy):
                inactive_flags[i] = False

        inactive_indices = np.nonzero(inactive_flags)[0]
        cnt_inactive = len(inactive_indices)
        inactive_x = np.empty(cnt_inactive, dtype=np.float32)
        inactive_y = np.empty(cnt_inactive, dtype=np.float32)
        inactive_op = np.empty(cnt_inactive, dtype=np.float32)

        for i in prange(cnt_inactive):
            original_idx = inactive_indices[i]
            px = all_positions_x[original_idx]
            py = all_positions_y[original_idx]
            inactive_x[i] = np.float32(px)
            inactive_y[i] = np.float32(py)
            lookup_idx = lookup_table[int(py), int(px)]
            if lookup_idx != -1:
                inactive_op[i] = opacity_values[lookup_idx]
            else:
                inactive_op[i] = 0.0 # Or some default
    else:
        inactive_x = np.empty(0, dtype=np.float32)
        inactive_y = np.empty(0, dtype=np.float32)
        inactive_op = np.empty(0, dtype=np.float32)

    # ---------- 5. 合并 step1 ----------
    step1_x = np.concatenate((active_x, inactive_x)) - offset[0]
    step1_y = np.concatenate((active_y, inactive_y)) - offset[1]
    step1_z = np.zeros(len(step1_x), dtype=np.float32)
    step1_op = np.concatenate((active_op, inactive_op))
    step1_sz = np.concatenate((active_sz, np.full(len(inactive_x), 20.0, dtype=np.float32)))

    # ---------- 6. 滚动层 ----------
    if orientation_int == 1:
        nz = np.nonzero(pattern_data[-2::-1])
        step2_z = (data_height - 2 - nz[0]).astype(np.float32)
    else:
        nz = np.nonzero(pattern_data[1:data_height])
        step2_z = (nz[0] + 1).astype(np.float32)

    step2_len = len(nz[0])
    step2_x = nz[2].astype(np.float32)
    step2_y = nz[1].astype(np.float32)

    step2_sz = np.empty(step2_len, dtype=np.float32)
    for i in prange(step2_len):
        ix = int(step2_x[i])
        iy = int(step2_y[i])
        iz = int(step2_z[i])
        val = pattern_data_thickness[iz, iy, ix] * 5.0
        max_val = 500 if orientation_int == 0 else 200
        step2_sz[i] = min(max(val, 0.0), max_val)

    step2_x -= offset[0]
    step2_y -= offset[1]

    # ---------- 7. 积雪效果 (Optimized) ----------
    if orientation_int == 1 and max_snow_ttl > 0:
        stack_depth, H, W = snow_ttl.shape
        new_snow_sizes = np.full((stack_depth, H, W), -1.0, dtype=np.float32)
        # 1. 更新TTL (消融 & 堆叠) - Parallelized
        for y in prange(H):
            for x in range(W):
                top_snow_z = -1
                for z in range(stack_depth):
                    if snow_ttl[z, y, x] > 0:
                        top_snow_z = z
                        break
                if top_snow_z != -1:
                    snow_ttl[top_snow_z, y, x] -= 1

                if pattern_data[-1, y, x] > 0:
                    # 获取当前雪花的实际厚度
                    actual_thickness = pattern_data_thickness[-1, y, x] * 5.0  # 与step2_sz的缩放一致
                    actual_size = min(max(actual_thickness, 10.0), 200.0)  # 限制范围，避免过大

                    highest_pos = stack_depth - 1
                    for z in range(stack_depth):
                        if snow_ttl[z, y, x] > 0:
                            highest_pos = z
                            break
                    new_pos = highest_pos - 1
                    if new_pos >= 0:
                        snow_ttl[new_pos, y, x] = max_snow_ttl
                        new_snow_sizes[new_pos, y, x] = actual_size  # 记录实际大小

        # 2. 准备渲染数据 (Optimized)
        snow_indices = np.nonzero(snow_ttl)
        snow_count = len(snow_indices[0])
        snow_x = snow_indices[2].astype(np.float32)
        snow_y = snow_indices[1].astype(np.float32)
        snow_z = (-snow_indices[0] * 5).astype(np.float32)
        
        # --- Numba-compatible way to get ttl_values ---
        ttl_values = np.empty(snow_count, dtype=np.float32)
        for i in prange(snow_count):
            z_idx = snow_indices[0][i]
            y_idx = snow_indices[1][i]
            x_idx = snow_indices[2][i]
            ttl_values[i] = snow_ttl[z_idx, y_idx, x_idx]

        snow_sz = np.empty(snow_count, dtype=np.float32)
        snow_op = np.empty(snow_count, dtype=np.float32)
        for i in prange(snow_count):
            z_idx = snow_indices[0][i]
            y_idx = snow_indices[1][i]
            x_idx = snow_indices[2][i]
            ttl_val = ttl_values[i] = snow_ttl[z_idx, y_idx, x_idx]

            actual_size = new_snow_sizes[z_idx, y_idx, x_idx]
            if actual_size >= 0.0:  # 注意这里是 >= 0，因为初始化为 -1
                snow_sz[i] = actual_size
            else:
                r = ttl_val / np.float32(max_snow_ttl)
                snow_sz[i] = np.float32(10.0) + r * np.float32(40.0)

            snow_op[i] = np.float32(0.2) + (ttl_val / np.float32(max_snow_ttl)) * np.float32(0.8)

        snow_x -= offset[0]
        snow_y -= offset[1]
    else:
        snow_x = np.empty(0, dtype=np.float32)
        snow_y = np.empty(0, dtype=np.float32)
        snow_z = np.empty(0, dtype=np.float32)
        snow_sz = np.empty(0, dtype=np.float32)
        snow_op = np.empty(0, dtype=np.float32)

    # ---------- 8. 最终合并 ----------
    all_x_no_light = np.concatenate((step1_x, step2_x, snow_x))
    all_y_no_light = np.concatenate((step1_y, step2_y, snow_y))
    all_z_no_light = np.concatenate((step1_z, step2_z, snow_z))
    all_sz_no_light = np.concatenate((step1_sz, step2_sz, snow_sz))
    all_op_no_light = np.concatenate((step1_op, np.ones(step2_len, dtype=np.float32), snow_op))

    # ---------- 9. 路灯效果 (Parallelized) ----------
    if orientation_int == 1:
        num_light_particles = 200
        light_x = np.empty(num_light_particles, dtype=np.float32)
        light_y = np.empty(num_light_particles, dtype=np.float32)
        light_z = np.empty(num_light_particles, dtype=np.float32)
        light_sz = np.empty(num_light_particles, dtype=np.float32)
        light_op = np.empty(num_light_particles, dtype=np.float32)

        light_source_pos = (W / 2, H / 2, data_height + 50)
        cone_length = (data_height + 50) * 0.4

        for i in prange(num_light_particles):
            z = light_source_pos[2] - np.random.power(2) * cone_length
            cone_ratio = (light_source_pos[2] - z) / cone_length
            max_radius = W / 1.2
            radius = np.random.uniform(0, max_radius) * cone_ratio
            angle = np.random.uniform(0, 2 * np.pi)
            x = light_source_pos[0] + radius * np.cos(angle)
            y = light_source_pos[1] + radius * np.sin(angle)
            
            dist_to_axis = np.sqrt((x - light_source_pos[0])**2 + (y - light_source_pos[1])**2)
            dist_to_source = np.sqrt(dist_to_axis**2 + (z - light_source_pos[2])**2)

            falloff_factor = (1 - dist_to_source / (data_height + 60))**3
            radial_factor = (1 - dist_to_axis / (W / 1.2))

            opacity = radial_factor * falloff_factor * 0.8
            size = radial_factor * falloff_factor * 120

            light_x[i] = x - offset[0]
            light_y[i] = y - offset[1]
            light_z[i] = z
            light_sz[i] = max(0, size)
            light_op[i] = max(0, opacity)

        lampshade_x = np.array([light_source_pos[0] - offset[0]], dtype=np.float32)
        lampshade_y = np.array([light_source_pos[1] - offset[1]], dtype=np.float32)
        lampshade_z = np.array([light_source_pos[2]], dtype=np.float32)
        lampshade_sz = np.array([600], dtype=np.float32)
        lampshade_op = np.array([1.0], dtype=np.float32)
    else:
        light_x = np.empty(0, dtype=np.float32)
        light_y = np.empty(0, dtype=np.float32)
        light_z = np.empty(0, dtype=np.float32)
        light_sz = np.empty(0, dtype=np.float32)
        light_op = np.empty(0, dtype=np.float32)
        lampshade_x = np.empty(0, dtype=np.float32)
        lampshade_y = np.empty(0, dtype=np.float32)
        lampshade_z = np.empty(0, dtype=np.float32)
        lampshade_sz = np.empty(0, dtype=np.float32)
        lampshade_op = np.empty(0, dtype=np.float32)

    # ---------- 10. 最终合并 & 分配类型 ----------
    all_x = np.concatenate((all_x_no_light, light_x, lampshade_x))
    all_y = np.concatenate((all_y_no_light, light_y, lampshade_y))
    all_z = np.concatenate((all_z_no_light, light_z, lampshade_z))
    all_sz = np.concatenate((all_sz_no_light, light_sz, lampshade_sz))
    all_op = np.concatenate((all_op_no_light, light_op, lampshade_op))

    type_others = np.zeros(len(all_x_no_light), dtype=np.int32)
    type_light = np.ones(len(light_x), dtype=np.int32)
    type_lampshade = np.full(len(lampshade_x), 2, dtype=np.int32)
    all_types = np.concatenate((type_others, type_light, type_lampshade))

    # ---------- 11. 计算颜色混合因子 (Parallelized) ----------
    blend_factors_snow = np.zeros(len(snow_x), dtype=np.float32)
    blend_factors_step1 = np.zeros(len(step1_x), dtype=np.float32)   # 强调气泡
    blend_factors_step2 = np.zeros(len(step2_x), dtype=np.float32)   # 滚动雪花

    if orientation_int == 1:
        light_center_x = W / 2 - offset[0]
        light_center_y = H / 2 - offset[1]

        # 1. 积雪（snow）——保持原状
        max_light_radius_snow = W / 1.2
        for i in prange(len(snow_x)):
            dist_to_center = np.sqrt((snow_x[i] - light_center_x)**2 +
                                     (snow_y[i] - light_center_y)**2)
            blend_factor = 1.0 - min(1.0, dist_to_center / max_light_radius_snow)
            blend_factors_snow[i] = blend_factor**2

        # 2. 强调气泡（step1）——不受灯光影响
        for i in prange(len(step1_x)):
            blend_factors_step1[i] = 0.0

        # 3. 滚动雪花（step2）——增强灯光混合
        light_source_z = light_source_pos[2]
        cone_length = (data_height + 50) * 1
        max_light_radius_base = W / 1.2
        min_blend = 0.2                   # 远处也保留基础橙色

        for i in prange(len(step2_x)):
            px = step2_x[i]
            py = step2_y[i]
            pz = step2_z[i]

            if pz < light_source_z and pz > (light_source_z - cone_length):
                cone_ratio = (light_source_z - pz) / cone_length
                current_max_radius = max_light_radius_base * cone_ratio
                dist_to_axis = np.sqrt((px - light_center_x)**2 +
                                       (py - light_center_y)**2)

                if dist_to_axis < current_max_radius:
                    blend_factor = ((1.0 - (dist_to_axis / current_max_radius))*0.9)**2
                    blend_factors_step2[i] = min_blend + (1.0 - min_blend) * blend_factor
                else:
                    blend_factors_step2[i] = min_blend
            else:
                blend_factors_step2[i] = 0.0

    # 合并结果
    blend_factors_others = np.concatenate((blend_factors_step1, blend_factors_step2))

    blend_factors_light = np.zeros(len(light_x), dtype=np.float32)
    blend_factors_lampshade = np.zeros(len(lampshade_x), dtype=np.float32)

    all_color_blend_factors = np.concatenate((blend_factors_others,
                                              blend_factors_snow,
                                              blend_factors_light,
                                              blend_factors_lampshade))

    return all_x, all_y, all_z, all_sz, all_op, all_types, all_color_blend_factors


@njit(cache=True, nogil=True, fastmath=True)
def calculate_particle_colors_njit(all_types, all_color_blend_factors, all_opacity, base_color_r, base_color_g, base_color_b):
    """
    njit优化的粒子颜色计算函数
    
    参数:
    - all_types: 粒子类型数组 (0=普通粒子&雪花, 1=灯光, 2=灯罩)
    - all_color_blend_factors: 颜色混合因子数组
    - all_opacity: 透明度数组
    - base_color_r, base_color_g, base_color_b: 基础颜色的RGB分量
    
    返回:
    - colors: (N, 4) 颜色数组 [R, G, B, A]
    """
    n_particles = len(all_types)
    colors = np.empty((n_particles, 4), dtype=np.float32)
    
    # 预定义颜色
    orange_r, orange_g, orange_b = np.float32(1.0), np.float32(0.6), np.float32(0.0)
    black_r, black_g, black_b = np.float32(0.0), np.float32(0.0), np.float32(0.0)
    
    # 向量化颜色计算
    for i in prange(n_particles):
        particle_type = all_types[i]
        opacity = all_opacity[i]
        
        if particle_type == 2:  # 灯罩
            final_r = black_r
            final_g = black_g
            final_b = black_b
        elif particle_type == 1:  # 灯光
            final_r = orange_r
            final_g = orange_g
            final_b = orange_b
        else:  # 普通粒子 & 雪花 (type 0)
            blend_factor = all_color_blend_factors[i]
            inv_blend = np.float32(1.0) - blend_factor
            
            final_r = inv_blend * base_color_r + blend_factor * orange_r
            final_g = inv_blend * base_color_g + blend_factor * orange_g
            final_b = inv_blend * base_color_b + blend_factor * orange_b
        
        colors[i, 0] = final_r
        colors[i, 1] = final_g
        colors[i, 2] = final_b
        colors[i, 3] = opacity
    
    return colors
