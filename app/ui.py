"""Оформление терминального интерфейса InfoCore."""

from __future__ import annotations

import os
import sys
from typing import Any


USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
UI_WIDTH = 78
UI_INNER_WIDTH = UI_WIDTH - 4


def clear_screen() -> None:
    """Очищает окно терминала перед новым экраном InfoCore."""
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="")


class Color:
    RED = "\033[91m"
    DARK_RED = "\033[31m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def paint(text: Any, color: str = Color.WHITE, *, bold: bool = False) -> str:
    value = str(text)
    if not USE_COLOR:
        return value
    prefix = Color.BOLD if bold else ""
    return f"{prefix}{color}{value}{Color.RESET}"


def banner() -> None:
    print()
    print(paint("╔" + "═" * (UI_WIDTH - 2) + "╗", Color.RED))
    logo = (
        "  ██╗███╗   ██╗███████╗ ██████╗ ██████╗ ██████╗ ███████╗",
        "  ██║████╗  ██║██╔════╝██╔═══██╗██╔══██╗██╔══██╗██╔════╝",
        "  ██║██╔██╗ ██║█████╗  ██║   ██║██████╔╝██████╔╝█████╗  ",
        "  ██║██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██╔══██╗██╔══╝  ",
        "  ██║██║ ╚████║██║     ╚██████╔╝██║  ██║██║  ██║███████╗",
        "  ╚═╝╚═╝  ╚═══╝╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝",
    )
    for line in logo:
        print(paint("║", Color.RED) + paint(line.center(UI_INNER_WIDTH), Color.WHITE, bold=True) + paint("║", Color.RED))
    print(paint("╠" + "═" * (UI_WIDTH - 2) + "╣", Color.RED))
    print(paint("║", Color.RED) + paint("DATABASE MANAGEMENT TERMINAL".center(UI_INNER_WIDTH), Color.GRAY) + paint("║", Color.RED))
    print(paint("╚" + "═" * (UI_WIDTH - 2) + "╝", Color.RED))
    print(paint("  ⠿ SECURE LOCAL CORE  •  CRUD DATABASE  •  v1.0", Color.RED, bold=True))


def title(text: str) -> None:
    print("\n" + paint(f"┏━━ {text} " + "━" * max(0, UI_WIDTH - len(text) - 6) + "┓", Color.RED, bold=True))


def success(text: str) -> None:
    print(paint(f"  ✓ {text}", Color.WHITE))


def error(text: str) -> None:
    print(paint(f"  ✗ {text}", Color.RED))


def info(text: str) -> None:
    print(paint(f"  ⠿ {text}", Color.GRAY))
