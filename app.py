import subprocess
import sys
import threading
import time
import os

# ── R2 后台同步线程 ────────────────────────────────────────
def r2_sync_loop():
    """后台线程：每小时同步一次到 R2"""
    time.sleep(60)
    while True:
        if os.environ.get("R2_ENDPOINT") and os.environ.get("R2_ACCESS_KEY"):
            try:
                result = subprocess.run(
                    [sys.executable, "scripts/sync_to_r2.py"],
                    capture_output=True, text=True, timeout=300
                )
                print("[R2] Sync output:", result.stdout[-500:] if result.stdout else "")
                if result.returncode != 0:
                    print("[R2] Sync error:", result.stderr[-200:])
            except Exception as e:
                print(f"[R2] Sync exception: {e}")
        time.sleep(3600)

r2_thread = threading.Thread(target=r2_sync_loop, daemon=True)
r2_thread.start()
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting HermesFace Sync Wrapper...")

    # Enhanced error handling: don't crash if sync fails
    try:
        subprocess.run([sys.executable, "scripts/sync_hf.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Sync failed with exit code {e.returncode}, but continuing startup...")
        print(f"    Error: {e}")
        print("    → Hermes Agent will start without initial dataset sync")
    except Exception as e:
        print(f"⚠️  Unexpected sync error: {e}")
        print("    → Hermes Agent will start anyway")
