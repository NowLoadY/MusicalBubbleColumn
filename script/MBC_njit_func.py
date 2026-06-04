from numba import njit, prange
import numpy as np


BUBBLE_X = 0
BUBBLE_Y = 1
BUBBLE_Z = 2
BUBBLE_AREA = 3
BUBBLE_VX = 4
BUBBLE_VY = 5
BUBBLE_ACTIVE = 6


@njit
def add_pattern(
    bit_array,
    volumes,
    average_volume,
    position_list,
    final_volume,
    final_volume_index,
    scaler,
    thickness_list,
    pattern_data,
    pattern_data_thickness,
    orientation,
    max_volume_up,
    max_volume_down,
    birth_curve_up,
    birth_curve_down,
):
    variances = []
    active_indices = np.where(bit_array)[0]
    for i in active_indices:
        volume_idx = min(i, len(volumes) - 1) if len(volumes) > 0 else 0
        x_center, y_center = position_list[i]
        volume_factor = ((volumes[volume_idx] - average_volume) / average_volume) if average_volume else 0
        max_volume = max_volume_up if orientation == "up" else max_volume_down
        birth_curve = birth_curve_up if orientation == "up" else birth_curve_down
        amplitude_base = max(0.0, 1 + scaler * volume_factor)
        final_volume_piece = min(max_volume, amplitude_base ** birth_curve)
        final_volume[final_volume_index] = final_volume_piece
        final_volume_index = (final_volume_index + 1) % len(final_volume)
        if final_volume_index == 0:
            variances.append(np.var(final_volume))

        thickness_list[i] = int(final_volume_piece)
        pattern_data[-1 if orientation == "down" else 0, x_center, y_center] = 1.0
        pattern_data_thickness[-1 if orientation == "down" else 0, x_center, y_center] = final_volume_piece + 1.0
    return variances


@njit
def _clamp_float(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


@njit
def _clamp_int(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


@njit
def _round_to_int(value):
    if value >= 0.0:
        return int(value + 0.5)
    return int(value - 0.5)


@njit
def _bubble_radius_m(area_units, area_unit_m2, min_radius_m, max_radius_m):
    area_m2 = max(area_units, 1.0) * area_unit_m2
    radius_m = np.sqrt(area_m2 / np.float32(np.pi))
    return max(min_radius_m, min(radius_m, max_radius_m))


@njit
def _bubble_screen_radius(area_units, area_unit_m2, min_radius_m, max_radius_m, screen_radius_per_meter, min_screen_radius):
    radius_m = _bubble_radius_m(area_units, area_unit_m2, min_radius_m, max_radius_m)
    return max(min_screen_radius, radius_m * screen_radius_per_meter)


@njit
def _terminal_velocity_m_s(
    radius_m,
    gravity_m_s2,
    liquid_density_kg_m3,
    gas_density_kg_m3,
    water_kinematic_viscosity_m2_s,
    drag_coefficient,
):
    density_delta = max(liquid_density_kg_m3 - gas_density_kg_m3, 1.0)
    dynamic_viscosity = max(liquid_density_kg_m3 * water_kinematic_viscosity_m2_s, 1.0e-9)
    stokes = (2.0 * density_delta * gravity_m_s2 * radius_m * radius_m) / (9.0 * dynamic_viscosity)
    inertial = np.sqrt(
        max(
            (8.0 * density_delta * gravity_m_s2 * radius_m)
            / (3.0 * max(drag_coefficient, 1.0e-6) * liquid_density_kg_m3),
            0.0,
        )
    )
    return max(0.0, min(stokes, inertial))


@njit
def _hydrostatic_area_units(
    area_units,
    current_layer,
    target_layer,
    data_height,
    vertical_cell_pitch_m,
    atmospheric_pressure_pa,
    liquid_density_kg_m3,
    gravity_m_s2,
):
    current_depth_m = max(data_height - 1 - current_layer, 0.0) * vertical_cell_pitch_m
    target_depth_m = max(data_height - 1 - target_layer, 0.0) * vertical_cell_pitch_m
    current_pressure = atmospheric_pressure_pa + liquid_density_kg_m3 * gravity_m_s2 * current_depth_m
    target_pressure = atmospheric_pressure_pa + liquid_density_kg_m3 * gravity_m_s2 * target_depth_m
    pressure_ratio = current_pressure / max(target_pressure, 1.0)
    return area_units * pressure_ratio ** (2.0 / 3.0)


@njit
def _find_inactive_particle(bubble_particles, start_index):
    capacity = bubble_particles.shape[0]
    for i in range(start_index, capacity):
        if bubble_particles[i, BUBBLE_ACTIVE] <= 0.0:
            return i
    for i in range(0, start_index):
        if bubble_particles[i, BUBBLE_ACTIVE] <= 0.0:
            return i
    return -1


@njit
def _decay_snow(snow_ttl, snow_sizes):
    stack_depth = snow_ttl.shape[0]
    rows = snow_ttl.shape[1]
    cols = snow_ttl.shape[2]
    for x in range(rows):
        for y in range(cols):
            top_snow_z = -1
            for z in range(stack_depth):
                if snow_ttl[z, x, y] > 0:
                    top_snow_z = z
                    break
            if top_snow_z != -1:
                snow_ttl[top_snow_z, x, y] -= 1
                if snow_ttl[top_snow_z, x, y] <= 0:
                    snow_sizes[top_snow_z, x, y] = 0.0


@njit
def _deposit_snow(snow_ttl, snow_sizes, x, y, size, max_snow_ttl):
    if max_snow_ttl <= 0:
        return

    stack_depth = snow_ttl.shape[0]
    ix = _clamp_int(_round_to_int(x), 0, snow_ttl.shape[1] - 1)
    iy = _clamp_int(_round_to_int(y), 0, snow_ttl.shape[2] - 1)

    highest_pos = stack_depth - 1
    for z in range(stack_depth):
        if snow_ttl[z, ix, iy] > 0:
            highest_pos = z
            break

    new_pos = highest_pos - 1
    if new_pos < 0:
        new_pos = 0

    snow_ttl[new_pos, ix, iy] = max_snow_ttl
    snow_sizes[new_pos, ix, iy] = size


@njit
def _spawn_birth_particles(pattern_data, pattern_data_thickness, bubble_particles, birth_layer):
    birth_layer_data = pattern_data[birth_layer]
    x_indices, y_indices = np.nonzero(birth_layer_data)
    slot_cursor = 0
    for i in range(len(x_indices)):
        slot = _find_inactive_particle(bubble_particles, slot_cursor)
        if slot < 0:
            break

        x = x_indices[i]
        y = y_indices[i]
        area_units = pattern_data_thickness[birth_layer, x, y]
        if area_units <= 0.0:
            continue

        bubble_particles[slot, BUBBLE_X] = np.float32(x)
        bubble_particles[slot, BUBBLE_Y] = np.float32(y)
        bubble_particles[slot, BUBBLE_Z] = np.float32(birth_layer)
        bubble_particles[slot, BUBBLE_AREA] = area_units
        bubble_particles[slot, BUBBLE_VX] = 0.0
        bubble_particles[slot, BUBBLE_VY] = 0.0
        bubble_particles[slot, BUBBLE_ACTIVE] = 1.0
        slot_cursor = slot + 1


@njit
def _split_particle_if_needed(
    bubble_particles,
    particle_index,
    radius_m,
    terminal_velocity,
    radius_grid,
    surface_tension_n_m,
    liquid_density_kg_m3,
    stable_bubble_radius_m,
    split_weber_number,
    horizontal_cell_pitch_m,
    min_bubble_radius_m,
    max_bubble_radius_m,
    bubble_area_unit_m2,
    max_x,
    max_y,
):
    area_units = bubble_particles[particle_index, BUBBLE_AREA]
    weber = (
        liquid_density_kg_m3
        * terminal_velocity
        * terminal_velocity
        * (2.0 * radius_m)
        / max(surface_tension_n_m, 1.0e-6)
    )
    if area_units <= 4.0:
        return
    if radius_m <= stable_bubble_radius_m and weber <= split_weber_number:
        return

    slot = _find_inactive_particle(bubble_particles, particle_index + 1)
    if slot < 0:
        return

    child_area = area_units * 0.5
    child_radius = _bubble_radius_m(child_area, bubble_area_unit_m2, min_bubble_radius_m, max_bubble_radius_m)
    child_radius_grid = child_radius / max(horizontal_cell_pitch_m, 1.0e-6)
    separation = max(1.0, max(radius_grid, child_radius_grid) * 2.2)
    angle = np.random.random() * np.float32(2.0 * np.pi)
    split_dx = np.cos(angle) * separation
    split_dy = np.sin(angle) * separation

    x = bubble_particles[particle_index, BUBBLE_X]
    y = bubble_particles[particle_index, BUBBLE_Y]
    z = bubble_particles[particle_index, BUBBLE_Z]
    vx = bubble_particles[particle_index, BUBBLE_VX]
    vy = bubble_particles[particle_index, BUBBLE_VY]

    bubble_particles[particle_index, BUBBLE_AREA] = child_area
    bubble_particles[particle_index, BUBBLE_X] = _clamp_float(x + split_dx, 0.0, max_x)
    bubble_particles[particle_index, BUBBLE_Y] = _clamp_float(y + split_dy, 0.0, max_y)
    bubble_particles[particle_index, BUBBLE_VX] = vx + split_dx * 0.03
    bubble_particles[particle_index, BUBBLE_VY] = vy + split_dy * 0.03

    bubble_particles[slot, BUBBLE_X] = _clamp_float(x - split_dx, 0.0, max_x)
    bubble_particles[slot, BUBBLE_Y] = _clamp_float(y - split_dy, 0.0, max_y)
    bubble_particles[slot, BUBBLE_Z] = z
    bubble_particles[slot, BUBBLE_AREA] = child_area
    bubble_particles[slot, BUBBLE_VX] = vx - split_dx * 0.03
    bubble_particles[slot, BUBBLE_VY] = vy - split_dy * 0.03
    bubble_particles[slot, BUBBLE_ACTIVE] = 1.0


@njit
def _advance_particle_positions(
    bubble_particles,
    snow_ttl,
    snow_sizes,
    data_height,
    orientation_int,
    vertical_cell_pitch_m,
    horizontal_cell_pitch_m,
    bubble_area_unit_m2,
    simulation_step_s,
    gravity_m_s2,
    atmospheric_pressure_pa,
    liquid_density_kg_m3,
    gas_density_kg_m3,
    water_kinematic_viscosity_m2_s,
    surface_tension_n_m,
    drag_coefficient,
    min_bubble_radius_m,
    max_bubble_radius_m,
    stable_bubble_radius_m,
    split_weber_number,
    max_rise_speed,
    max_snow_ttl,
    screen_radius_per_meter,
    min_screen_radius,
):
    direction = 1.0 if orientation_int == 0 else -1.0
    max_x = np.float32(snow_ttl.shape[1] - 1)
    max_y = np.float32(snow_ttl.shape[2] - 1)
    max_layer = np.float32(data_height - 1)
    safe_vertical_pitch = max(vertical_cell_pitch_m, 1.0e-6)
    safe_horizontal_pitch = max(horizontal_cell_pitch_m, 1.0e-6)

    for i in range(bubble_particles.shape[0]):
        if bubble_particles[i, BUBBLE_ACTIVE] <= 0.0:
            continue

        x = bubble_particles[i, BUBBLE_X]
        y = bubble_particles[i, BUBBLE_Y]
        z = bubble_particles[i, BUBBLE_Z]
        area_units = max(bubble_particles[i, BUBBLE_AREA], 1.0)

        radius_m = _bubble_radius_m(area_units, bubble_area_unit_m2, min_bubble_radius_m, max_bubble_radius_m)
        terminal_velocity = _terminal_velocity_m_s(
            radius_m,
            gravity_m_s2,
            liquid_density_kg_m3,
            gas_density_kg_m3,
            water_kinematic_viscosity_m2_s,
            drag_coefficient,
        )
        dz = terminal_velocity * simulation_step_s / safe_vertical_pitch
        if orientation_int == 1:
            dz *= 0.85
        dz = min(max(dz, 0.01), max_rise_speed)
        target_z = z + direction * dz

        radius_grid = max(radius_m / safe_horizontal_pitch, 0.35)
        reynolds = (2.0 * radius_m * terminal_velocity) / max(water_kinematic_viscosity_m2_s, 1.0e-9)
        eotvos = (
            (liquid_density_kg_m3 - gas_density_kg_m3)
            * gravity_m_s2
            * (2.0 * radius_m)
            * (2.0 * radius_m)
            / max(surface_tension_n_m, 1.0e-6)
        )
        wake_instability = max(0.0, min(1.0, (reynolds - 180.0) / 700.0))
        shape_instability = max(0.0, min(1.0, (eotvos - 3.0) / 9.0))
        effective_diffusivity = water_kinematic_viscosity_m2_s * (1.0 + min(reynolds, 1800.0) * 0.06)
        diffusion_cells = np.sqrt(2.0 * effective_diffusivity * simulation_step_s) / safe_horizontal_pitch
        wake_strength = diffusion_cells + (wake_instability + shape_instability) * min(2.0, radius_grid * 0.9)
        if orientation_int == 1:
            wake_strength = max(wake_strength * 0.75, min(1.2, 0.3 + radius_grid * 0.35))
        else:
            wake_strength = max(wake_strength, 0.05)

        vx = bubble_particles[i, BUBBLE_VX]
        vy = bubble_particles[i, BUBBLE_VY]
        vx = vx * 0.92 + (np.random.random() * 2.0 - 1.0) * wake_strength * 0.08
        vy = vy * 0.92 + (np.random.random() * 2.0 - 1.0) * wake_strength * 0.08
        max_lateral_speed = max(0.18, min(1.6, radius_grid * 0.45 + 0.18))
        vx = _clamp_float(vx, -max_lateral_speed, max_lateral_speed)
        vy = _clamp_float(vy, -max_lateral_speed, max_lateral_speed)

        x += vx
        y += vy
        if x < 0.0:
            x = 0.0
            vx = -vx * 0.35
        elif x > max_x:
            x = max_x
            vx = -vx * 0.35
        if y < 0.0:
            y = 0.0
            vy = -vy * 0.35
        elif y > max_y:
            y = max_y
            vy = -vy * 0.35

        new_area_units = _hydrostatic_area_units(
            area_units,
            z,
            _clamp_float(target_z, 0.0, max_layer),
            data_height,
            safe_vertical_pitch,
            atmospheric_pressure_pa,
            liquid_density_kg_m3,
            gravity_m_s2,
        )

        if orientation_int == 1 and target_z <= 0.0:
            landing_size = _bubble_screen_radius(
                new_area_units,
                bubble_area_unit_m2,
                min_bubble_radius_m,
                max_bubble_radius_m,
                screen_radius_per_meter,
                min_screen_radius,
            )
            _deposit_snow(snow_ttl, snow_sizes, x, y, landing_size, max_snow_ttl)
            bubble_particles[i, BUBBLE_ACTIVE] = 0.0
            continue
        if orientation_int == 0 and target_z >= max_layer:
            bubble_particles[i, BUBBLE_ACTIVE] = 0.0
            continue

        bubble_particles[i, BUBBLE_X] = x
        bubble_particles[i, BUBBLE_Y] = y
        bubble_particles[i, BUBBLE_Z] = _clamp_float(target_z, 0.0, max_layer)
        bubble_particles[i, BUBBLE_AREA] = new_area_units
        bubble_particles[i, BUBBLE_VX] = vx
        bubble_particles[i, BUBBLE_VY] = vy

        if orientation_int == 0:
            _split_particle_if_needed(
                bubble_particles,
                i,
                radius_m,
                terminal_velocity,
                radius_grid,
                surface_tension_n_m,
                liquid_density_kg_m3,
                stable_bubble_radius_m,
                split_weber_number,
                safe_horizontal_pitch,
                min_bubble_radius_m,
                max_bubble_radius_m,
                bubble_area_unit_m2,
                max_x,
                max_y,
            )


@njit
def _merge_particles(
    bubble_particles,
    particle_grid,
    vertical_cell_pitch_m,
    horizontal_cell_pitch_m,
    bubble_area_unit_m2,
    min_bubble_radius_m,
    max_bubble_radius_m,
    merge_efficiency,
    coalescence_factor,
    adjacent_grid_threshold,
):
    particle_grid.fill(-1)
    max_z = particle_grid.shape[0] - 1
    max_x = particle_grid.shape[1] - 1
    max_y = particle_grid.shape[2] - 1
    neighbor = max(1, adjacent_grid_threshold)
    safe_vertical_pitch = max(vertical_cell_pitch_m, 1.0e-6)
    safe_horizontal_pitch = max(horizontal_cell_pitch_m, 1.0e-6)

    for i in range(bubble_particles.shape[0]):
        if bubble_particles[i, BUBBLE_ACTIVE] <= 0.0:
            continue

        cz = _clamp_int(_round_to_int(bubble_particles[i, BUBBLE_Z]), 0, max_z)
        cx = _clamp_int(_round_to_int(bubble_particles[i, BUBBLE_X]), 0, max_x)
        cy = _clamp_int(_round_to_int(bubble_particles[i, BUBBLE_Y]), 0, max_y)
        merged = False

        for dz in range(-neighbor, neighbor + 1):
            nz = cz + dz
            if nz < 0 or nz > max_z:
                continue
            for dx in range(-neighbor, neighbor + 1):
                nx = cx + dx
                if nx < 0 or nx > max_x:
                    continue
                for dy in range(-neighbor, neighbor + 1):
                    ny = cy + dy
                    if ny < 0 or ny > max_y:
                        continue
                    other_index = particle_grid[nz, nx, ny]
                    if other_index < 0 or other_index == i:
                        continue
                    if bubble_particles[other_index, BUBBLE_ACTIVE] <= 0.0:
                        continue

                    area_a = max(bubble_particles[i, BUBBLE_AREA], 1.0)
                    area_b = max(bubble_particles[other_index, BUBBLE_AREA], 1.0)
                    radius_a = _bubble_radius_m(area_a, bubble_area_unit_m2, min_bubble_radius_m, max_bubble_radius_m)
                    radius_b = _bubble_radius_m(area_b, bubble_area_unit_m2, min_bubble_radius_m, max_bubble_radius_m)

                    dx_m = (bubble_particles[i, BUBBLE_X] - bubble_particles[other_index, BUBBLE_X]) * safe_horizontal_pitch
                    dy_m = (bubble_particles[i, BUBBLE_Y] - bubble_particles[other_index, BUBBLE_Y]) * safe_horizontal_pitch
                    dz_m = (bubble_particles[i, BUBBLE_Z] - bubble_particles[other_index, BUBBLE_Z]) * safe_vertical_pitch
                    distance_m = np.sqrt(dx_m * dx_m + dy_m * dy_m + dz_m * dz_m)

                    if distance_m <= (radius_a + radius_b) * coalescence_factor:
                        total_area = area_a + area_b
                        inv_total = 1.0 / max(total_area, 1.0)
                        for column in range(0, 6):
                            bubble_particles[other_index, column] = (
                                bubble_particles[other_index, column] * area_b
                                + bubble_particles[i, column] * area_a
                            ) * inv_total
                        bubble_particles[other_index, BUBBLE_AREA] = total_area * merge_efficiency
                        bubble_particles[i, BUBBLE_ACTIVE] = 0.0
                        merged = True
                        break
                if merged:
                    break
            if merged:
                break

        if not merged and particle_grid[cz, cx, cy] < 0:
            particle_grid[cz, cx, cy] = i


@njit
def advance_bubble_particles(
    pattern_data,
    pattern_data_thickness,
    bubble_particles,
    particle_grid,
    snow_ttl,
    snow_sizes,
    data_height,
    orientation_int,
    vertical_cell_pitch_m,
    horizontal_cell_pitch_m,
    bubble_area_unit_m2,
    simulation_step_s,
    gravity_m_s2,
    atmospheric_pressure_pa,
    liquid_density_kg_m3,
    gas_density_kg_m3,
    water_kinematic_viscosity_m2_s,
    surface_tension_n_m,
    drag_coefficient,
    min_bubble_radius_m,
    max_bubble_radius_m,
    stable_bubble_radius_m,
    split_weber_number,
    merge_efficiency,
    coalescence_factor,
    max_rise_speed,
    adjacent_grid_threshold,
    max_snow_ttl,
    screen_radius_per_meter,
    min_screen_radius,
):
    if orientation_int == 1 and max_snow_ttl > 0:
        _decay_snow(snow_ttl, snow_sizes)

    birth_layer = 0 if orientation_int == 0 else data_height - 1
    _spawn_birth_particles(pattern_data, pattern_data_thickness, bubble_particles, birth_layer)
    _advance_particle_positions(
        bubble_particles,
        snow_ttl,
        snow_sizes,
        data_height,
        orientation_int,
        vertical_cell_pitch_m,
        horizontal_cell_pitch_m,
        bubble_area_unit_m2,
        simulation_step_s,
        gravity_m_s2,
        atmospheric_pressure_pa,
        liquid_density_kg_m3,
        gas_density_kg_m3,
        water_kinematic_viscosity_m2_s,
        surface_tension_n_m,
        drag_coefficient,
        min_bubble_radius_m,
        max_bubble_radius_m,
        stable_bubble_radius_m,
        split_weber_number,
        max_rise_speed,
        max_snow_ttl,
        screen_radius_per_meter,
        min_screen_radius,
    )
    _merge_particles(
        bubble_particles,
        particle_grid,
        vertical_cell_pitch_m,
        horizontal_cell_pitch_m,
        bubble_area_unit_m2,
        min_bubble_radius_m,
        max_bubble_radius_m,
        merge_efficiency,
        coalescence_factor,
        adjacent_grid_threshold,
    )


@njit(cache=True, nogil=True, fastmath=True)
def calculate_pattern_data_3d(
    pattern_data,
    pattern_data_thickness,
    bubble_particles,
    offset,
    all_positions_x,
    all_positions_y,
    position_index_keys_x,
    position_index_keys_y,
    position_index_values,
    opacity_values,
    data_height,
    orientation_int,
    snow_ttl,
    snow_sizes,
    max_snow_ttl,
    bubble_area_unit_m2,
    min_bubble_radius_m,
    max_bubble_radius_m,
    bubble_screen_radius_per_meter,
    min_bubble_screen_radius,
    inactive_screen_radius,
    light_particle_screen_radius,
    lampshade_screen_radius,
):
    rows = pattern_data.shape[1]
    cols = pattern_data.shape[2]
    first_layer = 0 if orientation_int == 0 else pattern_data.shape[0] - 1
    p0 = pattern_data[first_layer]

    x0, y0 = np.nonzero(p0)
    len0 = len(x0)

    if orientation_int == 0:
        active_x = np.empty(3 * len0, dtype=np.float32)
        active_y = np.empty(3 * len0, dtype=np.float32)
        active_op = np.empty(3 * len0, dtype=np.float32)
        active_sz = np.empty(3 * len0, dtype=np.float32)
        for i in range(len0):
            area_units = pattern_data_thickness[first_layer, x0[i], y0[i]]
            base_radius = _bubble_screen_radius(
                area_units,
                bubble_area_unit_m2,
                min_bubble_radius_m,
                max_bubble_radius_m,
                bubble_screen_radius_per_meter,
                min_bubble_screen_radius,
            )
            for layer in range(3):
                out_index = layer * len0 + i
                active_x[out_index] = np.float32(x0[i])
                active_y[out_index] = np.float32(y0[i])
                if layer == 0:
                    active_op[out_index] = 0.8
                    active_sz[out_index] = base_radius
                elif layer == 1:
                    active_op[out_index] = 0.3
                    active_sz[out_index] = base_radius * 1.6
                else:
                    active_op[out_index] = 0.1
                    active_sz[out_index] = base_radius * 2.4
    else:
        active_x = np.empty(0, dtype=np.float32)
        active_y = np.empty(0, dtype=np.float32)
        active_op = np.empty(0, dtype=np.float32)
        active_sz = np.empty(0, dtype=np.float32)

    if orientation_int == 0:
        n_all = len(all_positions_x)
        lookup_table = np.full((rows, cols), -1, dtype=np.int32)
        for i in range(len(position_index_keys_x)):
            lookup_table[position_index_keys_x[i], position_index_keys_y[i]] = position_index_values[i]

        inactive_flags = np.ones(n_all, dtype=np.bool_)
        for i in prange(n_all):
            if p0[all_positions_x[i], all_positions_y[i]] != 0:
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
            lookup_idx = lookup_table[int(px), int(py)]
            inactive_op[i] = opacity_values[lookup_idx] if lookup_idx != -1 else 0.0
    else:
        inactive_x = np.empty(0, dtype=np.float32)
        inactive_y = np.empty(0, dtype=np.float32)
        inactive_op = np.empty(0, dtype=np.float32)

    step1_x = np.concatenate((active_x, inactive_x)) - offset[0]
    step1_y = np.concatenate((active_y, inactive_y)) - offset[1]
    step1_z = np.zeros(len(step1_x), dtype=np.float32)
    step1_op = np.concatenate((active_op, inactive_op))
    step1_sz = np.concatenate((active_sz, np.full(len(inactive_x), inactive_screen_radius, dtype=np.float32)))
    step1_types = np.concatenate((
        np.zeros(len(active_x), dtype=np.int32),
        np.full(len(inactive_x), 3, dtype=np.int32),
    ))

    active_particle_count = 0
    for i in range(bubble_particles.shape[0]):
        if bubble_particles[i, BUBBLE_ACTIVE] > 0.0:
            active_particle_count += 1

    step2_x = np.empty(active_particle_count, dtype=np.float32)
    step2_y = np.empty(active_particle_count, dtype=np.float32)
    step2_z = np.empty(active_particle_count, dtype=np.float32)
    step2_sz = np.empty(active_particle_count, dtype=np.float32)
    write_index = 0
    for i in range(bubble_particles.shape[0]):
        if bubble_particles[i, BUBBLE_ACTIVE] <= 0.0:
            continue
        step2_x[write_index] = bubble_particles[i, BUBBLE_X] - offset[0]
        step2_y[write_index] = bubble_particles[i, BUBBLE_Y] - offset[1]
        step2_z[write_index] = bubble_particles[i, BUBBLE_Z]
        step2_sz[write_index] = _bubble_screen_radius(
            bubble_particles[i, BUBBLE_AREA],
            bubble_area_unit_m2,
            min_bubble_radius_m,
            max_bubble_radius_m,
            bubble_screen_radius_per_meter,
            min_bubble_screen_radius,
        )
        write_index += 1

    if orientation_int == 1 and max_snow_ttl > 0:
        snow_indices = np.nonzero(snow_ttl)
        snow_count = len(snow_indices[0])
        snow_x = snow_indices[1].astype(np.float32)
        snow_y = snow_indices[2].astype(np.float32)
        snow_z = (-snow_indices[0] * 5).astype(np.float32)
        snow_sz = np.empty(snow_count, dtype=np.float32)
        snow_op = np.empty(snow_count, dtype=np.float32)
        for i in prange(snow_count):
            z_idx = snow_indices[0][i]
            x_idx = snow_indices[1][i]
            y_idx = snow_indices[2][i]
            ttl_val = snow_ttl[z_idx, x_idx, y_idx]
            snow_sz[i] = snow_sizes[z_idx, x_idx, y_idx]
            snow_op[i] = np.float32(0.2) + (ttl_val / np.float32(max_snow_ttl)) * np.float32(0.8)
        snow_x -= offset[0]
        snow_y -= offset[1]
    else:
        snow_x = np.empty(0, dtype=np.float32)
        snow_y = np.empty(0, dtype=np.float32)
        snow_z = np.empty(0, dtype=np.float32)
        snow_sz = np.empty(0, dtype=np.float32)
        snow_op = np.empty(0, dtype=np.float32)

    all_x_no_light = np.concatenate((step1_x, step2_x, snow_x))
    all_y_no_light = np.concatenate((step1_y, step2_y, snow_y))
    all_z_no_light = np.concatenate((step1_z, step2_z, snow_z))
    all_sz_no_light = np.concatenate((step1_sz, step2_sz, snow_sz))
    all_op_no_light = np.concatenate((step1_op, np.ones(len(step2_x), dtype=np.float32), snow_op))

    if orientation_int == 1:
        num_light_particles = 200
        light_x = np.empty(num_light_particles, dtype=np.float32)
        light_y = np.empty(num_light_particles, dtype=np.float32)
        light_z = np.empty(num_light_particles, dtype=np.float32)
        light_sz = np.empty(num_light_particles, dtype=np.float32)
        light_op = np.empty(num_light_particles, dtype=np.float32)

        light_source_x = rows / 2
        light_source_y = cols / 2
        light_source_z = data_height + 50
        cone_length = (data_height + 50) * 0.4
        max_radius = max(rows, cols) / 1.2

        for i in prange(num_light_particles):
            z = light_source_z - np.random.power(2) * cone_length
            cone_ratio = (light_source_z - z) / cone_length
            radius = np.random.uniform(0, max_radius) * cone_ratio
            angle = np.random.uniform(0, 2 * np.pi)
            x = light_source_x + radius * np.cos(angle)
            y = light_source_y + radius * np.sin(angle)

            dist_to_axis = np.sqrt((x - light_source_x) ** 2 + (y - light_source_y) ** 2)
            dist_to_source = np.sqrt(dist_to_axis ** 2 + (z - light_source_z) ** 2)
            falloff_factor = (1 - dist_to_source / (data_height + 60)) ** 3
            radial_factor = 1 - dist_to_axis / max_radius
            opacity = radial_factor * falloff_factor * 0.8
            size = radial_factor * falloff_factor * light_particle_screen_radius

            light_x[i] = x - offset[0]
            light_y[i] = y - offset[1]
            light_z[i] = z
            light_sz[i] = max(0, size)
            light_op[i] = max(0, opacity)

        lampshade_x = np.array([light_source_x - offset[0]], dtype=np.float32)
        lampshade_y = np.array([light_source_y - offset[1]], dtype=np.float32)
        lampshade_z = np.array([light_source_z], dtype=np.float32)
        lampshade_sz = np.array([lampshade_screen_radius], dtype=np.float32)
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

    all_x = np.concatenate((all_x_no_light, light_x, lampshade_x))
    all_y = np.concatenate((all_y_no_light, light_y, lampshade_y))
    all_z = np.concatenate((all_z_no_light, light_z, lampshade_z))
    all_sz = np.concatenate((all_sz_no_light, light_sz, lampshade_sz))
    all_op = np.concatenate((all_op_no_light, light_op, lampshade_op))

    type_others = np.concatenate((
        step1_types,
        np.zeros(len(step2_x), dtype=np.int32),
        np.zeros(len(snow_x), dtype=np.int32),
    ))
    type_light = np.ones(len(light_x), dtype=np.int32)
    type_lampshade = np.full(len(lampshade_x), 2, dtype=np.int32)
    all_types = np.concatenate((type_others, type_light, type_lampshade))

    blend_factors_snow = np.zeros(len(snow_x), dtype=np.float32)
    blend_factors_step1 = np.zeros(len(step1_x), dtype=np.float32)
    blend_factors_step2 = np.zeros(len(step2_x), dtype=np.float32)

    if orientation_int == 1:
        light_center_x = rows / 2 - offset[0]
        light_center_y = cols / 2 - offset[1]
        max_light_radius_snow = max(rows, cols) / 1.2
        for i in prange(len(snow_x)):
            dist_to_center = np.sqrt((snow_x[i] - light_center_x) ** 2 + (snow_y[i] - light_center_y) ** 2)
            blend_factor = 1.0 - min(1.0, dist_to_center / max_light_radius_snow)
            blend_factors_snow[i] = blend_factor ** 2

        light_source_z = data_height + 50
        cone_length = (data_height + 50) * 1.0
        max_light_radius_base = max(rows, cols) / 1.2
        min_blend = 0.2
        for i in prange(len(step2_x)):
            px = step2_x[i]
            py = step2_y[i]
            pz = step2_z[i]
            if pz < light_source_z and pz > (light_source_z - cone_length):
                cone_ratio = (light_source_z - pz) / cone_length
                current_max_radius = max_light_radius_base * cone_ratio
                dist_to_axis = np.sqrt((px - light_center_x) ** 2 + (py - light_center_y) ** 2)
                if dist_to_axis < current_max_radius:
                    blend_factor = ((1.0 - (dist_to_axis / current_max_radius)) * 0.9) ** 2
                    blend_factors_step2[i] = min_blend + (1.0 - min_blend) * blend_factor
                else:
                    blend_factors_step2[i] = min_blend

    blend_factors_others = np.concatenate((blend_factors_step1, blend_factors_step2))
    blend_factors_light = np.zeros(len(light_x), dtype=np.float32)
    blend_factors_lampshade = np.zeros(len(lampshade_x), dtype=np.float32)
    all_color_blend_factors = np.concatenate((
        blend_factors_others,
        blend_factors_snow,
        blend_factors_light,
        blend_factors_lampshade,
    ))

    return all_x, all_y, all_z, all_sz, all_op, all_types, all_color_blend_factors


@njit(cache=True, nogil=True, fastmath=True)
def calculate_particle_colors_njit(all_types, all_color_blend_factors, all_opacity, base_color_r, base_color_g, base_color_b):
    n_particles = len(all_types)
    colors = np.empty((n_particles, 4), dtype=np.float32)

    orange_r, orange_g, orange_b = np.float32(1.0), np.float32(0.6), np.float32(0.0)
    black_r, black_g, black_b = np.float32(0.0), np.float32(0.0), np.float32(0.0)

    for i in prange(n_particles):
        particle_type = all_types[i]
        opacity = all_opacity[i]
        if particle_type == 3 and opacity < 0.34:
            opacity = 0.34

        if particle_type == 2:
            final_r = black_r
            final_g = black_g
            final_b = black_b
        elif particle_type == 1:
            final_r = orange_r
            final_g = orange_g
            final_b = orange_b
        else:
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
