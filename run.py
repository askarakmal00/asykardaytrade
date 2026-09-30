import uvicorn
import os
import sys

# Ensure project root is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    # Ensure necessary directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("app/static", exist_ok=True)
    
    print("=" * 60)
    print("  IDX DAY TRADE SIGNAL SYSTEM (LOCAL FIRST)")
    print("  URL: http://localhost:8000")
    print("=" * 60)
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
