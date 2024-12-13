# Musical Bubble Column 🎵

![Musical Bubble Column Demo][demo-gif]

**Musical Bubble Column** is an innovative 3D music visualization project built with Python that transforms your MIDI music into a mesmerizing visual experience. By combining the power of **Matplotlib** and **Pygame**, it creates an immersive display of musical notes and rhythms arranged in a unique Fibonacci spiral pattern.


## ✨ Key Features

### 🎹 Interactive Piano Visualization
- Real-time piano key highlighting
- Dynamic note activation display
- Professional-grade MIDI playback

### 🌀 3D Dynamic Visualization
- Stunning 3D bubble animations
- Fibonacci-sequence based note arrangement
- Customizable viewing angles (Elevation & Azimuth)
- Real-time physics simulation for bubble movement

### 🎼 Advanced MIDI Processing
- Seamless MIDI file integration
- Automatic piano sound mapping
- Volume-sensitive visual effects

## 🚀 Quick Start

### Prerequisites
Ensure you have Python 3.7+ installed, then run:
```bash
pip install matplotlib mido pygame numpy scipy PyQt5 numba
```

### Running the Application
1. Clone this repository
2. Navigate to the project directory
3. Run the main application:
   ```bash
   python musicalbubblecolumn.py
   ```
4. Select your MIDI file and enjoy the show! 🎉

## 🎨 Visual Experience

### Bubble Physics
- Dynamic bubble generation based on note velocity
- Realistic floating and merging animations
- Volume-sensitive transparency and size adjustments

### Interactive Controls
- Real-time view angle adjustment
- Dynamic perspective control
- Customizable visualization parameters

## 🔧 Technical Architecture

### Core Components
- **PatternVisualizer3D**: Main visualization engine
- **MIDI Processor**: Handles MIDI data parsing and event management
- **Physics Engine**: Manages bubble dynamics and interactions

### Performance Optimizations
- Numba-accelerated computations
- Efficient memory management

## 📝 Notes
- Piano sound mapping is optimized for visualization
- Performance varies based on system specifications

## 🤝 Contributing
Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.

---
[demo-gif]: assets/demo.gif "Musical Bubble Column in Action"
