from matplotlib.gridspec import GridSpec
from PyQt5.QtCore import QEvent, QObject, Qt
import numpy as np
import matplotlib.pyplot as plt
from PyQt5 import QtGui
from MBC_Calc import generate_positions, calculate_opacity
from MBC_njit_func import add_pattern, calculate_bubble, calculate_pattern_data_3d
import MBC_config


class PatternVisualizer3D(QObject):
    def __init__(self, pos_type="Fibonacci", visualize_piano=True, orientation="up"):
        super().__init__()  # 初始化 QObject
        self.orientation=orientation
        self.visualize_piano = visualize_piano
        self.data_height = MBC_config.data_height_3d
        self.pos_type = pos_type
        self.total_center = (0, 0, self.data_height//2)
        self.working=True
        self.theme_index = 0
        self.fig_themes_rgba = MBC_config.fig_themes_rgba
        self.data_themes_rgb = MBC_config.data_themes_rgb
        self.window_opacity = 1.0  # 初始不透明度为100%
        self._initialize_plot()
        positions_and_offset = generate_positions(120, self.total_center[0], self.total_center[1], 2, 36, pos_type=self.pos_type)
        self.position_list, self.offset = positions_and_offset
        self._initialize_data()
        self.scaler = 1
        self.final_volume = np.zeros(30)
        self.final_volume_index = 0  # 用于跟踪数组的当前索引
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()

    def _initialize_plot(self):
        # 界面外观设定
        self.fig = plt.figure(facecolor=self.fig_themes_rgba[0], figsize=(8, 6))
        self.fig.canvas.manager.window.setWindowTitle("🎼Musical Bubble Column!🎹")
        self.fig.canvas.manager.window.setWindowFlags(self.fig.canvas.manager.window.windowFlags() | Qt.WindowStaysOnTopHint)
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()
        new_icon = QtGui.QIcon(MBC_config.PATH_TO_ICON)
        self.fig.canvas.manager.window.setWindowIcon(QtGui.QIcon(new_icon))
        self.fig.canvas.manager.window.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
                border-radius: 30px;
            }
        """)
        self.fig.canvas.manager.window.setWindowOpacity(self.window_opacity)
        # 界面交互属性设定
        self.fig.canvas.manager.window.installEventFilter(self)  # 安装事件过滤器
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)  # 连接鼠��移动事件
        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_press)  # 连接鼠标按下事件
        self.fig.canvas.mpl_connect('button_release_event', self.on_mouse_release)  # 连接鼠标松开事件
        self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)  # 连接滚轮事件
        self.fig.canvas.mpl_connect('close_event', self.handle_close)
        self.mouse_pressing=False
        self.mouse_controling_slider = False
        # 界面数据属性设定
        self.elev = 30
        self.target_elev = 30
        self.azim_angle = 30
        self.target_azim_speed = 1
        # 界面图表设定
        if self.visualize_piano:
            # 调整比例为40:1使钢琴视图更紧凑
            gs = GridSpec(2, 1, height_ratios=[40, 1], hspace=0)
            self.ax = self.fig.add_subplot(gs[0], projection='3d')
            self.piano_ax = self.fig.add_subplot(gs[1])
        else:
            gs = GridSpec(1, 1)
            self.ax = self.fig.add_subplot(gs[0], projection='3d')
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0, hspace=0)  # 移除所有边距
        self._hide_axes()
        self.ax.set_box_aspect([1, 1, 3])
        # 界面组件设定
        self.elev_slider = plt.axes([0.9, 0.1, 0.03, 0.8], facecolor='none')  # 创建滑条位置并设置颜色
        self.elev_slider = plt.Slider(self.elev_slider, '', 0, 90, orientation='vertical', valinit=self.elev, color=(1,1,1,0.0), initcolor="none", track_color=(1,1,1,0.1), handle_style={'facecolor': 'none', 'edgecolor': '0.6', 'size': 10})  # 初始化滑条并设置颜色
        self.elev_slider.on_changed(self.update_elev)  # 绑定滑条变化事件
        self.azim_slider = plt.axes([0.2, 0.02 if self.visualize_piano else 0, 0.6, 0.03], facecolor='none')  # 创建滑条位置并设置颜色
        self.azim_slider = plt.Slider(self.azim_slider, '', -5, 5, orientation='horizontal', valinit=self.target_azim_speed, color=(1,1,1,0.0), initcolor="none", track_color=(1,1,1,0.1), handle_style={'facecolor': 'none', 'edgecolor': '0.6', 'size': 10})  # 初始化滑条并设置颜色
        self.azim_slider.on_changed(self.update_azim)  # 绑定滑条变化事件
        if self.visualize_piano:
            self.piano_ax.set_xlim(0, 120)
            self.piano_ax.set_ylim(0, 1)
            self.piano_ax.axis('off')
            self.piano_keys = self.piano_ax.bar(range(120), [1]*120, color='gray', edgecolor='black', width=0.7)
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
        self.bubble_positions = np.array(self.position_list)  # 存储所有气泡的坐标位置
        self.bubble_indices = np.arange(len(self.position_list))  # 每个气泡对应的索引
        self.opacity_dict = calculate_opacity()
        self.defalt_zlim = (0, self.data_height+2)
        self.defalt_xlim = (-max_size//2, max_size//2)
        self.defalt_ylim = (-max_size//2, max_size//2)
        self.target_zlim = self.defalt_zlim
        self.target_xlim = self.defalt_xlim
        self.target_ylim = self.defalt_ylim
        self.zlim = self.defalt_zlim
        self.xlim = self.defalt_xlim
        self.ylim = self.defalt_ylim

    def update_pattern(self, new_pattern, volumes, average_volume, key_activation_bytes): #, radius=5
        # 检查绘图窗口是否仍然打开
        if not plt.fignum_exists(self.fig.number):
            self._initialize_plot()  # 重新初始化绘图窗口
        
        # 1.整理数据
        # 重置最后一层的pattern_data 和 pattern_data_thickness，淘汰边缘的旧数据
        self.pattern_data[-1 if self.orientation == "down" else 0, :, :] = 0
        self.pattern_data_thickness[-1 if self.orientation == "down" else 0, :, :] = 0
        self.azim_angle = (self.azim_angle - self.target_azim_speed) % 360
        self.elev = self.elev + (self.target_elev - self.elev) * 0.1
        
        # 2.解析、计算新数据
        if isinstance(new_pattern, bytes):
            bit_array = np.unpackbits(np.frombuffer(new_pattern, dtype=np.uint8))
            self._update_data_layer(bit_array, volumes, average_volume)
        key_activation_bit_array = None
        if key_activation_bytes is not None:
            key_activation_bit_array = np.unpackbits(np.frombuffer(key_activation_bytes, dtype=np.uint8))
        # 3.调整视图
        self.ax.cla()
        if self.mouse_controling_slider:
            self.target_xlim = (self.defalt_xlim[0]*1.5, self.defalt_xlim[1]*1.5)
            self.target_ylim = (self.defalt_ylim[0]*1.5, self.defalt_ylim[1]*1.5)
        # 平滑过渡到目标lim
        self.zlim = tuple(np.array(self.zlim) + (np.array(self.target_zlim) - np.array(self.zlim)) * 0.1)
        self.xlim = tuple(np.array(self.xlim) + (np.array(self.target_xlim) - np.array(self.xlim)) * 0.1)
        self.ylim = tuple(np.array(self.ylim) + (np.array(self.target_ylim) - np.array(self.ylim)) * 0.1)
        self.ax.set_xlim(self.xlim)
        self.ax.set_ylim(self.ylim)
        self.ax.set_zlim(self.zlim)
        self._hide_axes()

        # 4.绘制数据
        self._draw_pattern()
        if self.visualize_piano and key_activation_bit_array is not None:
            self._update_piano_keys(key_activation_bit_array, volumes)
        plt.pause(0.005)


    def _update_data_layer(self, bit_array, volumes, average_volume):
        variances = add_pattern(bit_array, volumes, average_volume, self.position_list, self.final_volume, self.final_volume_index, self.scaler, self.thickness_list, self.pattern_data, self.pattern_data_thickness, self.orientation)
        pattern_data_temp, pattern_data_thickness_temp = calculate_bubble(self.pattern_data, self.pattern_data_thickness, self.data_height)

        # 更新非边缘层
        self.pattern_data[1:self.data_height] = pattern_data_temp[1:self.data_height]
        self.pattern_data_thickness[1:self.data_height] = pattern_data_thickness_temp[1:self.data_height]

        if variances:
            variances_threashhold = 6  # 根据需要调整阈值
            if np.mean(variances) < variances_threashhold:
                self.scaler += 0.01
            else:
                self.scaler = max(0, self.scaler - 0.01)

    def _draw_pattern(self):
        all_positions = np.array(list(self.all_positions))
        
        all_x, all_y, all_z, all_sizes, all_opacity = calculate_pattern_data_3d(
            self.pattern_data,
            self.pattern_data_thickness,
            self.offset,
            all_positions[:, 0],  # 所有气泡的x坐标
            all_positions[:, 1],  # 所有气泡的y坐标
            self.bubble_positions[:, 0],  # 每个气泡的x坐标
            self.bubble_positions[:, 1],  # 每个气泡的y坐标
            self.bubble_indices,  # 气泡的索引编号
            self.opacity_dict,
            self.data_height
        )
        
        # 设置绘图参数
        scatter_kwargs = {
            'c': [self.data_color + (op,) for op in all_opacity],
            'marker': 'o',
            's': all_sizes,
            'alpha': None,  # 使用颜色中的alpha通道
            'edgecolors': 'none',  # 移除边框
            'antialiased': True,  # 抗锯齿设定
        }
        
        # 绘制散点图
        self.ax.scatter(all_x, all_y, all_z, **scatter_kwargs)

    def handle_close(self, event):
        plt.close(self.fig)
        self.working = False

    def eventFilter(self, source, event):
        if event.type() == QEvent.Leave:  # 检测鼠标离开窗口
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
                self.target_zlim = (self.defalt_zlim[0] * 0.6-self.data_height//10, self.defalt_zlim[1] * 0.6-self.data_height//10)
            else:
                self.target_xlim = self.defalt_xlim
                self.target_ylim = self.defalt_ylim
                self.target_zlim = self.defalt_zlim
        else:
            self.target_xlim = self.defalt_xlim
            self.target_ylim = self.defalt_ylim
            self.target_zlim = self.defalt_zlim

    def on_mouse_press(self, event):
        self.mouse_pressing = True
        if event.dblclick:
            self._change_theme()
        elif event.button == 2:  # 中键点击
            self.toggle_always_on_top(event)

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
                # 使用二次函数使低音量时更透明，高音量时更不透明
                normalized_volume = (volumes[i] / 127.0) ** 3  # 二次方使曲线更陡峭
                alpha = min(0.1 + normalized_volume * 0.9, 1.0)  # 0.1是最小透明度，0.9是可变范围
                new_color = (1, 1, 1, alpha)
            else:
                new_color = (1, 1, 1, 0.1)  # 未激活时保持低透明度
            if key.get_facecolor() != new_color:
                key.set_color(new_color)

    def _hide_axes(self):
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.pane.fill = False
            axis.set_pane_color((0, 0, 0, 0))
            axis.set_major_formatter(plt.NullFormatter())
            axis.set_visible(False)
            axis.line.set_visible(False)  # 隐藏坐标轴
            axis.set_ticks([])  # 隐藏刻度线

    def _change_theme(self):
        self.theme_index = (self.theme_index + 1) % len(self.fig_themes_rgba)  # 循环到下一个颜色
        self.fig.set_facecolor(self.fig_themes_rgba[self.theme_index])  # 设置新的 facecolor
        self.ax.set_facecolor(self.fig_themes_rgba[self.theme_index])
        self.data_color = self.data_themes_rgb[self.theme_index]  # 更新数据颜色

    def on_scroll(self, event):
        """处理鼠标滚轮事件来调整窗口透明度"""
        if event.inaxes:
            # 根据滚轮方向调整透明度
            delta = 0.05 if event.button == 'up' else -0.05
            self.window_opacity = max(0.3, min(1.0, self.window_opacity + delta))
            # 设置窗口透明度
            self.fig.canvas.manager.window.setWindowOpacity(self.window_opacity)
    
    def toggle_always_on_top(self, event):
        flags = self.fig.canvas.manager.window.windowFlags()
        if flags & Qt.WindowStaysOnTopHint:
            # 取消置顶
            self.fig.canvas.manager.window.setWindowFlags(
                flags & ~Qt.WindowStaysOnTopHint
            )
        else:
            # 设置置顶
            self.fig.canvas.manager.window.setWindowFlags(
                flags | Qt.WindowStaysOnTopHint
            )
        self.fig.canvas.manager.window.show()  # 需要重新显示窗口

def init_njit_func(visualizer):
    bit_array = np.unpackbits(np.frombuffer(bytes(15), dtype=np.uint8))
    add_pattern(bit_array, [1] * 120, 0, visualizer.position_list, visualizer.final_volume, visualizer.final_volume_index, visualizer.scaler, visualizer.thickness_list, visualizer.pattern_data, visualizer.pattern_data_thickness, visualizer.orientation)
    calculate_bubble(visualizer.pattern_data, visualizer.pattern_data_thickness, visualizer.data_height)
    bubble_positions = visualizer.bubble_positions
    all_positions = np.array(list(visualizer.all_positions))
    opacity_values = visualizer.opacity_dict
    calculate_pattern_data_3d(
        visualizer.pattern_data,
        visualizer.pattern_data_thickness,
        visualizer.offset,
        all_positions[:, 0],  # x坐标
        all_positions[:, 1],  # y坐标
        bubble_positions[:, 0],  # position_index的x坐标
        bubble_positions[:, 1],  # position_index的y坐标
        visualizer.bubble_indices,
        opacity_values,
        visualizer.data_height
    )
