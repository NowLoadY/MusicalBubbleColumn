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
import scipy.interpolate as scipy_interpolate
import pygame.midi
class PatternVisualizer3D:
    def __init__(self, visualize_piano=False, pos_type="Fibonacci", draw_index=False, orientation="up", terminal_show=False, draw_lines=True):
        self.orientation=orientation
        self.terminal_show=terminal_show
        self.draw_lines=draw_lines
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
        self.scaler = 2  # 初始scaler值
        self.final_volume = deque(maxlen=30)
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()

    def update_elev(self, val):
        self.target_elev = val
    def update_azim(self, val):
        self.target_azim_speed = val
    def _initialize_plot(self):
        self.fig = plt.figure(facecolor='black', figsize=(8, 9))
        self.fig.canvas.manager.window.setWindowTitle("🎼Musical Bubble Column!🎹")
        base_path = os_path.dirname(os_path.abspath(__file__))
        # 添加图片
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
        self.ax.set_zlim(-5, self.data_height+5)
        self.ax.set_box_aspect([1, 1, 3])
        self._create_base_3d_lines(2)
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
        # 动态调整大小
        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)
        required_size = (self.data_height, max_size + 1, max_size + 1)  # +1 因为索引从 0 开始
        self.data_no_thick = np.zeros(required_size, dtype=np.float32)
        self.data_only_thickness = np.zeros(required_size, dtype=np.float32)
        self.data = np.zeros(required_size, dtype=np.float32)
        print(f"Resized to {required_size}")
        self.thickness_list = [0] * 120
        self.old_pattern = None
        self.degradation_active = [False] * 120
        self.all_positions = set(self.position_list)
        self.opacity_dict = self._calculate_opacity()

    def _hide_axes_background(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.pane.fill = False
            axis.set_pane_color((0, 0, 0, 0))

    def update_view_angle(self):
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)

    def _generate_positions(self, num_positions, center_x, center_y, inner_radius, outer_radius, pos_type="Fibonacci", start_angle=0, end_angle=3*np.pi/4):
        """
        Generates a set of positions based on the specified pattern.
        
        :param num_positions: Number of positions to generate.
        :param center_x: X-coordinate of the center.
        :param center_y: Y-coordinate of the center.
        :param inner_radius: Inner radius for position calculation.
        :param outer_radius: Outer radius for position calculation.
        :param pos_type: Type of position generation ("Fibonacci", "circle", "arc").
        :param start_angle: Start angle for arc positions (radians), used when pos_type="arc".
        :param end_angle: End angle for arc positions (radians), used when pos_type="arc".
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

        elif pos_type == "arc":
            radius = 120  # Use only one radius for the arc
            angle_step = (end_angle - start_angle) / num_positions  # Calculate the angle step
            positions.clear()  # Ensure positions is cleared before starting

            for i in range(num_positions):
                angle = start_angle + i * angle_step  # Calculate the angle for each position
                x, y = int(center_x + radius * np.cos(angle)), int(center_y + radius * np.sin(angle))  # Calculate x, y based on radius and angle

                # Ensure no duplicates are added to the positions
                if (x, y) not in positions:
                    positions.append((x, y))
                else:
                    continue  # If duplicate, skip adding this coordinate (no need to change the radius)
            
            # If still less than desired positions, you might want to recheck the logic
            if len(positions) < num_positions:
                raise ValueError("Could not generate the required number of positions due to duplication.")
        
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
            line = [(cx+np.random.uniform(-20, 20), cy+np.random.uniform(-20, 20), cz+np.random.uniform(-20, 20)) for _ in range(40)]
            self.base_3d_lines.append(line)

    def _draw_random_3d_lines(self, change_val=5, x_rand=(-100, 100), y_rand=(-100, 100), max_length=30):
        z_rand=(-self.data_height, self.data_height)
        # 绘制折线段（白色）
        if change_val > 1:
            cx, cy, cz = self.total_center
            for i in range(len(self.base_3d_lines)):
                line = self.base_3d_lines[i]
                # 对每个折线段的每个坐标点都进行小范围的随机偏移并限制边界
                offset_line = [(np.clip(x + np.random.randint(-change_val, change_val), cx+x_rand[0], cx+x_rand[1]), 
                                np.clip(y + np.random.randint(-change_val, change_val), cy+y_rand[0], cy+y_rand[1]), 
                                np.clip(z + np.random.randint(min(-change_val/2,-1), max(change_val/2,1)), cz+z_rand[0], cz+z_rand[1])) 
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
                # 平滑插值
                t = np.linspace(0, 1, len(offset_line))
                smooth_xs = np.linspace(0, 1, num=400)  # 假设生成200个平滑点
                smooth_ys = np.linspace(0, 1, num=400)
                smooth_zs = np.linspace(0, 1, num=400)
                
                # 使用样条插值
                interp_x = scipy_interpolate.CubicSpline(t, [x for x, _, _ in offset_line])
                interp_y = scipy_interpolate.CubicSpline(t, [y for _, y, _ in offset_line])
                interp_z = scipy_interpolate.CubicSpline(t, [z for _, _, z in offset_line])
                
                smooth_x_vals = interp_x(smooth_xs)
                smooth_y_vals = interp_y(smooth_ys)
                smooth_z_vals = interp_z(smooth_zs)
                
                # 绘制平滑插值后的结果
                self.ax.plot3D(smooth_x_vals, smooth_y_vals, smooth_z_vals, color=(1,1,1,0.1), linewidth=1)
                #self.ax.scatter(xs, ys, zs, c='white', marker='o', s=1)
        else:
            for line in self.base_3d_lines:
                # 平滑插值
                t = np.linspace(0, 1, len(line))
                smooth_xs = np.linspace(0, 1, num=400)  # 生成400个平滑点
                smooth_ys = np.linspace(0, 1, num=400)
                smooth_zs = np.linspace(0, 1, num=400)
                
                # 使用样条插值
                interp_x = scipy_interpolate.CubicSpline(t, [x for x, _, _ in line])
                interp_y = scipy_interpolate.CubicSpline(t, [y for _, y, _ in line])
                interp_z = scipy_interpolate.CubicSpline(t, [z for _, _, z in line])
                
                smooth_x_vals = interp_x(smooth_xs)
                smooth_y_vals = interp_y(smooth_ys)
                smooth_z_vals = interp_z(smooth_zs)
                self.ax.plot3D(smooth_x_vals, smooth_y_vals, smooth_z_vals, color=(1,1,1,0.1), linewidth=1)
                #self.ax.scatter(xs, ys, zs, c='white', marker='o', s=1)

    def update_pattern(self, new_pattern, volumes, average_volume, now_velocity=1):
        if len(new_pattern) != 15:
            raise ValueError("new_pattern must be exactly 15 bytes long")
        bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
        # 滚动更新 data 和 data_no_thick
        self.data_no_thick = np.roll(self.data_no_thick, shift=-1 if self.orientation == "down" else 1, axis=0)  # 滚动更新 data_no_thick
        # 滚动更新 data_only_thickness 同步
        self.data_only_thickness = np.roll(self.data_only_thickness, shift=-1 if self.orientation == "down" else 1, axis=0)  # 滚动更新 data_only_thickness
        # 重置最后一层的 data 和 data_no_thick 和 data_only_thickness
        self.data_no_thick[-1 if self.orientation == "down" else 0, :, :] = 0  # 重置 data_no_thick 的最后一层
        self.data_only_thickness[-1 if self.orientation == "down" else 0, :, :] = 0  # 重置 data_only_thickness 的最后一层
        self.ax.cla()
        # 更新 thickness_list
        #self._update_thickness_list(bit_array)
        self._update_data_layer(bit_array, volumes, average_volume)
        if self.draw_lines:
            self._draw_random_3d_lines(change_val=3 * now_velocity / 127)
        
        self._draw_pattern()
        self._update_piano_keys(bit_array, volumes)  # 更新虚拟钢琴显示
        
        self.azim_angle=(self.azim_angle-self.target_azim_speed)%360
        self.elev = self.elev + (self.target_elev-self.elev)*0.1
        #self.fig.canvas.draw_idle()
        plt.pause(0.002)
        
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
        #position_set = set(self.position_list)
        variances = []
        for i in range(120):
            if bit_array[i]:
                x_center, y_center = self.position_list[i]
                volume_factor = ((volumes[i] - average_volume) / average_volume) if average_volume else 0
                final_volume_piece = min(500, (math.pow(1+self.scaler * volume_factor,3)))
                self.final_volume.append(final_volume_piece)
                #print(volumes[i], volumes[i] - average_volume, average_volume, volume_factor, self.scaler, final_volume_piece, self.thickness_list[i])
                if len(self.final_volume) > 10:
                    variance = np.var(self.final_volume)
                    variances.append(variance)
                thickness = int(final_volume_piece)
                
                if self.degradation_active[i]:
                    self.thickness_list[i] = max(0, thickness - 1)
                else:
                    self.thickness_list[i] = thickness
                total_thickness = self.thickness_list[i] + (1 * (119 - i)) // 119  # 让低音可视化气泡更大

                self.data_no_thick[-1 if self.orientation=="down" else 0, x_center, y_center] = 1  # 记录未应用 total_thickness 的点
                # for dx in range(-total_thickness, total_thickness + 1):
                #     for dy in range(-total_thickness, total_thickness + 1):
                #         if dx**2 + dy**2 <= total_thickness**2:
                #             nx, ny = x_center + dx, y_center + dy
                #             if (nx, ny) in position_set:
                #                 self.data[-1 if self.orientation=="down" else 0, nx, ny] = 1
                
                # 在这里同步 thickness 数据到 self.data_only_thickness
                self.data_only_thickness[-1 if self.orientation == "down" else 0, x_center, y_center] = total_thickness+1

        
        if variances:  # 检查 variances 是否为空
            variances_threashhold = 20
            if np.mean(variances) < variances_threashhold:  # 平均值阈值，根据需要调整
                self.scaler += 0.01
            else:
                self.scaler = max(0, self.scaler - 0.01)
            #print(np.mean(variances),self.scaler)
    def _draw_cylinder(self, color='white', alpha=0.05):
        # 计算圆柱面的参数
        center_x, center_y = 30, 30
        radius = max(np.linalg.norm(np.array([x, y]) - np.array([center_x, center_y])) for x, y in self.position_list)
        height = self.data_height

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
        expand = False
        self.ax.set_xlim(self.ax_xlim_min, self.ax_xlim_max)
        self.ax.set_ylim(self.ax_ylim_min, self.ax_ylim_max)
        self.ax.set_zlim(-5, self.data_height+5)
        self.ax.set_box_aspect([1, 1, 3])
        self._hide_axes()

        # 绘制顶层圆圈
        x, y, z = np.nonzero(np.atleast_3d(self.data_no_thick[-1 if self.orientation=="down" else 0]))  # 使用 data_no_thick
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
                if self.draw_index:
                    # 绘制索引号
                    for (x_val, y_val, _) in inactive_with_opacity:
                        index_position = self.position_list.index((x_val, y_val))
                        self.ax.text(x_val, y_val, self.data_height if self.orientation=="down" else 0, str(index_position), color='white', fontsize=6)
        
        # 绘制滚动的层
        all_x, all_y, all_z, all_sizes = [], [], [], []  # 用于存储大小的列表
        for i in range(1, self.data_height):
            if expand:
                x, y, z = np.nonzero(np.atleast_3d(self.data[i]))
            else:
                x, y, z = np.nonzero(np.atleast_3d(self.data_no_thick[i]))

            if x.size > 0 and y.size > 0 and z.size > 0:
                all_x.extend(x)
                all_y.extend(y)
                all_z.extend(z + i)  # 将 z 值加上层数
                
                # 获取对应位置的厚度值
                sizes = []
                for ix, iy in zip(x, y):
                    # 从 self.data_only_thickness[i] 获取厚度值
                    #print(i, ix, iy)
                    thickness = self.data_only_thickness[i][ix, iy]  # 获取厚度值
                    size = min(500, thickness * 5)  # 根据需求调整厚度到大小的映射
                    sizes.append(size)
                
                all_sizes.extend(sizes)  # 将大小添加到列表中

        if all_x:  # 如果有点需要绘制
            self.ax.scatter(all_x, all_y, all_z, c='white', marker='o', s=all_sizes)
            
        # 绘制落地的层
        if expand:
            x, y, z = np.nonzero(np.atleast_3d(self.data[0 if self.orientation=="down" else self.data_height-1]))
        else:
            x, y, z = np.nonzero(np.atleast_3d(self.data_no_thick[0 if self.orientation=="down" else self.data_height-1]))
        if x.size > 0 and y.size > 0 and z.size > 0:
            self.ax.scatter(x, y, z if self.orientation=="down" else self.data_height, c='white', marker='*', s=200)
        

    def _hide_axes(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.set_major_formatter(plt.NullFormatter())
            axis.set_visible(False)
            axis.line.set_visible(False)  # 隐藏坐标轴线
            axis.set_ticks([])  # 隐藏刻度线

    def connect_points(self, x, y, z):
        # 在每一层内部连接点
        for i in range(len(x) - 1):
            self.ax.plot([x[i], x[i + 1]], [y[i], y[i + 1]], [z[i], z[i + 1]], color=(1,1,1,0.75), lw=2)
    

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
    zero_pattern_interval = 2
    update_count = 0
    process_midi_thread_bool=True
    def process_midi():
        nonlocal new_pattern, update_count, volumes, now_velocity, process_midi_thread_bool
        for msg in midi_iterator:
            if msg.type in ['note_on', 'note_off']:
                mapped_note = map_note_to_range(msg.note)
                if 0 <= mapped_note < num_keys:
                    try:
                        msg_velocity = msg.velocity
                        key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg_velocity > 0) else 0
                        volumes[mapped_note] = msg_velocity if msg.type == 'note_on' else 0
                        total_volumes.append(msg_velocity)
                        now_velocity = msg_velocity
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
            visualizer.update_pattern(new_pattern, one_volumes, average_volume, now_velocity)
        else:
            visualizer.update_pattern(new_pattern, volumes, average_volume, now_velocity)
        update_count += 1
        
        # 检查 MIDI 是否仍在播放
        if not pygame.mixer.music.get_busy() and np.sum(visualizer.data) == 0:
            visualizer.working = False

            break  # 如果 MIDI 播放完且数据已清空，则退出
        visualizer.update_view_angle()
        if not visualizer.working:
            process_midi_thread_bool=False
            break

    midi_thread.join()
    pygame.mixer.music.stop()

def choose_midi_file():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    midi_file_path = filedialog.askopenfilename(
        title="选择MIDI文件",
        filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")])
    root.destroy()  # 关闭窗口
    return midi_file_path


if __name__ == "__main__":
    pygame.init()
    # 初始化MIDI
    pygame.midi.init()
    visualizer = None
    while True:
        # 弹出文件选择对话框让用户选择MIDI文件
        midi_file_path = choose_midi_file()
        if visualizer:
            plt.close(visualizer.fig)
        visualizer = PatternVisualizer3D(visualize_piano=False, orientation="up", pos_type="Fibonacci",
                                          draw_lines=False)#Fibonacci
        if midi_file_path:
            action_midi_visualization(visualizer, midi_file_path)
        else:
            break
