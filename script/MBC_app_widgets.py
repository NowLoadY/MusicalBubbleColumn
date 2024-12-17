import MBC_config
import threading
from collections import deque
import numpy as np
from mido import MidiFile
import pygame
import os.path as os_path
import os


class MidiVisualizer:
    def __init__(self, visualizer):
        self.visualizer = visualizer
        self.wav_channel = None
        self.process_midi_thread_bool = True
        self.midi_thread = None
        self.volumes = [0] * 120
        self.total_volumes = deque(maxlen=240)
        self.key_activation = np.zeros(120, dtype=int)
        self.new_pattern = bytes(15)
        self.key_activation_bytes = bytes(15)
        self.update_count = 0
        self.zero_pattern_interval = 2
        self.default_wav_playing = False
        
        pygame.mixer.init(frequency=44100, size=-16, channels=2)
        pygame.mixer.set_num_channels(2)
    
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
        pygame.mixer.init(frequency=44100, size=-16, channels=2)
        pygame.mixer.set_num_channels(2)

        try:
            pygame.mixer.music.load(temp_midi_path)
            pygame.mixer.music.play()
            
            # Check for vocal audio file (WAV or MP3)
            base_path = os.path.splitext(midi_path)[0] + '_vocal'
            wav_path = base_path + '.wav'
            mp3_path = base_path + '.mp3'
            
            # Play audio if it exists (either default or matching vocal file)
            if midi_path == MBC_config.DEFAULT_MIDI_PATH and os_path.exists(MBC_config.WAV_FILE_PATH):
                vocal_to_play = MBC_config.WAV_FILE_PATH
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
                    pygame.time.delay(300)
                if vocal_file_type == "mp3":
                    pygame.time.delay(100)
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
        note_array = np.clip((note - min_note) / (max_note - min_note) * 120, 0, 119)
        return int(note_array)
    
    def process_midi(self, midi_iterator, min_note, max_note):
        for msg in midi_iterator:
            if msg.type in ['note_on']:
                mapped_note = self.map_note_to_range(msg.note, min_note, max_note)
                if 0 <= mapped_note < 120:
                    self.key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg.velocity > 0) else 0
                    self.volumes[mapped_note] = msg.velocity if msg.type == 'note_on' else 0
                    self.total_volumes.append(msg.velocity)

                self.new_pattern = np.packbits(self.key_activation).tobytes()
                self.key_activation_bytes = np.packbits(self.key_activation).tobytes()
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
                one_volumes = [1] * 120
                self.visualizer.update_pattern(self.new_pattern, one_volumes, average_volume, None)
            else:
                self.visualizer.update_pattern(
                    self.new_pattern, 
                    self.volumes, 
                    average_volume, 
                    self.key_activation_bytes
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
