import sys
import os
import tkinter as tk
from PIL import Image, ImageTk, ImageGrab
import subprocess
import tempfile
import time

class ScreenshotSelector:
    def __init__(self):
        # 1. Capture the entire desktop FIRST (all screens)
        self.screenshot = ImageGrab.grab(all_screens=True)
        self.width, self.height = self.screenshot.size
        
        # Windows coordinates can be negative on multi-monitor setups
        # But Pillow and Tkinter sometimes handle them differently depending on the primary screen.
        # ImageGrab.grab(all_screens=True) starts from the bounding box of ALL monitors.
        
        self.root = tk.Tk()
        self.root.withdraw() # Hide root while initializing
        
        # Remove window decorations
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.8) # Slight transparency for the dim effect
        
        # Set geometry to cover all monitors
        # Note: In some multi-monitor setups, (0,0) is NOT the top-left if screens are arranged differently.
        # For simplicity, we assume (0,0) context for the captured image.
        self.root.geometry(f"{self.width}x{self.height}+0+0")
        
        # On multi-monitor, sometimes (+0+0) doesn't work if the primary isn't at the top-left.
        # But with overrideredirect, we can force it.
        
        self.canvas = tk.Canvas(self.root, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Show the captured screenshot as background (optional, but good for context)
        # We can also just use a grey overlay
        self.tk_img = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        
        # Add a dimming layer
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill="black", stipple="gray50")

        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        
        self.root.deiconify() # Show window

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=5)

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        self.root.withdraw()
        time.sleep(0.1)
        self.capture(self.start_x, self.start_y, end_x, end_y)
        self.root.destroy()

    def capture(self, x1, y1, x2, y2):
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)

        if right - left < 5 or bottom - top < 5:
            return

        # Crop from the pre-captured entire desktop image
        # This is more reliable for multi-monutors
        img = self.screenshot.crop((left, top, right, bottom))
        
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, "screenshot_selection.png")
        img.save(temp_path)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        ps_script = os.path.join(script_dir, "PrivateSend.ps1")
        cmd = f'powershell -ExecutionPolicy Bypass -File "{ps_script}" "{temp_path}" -noPrice'
        subprocess.Popen(f'cmd /c {cmd}', shell=True)

if __name__ == "__main__":
    selector = ScreenshotSelector()
    selector.root.mainloop()
