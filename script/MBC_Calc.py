import numpy as np


def generate_positions(num_positions, center_x, center_y, inner_radius, outer_radius, pos_type="Fibonacci"):
    positions = []
    if pos_type == "Fibonacci":
        golden_angle = np.pi * (3 - np.sqrt(5))
        while len(positions) < num_positions:
            positions.clear()
            for i in range(num_positions):
                radius = inner_radius + (outer_radius - inner_radius) * (i / num_positions)
                angle = i * golden_angle
                x, y = int(center_x + radius * np.cos(angle)), int(center_y + radius * np.sin(angle))
                if (x, y) not in positions:
                    positions.append((x, y))
                else:
                    outer_radius += 1
                    break
            if len(positions) >= num_positions:
                break
                
    elif pos_type == "circle":
        while len(positions) < num_positions:
            positions.clear()
            for i in range(num_positions):
                angle = 2 * np.pi * i / num_positions
                radius = inner_radius + (outer_radius - inner_radius) * 0.5
                x = int(center_x + radius * np.cos(angle))
                y = int(center_y + radius * np.sin(angle))
                if (x, y) not in positions:
                    positions.append((x, y))
            outer_radius += 1

    elif pos_type == "arc":
        arc_fraction = 1 / 4  # Default to 1/3 of the circle
        angle_range = 2 * np.pi * arc_fraction  # Angle range for the arc
        
        while len(positions) < num_positions:
            positions.clear()
            for i in range(num_positions):
                angle = i * angle_range / num_positions  # Spread the positions across the arc
                radius = outer_radius
                x = int(center_x + radius * np.cos(angle))
                y = int(center_y + radius * np.sin(angle))
                if (x, y) not in positions:
                    positions.append((x, y))
                else:
                    # If we find a duplicate, increase the radius and clear positions to retry
                    outer_radius += 1
                    break
            if len(positions) >= num_positions:
                break

    # 计算偏移量
    min_x = min(pos[0] for pos in positions)
    min_y = min(pos[1] for pos in positions)
    offset = (-min_x, -min_y)
    # 应用偏移量
    positions = [(x + offset[0], y + offset[1]) for x, y in positions]
    return positions, offset


def calculate_opacity():
    # 根据位置顺序计算透明度
    opacity_array = np.array([(i / 120) * 0.9 for i in range(120)])  # 使用 NumPy 数组
    return opacity_array  # 直接返回 NumPy 数组


def calculate_pattern_data(pattern_data, pattern_data_thickness, offset, all_positions, position_index, opacity_dict, data_height, orientation):
    # 第一层点集
    x, y, z = np.nonzero(np.atleast_3d(pattern_data[-1 if orientation=="down" else 0]))
    len_x = len(x)

    opacity = np.concatenate((np.full(len_x, 0.8), np.full(len_x, 0.3), np.full(len_x, 0.1)))
    size_list = np.concatenate((np.full(len_x, 100), np.full(len_x, 250), np.full(len_x, 500)))

    x = np.concatenate((x, x, x))  # 使用一次性合并
    y = np.concatenate((y, y, y))
    # 底盘点集
    # 获取非活动位置的坐标和透明度
    # 使用 NumPy 数组来提高效率
    active_positions = np.array(list(zip(x, y)))
    inactive_positions = np.array(list(all_positions - set(map(tuple, active_positions))))
    ix_val, iy_val, inactive_opacity = [], [], []
    if inactive_positions.size > 0:
        for pos in inactive_positions:
            ix_val.append(pos[0])
            iy_val.append(pos[1])
            if (pos[0], pos[1]) in position_index:
                inactive_opacity.append(opacity_dict[position_index[(pos[0], pos[1])]])

    # 合并所有点的坐标、透明度和大小
    step1_all_x = np.concatenate((x, np.array(ix_val))) - offset[0]
    step1_all_y = np.concatenate((y, np.array(iy_val))) - offset[1]
    step1_all_opacity = np.concatenate((opacity, inactive_opacity))
    step1_all_sizes = np.concatenate((size_list, np.full(len(ix_val), 10)))
    
    # 绘制滚动的层
    step2_all_x = np.empty(0)  # 初始化为 NumPy 数组
    step2_all_y = np.empty(0)
    step2_all_z = np.empty(0)
    step2_all_sizes = []  # 用于存储大小的列表
    # 获取所有非零点的坐标
    nonzero_indices = np.nonzero(pattern_data[1:data_height])  # 从第一层到最后一层
    x, y, z = nonzero_indices[1], nonzero_indices[2], nonzero_indices[0] + 1  # z 值加上层数
    
    if x.size > 0:
        step2_all_x = np.concatenate((step2_all_x, x - offset[0]))
        step2_all_y = np.concatenate((step2_all_y, y - offset[1]))
        step2_all_z = np.concatenate((step2_all_z, z))
        
        # 获取对应位置的厚度值
        thickness = pattern_data_thickness[1:data_height][nonzero_indices]  # 使用索引获取厚度值
        sizes = np.clip(thickness * 5, 0, 500)  # 根据需求调整厚度到大小的映射
        
        step2_all_sizes.extend(sizes)  # 将大小添加到列表中
    
    # 合并 step1 和 step2 的数据
    all_x = np.concatenate((step1_all_x, step2_all_x))
    all_y = np.concatenate((step1_all_y, step2_all_y))
    all_z = np.concatenate((np.full(len(step1_all_x), data_height) if orientation == "down" else np.zeros(len(step1_all_x)), step2_all_z))
    all_sizes = np.concatenate((step1_all_sizes, step2_all_sizes))
    
    if len(step2_all_x) > 0:
        all_opacity = np.concatenate((step1_all_opacity, np.ones(len(step2_all_x))))
    else:
        all_opacity = step1_all_opacity

    return all_x, all_y, all_z, all_sizes, all_opacity