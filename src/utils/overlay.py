"""
F.R.I.D.A.Y. Celestial Loom — Neon Orb Overlay.

A borderless, transparent, floating visualizer rendered in the top-right of
the macOS screen.  Implements four layers of premium visual behavior:

1. **Volumetric Depth & Layered Luminance**
   Matte outer ring → smoked-glass corona → radiant neon core.
2. **High-Frequency Optical Braiding**
   Rotating wave-thread arcs inspired by the SVG Celestial Loom design.
3. **Dynamic State Modulation (The Pulsing Logic)**
   Sinusoidal breath-cycle at ~0.8 Hz with state-specific color profiles.
4. **Screen Emissivity Effect**
   A wide, ultra-soft outer halo that bleeds light into surrounding desktop.
"""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger("friday.overlay")

try:
    import tkinter as tk
    TK_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    tk = None
    TK_AVAILABLE = False

# ── Icon asset path (PNG reference for FridayUI/docs) ────────
ICON_PNG = Path(__file__).resolve().parent.parent.parent / "assets" / "friday-icon.png"

# ── State color profiles ─────────────────────────────────────
# Each state maps to:  (core_color, corona_color, halo_color, dark_base)
STATE_COLORS: dict[str, tuple[str, str, str, str]] = {
    "verifying":  ("#0066FF", "#002299", "#001155", "#000022"),
    "ready":      ("#00F2FF", "#006688", "#003344", "#001122"),
    "listening":  ("#00F2FF", "#006688", "#003344", "#001122"),
    "processing": ("#BF00FF", "#550077", "#330044", "#110022"),
    "speaking":   ("#FF007F", "#880033", "#440022", "#220011"),
}
DEFAULT_PROFILE = STATE_COLORS["ready"]

# ── Animation constants ──────────────────────────────────────
WINDOW_SIZE  = 160           # px — window dimensions
CENTER       = WINDOW_SIZE // 2
BASE_RADIUS  = 28            # Core orb radius
CORONA_RINGS = 10            # Number of translucent corona layers
HALO_RINGS   = 6             # Number of outer emissivity rings
WAVE_THREADS = 6             # Number of braided arc threads
PULSE_HZ     = 0.8           # Breath-cycle frequency
FRAME_MS     = 25            # ~40 FPS
ROTATION_SPEED = 0.012       # Radians per frame for wave braiding


class FridayOverlay:
    """
    Manages the transparent, borderless, floating Celestial Loom orb
    at the top-right of the macOS screen.
    """

    def __init__(self) -> None:
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._running = False
        self._visible = False
        self._state = "ready"
        self._phase = 0.0          # Sinusoidal breath phase (radians)
        self._rotation = 0.0       # Wave braid rotation angle (radians)

    # ── Public API ───────────────────────────────────────────

    def start(self) -> None:
        """Starts the overlay graphics (instantiates Tkinter on the main thread)."""
        if not TK_AVAILABLE:
            logger.warning("Tkinter is not available in this Python environment. Glowing overlay will be disabled.")
            return
        if self._running:
            return
        self._running = True
        self._init_window()
        logger.info("Overlay engine initialized on the main thread.")

    def stop(self) -> None:
        """Stops the overlay completely."""
        self._running = False
        self._visible = False
        if self._root:
            try:
                self._root.destroy()
                self._root = None
            except Exception:
                pass

    def show(self, state: str = "ready") -> None:
        """Shows the glowing orb with state-specific color profile."""
        self._state = state
        self._visible = True
        if self._root:
            self._root.after(0, self._set_visibility, True)

    def hide(self) -> None:
        """Hides the overlay window."""
        self._visible = False
        if self._root:
            self._root.after(0, self._set_visibility, False)

    # ── Internal: window lifecycle ───────────────────────────

    def _set_visibility(self, visible: bool) -> None:
        if not self._root:
            return
        if visible:
            self._root.deiconify()
            self._root.lift()
            self._root.attributes("-topmost", True)
        else:
            self._root.withdraw()

    def _init_window(self) -> None:
        try:
            self._root = tk.Tk()
            self._root.overrideredirect(True)
            self._root.attributes("-topmost", True)
            self._root.config(bg="systemTransparent")

            # Position: top-right of screen, below menu bar
            screen_w = self._root.winfo_screenwidth()
            x = screen_w - WINDOW_SIZE - 16
            y = 36
            self._root.geometry(f"{WINDOW_SIZE}x{WINDOW_SIZE}+{x}+{y}")

            self._canvas = tk.Canvas(
                self._root,
                width=WINDOW_SIZE,
                height=WINDOW_SIZE,
                bg="systemTransparent",
                highlightthickness=0,
            )
            self._canvas.pack()

            # Hide initially
            self._root.withdraw()

            # Process initial window events
            self._root.update_idletasks()
            self._root.update()
        except Exception as e:
            logger.error(f"Failed to initialize overlay window: {e}")
            self._running = False

    def update(self) -> None:
        """Called periodically from the main thread loop to update graphics and process events."""
        if not self._running or not self._root:
            return

        try:
            now = time.time()
            if not hasattr(self, "_last_frame_time"):
                self._last_frame_time = 0.0

            # ~40 FPS = 25ms interval
            if now - self._last_frame_time >= (FRAME_MS / 1000.0):
                self._last_frame_time = now
                self._animate_frame()

            # Process pending Tkinter events (non-blocking)
            self._root.update_idletasks()
            self._root.update()
        except Exception as e:
            logger.error(f"Overlay update failed: {e}")
            self._running = False

    # ── Internal: animation engine ───────────────────────────

    def _animate_frame(self) -> None:
        if not self._root or not self._canvas or not self._running:
            return

        # Advance sinusoidal breath phase
        self._phase += (2 * math.pi * PULSE_HZ * FRAME_MS) / 1000.0
        if self._phase > 2 * math.pi:
            self._phase -= 2 * math.pi

        # Advance wave rotation
        self._rotation += ROTATION_SPEED

        if self._visible:
            self._canvas.delete("all")
            pulse = 0.5 + 0.5 * math.sin(self._phase)  # 0.0 → 1.0

            core, corona, halo, dark = STATE_COLORS.get(
                self._state, DEFAULT_PROFILE
            )

            # Layer 1: Screen Emissivity Halo (ultra-wide, ultra-soft)
            self._draw_halo(pulse, halo)

            # Layer 2: Smoked-glass corona (volumetric depth)
            self._draw_corona(pulse, dark, corona)

            # Layer 3: Matte outer calibration rings
            self._draw_calibration_rings()

            # Layer 4: Optical braided wave threads
            self._draw_wave_braids(pulse, core, corona)

            # Layer 5: Dense convergence core
            self._draw_core(pulse, core)

    # ── Drawing primitives ───────────────────────────────────

    def _draw_halo(self, pulse: float, halo_color: str) -> None:
        """Screen emissivity — wide, translucent glow bleeding outward."""
        for i in range(HALO_RINGS, 0, -1):
            radius = BASE_RADIUS + 30 + i * 6 * (0.6 + 0.4 * pulse)
            alpha_factor = (HALO_RINGS - i) / HALO_RINGS * 0.35
            color = self._blend("#000000", halo_color, alpha_factor * pulse)
            self._oval(radius, color)

    def _draw_corona(self, pulse: float, dark: str, corona_color: str) -> None:
        """Volumetric depth — layered concentric translucent rings."""
        for i in range(CORONA_RINGS, 0, -1):
            radius = BASE_RADIUS + i * 3.2 * (0.7 + 0.3 * pulse)
            factor = (CORONA_RINGS - i) / CORONA_RINGS
            color = self._blend(dark, corona_color, factor * (0.5 + 0.5 * pulse))
            self._oval(radius, color)

    def _draw_calibration_rings(self) -> None:
        """High-precision thin outer rings (static anchors)."""
        # Dashed outer ring
        r1 = BASE_RADIUS + 38
        self._canvas.create_oval(
            CENTER - r1, CENTER - r1, CENTER + r1, CENTER + r1,
            outline="#3A3F47", width=1, dash=(4, 16),
        )
        # Solid outermost ring
        r2 = BASE_RADIUS + 42
        self._canvas.create_oval(
            CENTER - r2, CENTER - r2, CENTER + r2, CENTER + r2,
            outline="#1F232B", width=1.5,
        )

    def _draw_wave_braids(self, pulse: float, core: str, corona: str) -> None:
        """
        High-frequency optical braiding — rotating arc-pairs that evoke
        the Celestial Loom SVG's mathematical wave clusters.
        """
        for t in range(WAVE_THREADS):
            angle_offset = (2 * math.pi / WAVE_THREADS) * t + self._rotation
            # Inner wave (deep indigo/blue anchors)
            r_inner = BASE_RADIUS + 6 + 8 * pulse
            self._draw_arc_pair(
                r_inner, angle_offset, corona, width=2, dash=(2, 2)
            )
            # Outer wave (cyan high-frequency strands)
            r_outer = BASE_RADIUS + 14 + 6 * pulse
            self._draw_arc_pair(
                r_outer, angle_offset + 0.3, core, width=1, dash=None
            )

    def _draw_arc_pair(
        self, radius: float, angle: float, color: str,
        width: int = 1, dash: tuple[int, ...] | None = None,
    ) -> None:
        """Draws a short arc pair symmetrically around center."""
        arc_extent = 35  # degrees
        start_deg = math.degrees(angle)
        kw: dict = {"outline": color, "width": width, "style": "arc"}
        if dash:
            kw["dash"] = dash
        # Arc A
        self._canvas.create_arc(
            CENTER - radius, CENTER - radius,
            CENTER + radius, CENTER + radius,
            start=start_deg, extent=arc_extent, **kw,
        )
        # Arc B (opposite)
        self._canvas.create_arc(
            CENTER - radius, CENTER - radius,
            CENTER + radius, CENTER + radius,
            start=start_deg + 180, extent=arc_extent, **kw,
        )

    def _draw_core(self, pulse: float, core_color: str) -> None:
        """Dense convergence node — white-hot center with pulsing core."""
        # Outer white glow
        glow_r = BASE_RADIUS - 2 + 4 * pulse
        glow_color = self._blend("#FFFFFF", core_color, 0.3)
        self._oval(glow_r, glow_color)

        # Inner solid orb
        core_r = BASE_RADIUS - 6
        self._oval(core_r, core_color)

        # Hot white center dot
        dot_r = 5 + 2 * pulse
        self._oval(dot_r, "#FFFFFF")

    # ── Helpers ──────────────────────────────────────────────

    def _oval(self, radius: float, color: str) -> None:
        """Shorthand: draw a filled oval centered on the window."""
        self._canvas.create_oval(
            CENTER - radius, CENTER - radius,
            CENTER + radius, CENTER + radius,
            fill=color, outline="",
        )

    @staticmethod
    def _blend(c1: str, c2: str, factor: float) -> str:
        """Blend two hex colors by a factor (0.0 = c1, 1.0 = c2)."""
        factor = max(0.0, min(1.0, factor))
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        r = int(r1 + factor * (r2 - r1))
        g = int(g1 + factor * (g2 - g1))
        b = int(b1 + factor * (b2 - b1))
        return f"#{r:02x}{g:02x}{b:02x}"
