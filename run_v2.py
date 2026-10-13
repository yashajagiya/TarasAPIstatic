"""
Taras F1 API v2 — Root Runner Launcher (run_v2.py)
Convenience launcher that delegates to v2/run_v2.py with full argument forwarding.

Usage:
  python run_v2.py                  # Auto-detect active weekend & run safely
  python run_v2.py --round 17       # Scrape specific round
  python run_v2.py --skip-scrape    # Build & verify without web requests
  python run_v2.py --stealth        # Maximum safety mode (3.5s - 6.5s delays)
  python run_v2.py --force          # Force re-scraping existing cached rounds
  python run_v2.py --loop           # Continuous scraping mode with polite jitter
  python run_v2.py --interval 300   # Set loop interval in seconds (default: 300)
  python run_v2.py --push           # Auto-deploy to GitHub if verified
"""

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
V2_RUNNER = os.path.join(BASE_DIR, "v2", "run_v2.py")

if __name__ == "__main__":
    if not os.path.exists(V2_RUNNER):
        print(f"Error: Could not locate v2 runner at {V2_RUNNER}")
        sys.exit(1)

    cmd = [sys.executable, V2_RUNNER] + sys.argv[1:]
    try:
        proc = subprocess.run(cmd, cwd=BASE_DIR)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        print("\n[run_v2] Interrupted by user.")
        sys.exit(0)
