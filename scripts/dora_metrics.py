"""Скрипт збору та розрахунку метрик DORA на основі запусків GitHub Actions.

Бонусне завдання до Лабораторної роботи №10.
Скрипт збирає дані про запуски робочого процесу CI Pipeline (ci.yml)
через GitHub CLI (`gh api`), розраховує час у черзі, тривалість виконання,
час першого коміту в PR і чотири ключові метрики DORA (2025).
"""

import argparse
import sys
from datetime import timedelta, timezone, tzinfo
from typing import List, Optional


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Розбір аргументів командного рядка."""
    parser = argparse.ArgumentParser(
        description="Розрахунок метрик DORA на основі історії запусків GitHub Actions (CI Pipeline)."
    )
    parser.add_argument(
        "--since",
        required=True,
        help="Початкова дата аналізу у форматі YYYY-MM-DD (включно).",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="Кінцева дата аналізу у форматі YYYY-MM-DD (опціонально).",
    )
    parser.add_argument(
        "--out",
        default="docs/ci-cd/dora-auto.md",
        help="Шлях для збереження Markdown-звіту (за замовчуванням docs/ci-cd/dora-auto.md).",
    )
    parser.add_argument(
        "--export-json",
        default=None,
        help="Шлях для експорту зібраних знеособлених даних у форматі JSON.",
    )
    parser.add_argument(
        "--utc-offset-hours",
        type=float,
        default=2.0,
        help="Зміщення часового поясу в годинах від UTC (за замовчуванням 2.0 для Києва UTC+2).",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Репозиторій у форматі owner/repo (якщо не вказано, визначається автоматично).",
    )
    return parser.parse_args(args)


def get_tz(offset_hours: float) -> tzinfo:
    """Повертає часовий пояс із заданим зміщенням у годинах від UTC."""
    return timezone(timedelta(hours=offset_hours))


def format_tz_label(offset_hours: float) -> str:
    """Форматує підпис часового поясу для звітів."""
    sign = "+" if offset_hours >= 0 else "-"
    val = abs(offset_hours)
    if val.is_integer():
        return f"UTC{sign}{int(val)}"
    return f"UTC{sign}{val:.1f}"


def main(argv: Optional[List[str]] = None) -> int:
    """Точка входу CLI."""
    args = parse_args(argv)
    tz_label = format_tz_label(args.utc_offset_hours)
    print(f"DORA metrics: since={args.since}, until={args.until}, tz={tz_label}, out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
