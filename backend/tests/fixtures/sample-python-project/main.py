"""Main entry: imports config/logger/utils/animals and wires them together."""
from __future__ import annotations

from config import Config, load_config, default_config
from logger import Logger
from utils import add, multiply, format_pair
from animals import Animal, Dog, Cat, make_animals


def main() -> None:
    """Program entry point."""
    cfg: Config = load_config("sample")
    default: Config = default_config()
    logger = Logger(cfg.name)

    x = add(1, 2)
    y = multiply(3, 4)
    pair = format_pair(x, y)
    logger.info(pair)

    animals = make_animals()
    for a in animals:
        logger.info(a.describe())


if __name__ == "__main__":
    main()
