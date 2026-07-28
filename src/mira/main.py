"""Entry point."""

from mira.config import load_env
from mira.display import server


def main():
    load_env()
    server.run()


if __name__ == "__main__":
    main()

