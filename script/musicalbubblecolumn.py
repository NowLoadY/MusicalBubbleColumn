"""
Musical Bubble Column!
"""
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import numpy as np
from mido import MidiFile
import pygame
import threading
from collections import deque
from matplotlib.gridspec import GridSpec
from PyQt5 import QtGui
import os.path as os_path
import pygame.midi
from PyQt5.QtWidgets import QApplication, QFileDialog
import sys
from scipy.spatial import cKDTree
from PyQt5 import QtCore
from numba import njit


class PatternVisualizer3D:
    def __init__(self, visualize_piano=False, pos_type="Fibonacci", draw_index=False, orientation="up"):
        self.orientation=orientation
        self.data_height = 560
        self.draw_index = draw_index
        self.pos_type = pos_type
        self.total_center = (0, 0, self.data_height//2)
        self.visualize_piano = visualize_piano
        self.working=True
        self._initialize_plot()
        self.position_list = self._generate_positions(120, self.total_center[0], self.total_center[1], 1, 18, pos_type=self.pos_type)
        self._initialize_data()
        self.scaler = 1
        self.final_volume = np.zeros(30)
        self.final_volume_index = 0  # 用于跟踪数组的当前索引
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()

    def _initialize_plot(self):
        self.elev = 30
        self.target_elev = 30
        self.azim_angle = 30
        self.target_azim_speed = 2
        self.fig = plt.figure(facecolor='black', figsize=(6, 7))
        self.fig.canvas.manager.window.setWindowTitle("🎼Musical Bubble Column!🎹")
        base_path = os_path.dirname(os_path.abspath(__file__))
        PATH_TO_ICON = os_path.join(base_path, "icon.png")
        new_icon = QtGui.QIcon(PATH_TO_ICON)
        fig = plt.gcf()
        fig.canvas.manager.window.setWindowIcon(QtGui.QIcon(new_icon))
        if self.visualize_piano:
            if self.orientation == "down":
                gs = GridSpec(2, 1, height_ratios=[1, 30])
                self.piano_ax = self.fig.add_subplot(gs[0])
                self.ax = self.fig.add_subplot(gs[1], projection='3d')
            else:
                gs = GridSpec(2, 1, height_ratios=[30, 1])
                self.ax = self.fig.add_subplot(gs[0], projection='3d')
                self.piano_ax = self.fig.add_subplot(gs[1])
        else:
            gs = GridSpec(1, 1)
            self.ax = self.fig.add_subplot(gs[0], projection='3d')
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self._hide_axes()
        self.ax.set_facecolor((0, 0, 0, 0))
        self.ax.set_box_aspect([1, 1, 4])
        self.elev_slider = plt.axes([0.9, 0.2 if self.orientation=="down" else 0.1, 0.03, 0.6], facecolor='none')  # 创建滑条位置并设置颜色
        self.elev_slider = plt.Slider(self.elev_slider, 'Elev', 0, 90, orientation='vertical', valinit=self.elev, color=(1,1,1,0.0), initcolor="none", track_color=(1,1,1,0.05), handle_style={'facecolor': 'none', 'edgecolor': '1', 'size': 10})  # 初始化滑条并设置颜色
        self.elev_slider.on_changed(self.update_elev)  # 绑定滑条变化事件
        self.azim_slider = plt.axes([0.2, 0.01 if self.orientation=="down" else 0.1, 0.6, 0.03], facecolor='none')  # 创建滑条位置并设置颜色
        self.azim_slider = plt.Slider(self.azim_slider, 'Azim', -5, 5, orientation='horizontal', valinit=self.target_azim_speed, color=(1,1,1,0.0), initcolor="none", track_color=(1,1,1,0.05), handle_style={'facecolor': 'none', 'edgecolor': '1', 'size': 10})  # 初始化滑条并设置颜色
        self.azim_slider.on_changed(self.update_azim)  # 绑定滑条变化事件
        self.fig.canvas.mpl_connect('close_event', self.handle_close)
        if self.visualize_piano:
            self.piano_ax.set_xlim(0, 120)
            self.piano_ax.set_ylim(0, 1)
            self.piano_ax.axis('off')
            self.piano_keys = self.piano_ax.bar(range(120), [1]*120, color='gray', edgecolor='black', width=0.5)

    def _initialize_data(self):
        # 动态data大小
        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)
        self.pattern_data_required_size = (self.data_height, max_size + 1, max_size + 1)  # +1 因为索引从 0 开始
        self.pattern_data = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        self.pattern_data_thickness = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        print(f"required_size {self.pattern_data_required_size}")
        self.thickness_list = [0] * 120
        self.all_positions = set(self.position_list)
        self.position_tree = cKDTree(self.position_list)  # 创建KD树
        self.opacity_dict = self._calculate_opacity()

    def _generate_positions(self, num_positions, center_x, center_y, inner_radius, outer_radius, pos_type="Fibonacci"):
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

        self._update_axis_limits(positions)
        # 计算偏移量
        min_x = min(pos[0] for pos in positions)
        min_y = min(pos[1] for pos in positions)
        self.offset = (-min_x, -min_y)
        # 应用偏移量
        positions = [(x + self.offset[0], y + self.offset[1]) for x, y in positions]
        return positions

    def update_pattern(self, new_pattern, volumes, average_volume, radius=5):
        if isinstance(new_pattern, bytes):
            bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
        elif isinstance(new_pattern, list) and all(isinstance(coord, tuple) and len(coord) == 2 for coord in new_pattern):
            bit_array = np.zeros(120, dtype=np.uint8)
            for coord in new_pattern:
                # 查找最近的坐标
                adjusted_coord = (coord[0] + self.offset[0], coord[1] + self.offset[1])
                dist, index = self.position_tree.query(adjusted_coord, distance_upper_bound=radius)
                if dist != float('inf'):  # 如果找到在半径范围内的点
                    bit_array[index] = 1
        else:
            raise ValueError("new_pattern must be either a bytes object or a list of (x, y) tuples.")

        # 重置最后一层的pattern_data 和 pattern_data_thickness，淘汰边缘的旧数据
        self.pattern_data[-1 if self.orientation == "down" else 0, :, :] = 0
        self.pattern_data_thickness[-1 if self.orientation == "down" else 0, :, :] = 0
        self.azim_angle = (self.azim_angle - self.target_azim_speed) % 360
        self.elev = self.elev + (self.target_elev - self.elev) * 0.1
        self._update_data_layer(bit_array, volumes, average_volume)
        
        self.ax.cla()
        self.ax.set_zlim(0, self.data_height+2)
        self._hide_axes()
        self._draw_pattern()
        if self.visualize_piano:
            self._update_piano_keys(bit_array, volumes)
        
        plt.pause(0.002)

    def _update_data_layer(self, bit_array, volumes, average_volume):
        variances = add_pattern(bit_array, volumes, average_volume, self.position_list, self.final_volume, self.final_volume_index, self.scaler, self.thickness_list, self.pattern_data, self.pattern_data_thickness, self.orientation)
        pattern_data_temp, pattern_data_thickness_temp = calculate_bubble(self.pattern_data, self.pattern_data_thickness, self.data_height)

        # 更新非边缘层
        for layer in range(1, self.data_height):
            self.pattern_data[layer] = pattern_data_temp[layer]
            self.pattern_data_thickness[layer] = pattern_data_thickness_temp[layer]

        if variances:
            variances_threashhold = 8
            if np.mean(variances) < variances_threashhold:  # 平均值阈值，根据需要调整
                self.scaler += 0.01
            else:
                self.scaler = max(0, self.scaler - 0.01)

    def _draw_pattern(self):
        # 第一层点集
        x, y, z = np.nonzero(np.atleast_3d(self.pattern_data[-1 if self.orientation=="down" else 0]))  # 使用 pattern_data
        len_x = len(x)
        opacity = [0.8]*len_x + [0.3]*len_x + [0.1]*len_x
        size_list = [100]*len_x + [250]*len_x + [500]*len_x
        x = np.append(np.append(x, x), x)
        y = np.append(np.append(y, y), y)
        # 底盘点集
        # 获取非活动位置的坐标和透明度
        active_positions = set(zip(x, y))
        inactive_positions = self.all_positions - active_positions
        ix_val, iy_val, inactive_opacity = [], [], []
        if inactive_positions:
            inactive_with_opacity = [(ix_val, iy_val, self.opacity_dict[self.position_list.index((ix_val, iy_val))]) 
                                      for ix_val, iy_val in inactive_positions]
            if inactive_with_opacity:
                ix_val, iy_val, inactive_opacity = zip(*inactive_with_opacity)
        
        # 合并所有点的坐标、透明度和大小
        all_x = np.concatenate((x, np.array(ix_val)))
        all_y = np.concatenate((y, np.array(iy_val)))
        all_opacity = opacity + list(inactive_opacity)
        all_sizes = size_list + [10] * len(ix_val)
        
        if all_x.size > 0 and all_y.size > 0:
            self.ax.scatter(all_x - self.offset[0], all_y - self.offset[1], self.data_height if self.orientation=="down" else 0, c=[(1, 1, 1, op) for op in all_opacity], marker='o', s=all_sizes)

        # 绘制滚动的层
        all_x, all_y, all_z, all_sizes = [], [], [], []  # 用于存储大小的列表
        # 获取所有非零点的坐标
        nonzero_indices = np.nonzero(self.pattern_data[1:self.data_height])  # 从第一层到最后一层
        x, y, z = nonzero_indices[1], nonzero_indices[2], nonzero_indices[0] + 1  # z 值加上层数
        
        if x.size > 0 and y.size > 0 and z.size > 0:
            all_x.extend(x - self.offset[0])
            all_y.extend(y - self.offset[1])
            all_z.extend(z)  # z 值已经加上层数
            
            # 获取对应位置的厚度值
            thickness = self.pattern_data_thickness[1:self.data_height][nonzero_indices]  # 使用索引获取厚度值
            sizes = np.clip(thickness * 5, 0, 500)  # 根据需求调整厚度到大小的映射
            
            all_sizes.extend(sizes)  # 将大小添加到列表中

        if all_x:  # 如果有点需要绘制
            self.ax.scatter(all_x, all_y, all_z, c='white', marker='o', s=all_sizes)
            
        # 绘制最后一层
        x, y, z = np.nonzero(np.atleast_3d(self.pattern_data[0 if self.orientation=="down" else self.data_height-1]))
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x - self.offset[0], y - self.offset[1], z if self.orientation=="down" else self.data_height, c='white', marker='*', s=200)

    def handle_close(self, event):
        plt.close(self.fig)
        self.working = False

    def update_elev(self, val):
        self.target_elev = val

    def update_azim(self, val):
        self.target_azim_speed = val

    def update_view_angle(self):
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)

    def _update_axis_limits(self, positions):
        min_x, max_x = min(positions, key=lambda pos: pos[0])[0], max(positions, key=lambda pos: pos[0])[0]
        min_y, max_y = min(positions, key=lambda pos: pos[1])[1], max(positions, key=lambda pos: pos[1])[1]
        self.ax_xlim_min, self.ax_xlim_max = min_x, max_x
        self.ax_ylim_min, self.ax_ylim_max = min_y, max_y

    def _update_piano_keys(self, bit_array, volumes):
        for i, key in enumerate(self.piano_keys):
            if bit_array[i]:
                alpha = min((volumes[i]*0.2+0.8*127) / 127, 1)  # velocity 的最大值为 127
                new_color = (1, 1, 1, alpha)
            else:
                new_color = (1, 1, 1, 0.2)
            if key.get_facecolor() != new_color:
                key.set_color(new_color)

    def _calculate_opacity(self):
        # 根据位置顺序计算透明度
        opacity_array = np.array([(i / 120) * 0.9 for i in range(120)])  # 使用 NumPy 数组
        return opacity_array  # 直接返回 NumPy 数组

    def _hide_axes(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.pane.fill = False
            axis.set_pane_color((0, 0, 0, 0))
            axis.set_major_formatter(plt.NullFormatter())
            axis.set_visible(False)
            axis.line.set_visible(False)  # 隐藏坐标轴线
            axis.set_ticks([])  # 隐藏刻度线

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
    # 针对每个非边缘层的气泡计算上升速度
    pattern_data_temp = np.zeros(pattern_data.shape, dtype=np.float32)
    pattern_data_thickness_temp = np.zeros(pattern_data_thickness.shape, dtype=np.float32)

    for layer in range(0, data_height - 1):  # 遍历非边缘层
        x, y = np.nonzero(pattern_data[layer])  # 获取当前层的气泡位置
        if x.size == 0:  # 如果当前层没有气泡，跳过当前层
            continue
        
        thickness = pattern_data_thickness[layer]  # 获取当前气泡的厚度
        for ix, iy in zip(x, y):
            th = thickness[ix, iy]  # 获取厚度值
            rise_speed = 5 + np.minimum(10 * (layer / (3 * data_height / 4)), 10) + np.minimum(th * 0.1, 8)  # 计算上升速度
            rise_speed = np.clip(np.array(rise_speed), 0, 18)  # 限制上升速度的最大值
            target_layer = np.minimum(layer + rise_speed.astype(np.int32), data_height - 1)  # 目标层

            # 检查目标位置是否已有气泡
            if pattern_data_temp[target_layer, ix, iy] == 1:
                # 如果有气泡，则将厚度相加
                pattern_data_thickness_temp[target_layer][ix, iy] += th
            else:
                pattern_data_thickness_temp[target_layer][ix, iy] = th  # 更新新位置的厚度
            pattern_data_temp[target_layer, ix, iy] = 1  # 使气泡上升

    # 合并相邻气泡
    for layer in range(data_height):
        x, y = np.nonzero(pattern_data_temp[layer])  # 获取当前层的气泡位置
        for i in range(len(x)):
            for j in range(i + 1, len(x)):
                # 计算气泡之间的距离
                distance = np.sqrt((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2)
                if 2*distance < np.sqrt(pattern_data_thickness_temp[layer, x[i], y[i]] + pattern_data_thickness_temp[layer, x[j], y[j]]):
                    # 合并气泡
                    new_x = (x[i] + x[j]) // 2
                    new_y = (y[i] + y[j]) // 2
                    pattern_data_temp[layer, new_x, new_y] = 1
                    pattern_data_thickness_temp[layer, new_x, new_y] = np.minimum(500, pattern_data_thickness_temp[layer, x[i], y[i]] + pattern_data_thickness_temp[layer, x[j], y[j]])  # 使用更新后的厚度
                    # 移除原气泡及其厚度
                    pattern_data_temp[layer, x[i], y[i]] = 0
                    pattern_data_temp[layer, x[j], y[j]] = 0
                    pattern_data_thickness_temp[layer, x[i], y[i]] = 0
                    pattern_data_thickness_temp[layer, x[j], y[j]] = 0

    return pattern_data_temp, pattern_data_thickness_temp

def action_midi_visualization(visualizer, midi_path):
    temp_midi_path = "temp_midi_file.mid"  # 定义临时MIDI文件路径

    midi = MidiFile(midi_path)
    for track in midi.tracks:
        for msg in track:
            if msg.type == 'program_change':
                msg.program = 0  # 将音色更改为钢琴音色
    midi.save(temp_midi_path)

    pygame.mixer.init()
    pygame.mixer.music.load(temp_midi_path)
    pygame.mixer.music.play()
    min_note, max_note = 127, 0
    total_volumes = deque(maxlen=480)
    for track in midi.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                min_note, max_note = min(min_note, msg.note), max(max_note, msg.note)

    def map_note_to_range(note):
        note_array = np.clip((note - min_note) / (max_note - min_note) * 120, 0, 119)
        return int(note_array)

    num_keys = 120
    volumes = [0] * num_keys
    average_volume = 0
    key_activation = np.zeros(num_keys, dtype=int)
    midi_iterator = iter(midi.play())
    new_pattern = bytes(15)
    zero_pattern_interval = 2
    update_count = 0
    process_midi_thread_bool=True

    def process_midi():
        nonlocal new_pattern, update_count, volumes, process_midi_thread_bool
        for msg in midi_iterator:
            if msg.type in ['note_on', 'note_off']:
                mapped_note = map_note_to_range(msg.note)
                if 0 <= mapped_note < num_keys:
                    key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg.velocity > 0) else 0
                    volumes[mapped_note] = msg.velocity if msg.type == 'note_on' else 0
                    total_volumes.append(msg.velocity)

                new_pattern = np.packbits(key_activation).tobytes()
                update_count = 0
            
            if not pygame.mixer.music.get_busy() or not process_midi_thread_bool:
                break

    midi_thread = threading.Thread(target=process_midi)
    midi_thread.start()

    while True:
        visualizer.working = True
        if total_volumes:
            average_volume = sum(total_volumes) / len(total_volumes)
        if update_count % zero_pattern_interval == 0:
            new_pattern = bytes(15)
            one_volumes = [1] * 120
            visualizer.update_pattern(new_pattern, one_volumes, average_volume)
        else:
            visualizer.update_pattern(new_pattern, volumes, average_volume)
        update_count += 1
        
        # 检查 MIDI 是否仍在播放
        if not pygame.mixer.music.get_busy() and np.sum(visualizer.pattern_data) == 0:
            visualizer.working = False

            break  # 如果 MIDI 播放完且数据已清空，则退出
        visualizer.update_view_angle()
        if not visualizer.working:
            process_midi_thread_bool=False
            break

    midi_thread.join()
    pygame.mixer.music.stop()

def choose_midi_file(app):
    # 设置全局样式表
    app.setStyleSheet("""
        QFileDialog {
            background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #e0e0e0);
            color: #000000;
            border-radius: 15px;
        }
        QPushButton {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #000000;
            padding: 5px;
            border-radius: 10px;
        }
        QPushButton:hover {
            background-color: #f0f0f0;
        }
        QLineEdit {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #000000;
            border-radius: 10px;
        }
        QLabel {
            color: #000000;
        }
    """)

    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog  # 使用非原生对话框
    options |= QFileDialog.HideNameFilterDetails  # 隐藏文件类型过滤器的详细信息
    dialog = QFileDialog(None, "选择MIDI文件", "", "MIDI files (*.mid *.midi);;All files (*.*)", options=options)
    dialog.setFileMode(QFileDialog.ExistingFile)  # 只允许选择现有文件
    dialog.setViewMode(QFileDialog.List)
    dialog.resize(1200, 1200)  # 设置默认窗口大小
    dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)  # 设置窗口置顶
    if dialog.exec_() == QFileDialog.Accepted:
        midi_file_path = dialog.selectedFiles()[0]
    else:
        midi_file_path = None
    return midi_file_path


if __name__ == "__main__":
    pygame.init()
    pygame.midi.init()
    app = QApplication(sys.argv)  # 在主线程中创建 QApplication 实例
    visualizer = None

    while True:
        midi_file_path = choose_midi_file(app)  # 传递 app 实例
        
        if visualizer:
            plt.close(visualizer.fig)
        visualizer = PatternVisualizer3D(visualize_piano=True, orientation="up", pos_type="Fibonacci")  # Fibonacci
        new_pattern = bytes(15)
        one_volumes = [1] * 120
        visualizer.update_pattern(new_pattern, one_volumes, 0)
        if midi_file_path:
            action_midi_visualization(visualizer, midi_file_path)
        else:
            break
