"""
Taras F1 API v1 — Root Runner Launcher (run_v1.py)
Convenience launcher that delegates to v1/run_v1.py with full argument forwarding.

Usage:
  python run_v1.py                  # Run all v1 pipelines safely once
  python run_v1.py --stealth        # Maximum safety mode (3.5s - 6.5s delays)
  python run_v1.py --force          # Force re-scraping existing cached sessions
  python run_v1.py --loop           # Continuous scraping mode with polite jitter
  python run_v1.py --interval 300   # Set loop interval in seconds (default: 300)
  python run_v1.py --push           # Auto-deploy to GitHub if verified
  python run_v1.py --skip-sessions  # Only update standings and calendar
  python run_v1.py --skip-standings # Only update session classifications
"""

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
V1_RUNNER = os.path.join(BASE_DIR, "v1", "run_v1.py")

if __name__ == "__main__":
    if not os.path.exists(V1_RUNNER):
        print(f"Error: Could not locate v1 runner at {V1_RUNNER}")
        sys.exit(1)

    cmd = [sys.executable, V1_RUNNER] + sys.argv[1:]
    try:
        proc = subprocess.run(cmd, cwd=BASE_DIR)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        print("\n[run_v1] Interrupted by user.")
        sys.exit(0)
