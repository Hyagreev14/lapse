import os
import sys
import time
import shutil
import argparse
import subprocess
import signal
from datetime import datetime

class TimelapseCLI:
    def __init__(self, args):
        self.args = args
        self.frame_count = 0
        self.running = True
        
        # Calculate playback FPS from the requested frame duration
        # If a screenshot should last 2 seconds, FPS = 1 / 2 = 0.5
        self.playback_fps = 1.0 / self.args.duration
        
        # Temporary storage directory for frames
        self.temp_dir = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Temp', 'timelapse_frames')
        
        # Validate FFmpeg presence
        if not shutil.which("ffmpeg"):
            print("[ERROR] FFmpeg was not found in your System PATH.", file=sys.stderr)
            print("Please ensure ffmpeg.exe is installed and configured correctly.", file=sys.stderr)
            sys.exit(1)

    def setup_directories(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.args.output, exist_ok=True)

    def handle_shutdown(self, signum, frame):
        """Intercepts Ctrl+C safely to trigger stitching"""
        print("\n\n[INFO] Capture stopped by user. Initialising stitching phase...")
        self.running = False

    def start_capture(self):
        self.setup_directories()
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        print("=" * 60)
        print("          ADVANCED CLI SCREEN TIMELAPSE STUDIO")
        print("=" * 60)
        print(f"[*] Capture Interval : Every {self.args.interval} second(s)")
        print(f"[*] Frame Duration   : {self.args.duration} second(s) per screenshot ({self.playback_fps:.3f} FPS)")
        print(f"[*] Output Directory : {os.path.abspath(self.args.output)}")
        print(f"[*] Output File Name : {self.args.name}")
        print("[!] PRESS [Ctrl + C] TO STOP CAPTURING AND BUILD VIDEO")
        print("-" * 60)

        base_index = 100001
        
        while self.running:
            filename = os.path.join(self.temp_dir, f"frame_{base_index + self.frame_count}.png")
            
            # Silent screen grab using gdigrab
            cmd = f'ffmpeg -v error -y -f gdigrab -framerate 1 -i desktop -vframes 1 "{filename}"'
            result = subprocess.run(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode == 0:
                self.frame_count += 1
                sys.stdout.write(f"\r[+] Frames captured: {self.frame_count} ")
                sys.stdout.flush()
            else:
                print(f"\n[WARN] Failed to capture frame {self.frame_count}. Retrying...")

            # Interruptible sleep interval
            for _ in range(int(self.args.interval * 2)):
                if not self.running:
                    break
                time.sleep(0.5)
                
        self.stitch_video()

    def stitch_video(self):
        if self.frame_count == 0:
            print("[INFO] No frames captured. Operation aborted.")
            return

        final_video = os.path.join(self.args.output, self.args.name)
        input_pattern = os.path.join(self.temp_dir, "frame_1%05d.png")
        
        print(f"\n[*] Compiling video with H.264 compression...")
        
        # -r sets the frame rate (input layout duration), -y forces overwrite if the file exists
        stitch_cmd = f'ffmpeg -y -v info -r {self.playback_fps} -i "{input_pattern}" -c:v libx264 -pix_fmt yuv420p "{final_video}"'
        
        result = subprocess.run(stitch_cmd, shell=True)
        
        print("[*] Cleaning up temporary image buffers...")
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        if result.returncode == 0:
            print("-" * 60)
            print(f"[SUCCESS] Video cleanly exported to:\n{os.path.abspath(final_video)}")
            print("-" * 60)
        else:
            print("[ERROR] FFmpeg pipeline failed during compilation.", file=sys.stderr)

if __name__ == "__main__":
    # Fallback default locations
    default_out = os.path.join(os.environ['USERPROFILE'], 'Desktop')
    default_name = f"timelapse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    parser = argparse.ArgumentParser(description="CLI Screen Capture & Timelapse Builder")
    
    # -i / --interval
    parser.add_argument("-i", "--interval", type=float, default=5.0,
                        help="Capture frequency in seconds (e.g., 5 for taking a screenshot every 5s)")
    
    # -d / --duration
    parser.add_argument("-d", "--duration", type=float, default=1.0,
                        help="How long each screenshot lasts in the final video in seconds (e.g., 1 or 0.5)")
    
    # -o / --output
    parser.add_argument("-o", "--output", type=str, default=default_out,
                        help="Path to the final output destination directory")
    
    # -n / --name
    parser.add_argument("-n", "--name", type=str, default=default_name,
                        help="Name of the final video file (e.g., output.mp4)")

    args = parser.parse_args()
    
    # Quick sanity check for extension safety
    if not args.name.lower().endswith('.mp4'):
        args.name += '.mp4'

    app = TimelapseCLI(args)
    app.start_capture()
