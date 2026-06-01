"""
F.R.I.D.A.Y. Siri-like Glowing Overlay.

Provides a borderless, transparent, floating glowing circular visualizer
in the top-right of the screen during active voice interactions.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from src.utils.logger import get_logger

logger = get_logger("friday.overlay")

class FridayOverlay:
    """
    Manages a transparent, borderless, floating glowing Siri-like orb
    at the top-right of the screen.
    """

    def __init__(self) -> None:
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._visible = False
        self._pulse_dir = 1
        self._pulse_val = 0.5
        self._orb_color = "#00f0ff" # Neon Cyan/Blue default
        self._glow_objects: list[int] = []

    def start(self) -> None:
        """Starts the overlay thread (window stays hidden initially)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_window, daemon=True, name="friday-overlay")
        self._thread.start()
        logger.info("Overlay engine initialized.")

    def stop(self) -> None:
        """Stops the overlay completely."""
        self._running = False
        self._visible = False
        if self._root:
            try:
                self._root.quit()
            except Exception:
                pass

    def show(self, state: str = "verifying") -> None:
        """Shows the glowing orb with state-specific colors."""
        # Set state color
        if state == "verifying":
            self._orb_color = "#0066ff" # Deep blue
        elif state == "ready":
            self._orb_color = "#00f0ff" # Vibrant cyan
        elif state == "processing":
            self._orb_color = "#bf00ff" # Neon purple
        elif state == "speaking":
            self._orb_color = "#ff007f" # Neon pink/rose
        else:
            self._orb_color = "#00f0ff"

        self._visible = True
        if self._root:
            self._root.after(0, self._set_visibility, True)

    def hide(self) -> None:
        """Hides the overlay window."""
        self._visible = False
        if self._root:
            self._root.after(0, self._set_visibility, False)

    def _set_visibility(self, visible: bool) -> None:
        if not self._root:
            return
        if visible:
            self._root.deiconify()
            self._root.lift()
            self._root.attributes("-topmost", True)
        else:
            self._root.withdraw()

    def _run_window(self) -> None:
        try:
            self._root = tk.Tk()
            self._root.overrideredirect(True) # Borderless
            self._root.attributes("-topmost", True) # Always on top
            self._root.config(bg="systemTransparent") # macOS transparent
            
            # Position at top-right of screen
            screen_width = self._root.winfo_screenwidth()
            window_width = 120
            window_height = 120
            x = screen_width - window_width - 20
            y = 40 # Right below menu bar
            self._root.geometry(f"{window_width}x{window_height}+{x}+{y}")

            # Create canvas
            self._canvas = tk.Canvas(
                self._root,
                width=window_width,
                height=window_height,
                bg="systemTransparent",
                highlightthickness=0
            )
            self._canvas.pack()

            # Start animation loop
            self._animate()

            # Hide initially
            self._root.withdraw()

            # Run loop
            self._root.mainloop()
        except Exception as e:
            logger.error(f"Overlay window crashed: {e}")

    def _animate(self) -> None:
        if not self._root or not self._canvas or not self._running:
            return

        # Simple pulse calculation
        self._pulse_val += 0.05 * self._pulse_dir
        if self._pulse_val >= 1.0:
            self._pulse_val = 1.0
            self._pulse_dir = -1
        elif self._pulse_val <= 0.4:
            self._pulse_val = 0.4
            self._pulse_dir = 1

        if self._visible:
            self._canvas.delete("all")
            
            # Draw glowing Siri-like gradient orb
            center_x = 60
            center_y = 60
            base_radius = 28
            
            # Layer translucent concentric circles for neon glow effect
            layers = 8
            for i in range(layers, 0, -1):
                # Calculate alpha glow size
                radius = base_radius + (i * 3.5) * self._pulse_val
                # Translucency color mappings (Siri blue/purple blend)
                if self._orb_color == "#00f0ff": # Cyan
                    color = self._blend_colors("#000022", "#00f0ff", (layers - i) / layers)
                elif self._orb_color == "#0066ff": # Deep blue
                    color = self._blend_colors("#000022", "#0066ff", (layers - i) / layers)
                elif self._orb_color == "#bf00ff": # Purple
                    color = self._blend_colors("#110022", "#bf00ff", (layers - i) / layers)
                else: # Rose
                    color = self._blend_colors("#220011", "#ff007f", (layers - i) / layers)
                
                self._canvas.create_oval(
                    center_x - radius, center_y - radius,
                    center_x + radius, center_y + radius,
                    fill=color, outline="", stipple=""
                )

            # Core sharp orb
            core_radius = base_radius - 2
            self._canvas.create_oval(
                center_x - core_radius, center_y - core_radius,
                center_x + core_radius, center_y + core_radius,
                fill=self._orb_color, outline=""
            )

        # Schedule next frame in 30ms
        self._root.after(30, self._animate)

    def _blend_colors(self, color1: str, color2: str, factor: float) -> str:
        """Blends two hex colors together."""
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        
        r = int(r1 + factor * (r2 - r1))
        g = int(g1 + factor * (g2 - g1))
        b = int(b1 + factor * (b2 - b1))
        
        return f"#{r:02x}{g:02x}{b:02x}"
