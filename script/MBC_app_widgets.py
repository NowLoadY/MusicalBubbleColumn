import MBC_config
from MBC_config import get_config
import threading
from collections import deque
import numpy as np
from mido import MidiFile
import pygame
import os.path as os_path
import os


class MidiVisualizer:
    def __init__(self, visualizer):
        self.config = get_config()
        self.visualizer = visualizer
        self.wav_channel = None
        self.process_midi_thread_bool = True
        self.midi_thread = None
        
        # Initialize arrays with config values
        pattern_key_count = self.config.audio.pattern_key_count
        midi_key_count = self.config.audio.midi_note_max - self.config.audio.midi_note_min + 1
        
        self.volumes = [0] * pattern_key_count
        self.total_volumes = deque(maxlen=self.config.audio.total_volumes_maxlen)
        self.key_activation = np.zeros(pattern_key_count, dtype=int)
        self.new_pattern = bytes(15)  # Keep as is for now
        self.key_activation_bytes = bytes(15)  # Keep as is for now
        self.update_count = 0
        self.zero_pattern_interval = self.config.audio.zero_pattern_interval
        self.default_wav_playing = False
        self.key_activation_real = np.zeros(midi_key_count + 8, dtype=np.uint8)  # 真实钢琴键位
        self.key_activation_real_bytes = bytes(16)  # 16 bytes for 128 bits (1 bit per key)
        self.volumes_real = np.zeros(midi_key_count + 8, dtype=np.uint8)
        
        # Initialize pygame mixer with config
        pygame.mixer.init(
            frequency=self.config.audio.frequency,
            size=self.config.audio.size,
            channels=self.config.audio.channels
        )
        pygame.mixer.set_num_channels(self.config.audio.mixer_channels)
    
    def prepare_midi_file(self, midi_path):
        temp_midi_path = "temp_midi_file.mid"
        midi = MidiFile(midi_path)
        for track in midi.tracks:
            for msg in track:
                if msg.type == 'program_change':
                    msg.program = 0  # Piano sound
        midi.save(temp_midi_path)
        return midi, temp_midi_path
        
    def stop_all_audio(self):
        """Stop all playing audio including MIDI and WAV"""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()  # Add this line to unload the MIDI file
            
            # Stop and clear all mixer channels
            pygame.mixer.stop()  # Stop all channels
            
            if self.wav_channel is not None:
                self.wav_channel.stop()
                self.wav_channel = None
            
            self.default_wav_playing = False
        except Exception as e:
            print(f"Error stopping audio: {e}")
    
    def setup_audio(self, midi_path, temp_midi_path):
        # Stop any existing audio first
        self.stop_all_audio()
        
        # Reinitialize mixer to ensure clean state
        pygame.mixer.quit()
        pygame.mixer.init(
            frequency=self.config.audio.frequency,
            size=self.config.audio.size,
            channels=self.config.audio.channels
        )
        pygame.mixer.set_num_channels(self.config.audio.mixer_channels)

        try:
            pygame.mixer.music.load(temp_midi_path)
            pygame.mixer.music.play()
            
            # Check for vocal audio file (WAV or MP3)
            base_path = os.path.splitext(midi_path)[0] + '_vocal'
            wav_path = base_path + '.wav'
            mp3_path = base_path + '.mp3'
            
            # Play audio if it exists (either default or matching vocal file)
            if midi_path == self.config.file_paths.default_midi_path and os_path.exists(self.config.file_paths.default_wav_path):
                vocal_to_play = self.config.file_paths.default_wav_path
                vocal_file_type = "wav"
            elif os_path.exists(wav_path):
                vocal_to_play = wav_path
                vocal_file_type = "wav"
            elif os_path.exists(mp3_path):
                vocal_to_play = mp3_path
                vocal_file_type = "mp3"
            else:
                vocal_to_play = None
            
            if vocal_to_play:
                self.wav_channel = pygame.mixer.Channel(1)
                vocal_sound = pygame.mixer.Sound(vocal_to_play)
                if vocal_file_type == "wav":
                    pygame.time.delay(self.config.audio.wav_delay_ms)
                if vocal_file_type == "mp3":
                    pygame.time.delay(self.config.audio.mp3_delay_ms)
                self.wav_channel.play(vocal_sound)
                self.default_wav_playing = True
        except Exception as e:
            print(f"Error setting up audio: {e}")
    
    def get_note_range(self, midi):
        min_note, max_note = 127, 0
        for track in midi.tracks:
            for msg in track:
                if msg.type in ['note_on', 'note_off']:
                    min_note = min(min_note, msg.note)
                    max_note = max(max_note, msg.note)
        return min_note, max_note
    
    def map_note_to_range(self, note, min_note, max_note):
        # Map MIDI note to piano key index using config values
        piano_key = note - self.config.audio.midi_note_min
        # Ensure the note is within the piano's range
        piano_key = max(0, min(self.config.audio.piano_key_count - 1, piano_key))
        return piano_key
    
    def process_midi(self, midi_iterator, min_note, max_note):
        for msg in midi_iterator:
            if msg.type == 'note_on':
                note = msg.note  # 真实MIDI键位

                # 1. 计算new_pattern（120键映射，用于模式）
                mapped_note = self.map_note_to_range(note, min_note, max_note)
                if 0 <= mapped_note < self.config.audio.pattern_key_count:
                    self.key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg.velocity > 0) else 0
                    self.volumes[mapped_note] = msg.velocity if msg.type == 'note_on' else 0
                    self.total_volumes.append(msg.velocity)

                self.new_pattern = np.packbits(self.key_activation).tobytes()

                # 2. 记录真实键位激活（用于钢琴可视化）
                if self.config.audio.midi_note_min <= note <= self.config.audio.midi_note_max:
                    self.key_activation_real[note] = 1 if msg.velocity > 0 else 0
                    self.volumes_real[note] = msg.velocity  # 用真实键位存音量

                self.key_activation_real_bytes = np.packbits(self.key_activation_real).tobytes()
                self.update_count = 0

            if not pygame.mixer.music.get_busy() or not self.process_midi_thread_bool:
                break
    
    def visualize(self, midi_path):
        # Stop any existing audio before starting new visualization
        self.stop_all_audio()
        
        self.visualizer.working = True
        self.process_midi_thread_bool = True
        
        # Prepare and play MIDI
        midi, temp_midi_path = self.prepare_midi_file(midi_path)
        self.setup_audio(midi_path, temp_midi_path)
        
        # Setup MIDI processing
        min_note, max_note = self.get_note_range(midi)
        midi_iterator = iter(midi.play())
        
        # Start MIDI processing thread
        self.midi_thread = threading.Thread(
            target=self.process_midi, 
            args=(midi_iterator, min_note, max_note)
        )
        self.midi_thread.start()
        
        # Main visualization loop
        while True:
            average_volume = sum(self.total_volumes) / len(self.total_volumes) if self.total_volumes else 0
            
            if self.update_count % self.zero_pattern_interval == 0:
                self.new_pattern = bytes(15)
                one_volumes = [1] * self.config.audio.pattern_key_count
                self.visualizer.update_pattern(self.new_pattern, one_volumes, average_volume, None, None)
            else:
                self.visualizer.update_pattern(
                    new_pattern=self.new_pattern,
                    volumes=self.volumes,         # 长度固定 120
                    average_volume=average_volume,
                    key_activation_bytes=self.key_activation_real_bytes,
                    volumes_real=self.volumes_real,
                )
            self.update_count += 1
            
            if not pygame.mixer.music.get_busy() and np.sum(self.visualizer.pattern_data) == 0:
                self.visualizer.working = False
                break
                
            self.visualizer.update_view_angle()
            if not self.visualizer.working:
                self.process_midi_thread_bool = False
                # 如果默认WAV在播放，停止它
                if self.default_wav_playing:
                    self.stop_all_audio()
                break
        
        self.midi_thread.join()
        pygame.mixer.music.stop()
