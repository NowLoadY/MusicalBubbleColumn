# Musical Bubble Column！

**Musical Bubble Column** 是一个基于 Python 的 3D 音乐可视化项目，使用 MIDI 音乐文件生成可视化效果。通过 **Matplotlib** 和 **Pygame**，它将音符以 Fibonacci 螺旋图案的形式呈现出来。

## 特性

<p align="center">   <img src="asset/preview.gif" width="40%" /> </p>

### 钢琴可视化

- 钢琴键可视化（可视化中的虚拟钢琴键并不严格匹配实际钢琴键）
- 音符显示
- MIDI 播放

### 3D 可视化

- 3D 气泡动画
- 基于 Fibonacci 数列的布局
- 可调节的视角（高度与方位角）
- 基本物理模拟

### MIDI 处理

- 支持 MIDI 文件
- 钢琴音符映射
- 基于音量的视觉效果

## 开始使用

### 前提条件

需要 Python 3.7+ 和以下包：（测试3.11）

```bash
pip install matplotlib mido pygame numpy scipy PyQt5 numba
```

### 运行应用程序

1. 克隆此仓库

2. 进入项目目录

3. 运行主程序：

   ```bash
   python musicalbubblecolumn.py
   ```

4. 选择您的 MIDI 文件开始播放

直接从 [发布页面](https://github.com/NowLoadY/MusicalBubbleColumn/releases) 下载预编译的 .exe 文件，直接运行就OK

## 特性详细说明

### 可视化

- 根据音符生成气泡
- 漂浮动画
- 基于音量的视觉效果

### 控制

- 视角调整
- 透视控制
- 可视化设置

## 技术细节

### 组件

- **PatternVisualizer3D**: 可视化引擎
- **MIDI Processor**: MIDI 数据处理
- **Physics Sim**: 气泡运动模拟

### 优化

- Numba 加速
- 内存管理

## 注意事项

- 优化支持标准 MIDI 文件
- 性能依赖于系统硬件

## 贡献
什么？真的有人会上传修改吗！？
- 错误报告
- 功能建议
- 提交拉取请求

## 许可

本项目遵循 GNU 通用公共许可证 v3.0（GPL-3.0）- 详细内容请参阅 LICENSE 文件。