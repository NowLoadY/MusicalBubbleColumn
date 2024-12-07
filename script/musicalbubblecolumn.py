"""
Musical Bubble Column!
"""
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import numpy as np
from mido import MidiFile
import pygame
import math
import threading
from collections import deque
from matplotlib.gridspec import GridSpec
from PyQt5 import QtGui
import os.path as os_path
import pygame.midi
from PyQt5.QtWidgets import QApplication, QFileDialog
import sys


class PatternVisualizer3D:
    def __init__(self, visualize_piano=False, pos_type="Fibonacci", draw_index=False, orientation="up"):
        self.orientation=orientation
        self.elev = 30
        self.target_elev = 30
        self.target_azim_speed = 2
        self.data_height = 40
        self.draw_index = draw_index
        self.pos_type = pos_type
        self.total_center = (30, 30, self.data_height//2)
        self.visualize_piano = visualize_piano
        self.working=True
        self._initialize_plot()
        self.position_list = self._generate_positions(120, self.total_center[0], self.total_center[1], 1, 18, pos_type=self.pos_type)
        self._initialize_data()
        self.scaler = 2
        self.final_volume = deque(maxlen=30)
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()

    def update_elev(self, val):
        self.target_elev = val

    def update_azim(self, val):
        self.target_azim_speed = val

    def _initialize_plot(self):
        self.fig = plt.figure(facecolor='black', figsize=(5, 5))
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
        self.azim_angle = 30
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)
        plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
        self._hide_axes_background()
        self.ax.set_facecolor((0, 0, 0, 0))
        self.ax.set_box_aspect([1, 1, 3])
        self.elev_slider = plt.axes([0.9, 0.2 if self.orientation=="down" else 0.1, 0.03, 0.6], facecolor='none')  # 创建滑条位置并设置颜色
        self.elev_slider = plt.Slider(self.elev_slider, 'Elev', -90, 90, orientation='vertical', valinit=self.elev, color=(1,1,1,0.0), initcolor="none", track_color=(1,1,1,0.05), handle_style={'facecolor': 'none', 'edgecolor': '1', 'size': 10})  # 初始化滑条并设置颜色
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

    def handle_close(self, event):
        plt.close(self.fig)
        self.working = False

    def _initialize_data(self):
        # 动态data大小
        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)
        required_size = (self.data_height, max_size + 1, max_size + 1)  # +1 因为索引从 0 开始
        self.pattern_data = np.zeros(required_size, dtype=np.float32)
        self.pattern_data_thickness = np.zeros(required_size, dtype=np.float32)
        print(f"required_size {required_size}")
        self.thickness_list = [0] * 120
        self.all_positions = set(self.position_list)
        self.opacity_dict = self._calculate_opacity()

    def _hide_axes_background(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.pane.fill = False
            axis.set_pane_color((0, 0, 0, 0))

    def update_view_angle(self):
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)

    def _generate_positions(self, num_positions, center_x, center_y, inner_radius, outer_radius, pos_type="Fibonacci"):
        """
        Generates a set of positions based on the specified pattern.
        
        :param num_positions: Number of positions to generate.
        :param center_x: X-coordinate of the center.
        :param center_y: Y-coordinate of the center.
        :param inner_radius: Inner radius for position calculation.
        :param outer_radius: Outer radius for position calculation.
        :param pos_type: Type of position generation ("Fibonacci", "circle", "arc").
        :return: List of (x, y) positions.
        """
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
        return positions
    
    def _update_axis_limits(self, positions):
        min_x, max_x = min(positions, key=lambda pos: pos[0])[0], max(positions, key=lambda pos: pos[0])[0]
        min_y, max_y = min(positions, key=lambda pos: pos[1])[1], max(positions, key=lambda pos: pos[1])[1]
        self.ax_xlim_min, self.ax_xlim_max = min_x, max_x
        self.ax_ylim_min, self.ax_ylim_max = min_y, max_y

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

    def update_pattern(self, new_pattern, volumes, average_volume):
        bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
        # 滚动 pattern_data的旧数据
        self.pattern_data = np.roll(self.pattern_data, shift=-1 if self.orientation == "down" else 1, axis=0)  # 滚动更新 pattern_data
        # 滚动 pattern_data_thickness的旧数据
        self.pattern_data_thickness = np.roll(self.pattern_data_thickness, shift=-1 if self.orientation == "down" else 1, axis=0)  # 滚动更新 pattern_data_thickness
        # 重置最后一层的pattern_data 和 pattern_data_thickness，淘汰边缘的旧数据
        self.pattern_data[-1 if self.orientation == "down" else 0, :, :] = 0  # 重置 pattern_data 的最后一层
        self.pattern_data_thickness[-1 if self.orientation == "down" else 0, :, :] = 0  # 重置 pattern_data_thickness 的最后一层
        self.azim_angle=(self.azim_angle-self.target_azim_speed)%360
        self.elev = self.elev + (self.target_elev-self.elev)*0.1
        self._update_data_layer(bit_array, volumes, average_volume)
        
        self.ax.cla()
        self.ax.set_xlim(self.ax_xlim_min, self.ax_xlim_max)
        self.ax.set_ylim(self.ax_ylim_min, self.ax_ylim_max)
        self.ax.set_zlim(-5, self.data_height+5)
        self._hide_axes()
        self._draw_pattern()
        self._update_piano_keys(bit_array, volumes)  # 更新虚拟钢琴显示
        
        plt.pause(0.002)

    def _update_data_layer(self, bit_array, volumes, average_volume):
        variances = []
        for i in range(120):
            if bit_array[i]:
                x_center, y_center = self.position_list[i]
                volume_factor = ((volumes[i] - average_volume) / average_volume) if average_volume else 0
                final_volume_piece = min(500, (math.pow(1+self.scaler * volume_factor,3)))
                self.final_volume.append(final_volume_piece)
                if len(self.final_volume) > 10:
                    variance = np.var(self.final_volume)
                    variances.append(variance)
                
                self.thickness_list[i] = int(final_volume_piece)  # 更新 thickness_list
                total_thickness = self.thickness_list[i] + (1 * (119 - i)) // 119  # 让低音可视化气泡更大
                # 将这次要可视化的数据赋予给data的最边缘一层
                self.pattern_data[-1 if self.orientation=="down" else 0, x_center, y_center] = 1
                self.pattern_data_thickness[-1 if self.orientation == "down" else 0, x_center, y_center] = total_thickness+1

        if variances:
            variances_threashhold = 20
            if np.mean(variances) < variances_threashhold:  # 平均值阈值，根据需要调整
                self.scaler += 0.01
            else:
                self.scaler = max(0, self.scaler - 0.01)

    def _calculate_opacity(self):
        # 根据位置顺序计算透明度
        opacity_list = [(i / 120) * 0.9 for i in range(120)]
        all_positions = self.all_positions
        return {pos: opacity_list[self.position_list.index(pos)] for pos in all_positions}

    def _draw_pattern(self):
        # 绘制顶层圆圈
        x, y, z = np.nonzero(np.atleast_3d(self.pattern_data[-1 if self.orientation=="down" else 0]))  # 使用 pattern_data
        len_x = len(x)
        opacity = [0.8]*len_x+[0.3]*len_x+[0.1]*len_x
        size_list = [100]*len_x+[250]*len_x+[500]*len_x
        x = np.append(np.append(x, x),x)
        y = np.append(np.append(y, y),y)
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x, y, self.data_height if self.orientation=="down" else 0, c=[(1, 1, 1, op) for op in opacity], marker='o', s=[sz for sz in size_list])
        
        # 绘制未激活的灰色点
        all_positions = set(self.position_list)
        active_positions = set(zip(x, y))
        inactive_positions = all_positions - active_positions
        opacity_dict = self.opacity_dict
        if inactive_positions:
            inactive_with_opacity = [(ix_val, iy_val, opacity_dict[(ix_val, iy_val)]) 
                                      for ix_val, iy_val in inactive_positions if (ix_val, iy_val) in opacity_dict]
            if inactive_with_opacity:
                ix_val, iy_val, opacity = zip(*inactive_with_opacity)
                self.ax.scatter(ix_val, iy_val, self.data_height if self.orientation=="down" else 0, c=[(1, 1, 1, op) for op in opacity], marker='o', s=5)
                if self.draw_index:  # 绘制索引号
                    for (x_val, y_val, _) in inactive_with_opacity:
                        index_position = self.position_list.index((x_val, y_val))
                        self.ax.text(x_val, y_val, self.data_height if self.orientation=="down" else 0, str(index_position), color='white', fontsize=6)
        
        # 绘制滚动的层
        all_x, all_y, all_z, all_sizes = [], [], [], []  # 用于存储大小的列表
        for i in range(1, self.data_height):
            x, y, z = np.nonzero(np.atleast_3d(self.pattern_data[i]))

            if x.size > 0 and y.size > 0 and z.size > 0:
                all_x.extend(x)
                all_y.extend(y)
                all_z.extend(z + i)  # 将 z 值加上层数
                
                # 获取对应位置的厚度值
                sizes = []
                for ix, iy in zip(x, y):
                    thickness = self.pattern_data_thickness[i][ix, iy]  # 获取厚度值
                    size = min(500, thickness * 5)  # 根据需求调整厚度到大小的映射
                    sizes.append(size)
                
                all_sizes.extend(sizes)  # 将大小添加到列表中

        if all_x:  # 如果有点需要绘制
            self.ax.scatter(all_x, all_y, all_z, c='white', marker='o', s=all_sizes)
            
        # 绘制落地的层
        x, y, z = np.nonzero(np.atleast_3d(self.pattern_data[0 if self.orientation=="down" else self.data_height-1]))
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x, y, z if self.orientation=="down" else self.data_height, c='white', marker='*', s=200)

    def _hide_axes(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.set_major_formatter(plt.NullFormatter())
            axis.set_visible(False)
            axis.line.set_visible(False)  # 隐藏坐标轴线
            axis.set_ticks([])  # 隐藏刻度线


def action_midi_visualization(visualizer, midi_path):
    temp_midi_path = "temp_midi_file.mid"  # 定义临时MIDI文件路径
    try:
        midi = MidiFile(midi_path)
        for track in midi.tracks:
            for msg in track:
                if msg.type == 'program_change':
                    msg.program = 0  # 将音色更改为钢琴音色
        midi.save(temp_midi_path)
    except OSError as e:
        print(f"Error loading MIDI file: {e}")
        return
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
        return max(0, min(int((note - min_note) / (max_note - min_note) * 120), 119))

    num_keys = 120
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
                    try:
                        msg_velocity = msg.velocity
                        key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg_velocity > 0) else 0
                        volumes[mapped_note] = msg_velocity if msg.type == 'note_on' else 0
                        total_volumes.append(msg_velocity)
                    except:
                        key_activation = np.zeros(num_keys, dtype=int)
                new_pattern = np.packbits(key_activation).tobytes()
                update_count = 0
            if not pygame.mixer.music.get_busy():
                break
            if not process_midi_thread_bool:
                break

    midi_thread = threading.Thread(target=process_midi)
    midi_thread.start()
    volumes = [0] * num_keys
    average_volume = 0

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

def choose_midi_file():
    app = QApplication(sys.argv)

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
    if dialog.exec_() == QFileDialog.Accepted:
        midi_file_path = dialog.selectedFiles()[0]
    else:
        midi_file_path = None

    return midi_file_path


if __name__ == "__main__":
    pygame.init()
    pygame.midi.init()
    visualizer = None

    while True:
        midi_file_path = choose_midi_file()  # 弹出文件选择对话框让用户选择MIDI文件

        if visualizer:
            plt.close(visualizer.fig)
        visualizer = PatternVisualizer3D(visualize_piano=False, orientation="up", pos_type="Fibonacci")  # Fibonacci
        if midi_file_path:
            action_midi_visualization(visualizer, midi_file_path)
        else:
            break
