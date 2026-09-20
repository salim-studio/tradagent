"""One-command start: python run.py [--symbols BTC,ETH,SOL] [--dashboard]"""
import sys
sys.path.insert(0, ".")
from cli import main
if __name__ == "__main__":
    # python run.py  ==  tradagent run (quick default)
    if len(sys.argv) == 1 or sys.argv[1].startswith("-"):
        sys.argv.insert(1, "run")
    main()
