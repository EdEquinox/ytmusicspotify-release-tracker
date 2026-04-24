"""Compat entrypoint; prefer `python main.py` or the Docker image CMD."""

from main import main

if __name__ == "__main__":
    main()
