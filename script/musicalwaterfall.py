"""
musical waterfall!
"""
import matplotlib
matplotlib.use('Qt5Agg')  # 使用 Qt5 后端
import matplotlib.pyplot as plt
import numpy as np
from mido import MidiFile
import pygame
import threading
from collections import deque
from matplotlib.gridspec import GridSpec
from PyQt5 import QtGui

class PatternVisualizer3D:
    def __init__(self, visualize_piano=True, pos_type="Fibonacci", draw_index=False, orientation="up", terminal_show=True, draw_lines=True):
        self.orientation=orientation
        self.terminal_show=terminal_show
        self.draw_lines=draw_lines
        self.elev = 30
        self.draw_index = draw_index
        self.pos_type = pos_type
        self.total_center = (30, 30, 15)
        self.visualize_piano = visualize_piano
        self._initialize_plot()
        self.position_list = self._generate_positions(120, self.total_center[0], self.total_center[1], 1, 18, pos_type=self.pos_type)
        self._initialize_data()
        if self.pos_type!= "line":
            self.data_no_thick = np.zeros((30, 120, 120))  # 未应用 total_thickness 的数据
        else:
            self.data_no_thick = np.zeros((30, 1200, 120))
        self.scaler = 1  # 初始scaler值
        self.final_volume = deque(maxlen=15)

    def update_elev(self, val):
        self.elev = val

    def _initialize_plot(self):
        self.fig = plt.figure(facecolor='black', figsize=(12, 8))
        self.fig.canvas.manager.window.setWindowTitle("musical waterfall")
        PATH_TO_ICON = "icon.png"
        new_icon = QtGui.QIcon(PATH_TO_ICON)
        fig =plt.gcf()
        fig.canvas.manager.window.setWindowIcon(QtGui.QIcon(new_icon))
        if self.visualize_piano:
            if self.orientation == "down":
                gs = GridSpec(2, 1, height_ratios=[1, 20])
                self.piano_ax = self.fig.add_subplot(gs[0])
                self.ax = self.fig.add_subplot(gs[1], projection='3d')
            else:
                gs = GridSpec(2, 1, height_ratios=[20, 1])
                self.ax = self.fig.add_subplot(gs[0], projection='3d')
                self.piano_ax = self.fig.add_subplot(gs[1])
        else:
            gs = GridSpec(1, 1)
            self.ax = self.fig.add_subplot(gs[0], projection='3d')
        self.azim_angle = 30
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)
        plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
        self._hide_axes_background()
        self.ax.set_facecolor((0, 0, 0, 0))
        self.ax.set_zlim(0, 30)
        self.ax.set_box_aspect([1, 1, 4])
        self._create_base_3d_lines(2)
        self.elev_slider = plt.axes([0.1, 0.01 if self.orientation=="down" else 0.1, 0.8, 0.03], facecolor='none')  # 创建滑条位置并设置颜色
        self.elev_slider = plt.Slider(self.elev_slider, 'Elev', -90, 90, valinit=self.elev, color=(1,1,1,0.1), initcolor="none", track_color=(1,1,1,0.1), handle_style={'facecolor': 'black', 'edgecolor': '1', 'size': 20})  # 初始化滑条并设置颜色
        self.elev_slider.on_changed(self.update_elev)  # 绑定滑条变化事件
        if self.visualize_piano:
            self.piano_ax.set_xlim(0, 120)
            self.piano_ax.set_ylim(0, 1)
            self.piano_ax.axis('off')
            self.piano_keys = self.piano_ax.bar(range(120), [1]*120, color='gray', edgecolor='black', width=0.5)

    def _initialize_data(self):
        if self.pos_type!= "line":
            self.data = np.zeros((30, 120, 120))
        else:
            self.data = np.zeros((30, 1200, 120))
        self.thickness_list = [0] * 120
        self.old_pattern = None
        self.degradation_active = [False] * 120
        self.all_positions = set(self.position_list)
        self.opacity_dict = self._calculate_opacity()  # 计算透明度列表

    def _hide_axes_background(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.pane.fill = False
            axis.set_pane_color((0, 0, 0, 0))

    def update_view_angle(self, d_angle):
        self.azim_angle = (self.azim_angle + d_angle) % 360
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)

    def _generate_positions(self, num_positions, center_x, center_y, inner_radius, outer_radius, pos_type="line"):
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
                    angle = 2 * np.pi * i / num_positions  # 计算角度
                    radius = inner_radius + (outer_radius - inner_radius) * 0.5
                    x = int(center_x + radius * np.cos(angle))
                    y = int(center_y + radius * np.sin(angle))
                    if (x, y) not in positions:
                        positions.append((x, y))
                outer_radius += 1
        elif pos_type == "line":
            for i in range(num_positions):
                x = int(10*i)
                y = center_y
                positions.append((x, y))
        print(len(positions))
        self._update_axis_limits(positions)
        return positions
    
    def _update_axis_limits(self, positions):
        min_x, max_x = min(positions, key=lambda pos: pos[0])[0], max(positions, key=lambda pos: pos[0])[0]
        try:
            min_y, max_y = min(positions, key=lambda pos: pos[1])[1], max(positions, key=lambda pos: pos[1])[1]
        except:
            min_y, max_y = -10, 10
        self.ax_xlim_min, self.ax_xlim_max = min_x, max_x
        self.ax_ylim_min, self.ax_ylim_max = min_y, max_y
        self.ax.set_xlim(self.ax_xlim_min, self.ax_xlim_max)
        self.ax.set_ylim(self.ax_ylim_min, self.ax_ylim_max)

    def _update_piano_keys(self, bit_array, volumes):
        if self.visualize_piano:
            for i, key in enumerate(self.piano_keys):
                if bit_array[i]:
                    alpha = min((volumes[i]*0.2+0.8*127) / 127, 1)  # velocity 的最大值为 127
                    new_color = (1, 1, 1, alpha)
                else:
                    new_color = (1, 1, 1, 0.2)
                if key.get_facecolor() != new_color:
                    key.set_color(new_color)

    def _create_base_3d_lines(self, num_lines):
        # 创建num_lines条3维折线条
        self.base_3d_lines = []
        for _ in range(num_lines):
            # 随机生成每条折线的坐标
            cx, cy, cz = self.total_center
            line = [(cx+np.random.uniform(-100, 100), cy+np.random.uniform(-100, 100), cz+np.random.uniform(-1, 1)) for _ in range(10)]
            self.base_3d_lines.append(line)

    def _draw_random_3d_lines(self, change_val=5, x_rand=(-100, 100), y_rand=(-100, 100), z_rand=(-30, 30), max_length=50):
        # 绘制折线段（白色）
        if change_val > 1:
            cx, cy, cz = self.total_center
            for i in range(len(self.base_3d_lines)):
                line = self.base_3d_lines[i]
                # 对每个折线段的每个坐标点都进行小范围的随机偏移并限制边界
                offset_line = [(np.clip(x + np.random.randint(-change_val, change_val), cx+x_rand[0], cx+x_rand[1]), 
                                np.clip(y + np.random.randint(-change_val, change_val), cy+y_rand[0], cy+y_rand[1]), 
                                np.clip(z + np.random.randint(-change_val, change_val), cz+z_rand[0], cz+z_rand[1])) 
                                for x, y, z in line]
                # 计算线段长度并进行缩放
                length = np.linalg.norm(np.array(offset_line[-1]) - np.array(offset_line[0]))
                # 先限制长度
                if length > max_length:
                    # 计算折线的中心
                    center_x = np.mean([x for x, _, _ in offset_line])
                    center_y = np.mean([y for _, y, _ in offset_line])
                    center_z = np.mean([z for _, _, z in offset_line])
                    # 根据中心点进行缩放
                    scale = (max_length / length)**(1/3)
                    offset_line = [(np.clip(center_x + (x - center_x) * scale, x_rand[0], x_rand[1]), 
                                    np.clip(center_y + (y - center_y) * scale, y_rand[0], y_rand[1]), 
                                    np.clip(center_z + (z - center_z) * scale, z_rand[0], z_rand[1])) for x, y, z in offset_line]
                
                # 限制每条折线的平均中心
                avg_center = np.mean(offset_line, axis=0)
                bias = self.total_center - avg_center
                offset_line = [(x + bias[0], 
                                y + bias[1], 
                                z + bias[2]) for x, y, z in offset_line]

                # 更新 self.base_3d_lines
                self.base_3d_lines[i] = offset_line
                # 绘制偏移后的结果
                xs, ys, zs = zip(*offset_line)
                self.ax.plot3D(xs, ys, zs, color=(1,1,1,0.5), linewidth=0.1)
                self.ax.scatter(xs, ys, zs, c='white', marker='o', s=1)
        else:
            for line in self.base_3d_lines:
                xs, ys, zs = zip(*line)
                self.ax.plot3D(xs, ys, zs, color=(1,1,1,0.5), linewidth=0.1)
                self.ax.scatter(xs, ys, zs, c='white', marker='o', s=1)

    def update_pattern(self, new_pattern, volumes, average_volume, now_velocity=1):
        if len(new_pattern) != 15:
            raise ValueError("new_pattern must be exactly 15 bytes long")
        bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
        self.data = np.roll(self.data, shift=-1 if self.orientation=="down" else 1, axis=0)
        self.data_no_thick = np.roll(self.data_no_thick, shift=-1 if self.orientation=="down" else 1, axis=0)  # 滚动更新 data_no_thick
        self.data[-1 if self.orientation=="down" else 0, :, :] = 0
        self.data_no_thick[-1 if self.orientation=="down" else 0, :, :] = 0  # 重置 data_no_thick 的最后一层
        self.ax.cla()
        if self.terminal_show:
            print("".join(str(bit_array).replace("[","").replace("]","").replace("0"," ").replace("1","o").replace("\r","").replace("\n","")))
        self._update_thickness_list(bit_array)
        self._update_data_layer(bit_array, volumes, average_volume)
        if self.draw_lines:
            self._draw_random_3d_lines(change_val=5*now_velocity/127)
        self._draw_pattern()
        self._update_piano_keys(bit_array, volumes)  # 更新虚拟钢琴显示
        if not self.pos_type == "line":
            self._draw_cylinder()
        self.fig.canvas.draw_idle()
        plt.pause(0.01)
        self.old_pattern = new_pattern

    def _update_thickness_list(self, bit_array):
        if self.old_pattern is not None:
            old_bit_array = np.unpackbits(np.frombuffer(self.old_pattern, dtype=np.uint8))
            for i in range(120):
                if bit_array[i] == old_bit_array[i] == 1 and self.thickness_list[i] >= 1:
                    self.degradation_active[i] = True
                else:
                    self.thickness_list[i] = 0
                    self.degradation_active[i] = False

    def _update_data_layer(self, bit_array, volumes, average_volume):
        position_set = set(self.position_list)
        variances = []
        for i in range(120):
            if bit_array[i]:
                x_center, y_center = self.position_list[i]
                volume_factor = (max((volumes[i] - average_volume), 0) / average_volume) if average_volume else 0
                self.final_volume.append(self.thickness_list[i] + (self.scaler * volume_factor) ** 2)
                if len(self.final_volume) > 10:
                    variance = np.var(self.final_volume)
                    variances.append(variance)
                thickness = min(5, int(self.thickness_list[i] + (self.scaler * volume_factor) ** 2))
                if self.degradation_active[i]:
                    self.thickness_list[i] = max(0, thickness - 1)
                else:
                    self.thickness_list[i] = thickness
                total_thickness = self.thickness_list[i] + (1 * (119 - i)) // 119
                self.data_no_thick[-1 if self.orientation=="down" else 0, x_center, y_center] = 1  # 记录未应用 total_thickness 的点
                for dx in range(-total_thickness, total_thickness + 1):
                    for dy in range(-total_thickness, total_thickness + 1):
                        if dx**2 + dy**2 <= total_thickness**2:
                            nx, ny = x_center + dx, y_center + dy
                            if (nx, ny) in position_set:
                                self.data[-1 if self.orientation=="down" else 0, nx, ny] = 1
        if variances:  # 检查 variances 是否为空
            if np.mean(variances) < 0.75:  # 平均值阈值，根据需要调整
                self.scaler += 0.01
            else:
                self.scaler = max(0, min(self.scaler - 0.001, 2))

    def _draw_cylinder(self, color='white', alpha=0.05):
        # 计算圆柱面的参数
        center_x, center_y = 30, 30
        radius = max(np.linalg.norm(np.array([x, y]) - np.array([center_x, center_y])) for x, y in self.position_list)
        height = 30

        # 创建圆柱面
        z = np.linspace(0, height, 50)
        theta = np.linspace(0, 2 * np.pi, 30)
        theta_grid, z_grid = np.meshgrid(theta, z)
        x_grid = center_x + radius * np.cos(theta_grid)
        y_grid = center_y + radius * np.sin(theta_grid)

        # 绘制半透明圆柱面
        self.ax.plot_surface(x_grid, y_grid, z_grid, color=color, alpha=alpha, edgecolor='none')

    def _calculate_opacity(self):
        # 根据位置顺序计算透明度
        opacity_list = [(i / 120) * 0.9 for i in range(120)]
        all_positions = self.all_positions
        return {pos: opacity_list[self.position_list.index(pos)] for pos in all_positions}

    def _draw_pattern(self):
        self.ax.set_xlim(self.ax_xlim_min, self.ax_xlim_max)
        self.ax.set_ylim(self.ax_ylim_min, self.ax_ylim_max)
        self.ax.set_zlim(0, 30)
        self.ax.set_box_aspect([1, 1, 4])
        self._hide_axes()

        x, y, z = np.nonzero(np.atleast_3d(self.data_no_thick[-1 if self.orientation=="down" else 0]))  # 使用 data_no_thick
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x, y, 30 if self.orientation=="down" else 0, c='white', marker='o', s=100)
        
        # 绘制未激活的灰色点（片段一）
        all_positions = set(self.position_list)
        active_positions = set(zip(x, y))
        inactive_positions = all_positions - active_positions
        # 绘制未激活的灰色点（片段二）
        opacity_dict = self.opacity_dict
        if inactive_positions:
            inactive_with_opacity = [(ix_val, iy_val, opacity_dict[(ix_val, iy_val)]) 
                                      for ix_val, iy_val in inactive_positions if (ix_val, iy_val) in opacity_dict]
            if inactive_with_opacity:
                ix_val, iy_val, opacity = zip(*inactive_with_opacity)
                self.ax.scatter(ix_val, iy_val, 30 if self.orientation=="down" else 0, c=[(1, 1, 1, op) for op in opacity], marker='o', s=5)
                if self.draw_index:
                    # 绘制索引号
                    for (x_val, y_val, _) in inactive_with_opacity:
                        index_position = self.position_list.index((x_val, y_val))
                        self.ax.text(x_val, y_val, 30 if self.orientation=="down" else 0, str(index_position), color='white', fontsize=6)
        # 绘制滚动的层
        all_x, all_y, all_z = [], [], []
        for i in range(1, 30):
            x, y, z = np.nonzero(np.atleast_3d(self.data[i]))
            if x.size > 0 and y.size > 0 and z.size > 0:
                all_x.extend(x)
                all_y.extend(y)
                all_z.extend(z + i)  # 将 z 值加上层数

        if all_x:  # 如果有点需要绘制
            self.ax.scatter(all_x, all_y, all_z, c='#FFFAFA', marker='o')

        # 绘制落地的层
        x, y, z = np.nonzero(np.atleast_3d(self.data[0 if self.orientation=="down" else 29]))
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x, y, z if self.orientation=="down" else 30, c='white', marker='*', s=200)

    def _hide_axes(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.set_major_formatter(plt.NullFormatter())
            axis.set_visible(False)
            axis.line.set_visible(False)  # 隐藏坐标轴线
            axis.set_ticks([])  # 隐藏刻度线

def action_midi_visualization(visualizer, midi_path):
    try:
        midi = MidiFile(midi_path)
    except OSError as e:
        print(f"Error loading MIDI file: {e}")
        return
    pygame.mixer.init()
    pygame.mixer.music.load(midi_path)
    pygame.mixer.music.play()

    min_note, max_note = 127, 0
    total_volumes = deque(maxlen=480)
    now_velocity = 1
    for track in midi.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                min_note, max_note = min(min_note, msg.note), max(max_note, msg.note)

    def map_note_to_range(note):
        return max(0, min(int((note - min_note) / (max_note - min_note) * 120), 119))

    num_keys = 120
    key_activation = np.zeros(num_keys, dtype=int)
    midi_iterator = iter(midi.play())
    new_pattern = bytes(15)
    last_update_time = pygame.time.get_ticks()
    update_interval = 100 // 60
    zero_pattern_interval = 10
    update_count = 0

    def process_midi():
        nonlocal new_pattern, update_count, volumes, now_velocity
        for msg in midi_iterator:
            if msg.type in ['note_on', 'note_off']:
                mapped_note = map_note_to_range(msg.note)
                if 0 <= mapped_note < num_keys:
                    key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg.velocity > 0) else 0
                    volumes[mapped_note] = msg.velocity if msg.type == 'note_on' else 0
                    total_volumes.append(msg.velocity)
                    now_velocity = msg.velocity
                new_pattern = np.packbits(key_activation).tobytes()
                update_count = 0
            if not pygame.mixer.music.get_busy():
                break

    midi_thread = threading.Thread(target=process_midi)
    midi_thread.start()
    volumes = [0] * num_keys
    average_volume = 0

    while True:
        if total_volumes:
            average_volume = sum(total_volumes) / len(total_volumes)
        current_time = pygame.time.get_ticks()
        if current_time - last_update_time >= update_interval:
            if update_count % zero_pattern_interval == 0:
                new_pattern = bytes(15)
                one_volumes = [1] * 120
                visualizer.update_pattern(new_pattern, one_volumes, average_volume,now_velocity)
            else:
                visualizer.update_pattern(new_pattern, volumes, average_volume,now_velocity)
            last_update_time = current_time
            update_count += 1
        
        # 检查 MIDI 是否仍在播放
        if not pygame.mixer.music.get_busy() and np.sum(visualizer.data) == 0:
            break  # 如果 MIDI 播放完且数据已清空，则退出
        visualizer.update_view_angle(2)

    midi_thread.join()
    pygame.mixer.music.stop()

if __name__ == "__main__":
    pygame.init()
    visualize_piano = input("是否可视化虚拟钢琴？(y/n): ").strip().lower() == 'y'
    visualizer = PatternVisualizer3D(visualize_piano=visualize_piano, orientation="up", pos_type="Fibonacci", draw_lines=True)#Fibonacci
    action_midi_visualization(visualizer, 'SomethingComforting_for_Piano_Solo.mid')
    #action_midi_visualization(visualizer, 'Can_you_hear_the_music.mid')
