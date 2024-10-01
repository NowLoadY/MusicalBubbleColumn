import matplotlib
matplotlib.use('Qt5Agg')  # 使用 Qt5 后端
import matplotlib.pyplot as plt
import numpy as np
from mido import MidiFile
import pygame
import threading
from collections import deque
from matplotlib.gridspec import GridSpec

class PatternVisualizer3D:
    def __init__(self, visualize_piano=True):
        self.visualize_piano = visualize_piano
        self._initialize_plot()
        self.position_list = self._generate_spiral_positions(120, 30, 30, 1, 18)
        self._initialize_data()
        self.data_no_thick = np.zeros((30, 120, 120))  # 未应用 total_thickness 的数据
        self.scaler = 1  # 初始scaler值
        self.final_volume = deque(maxlen=15)
        
    def _initialize_plot(self):
        self.fig = plt.figure(facecolor='#FFFAF0', figsize=(12, 8))
        if self.visualize_piano:
            gs = GridSpec(2, 1, height_ratios=[4, 1])
            self.ax = self.fig.add_subplot(gs[0], projection='3d')
        else:
            gs = GridSpec(1, 1)
            self.ax = self.fig.add_subplot(gs[0], projection='3d')
        self.azim_angle = 30
        self.ax.view_init(elev=-40, azim=self.azim_angle)
        plt.subplots_adjust(left=0.001, right=0.999, top=0.999, bottom=0.001)
        self._hide_axes_background()
        self.ax.grid(color='#9BCD9B')
        self.ax.set_facecolor((0, 0, 0, 0))
        self.ax.set_title('3D Pattern Visualization')
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')
        self.ax.set_zlim(0, 30)
        self.ax.set_box_aspect([1, 1, 4])

        if self.visualize_piano:
            self.piano_ax = self.fig.add_subplot(gs[1])
            self.piano_ax.set_xlim(0, 120)
            self.piano_ax.set_ylim(0, 1)
            self.piano_ax.axis('off')
            self.piano_keys = self.piano_ax.bar(range(120), [1]*120, color='gray', edgecolor='black')

    def _initialize_data(self):
        self.data = np.zeros((30, 120, 120))
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
        self.ax.view_init(elev=-40, azim=self.azim_angle)

    def _generate_spiral_positions(self, num_positions, center_x, center_y, inner_radius, outer_radius):
        positions = []
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
        self._update_axis_limits(positions)
        return positions

    def _update_axis_limits(self, positions):
        min_x, max_x = min(positions, key=lambda pos: pos[0])[0], max(positions, key=lambda pos: pos[0])[0]
        min_y, max_y = min(positions, key=lambda pos: pos[1])[1], max(positions, key=lambda pos: pos[1])[1]
        self.ax_xlim_min, self.ax_xlim_max = min_x, max_x
        self.ax_ylim_min, self.ax_ylim_max = min_y, max_y
        self.ax.set_xlim(self.ax_xlim_min, self.ax_xlim_max)
        self.ax.set_ylim(self.ax_ylim_min, self.ax_ylim_max)

    def _update_piano_keys(self, bit_array, volumes):
        if self.visualize_piano:
            for i, key in enumerate(self.piano_keys):
                if bit_array[i]:
                    alpha = min((volumes[i]/0.75+0.25*127) / 127, 1)  # 假设 velocity 的最大值为 127
                    new_color = (0, 0, 0, alpha)
                else:
                    new_color = 'white'
                if key.get_facecolor() != new_color:
                    key.set_color(new_color)

    def update_pattern(self, new_pattern, volumes, average_volume):
        if len(new_pattern) != 15:
            raise ValueError("new_pattern must be exactly 15 bytes long")
        bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
        self.data = np.roll(self.data, shift=-1, axis=0)
        self.data_no_thick = np.roll(self.data_no_thick, shift=-1, axis=0)  # 滚动更新 data_no_thick
        self.data[-1, :, :] = 0
        self.data_no_thick[-1, :, :] = 0  # 重置 data_no_thick 的最后一层
        self._update_thickness_list(bit_array)
        self._update_data_layer(bit_array, volumes, average_volume)
        self._draw_pattern()
        self._update_piano_keys(bit_array, volumes)  # 更新虚拟钢琴显示
        #self._draw_cylinder()
        self.fig.canvas.draw()
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
                self.data_no_thick[-1, x_center, y_center] = 1  # 记录未应用 total_thickness 的点
                for dx in range(-total_thickness, total_thickness + 1):
                    for dy in range(-total_thickness, total_thickness + 1):
                        if dx**2 + dy**2 <= total_thickness**2:
                            nx, ny = x_center + dx, y_center + dy
                            if (nx, ny) in position_set:
                                self.data[-1, nx, ny] = 1
        if variances:  # 检查 variances 是否为空
            if np.mean(variances) < 0.75:  # 平均值阈值，可根据需要调整
                self.scaler += 0.01
            else:
                self.scaler = max(0, min(self.scaler - 0.01, 2))

    def _draw_cylinder(self):
        # 计算圆柱面的参数
        center_x, center_y = 30, 30
        radius = max(np.linalg.norm(np.array([x, y]) - np.array([center_x, center_y])) for x, y in self.position_list)
        height = 30

        # 创建圆柱面
        z = np.linspace(0, height, 50)
        theta = np.linspace(0, 2 * np.pi, 100)
        theta_grid, z_grid = np.meshgrid(theta, z)
        x_grid = center_x + radius * np.cos(theta_grid)
        y_grid = center_y + radius * np.sin(theta_grid)

        # 绘制半透明圆柱面
        self.ax.plot_surface(x_grid, y_grid, z_grid, color='grey', alpha=0.1, edgecolor='none')

    def _calculate_opacity(self):
        # 根据位置顺序计算透明度
        opacity_list = [1 - (i / 120) * 0.9 for i in range(120)]  # 从1到0.1的透明度
        all_positions = self.all_positions
        return {pos: opacity_list[self.position_list.index(pos)] for pos in all_positions}

    def _draw_pattern(self):
        self.ax.cla()
        self.ax.set_xlim(self.ax_xlim_min, self.ax_xlim_max)
        self.ax.set_ylim(self.ax_ylim_min, self.ax_ylim_max)
        self.ax.set_zlim(0, 30)
        self.ax.grid(color='#9BCD9B')
        self.ax.set_box_aspect([1, 1, 4])
        self._hide_axes()

        x, y, z = np.nonzero(np.atleast_3d(self.data_no_thick[-1]))  # 使用 data_no_thick
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x, y, 30, c='black', marker='o', s=100)

        # 绘制未激活的灰色点（片段一）
        all_positions = set(self.position_list)
        active_positions = set(zip(x, y))
        inactive_positions = all_positions - active_positions

        # 绘制未激活的灰色点（片段二）
        opacity_dict = self.opacity_dict
        if inactive_positions:  # 只在有未激活点时绘制
            inactive_with_opacity = [(ix_val, iy_val, opacity_dict[(ix_val, iy_val)]) 
                                      for ix_val, iy_val in inactive_positions if (ix_val, iy_val) in opacity_dict]
            if inactive_with_opacity:  # 确保有点需要绘制
                ix_val, iy_val, opacity = zip(*inactive_with_opacity)
                self.ax.scatter(ix_val, iy_val, 30, c=[(0, 0, 0, op) for op in opacity], marker='o', s=5)
                
        # 绘制滚动的蓝色层
        all_x, all_y, all_z = [], [], []
        for i in range(1, 30):
            x, y, z = np.nonzero(np.atleast_3d(self.data[i]))
            if x.size > 0 and y.size > 0 and z.size > 0:
                all_x.extend(x)
                all_y.extend(y)
                all_z.extend(z + i)  # 将 z 值加上层数
        if all_x:  # 如果有点需要绘制
            self.ax.scatter(all_x, all_y, all_z, c='#6495ED', marker='o')

        # 绘制落地的层
        x, y, z = np.nonzero(np.atleast_3d(self.data[0]))
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x, y, z, c='lightblue', marker='*', s=100)

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
    for track in midi.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                min_note, max_note = min(min_note, msg.note), max(max_note, msg.note)

    def map_note_to_range(note):
        return max(0, min(int((note - min_note) / (max_note - min_note) * 120), 119))

    num_keys = 120
    key_activation = np.zeros(num_keys, dtype=int)
    clock = pygame.time.Clock()
    midi_iterator = iter(midi.play())
    new_pattern = bytes(15)
    last_update_time = pygame.time.get_ticks()
    update_interval = 100 // 60
    zero_pattern_interval = 10
    update_count = 0

    def process_midi():
        nonlocal new_pattern, update_count, volumes
        for msg in midi_iterator:
            if msg.type in ['note_on', 'note_off']:
                mapped_note = map_note_to_range(msg.note)
                if 0 <= mapped_note < num_keys:
                    key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg.velocity > 0) else 0
                    volumes[mapped_note] = msg.velocity if msg.type == 'note_on' else 0
                    #if msg.velocity > 0:
                    total_volumes.append(msg.velocity)
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
                visualizer.update_pattern(new_pattern, one_volumes, average_volume)
            else:
                visualizer.update_pattern(new_pattern, volumes, average_volume)
            last_update_time = current_time
            update_count += 1
        
        # 检查 MIDI 是否仍在播放
        if not pygame.mixer.music.get_busy() and np.sum(visualizer.data) == 0:
            break  # 如果 MIDI 播放完且数据已清空，则退出
        
        visualizer.update_view_angle(2)
        clock.tick(60)

    midi_thread.join()
    pygame.mixer.music.stop()

if __name__ == "__main__":
    visualize_piano = input("是否可视化虚拟钢琴？(y/n): ").strip().lower() == 'y'
    visualizer = PatternVisualizer3D(visualize_piano=visualize_piano)
    action_midi_visualization(visualizer, 'SomethingComforting_for_Piano_Solo.mid')
    #action_midi_visualization(visualizer, 'midi2.mid')