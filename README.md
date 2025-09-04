<div align="center" style="display: flex; align-items: center; justify-content: center;">
  <img src="asset/rounded_icon.png" width="15%" style="margin-right: 50px; margin-bottom: 10px;" /> 
  <h1>Musical Bubble Column!</h1>
</div>

# Overview
[让我们说中文](README_ch.md)

**Musical Bubble Column** is a 3D music visualization project built with Python that displays MIDI music in a visual format. Using **Matplotlib** and **Pygame**, it creates a visual representation of musical notes arranged in a Fibonacci spiral pattern.

## ToDoList
- [ ] Use better render engine

## Features
<div align="center">
  <img src="asset/preview.gif" width="50%" />
</div>

### Piano Visualization
- Piano key visualization (The virtual piano keys in the visualization do not strictly match the actual piano keys.)
- Note display
- MIDI playback

### 3D Visualization
- 3D bubble animations
- Fibonacci-sequence based layout
- Adjustable viewing angles (Elevation & Azimuth)
- Basic physics simulation

### MIDI Processing
- MIDI file support
- Piano sound mapping
- Volume-based visual effects

# Getting Started

## Prerequisites
Python 3.7+ and the following packages are required:
```bash
pip install matplotlib mido pygame numpy scipy PyQt5 numba
```

## Running the Application
1. Clone this repository
2. Navigate to the project directory
3. Run the main application:
   ```bash
   python musicalbubblecolumn.py
   ```
4. Select your MIDI file to start

Alternatively, you can download the precompiled .exe file from the [releases](https://github.com/NowLoadY/MusicalBubbleColumn/releases) section and run it directly without needing to set up the Python environment.

# Features in Detail

## Visualization
- Bubble generation based on notes
- Floating animations
- Volume-based visual effects

## Interactive Controls
<div align="center">
<table>
<tr>
  <td><img src="asset/pitch.gif" width="100%" /></td>
  <td><img src="asset/rotate.gif" width="100%" /></td>
  <td><img src="asset/zoomin.gif" width="100%" /></td>
</tr>
<tr align="center">
  <td>View adj: elev</td>
  <td>View adj: azim</td>
  <td>Zoom in/out</td>
</tr>
</table>
</div>

## Technical Details

### Components
- **PatternVisualizer3D**: Visualization engine
- **MIDI Processor**: MIDI data handling
- **Physics Sim**: Bubble movement

### Optimizations
- Numba acceleration
- Memory management

# Notes
- Optimized for standard MIDI files
- Performance depends on system hardware

# Contributing
welcome:
- Bug reports
- Feature suggestions
- Pull requests

# Collaboration

If you're interested in collaborating on this project or have any ideas for improvement, feel free to reach out! I'm open to discussions and welcome any contributions that could enhance this visualization tool.

You can:
- Open an issue for discussion
- Submit a pull request
- Contact me for any questions or suggestions

# License
This project is licensed under the GNU General Public License v3.0 (GPL-3.0) - see the LICENSE file for details.

# AI Project
This project heavily leverages AI-assisted programming.

# Project Structure
```mermaid
graph TD
    subgraph User Interface
        A[/File Selection/]
        B([3D Visualization Window])
    end

    subgraph Core Processing
        C{{MIDI Event Processor}}
        D{{Pattern Visualizer}}
        E([Physics Engine])
    end

    subgraph Data Flow
        F[(Pattern Data)]
        G([Position Calculator])
    end

    A -->|MIDI File| C
    C -->|Note Events| D
    G -->|Bubble Positions| D
    F -->|Pattern Buffer| D
    E -->|Bubble Movement| D
    D -->|Visualization| B

    style A fill:#ffffff,stroke:#003366,stroke-width:2px
    style B fill:#ffffff,stroke:#003366,stroke-width:2px
    style C fill:#003366,stroke:#003366,stroke-width:2px,color:#ffffff
    style D fill:#003366,stroke:#003366,stroke-width:2px,color:#ffffff
    style E fill:#ffffff,stroke:#003366,stroke-width:2px
    style F fill:#ffffff,stroke:#003366,stroke-width:2px
    style G fill:#ffffff,stroke:#003366,stroke-width:2px
```

# similar to this, 12 years ago? Cool!
chatgpt found me this:
[![similar to this, 12 years ago? cool](https://img.youtube.com/vi/2s8dPpujrB4/0.jpg)](https://www.youtube.com/watch?v=2s8dPpujrB4)
