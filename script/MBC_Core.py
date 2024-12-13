from matplotlib.gridspec import GridSpec
from PyQt5.QtCore import QEvent, QObject
from numba import njit
import numpy as np
import matplotlib.pyplot as plt
from PyQt5 import QtCore
from PyQt5 import QtGui
import os.path as os_path
#from scipy.spatial import cKDTree
base_path = os_path.dirname(os_path.abspath(__file__))
PATH_TO_ICON = os_path.join(base_path, "icon.png")


class PatternVisualizer3D(QObject):
    def __init__(self, visualize_piano=False, pos_type="Fibonacci", orientation="up"):
        super().__init__()  # 初始化 QObject
        self.orientation=orientation
        self.data_height = 300
        self.pos_type = pos_type
        self.total_center = (0, 0, self.data_height//2)
        self.visualize_piano = visualize_piano
        self.working=True
        self.theme_index = 0
        self.fig_themes_rgba = [(0.,0.,60/255,1.), (0.,0.,0.,1.), (1.,1.,1.,1.), (232/255,212/255,114/255,1.)]
        self.data_themes_rgb = [(229/255,248/255,1.), (1.,1.,1.), (0.,0.,0.), (184/255, 34/255, 20/255)]
        self._initialize_plot()
        self.position_list = self._generate_positions(120, self.total_center[0], self.total_center[1], 2, 36, pos_type=self.pos_type)
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
        self.target_azim_speed = 1
        self.fig = plt.figure(facecolor=self.fig_themes_rgba[0], figsize=(8, 6))
        self.fig.canvas.manager.window.setWindowTitle("🎼Musical Bubble Column!🎹")
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()
        new_icon = QtGui.QIcon(PATH_TO_ICON)
        self.mouse_pressing=False
        self.mouse_controling_slider = False
        self.fig.canvas.manager.window.setWindowIcon(QtGui.QIcon(new_icon))
        self.fig.canvas.manager.window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.WindowCloseButtonHint)  # 设置窗口置顶
        #self.fig.canvas.manager.window.setWindowOpacity(0.9)  # 窗口半透明
        # self.main_window_shadow = QGraphicsDropShadowEffect()
        # self.main_window_shadow.setBlurRadius(20)
        # self.main_window_shadow.setColor(QColor(*[int(x) for x in self.fig_themes_rgba[self.theme_index]]))
        # self.main_window_shadow.setOffset(0, 0)
        # self.fig.canvas.manager.window.setGraphicsEffect(self.main_window_shadow)
        self.fig.canvas.manager.window.installEventFilter(self)  # 安装事件过滤器
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)  # 连接鼠标移动事件
        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_click)  # 连接鼠标点击事件
        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_press)  # 连接鼠标按下事件
        self.fig.canvas.mpl_connect('button_release_event', self.on_mouse_release)  # 连接鼠标松开事件
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
        self.ax.set_box_aspect([1, 1, 3])
        self.elev_slider = plt.axes([0.9, 0.1, 0.03, 0.8], facecolor='none')  # 创建滑条位置并设置颜色
        self.elev_slider = plt.Slider(self.elev_slider, '', 0, 90, orientation='vertical', valinit=self.elev, color=(1,1,1,0.0), initcolor="none", track_color=(1,1,1,0.1), handle_style={'facecolor': 'none', 'edgecolor': '0.6', 'size': 10})  # 初始化滑条并设置颜色
        self.elev_slider.on_changed(self.update_elev)  # 绑定滑条变化事件
        self.azim_slider = plt.axes([0.2, 0.01 if self.orientation=="down" else 0.1, 0.6, 0.03], facecolor='none')  # 创建滑条位置并设置颜色
        self.azim_slider = plt.Slider(self.azim_slider, '', -5, 5, orientation='horizontal', valinit=self.target_azim_speed, color=(1,1,1,0.0), initcolor="none", track_color=(1,1,1,0.1), handle_style={'facecolor': 'none', 'edgecolor': '0.6', 'size': 10})  # 初始化滑条并设置颜色
        self.azim_slider.on_changed(self.update_azim)  # 绑定滑条变化事件
        self.fig.canvas.mpl_connect('close_event', self.handle_close)
        if self.visualize_piano:
            self.piano_ax.set_xlim(0, 120)
            self.piano_ax.set_ylim(0, 1)
            self.piano_ax.axis('off')
            self.piano_keys = self.piano_ax.bar(range(120), [1]*120, color='gray', edgecolor='black', width=0.5)
        # 保持颜色设定
        self.fig.set_facecolor(self.fig_themes_rgba[self.theme_index])
        self.ax.set_facecolor(self.fig_themes_rgba[self.theme_index])
        self.data_color = self.data_themes_rgb[self.theme_index]

    def _initialize_data(self):
        # 动态data大小
        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)
        self.pattern_data_required_size = (self.data_height, max_size + 1, max_size + 1)  # +1 因为索引从 0 开始
        self.pattern_data = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        self.pattern_data_thickness = np.zeros(self.pattern_data_required_size, dtype=np.float32)
        self.thickness_list = [0] * 120
        self.all_positions = set(self.position_list)
        self.position_index = {pos: idx for idx, pos in enumerate(self.position_list)}
        #self.position_tree = cKDTree(self.position_list)  # 创建KD树
        self.opacity_dict = self._calculate_opacity()
        self.defalt_zlim = (0, self.data_height+2)
        self.defalt_xlim = (-max_size//2, max_size//2)
        self.defalt_ylim = (-max_size//2, max_size//2)
        self.target_zlim = self.defalt_zlim
        self.target_xlim = self.defalt_xlim
        self.target_ylim = self.defalt_ylim
        self.zlim = self.defalt_zlim
        self.xlim = self.defalt_xlim
        self.ylim = self.defalt_ylim

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
        self.offset = (-min_x, -min_y)
        # 应用偏移量
        positions = [(x + self.offset[0], y + self.offset[1]) for x, y in positions]
        return positions

    def update_pattern(self, new_pattern, volumes, average_volume): #, radius=5
        # 检查绘图窗口是否仍然打开
        if not plt.fignum_exists(self.fig.number):
            self._initialize_plot()  # 重新初始化绘图窗口
            #self._initialize_data()
        if isinstance(new_pattern, bytes):
            bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))

        # 重置最后一层的pattern_data 和 pattern_data_thickness，淘汰边缘的旧数据
        self.pattern_data[-1 if self.orientation == "down" else 0, :, :] = 0
        self.pattern_data_thickness[-1 if self.orientation == "down" else 0, :, :] = 0
        self.azim_angle = (self.azim_angle - self.target_azim_speed) % 360
        self.elev = self.elev + (self.target_elev - self.elev) * 0.1

        self._update_data_layer(bit_array, volumes, average_volume)
        
        self.ax.cla()
        if self.mouse_controling_slider:
            self.target_xlim = (self.defalt_xlim[0]*1.5, self.defalt_xlim[1]*1.5)
            self.target_ylim = (self.defalt_ylim[0]*1.5, self.defalt_ylim[1]*1.5)
        # 平滑过渡到目标限制
        self.zlim = tuple(np.array(self.zlim) + (np.array(self.target_zlim) - np.array(self.zlim)) * 0.1)
        self.xlim = tuple(np.array(self.xlim) + (np.array(self.target_xlim) - np.array(self.xlim)) * 0.1)
        self.ylim = tuple(np.array(self.ylim) + (np.array(self.target_ylim) - np.array(self.ylim)) * 0.1)
        self.ax.set_xlim(self.xlim)
        self.ax.set_ylim(self.ylim)
        self.ax.set_zlim(self.zlim)

        self._hide_axes()
        self._draw_pattern()
        if self.visualize_piano:
            self._update_piano_keys(bit_array, volumes)
        
        plt.pause(0.003)

    def _update_data_layer(self, bit_array, volumes, average_volume):
        variances = add_pattern(bit_array, volumes, average_volume, self.position_list, self.final_volume, self.final_volume_index, self.scaler, self.thickness_list, self.pattern_data, self.pattern_data_thickness, self.orientation)
        pattern_data_temp, pattern_data_thickness_temp = calculate_bubble(self.pattern_data, self.pattern_data_thickness, self.data_height)

        # 使用 NumPy 向量化操作更新非边缘层
        self.pattern_data[1:self.data_height] = pattern_data_temp[1:self.data_height]
        self.pattern_data_thickness[1:self.data_height] = pattern_data_thickness_temp[1:self.data_height]

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

        # 优化 opacity 和 size_list 的计算
        opacity = np.concatenate((np.full(len_x, 0.8), np.full(len_x, 0.3), np.full(len_x, 0.1)))
        size_list = np.concatenate((np.full(len_x, 100), np.full(len_x, 250), np.full(len_x, 500)))

        x = np.concatenate((x, x, x))  # 使用一次性合并
        y = np.concatenate((y, y, y))
        # 底盘点集
        # 获取非活动位置的坐标和透明度
        # 使用 NumPy 数组来提高效率
        active_positions = np.array(list(zip(x, y)))
        inactive_positions = np.array(list(self.all_positions - set(map(tuple, active_positions))))
        ix_val, iy_val, inactive_opacity = [], [], []
        if inactive_positions.size > 0:
            for pos in inactive_positions:
                ix_val.append(pos[0])
                iy_val.append(pos[1])
                if (pos[0], pos[1]) in self.position_index:
                    inactive_opacity.append(self.opacity_dict[self.position_index[(pos[0], pos[1])]])

        # 合并所有点的坐标、透明度和大小
        step1_all_x = np.concatenate((x, np.array(ix_val))) - self.offset[0]
        step1_all_y = np.concatenate((y, np.array(iy_val))) - self.offset[1]
        step1_all_opacity = np.concatenate((opacity, inactive_opacity))
        step1_all_sizes = np.concatenate((size_list, np.full(len(ix_val), 10)))
        
        # 绘制滚动的层
        step2_all_x = np.empty(0)  # 初始化为 NumPy 数组
        step2_all_y = np.empty(0)
        step2_all_z = np.empty(0)
        step2_all_sizes = []  # 用于存储大小的列表
        # 获取所有非零点的坐标
        nonzero_indices = np.nonzero(self.pattern_data[1:self.data_height])  # 从第一层到最后一层
        x, y, z = nonzero_indices[1], nonzero_indices[2], nonzero_indices[0] + 1  # z 值加上层数
        
        if x.size > 0:
            step2_all_x = np.concatenate((step2_all_x, x - self.offset[0]))
            step2_all_y = np.concatenate((step2_all_y, y - self.offset[1]))
            step2_all_z = np.concatenate((step2_all_z, z))
            
            # 获取对应位置的厚度值
            thickness = self.pattern_data_thickness[1:self.data_height][nonzero_indices]  # 使用索引获取厚度值
            sizes = np.clip(thickness * 5, 0, 500)  # 根据需求调整厚度到大小的映射
            
            step2_all_sizes.extend(sizes)  # 将大小添加到列表中
        
        # 合并 step1 和 step2 的数据
        all_x = np.concatenate((step1_all_x, step2_all_x))
        all_y = np.concatenate((step1_all_y, step2_all_y))
        all_z = np.concatenate((np.full(len(step1_all_x), self.data_height) if self.orientation == "down" else np.zeros(len(step1_all_x)), step2_all_z))
        all_sizes = np.concatenate((step1_all_sizes, step2_all_sizes))
        
        if len(step2_all_x) > 0:
            all_opacity = np.concatenate((step1_all_opacity, np.ones(len(step2_all_x))))
        else:
            all_opacity = step1_all_opacity

        self.ax.scatter(all_x, all_y, all_z, c=[self.data_color + (op,) for op in all_opacity], marker='o', s=all_sizes)

        # 绘制最后一层
        #x, y, z = np.nonzero(np.atleast_3d(self.pattern_data[0 if self.orientation=="down" else self.data_height-1]))
        #if x.size > 0 and y.size > 0 and z.size > 0:
            #self.ax.scatter(x - self.offset[0], y - self.offset[1], z if self.orientation=="down" else self.data_height, c='white', marker='*', s=200)

    def handle_close(self, event):
        plt.close(self.fig)
        self.working = False

    def eventFilter(self, source, event):
        if event.type() == QEvent.Leave:  # 检测鼠标离开窗口
            #print("Mouse has left the window!")
            self.on_mouse_leave()
        return super().eventFilter(source, event)

    def on_mouse_leave(self):
        # 处理鼠标离开窗口时的逻辑
        self.target_xlim = self.defalt_xlim
        self.target_ylim = self.defalt_ylim
        self.target_zlim = self.defalt_zlim

    def on_mouse_move(self, event):
        # 检查鼠标是否在绘图区域内
        if event.inaxes:
            # 检查鼠标是否在 elev_slider 上
            if self.elev_slider.ax.contains(event)[0] or self.azim_slider.ax.contains(event)[0]:
                self.target_xlim = (self.defalt_xlim[0]*1.5, self.defalt_xlim[1]*1.5)
                self.target_ylim = (self.defalt_ylim[0]*1.5, self.defalt_ylim[1]*1.5)
                if self.mouse_pressing:
                    self.mouse_controling_slider=True
            # 检查鼠标是否在主体范围内
            elif (abs(event.xdata)<0.06) and (abs(event.ydata)<0.08):
                self.target_xlim = (self.defalt_xlim[0]*0.6, self.defalt_xlim[1]*0.6)
                self.target_ylim = (self.defalt_ylim[0]*0.6, self.defalt_ylim[1]*0.6)
                self.target_zlim = (self.defalt_zlim[0] * 0.6, self.defalt_zlim[1] * 0.6)
            else:
                self.target_xlim = self.defalt_xlim
                self.target_ylim = self.defalt_ylim
                self.target_zlim = self.defalt_zlim
        else:
            self.target_xlim = self.defalt_xlim
            self.target_ylim = self.defalt_ylim
            self.target_zlim = self.defalt_zlim

    def on_mouse_click(self, event):
        if event.dblclick:
            self._change_theme()
            print(f"Double-click detected at {event.x}, {event.y}")
        else:
            print(f"Single click at {event.x}, {event.y}")

    def on_mouse_press(self, event):
        self.mouse_pressing = True

    def on_mouse_release(self, event):
        self.mouse_pressing = False
        if self.mouse_controling_slider:
            self.target_xlim = self.defalt_xlim
            self.target_ylim = self.defalt_ylim
            self.mouse_controling_slider = False

    def update_elev(self, val):
        self.target_elev = val

    def update_azim(self, val):
        self.target_azim_speed = val

    def update_view_angle(self):
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)

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

    def _change_theme(self):
        self.theme_index = (self.theme_index + 1) % len(self.fig_themes_rgba)  # 循环到下一个颜色
        self.fig.set_facecolor(self.fig_themes_rgba[self.theme_index])  # 设置新的 facecolor
        self.ax.set_facecolor(self.fig_themes_rgba[self.theme_index])
        # 更新数据点颜色
        self.data_color = self.data_themes_rgb[self.theme_index]  # 更新数据颜色

def init_njit_func(visualizer, new_pattern, volumes, average_volume):
    if isinstance(new_pattern, bytes):
        bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
    add_pattern(bit_array, volumes, average_volume, visualizer.position_list, visualizer.final_volume, visualizer.final_volume_index, visualizer.scaler, visualizer.thickness_list, visualizer.pattern_data, visualizer.pattern_data_thickness, visualizer.orientation)
    calculate_bubble(visualizer.pattern_data, visualizer.pattern_data_thickness, visualizer.data_height)


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
        # 获取 pattern_data_temp 的形状
        max_x = pattern_data_temp.shape[1] - 1
        max_y = pattern_data_temp.shape[2] - 1
        for ix, iy in zip(x, y):
            th = thickness[ix, iy]  # 获取厚度值
            rise_speed = 5 + np.minimum(10 * (layer / (3 * data_height / 4)), 10) + np.minimum(th * 0.1, 8)  # 计算上升速度
            rise_speed = np.clip(np.array(rise_speed), 0, 18)  # 限制上升速度的最大值
            target_layer = np.minimum(layer + rise_speed.astype(np.int32), data_height - 1)  # 目标层

            # 添加轻微的抖动效果
            jitter_x = np.random.randint(-1, 2)  # 随机抖动 -1, 0, 1
            jitter_y = np.random.randint(-1, 2)  # 随机抖动 -1, 0, 1
            target_x = np.maximum(0, np.minimum(ix + jitter_x, max_x))  # 确保不超出范围
            target_y = np.maximum(0, np.minimum(iy + jitter_y, max_y))  # 确保不超出范围
            # 检查目标位置是否已有气泡
            if pattern_data_temp[target_layer, target_x, target_y] == 1:
                # 如果有气泡，则将厚度相加
                pattern_data_thickness_temp[target_layer][target_x, target_y] += th
            else:
                pattern_data_thickness_temp[target_layer][target_x, target_y] = th  # 更新新位置的厚度
            pattern_data_temp[target_layer, target_x, target_y] = 1  # 使气泡上升

            # 根据高度调整气泡大小
            size_increase = 1 + (target_layer / data_height) * 0.05  # 高度带来的大小加成
            pattern_data_thickness_temp[target_layer][target_x, target_y] *= size_increase  # 调整厚度以反映大小变化

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