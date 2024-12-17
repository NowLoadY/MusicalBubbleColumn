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
        arc_fraction = 1 / 3
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
    opacity_array = np.zeros(120, dtype=np.float32)
    for i in range(120):
        opacity_array[i] = 0.1 + (i / 120) * 0.6
    return opacity_array
