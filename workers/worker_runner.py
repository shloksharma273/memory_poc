#!/usr/bin/env python
"""
Standalone worker runner.
"""

import sys
import os

# Add the project root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ingestion_worker import worker_loop

if __name__ == "__main__":
    try:
        worker_loop()
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")
