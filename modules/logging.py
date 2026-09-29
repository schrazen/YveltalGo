import os
import sys
from typing import List
from rich.table import Table
from datetime import datetime
from rich.console import Console
from discord.ext.commands import Bot

# Electron / piped stdio is not a TTY; forcing terminal features raises OSError(22) on Windows.
console = Console(force_terminal=sys.stdout.isatty())

HUNT_RARITY_ORDER = [
    "Common",
    "Uncommon",
    "Rare",
    "Super Rare",
    "Legendary",
    "Shiny",
    "Shiny Event",
    "Shiny Full-odds",
    "Unknown",
]

HUNT_SHORT = {
    "Common": "C",
    "Uncommon": "U",
    "Rare": "R",
    "Super Rare": "SR",
    "Legendary": "L",
    "Shiny": "S",
    "Shiny Event": "SE",
    "Shiny Full-odds": "SFO",
    "Unknown": "?",
}

FISH_RARITY_ORDER = [
    "Common",
    "Uncommon",
    "Rare",
    "Super Rare",
    "Legendary",
    "Shiny",
    "Golden",
    "Unknown",
]

FISH_SHORT = {
    "Common": "C",
    "Uncommon": "U",
    "Rare": "R",
    "Super Rare": "SR",
    "Legendary": "L",
    "Shiny": "S",
    "Golden": "G",
    "Unknown": "?",
}


def format_rarity_counts(counts: dict, order: list, short_names: dict) -> str:
    return " ".join([f"{short_names[name]}:{int(counts.get(name, 0))}" for name in order])


def aggregate_rarity_counts(bots: List[Bot], attribute_name: str, order: list) -> dict:
    totals = {name: 0 for name in order}

    for bot in bots:
        if not bot.is_ready():
            continue

        counts = getattr(bot, attribute_name, {}) or {}
        for name in order:
            totals[name] += int(counts.get(name, 0))

    return totals


def logger(bots: List[Bot], start_time: datetime, clear_console: bool) -> None:
    elapsed_time = datetime.now() - start_time
    hours = elapsed_time.seconds // 3600
    minutes = (elapsed_time.seconds % 3600) // 60
    seconds = elapsed_time.seconds % 60

    table = Table(
        show_header=True,
        title=f"PokeGrinder ETA {hours} hours {minutes} minutes {seconds} seconds",
        header_style="bold green",
        title_style="bold red"
    )

    [
        table.add_column(
            name,
            style="bold blue"
        ) for name in [
            "Username",
            "Session E/C/FE/FC/$",
            "Lifetime E/C/FE/FC/$",
            "Hunt Rarity S/L",
            "Fish Rarity S/L",
            "Hunting Status",
            "Fishing Status",
            "AutoFight Status",
            "AF Guard"
        ]
    ]

    total_encounters, total_catches, total_fish_encounters, total_fish_catches, total_coins_earned = 0, 0, 0, 0, 0
    total_lifetime_encounters, total_lifetime_catches = 0, 0
    total_lifetime_fish_encounters, total_lifetime_fish_catches, total_lifetime_coins_earned = 0, 0, 0

    for bot in bots:
        if not bot.is_ready():
            continue

        table.add_row(
            str(bot.user.name),
            f"{bot.encounters}/{bot.catches}/{bot.fish_encounters}/{bot.fish_catches}/${bot.coins_earned}",
            f"{bot.lifetime_encounters}/{bot.lifetime_catches}/{bot.lifetime_fish_encounters}/{bot.lifetime_fish_catches}/${bot.lifetime_coins_earned}",
            (
                f"S[{format_rarity_counts(getattr(bot, 'hunt_rarity_catches', {}), HUNT_RARITY_ORDER, HUNT_SHORT)}] "
                f"L[{format_rarity_counts(getattr(bot, 'lifetime_hunt_rarity_catches', {}), HUNT_RARITY_ORDER, HUNT_SHORT)}]"
            ),
            (
                f"S[{format_rarity_counts(getattr(bot, 'fish_rarity_catches', {}), FISH_RARITY_ORDER, FISH_SHORT)}] "
                f"L[{format_rarity_counts(getattr(bot, 'lifetime_fish_rarity_catches', {}), FISH_RARITY_ORDER, FISH_SHORT)}]"
            ),
            str(bot.hunting_status),
            str(bot.fishing_status),
            str(getattr(bot, "autofight_status", "Disabled")),
            str(getattr(bot, "autofight_guard_status", "")),
        )

        total_encounters += bot.encounters
        total_catches += bot.catches
        total_fish_encounters += bot.fish_encounters
        total_fish_catches += bot.fish_catches
        total_coins_earned += bot.coins_earned
        total_lifetime_encounters += bot.lifetime_encounters
        total_lifetime_catches += bot.lifetime_catches
        total_lifetime_fish_encounters += bot.lifetime_fish_encounters
        total_lifetime_fish_catches += bot.lifetime_fish_catches
        total_lifetime_coins_earned += bot.lifetime_coins_earned

    table.add_section()

    total_hunt_rarity = aggregate_rarity_counts(
        bots,
        "hunt_rarity_catches",
        HUNT_RARITY_ORDER,
    )
    total_lifetime_hunt_rarity = aggregate_rarity_counts(
        bots,
        "lifetime_hunt_rarity_catches",
        HUNT_RARITY_ORDER,
    )
    total_fish_rarity = aggregate_rarity_counts(
        bots,
        "fish_rarity_catches",
        FISH_RARITY_ORDER,
    )
    total_lifetime_fish_rarity = aggregate_rarity_counts(
        bots,
        "lifetime_fish_rarity_catches",
        FISH_RARITY_ORDER,
    )

    table.add_row(
        "Total",
        f"{total_encounters}/{total_catches}/{total_fish_encounters}/{total_fish_catches}/${total_coins_earned}",
        f"{total_lifetime_encounters}/{total_lifetime_catches}/{total_lifetime_fish_encounters}/{total_lifetime_fish_catches}/${total_lifetime_coins_earned}",
        (
            f"S[{format_rarity_counts(total_hunt_rarity, HUNT_RARITY_ORDER, HUNT_SHORT)}] "
            f"L[{format_rarity_counts(total_lifetime_hunt_rarity, HUNT_RARITY_ORDER, HUNT_SHORT)}]"
        ),
        (
            f"S[{format_rarity_counts(total_fish_rarity, FISH_RARITY_ORDER, FISH_SHORT)}] "
            f"L[{format_rarity_counts(total_lifetime_fish_rarity, FISH_RARITY_ORDER, FISH_SHORT)}]"
        ),
        "-",
        "-",
        "-",
        "-",
        style="bold red"
    )

    if clear_console and sys.stdout.isatty():
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except OSError:
            pass

    console.print(r"""__________       __            ________      .__            .___            
\______   \____ |  | __ ____  /  _____/______|__| ____    __| _/___________ 
 |     ___/  _ \|  |/ // __ \/   \  __\_  __ \  |/    \  / __ |/ __ \_  __ \
 |    |  (  <_> )    <\  ___/\    \_\  \  | \/  |   |  \/ /_/ \  ___/|  | \/
 |____|   \____/|__|_ \\___  >\______  /__|  |__|___|  /\____ |\___  >__|   
                     \/    \/        \/              \/      \/    \/       """, style='bold blue')
    console.print(table)
