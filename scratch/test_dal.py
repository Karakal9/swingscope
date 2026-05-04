import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent))

import config as cfg
from analyze import analyze_ticker
from rich.console import Console

console = Console()

def test_dal():
    result = analyze_ticker("DAL", force_refresh=True)
    if result:
        print(f"Ticker: {result['ticker']}")
        print(f"Setup: {result['setup']}")
        print(f"Score: {result['score']}")
        print(f"Verdict: {result['verdict']}")
        print("\nDiscrete Fields:")
        for k, v in result['discrete_fields'].items():
            print(f"  {k}: {v}")
        
if __name__ == "__main__":
    test_dal()
