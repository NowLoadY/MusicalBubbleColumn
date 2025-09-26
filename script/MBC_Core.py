from matplotlib.gridspec import GridSpec
from PyQt5.QtCore import QEvent, QObject, Qt
import numpy as np
import matplotlib.pyplot as plt
from PyQt5 import QtGui
from MBC_Calc import generate_positions, calculate_opacity
import MBC_njit_func
import MBC_config
from MBC_config import get_config
from MBC_BubbleGenerator import BubbleGenerator
from MBC_PhysicsHandler import PhysicsHandler
from MBC_PhysicsInterface import NjitPhysicsEngine
from MBC_RenderInterface import MatplotlibRenderer, RenderSettings, CameraState, convert_njit_to_particles


class PatternVisualizer3D(QObject):
    def __init__(self, pos_type=None, visualize_piano=None, orientation=None):
        super().__init__()  # 初始化 QObject
        self.config = get_config()
        
        # Use config defaults if not specified
        self.orientation = orientation or self.config.visualization.default_orientation
        self.visualize_piano = visualize_piano if visualize_piano is not None else self.config.visualization.visualize_piano
        self.pos_type = pos_type or self.config.visualization.default_pos_type
        
        self.data_height = self.config.visualization.data_height_3d
        self.total_center = (0, 0, self.data_height//2)
        self.working = True
        self.theme_index = self.config.theme.default_theme_index
        self.fig_themes_rgba = self.config.theme.fig_themes_rgba
        self.data_themes_rgb = self.config.theme.data_themes_rgb
        self.window_opacity = self.config.visualization.window_opacity
        
        self._initialize_plot()
        positions_and_offset = generate_positions(
            self.config.visualization.num_positions,
            self.total_center[0], 
            self.total_center[1], 
            self.config.visualization.inner_radius, 
            self.config.visualization.outer_radius, 
            pos_type=self.pos_type
        )
        self.position_list, self.offset = positions_and_offset
        self._initialize_data()
        
        # 初始化模块化组件
        self.bubble_generator = BubbleGenerator(self.position_list, self.orientation)
        
        # 计算数据范围用于物理处理器
        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)
        
        # 初始化物理处理器（状态管理）
        self.physics_handler = PhysicsHandler(
            data_height=self.data_height,
            max_x=max_size,
            max_y=max_size,
            all_positions=self.all_positions_array,
            bubble_positions=self.bubble_positions,
            bubble_indices=self.bubble_indices,
            opacity_dict=self.opacity_dict,
            offset=self.offset,
            orientation=self.orientation
        )
        
        # 初始化物理引擎接口（可替换的引擎实现）
        self.physics_engine = NjitPhysicsEngine()
        
        # 初始化渲染引擎接口（可替换的渲染实现）
        #self.render_engine = MatplotlibRenderer()
        from MBC_ThreeJSRenderer import ThreeJSRenderer
        self.render_engine = ThreeJSRenderer()
        render_settings = RenderSettings(
            background_color=self.fig_themes_rgba[self.theme_index],
            window_opacity=self.window_opacity,
            antialiasing=True
        )
        self.render_engine.initialize(render_settings)
        # 将matplotlib对象传递给渲染器（仅适用于MatplotlibRenderer）
        if hasattr(self.render_engine, 'set_matplotlib_objects'):
            self.render_engine.set_matplotlib_objects(self.fig, self.ax)
        
        # 将现有的pattern_data传递给PhysicsHandler以保持兼容性
        self.physics_handler.set_raw_pattern_data(self.pattern_data, self.pattern_data_thickness)
        
        # 保持向后兼容性 - 这些属性可能被其他代码使用
        self.scaler = 1  # 现在由BubbleGenerator管理
        self.final_volume = np.zeros(self.config.physics.final_volume_history_size)  # 现在由BubbleGenerator管理
        self.final_volume_index = 0  # 现在由BubbleGenerator管理
        self.thickness_list = [0] * 120  # 现在由BubbleGenerator管理，但保持引用
        
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()
        
        # 这些现在由PhysicsHandler管理，但保持引用以兼容现有代码
        self.MAX_SNOW_STACK_HEIGHT = self.config.physics.max_snow_stack_height
        self.snow_ttl = self.physics_handler.snow_ttl  # 引用PhysicsHandler的snow_ttl
        self.MAX_SNOW_TTL = self.config.physics.max_snow_ttl

    def _create_slider(self, pos, val_range, init_val, orientation, callback):
        ax = plt.axes(pos, facecolor='none')
        slider = plt.Slider(ax, '', *val_range, orientation=orientation,
                            valinit=init_val, color=(1,1,1,0.0), initcolor="none",
                            track_color=(1,1,1,0.1),
                            handle_style={'facecolor': 'none', 'edgecolor': '0.6', 'size': 10})
        slider.on_changed(callback)
        return slider
    
    def _initialize_plot(self):
        # 界面外观设定
        self.fig = plt.figure(
            facecolor=self.fig_themes_rgba[0], 
            figsize=self.config.ui.default_figure_size
        )
        self.fig.canvas.manager.window.setWindowTitle(self.config.ui.window_title)
        self.fig.canvas.manager.window.setWindowFlags(self.fig.canvas.manager.window.windowFlags() | Qt.WindowStaysOnTopHint)
        self.toolbar = self.fig.canvas.manager.toolbar
        self.toolbar.hide()
        new_icon = QtGui.QIcon(self.config.file_paths.icon_path)
        self.fig.canvas.manager.window.setWindowIcon(new_icon)
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
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press) # 连接键盘按下事件
        self.fig.canvas.mpl_connect('close_event', self.handle_close)
        self.fig.canvas.mpl_connect('resize_event', self.on_resize)
        self.mouse_pressing=False
        self.mouse_controling_slider = False
        # 界面数据属性设定
        self.elev = self.config.visualization.default_elev
        self.target_elev = self.config.visualization.default_elev
        self.azim_angle = self.config.visualization.default_azim_angle
        self.target_azim_speed = self.config.visualization.default_azim_speed
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
        self.ax.margins(0)
        self.on_resize()
        # 界面组件设定
        self.elev_slider = self._create_slider(self.config.ui.elev_slider_pos, (0, 90), self.elev, 'vertical', self.update_elev)
        azim_pos = self.config.ui.azim_slider_pos if self.visualize_piano else self.config.ui.azim_slider_pos_no_piano
        self.azim_slider = self._create_slider(azim_pos, (-5, 5), self.target_azim_speed, 'horizontal', self.update_azim)
        if self.visualize_piano:
            self.piano_ax.set_xlim(*self.config.ui.piano_xlim)
            self.piano_ax.set_ylim(*self.config.ui.piano_ylim)
            self.piano_ax.axis('off')

            white_key_width = self.config.ui.white_key_width
            black_key_width = self.config.ui.black_key_width
            black_key_height = self.config.ui.black_key_height

            self.white_key_map = {}  # midi_note -> white_key_index
            self.white_keys = []
            self.black_keys = []

            white_index = 0
            for note in range(21, 109):
                if not self.is_black_key(note):
                    # 绘制白键
                    rect = plt.Rectangle((white_index, 0), white_key_width, 1,
                                        facecolor='white', edgecolor='black')
                    self.piano_ax.add_patch(rect)
                    self.white_keys.append(rect)
                    self.white_key_map[note] = white_index
                    white_index += 1

            # 再绘制黑键，嵌入白键之间
            self.black_key_map = {}
            for note in range(21, 109):
                if self.is_black_key(note):
                    left_white = note - 1
                    while self.is_black_key(left_white):
                        left_white -= 1
                    if left_white in self.white_key_map:
                        x = self.white_key_map[left_white] + 1 - self.config.ui.black_key_x_offset
                        rect = plt.Rectangle((x, self.config.ui.black_key_y_offset), black_key_width, black_key_height,
                                            facecolor='black', edgecolor='black')
                        self.piano_ax.add_patch(rect)
                        self.black_keys.append(rect)
                        self.black_key_map[note] = rect  # 构建映射

            self.piano_keys = self.white_keys + self.black_keys  # 使用实例属性
            
        # 保持颜色设定
        self.fig.set_facecolor(self.fig_themes_rgba[self.theme_index])
        self.ax.set_facecolor(self.fig_themes_rgba[self.theme_index])
        self.data_color = self.data_themes_rgb[self.theme_index]

    @staticmethod
    def is_black_key(note):
        """判断MIDI音符是否为黑键（21~108）"""
        # 黑键的MIDI音符号（模12）
        black_keys_mod = [1, 3, 6, 8, 10]  # C#, D#, F#, G#, A#
        return (note % 12) in black_keys_mod

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
        self.all_positions_array = np.array(list(self.all_positions))
        self.bubble_positions = np.array(self.position_list)  # 存储所有气泡的坐标位置
        self.bubble_indices = np.arange(len(self.position_list))  # 每个气泡对应的索引
        self.opacity_dict = calculate_opacity()
        self.defalt_zlim = (0, self.data_height+2)
        self.defalt_xlim = (-max_size//(2 if self.orientation == "up" else 3), max_size//(2 if self.orientation == "up" else 3))
        self.defalt_ylim = (-max_size//(2 if self.orientation == "up" else 3), max_size//(2 if self.orientation == "up" else 3))
        self.target_zlim = self.defalt_zlim
        self.target_xlim = self.defalt_xlim
        self.target_ylim = self.defalt_ylim
        self.zlim = self.defalt_zlim
        self.xlim = self.defalt_xlim
        self.ylim = self.defalt_ylim

    def update_pattern(self, new_pattern, volumes, average_volume, key_activation_bytes, volumes_real): #, radius=5
        # 检查绘图窗口是否仍然打开
        if not plt.fignum_exists(self.fig.number):
            self._initialize_plot()  # 重新初始化绘图窗口
        
        # 1.整理数据
        # 重置最后一层的pattern_data 和 pattern_data_thickness，淘汰边缘的旧数据
        self.pattern_data[-1 if self.orientation == "down" else 0, :, :] = 0
        self.pattern_data_thickness[-1 if self.orientation == "down" else 0, :, :] = 0
        self.azim_angle = (self.azim_angle - self.target_azim_speed) % 360
        self.elev = self.elev + (self.target_elev - self.elev) * self.config.visualization.view_transition_rate
        
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
        transition_rate = self.config.visualization.view_transition_rate
        self.zlim = tuple(np.array(self.zlim) + (np.array(self.target_zlim) - np.array(self.zlim)) * transition_rate)
        self.xlim = tuple(np.array(self.xlim) + (np.array(self.target_xlim) - np.array(self.xlim)) * transition_rate)
        self.ylim = tuple(np.array(self.ylim) + (np.array(self.target_ylim) - np.array(self.ylim)) * transition_rate)
        self.ax.set_xlim(self.xlim)
        self.ax.set_ylim(self.ylim)
        self.ax.set_zlim(self.zlim)
        self._hide_axes()
        self.ax.margins(0)
        # 4.绘制数据
        self._draw_pattern()
        if self.visualize_piano and key_activation_bit_array is not None:
            self._update_piano_keys(key_activation_bit_array, volumes_real)
        plt.pause(self.config.visualization.pause_duration)


    def _update_data_layer(self, bit_array, volumes, average_volume):
        # 清理后的高性能版本：通过物理引擎接口调用，但保持性能
        # 1. 重置边缘层，淘汰旧数据 (从原有逻辑)
        self.pattern_data[-1 if self.orientation == "down" else 0, :, :] = 0
        self.pattern_data_thickness[-1 if self.orientation == "down" else 0, :, :] = 0
        
        # 2. 通过物理引擎接口进行气泡生成（可替换的引擎）
        variances = self.physics_engine.add_pattern(
            bit_array, volumes, average_volume, 
            self.bubble_generator.position_list, 
            self.bubble_generator.final_volume, 
            self.bubble_generator.final_volume_index, 
            self.bubble_generator.scaler, 
            self.bubble_generator.thickness_list, 
            self.pattern_data, 
            self.pattern_data_thickness, 
            self.orientation
        )
        
        # 手动更新final_volume_index（因为add_pattern会修改但不返回）
        active_indices = np.where(bit_array)[0]
        if len(active_indices) > 0:
            self.bubble_generator.final_volume_index = (self.bubble_generator.final_volume_index + len(active_indices)) % self.config.physics.final_volume_history_size
        
        # 3. 通过物理引擎接口进行物理计算（可替换的引擎）
        pattern_data_temp, pattern_data_thickness_temp = self.physics_engine.calculate_bubble(
            self.pattern_data, 
            self.pattern_data_thickness, 
            self.data_height, 
            orientation=self.orientation
        )
        
        # 4. 更新非边缘层（原有逻辑）
        self.pattern_data[1:self.data_height] = pattern_data_temp[1:self.data_height]
        self.pattern_data_thickness[1:self.data_height] = pattern_data_thickness_temp[1:self.data_height]
        
        # 5. 使用BubbleGenerator的状态管理方法
        self.bubble_generator.update_scaler_from_variances(variances)
        
        # 6. 更新兼容性属性
        self.scaler = self.bubble_generator.scaler

    def _draw_pattern(self):
        # 渲染引擎分离版本：支持可替换的渲染系统
        all_positions = self.all_positions_array
        orientation_int = 0 if self.orientation == "up" else 1
        
        # 1. 通过物理引擎获取渲染数据
        all_x, all_y, all_z, all_sizes, all_opacity, all_types, all_color_blend_factors = self.physics_engine.calculate_render_data(
            self.pattern_data,
            self.pattern_data_thickness,
            self.offset,
            all_positions[:, 0], all_positions[:, 1],
            self.bubble_positions[:, 0], self.bubble_positions[:, 1],
            self.bubble_indices, self.opacity_dict, self.data_height,
            orientation_int, self.snow_ttl, self.MAX_SNOW_TTL
        )
        
        # 2. 转换为标准化的渲染粒子对象
        base_color = np.array(self.data_color)
        particles = convert_njit_to_particles(
            all_x, all_y, all_z, all_sizes, all_opacity, 
            all_types, all_color_blend_factors, base_color
        )
        
        # 3. 创建相机状态
        camera = CameraState(
            position=(0, 0, 0),  # matplotlib使用view_init，这些值会被覆盖
            target=(0, 0, 0),
            up=(0, 0, 1),
            elev=self.elev,
            azim=self.azim_angle,
            x_range=self.xlim,
            y_range=self.ylim, 
            z_range=self.zlim
        )
        
        # 4. 通过渲染引擎接口渲染（可替换的渲染器）
        self.render_engine.render_frame(particles, camera)

    def toggle_orientation(self):
        if self.orientation == "up":
            self.orientation = "down"
        else:
            self.orientation = "up"

        # 同步模块的方向状态
        self.bubble_generator.toggle_orientation()
        self.physics_handler.toggle_orientation()

        max_x = max(abs(pos[0]) for pos in self.position_list)
        max_y = max(abs(pos[1]) for pos in self.position_list)
        max_size = max(max_x, max_y)
        self.defalt_xlim = (-max_size//(2 if self.orientation == "up" else 3), max_size//(2 if self.orientation == "up" else 3))
        self.defalt_ylim = (-max_size//(2 if self.orientation == "up" else 3), max_size//(2 if self.orientation == "up" else 3))
        self.target_xlim = self.defalt_xlim
        self.target_ylim = self.defalt_ylim

    def handle_close(self, event):
        plt.close(self.fig)
        self.working = False

    def on_key_press(self, event):
        if event.key == 'r' or event.key == 'R':
            self.toggle_orientation()

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
            
    def on_resize(self, event=None):
        width, height = self.fig.canvas.get_width_height()

        z_scale = 3 * (height / width)
        self.ax.set_box_aspect([1, 1, z_scale])
        self.ax.set_position([0, 0, 1, 1])

    def update_elev(self, val):
        self.target_elev = val

    def update_azim(self, val):
        self.target_azim_speed = val

    def update_view_angle(self):
        self.ax.view_init(elev=self.elev, azim=self.azim_angle)

    def _update_piano_keys(self, bit_array, volumes):
        # 更新白键
        for midi_note, white_idx in self.white_key_map.items():
            key = self.white_keys[white_idx]
            if midi_note < len(bit_array) and bit_array[midi_note]:
                vol = volumes[midi_note] / 127.0
                alpha = min(0.3 + vol * 0.7, 1.0)
                new_color = (0.9 - vol * 0.5, 0.9 - vol * 0.5, 0.9 - vol * 0.5, alpha)  # 向灰色/黑色偏移
            else:
                new_color = (1, 1, 1, 1.0)  # 初始更白

            key.set_facecolor(new_color)

        # 更新黑键
        for midi_note, key in self.black_key_map.items():
            if midi_note < len(bit_array) and bit_array[midi_note]:
                vol = volumes[midi_note] / 127.0
                alpha = min(0.7 + vol * 0.3, 1.0)
                new_color = (0.7 + vol * 0.3, 0.7 + vol * 0.3, 0.7 + vol * 0.3, alpha)  # 向灰白色偏移
            else:
                new_color = (0.1, 0.1, 0.1, 1.0)  # 初始更黑

            key.set_facecolor(new_color)

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
        
        # 更新渲染引擎设置
        updated_settings = RenderSettings(
            background_color=self.fig_themes_rgba[self.theme_index],
            window_opacity=self.window_opacity,
            antialiasing=True
        )
        self.render_engine.update_settings(updated_settings)

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
        new_flags = flags ^ Qt.WindowStaysOnTopHint  # 切换置顶状态
        if new_flags != flags:
            self.fig.canvas.manager.window.setWindowFlags(new_flags)
            self.fig.canvas.manager.window.show()  # 需要重新显示窗口使设置生效

def init_njit_func(visualizer):
    """初始化njit函数 - 使用物理引擎接口进行初始化"""
    # 创建测试数据进行初始化
    bit_array = np.unpackbits(np.frombuffer(bytes(15), dtype=np.uint8))
    test_volumes = [1] * 120
    
    # 使用物理引擎接口进行初始化（测试njit编译）
    # 1. 测试气泡生成
    test_variances = visualizer.physics_engine.add_pattern(
        bit_array, test_volumes, 0,
        visualizer.bubble_generator.position_list,
        visualizer.bubble_generator.final_volume,
        visualizer.bubble_generator.final_volume_index,
        visualizer.bubble_generator.scaler,
        visualizer.bubble_generator.thickness_list,
        visualizer.pattern_data,
        visualizer.pattern_data_thickness,
        visualizer.orientation
    )
    
    # 2. 测试物理计算
    test_pattern_data, test_pattern_thickness = visualizer.physics_engine.calculate_bubble(
        visualizer.pattern_data, visualizer.pattern_data_thickness, 
        visualizer.data_height, visualizer.orientation
    )
    
    # 3. 测试渲染数据计算
    all_positions = visualizer.all_positions_array
    orientation_int = 0 if visualizer.orientation == "up" else 1
    test_render_data = visualizer.physics_engine.calculate_render_data(
        visualizer.pattern_data, visualizer.pattern_data_thickness, visualizer.offset,
        all_positions[:, 0], all_positions[:, 1],
        visualizer.bubble_positions[:, 0], visualizer.bubble_positions[:, 1],
        visualizer.bubble_indices, visualizer.opacity_dict, visualizer.data_height,
        orientation_int, visualizer.snow_ttl, visualizer.MAX_SNOW_TTL
    )
    
    # 4. 清理测试数据
    visualizer.physics_handler.reset_physics()
    visualizer.bubble_generator.reset_generator()
