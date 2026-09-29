import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.pokemeow_reader import parse_pokemeow_response, record_pokemeow_event, get_session_complications_summary


class DummyEmbed:
    def __init__(self, description="", title="", footer=""):
        self.description = description
        self.title = title

        class Footer:
            def __init__(self, text):
                self.text = text

        self.footer = Footer(footer)
        self.fields = []
        self.author = None


class DummyMessage:
    def __init__(self, content="", description="", footer=""):
        self.content = content
        self.embeds = [DummyEmbed(description=description, footer=footer)] if description or footer else []


def test_reader():
    # 1. Flee test
    m_flee = DummyMessage(description="The wild **Pikachu** ran away!")
    res_flee = parse_pokemeow_response(m_flee, context_module="hunting", ball_used="pb")
    assert res_flee["category"] == "hunt_flee", f"Expected hunt_flee, got {res_flee}"
    assert res_flee["is_complication"] is True
    assert res_flee["details"]["pokemon_name"] == "Pikachu"
    assert res_flee["details"]["ball_used"] == "pb"

    # 2. Ball starvation test
    m_balls = DummyMessage(content="You don't have enough Pokeballs to catch this Pokemon!")
    res_balls = parse_pokemeow_response(m_balls, context_module="hunting")
    assert res_balls["category"] == "ball_starvation", f"Expected ball_starvation, got {res_balls}"
    assert res_balls["is_complication"] is True

    # 3. Coin starvation test
    m_coins = DummyMessage(content="You don't have enough Pokécoins to purchase this item!")
    res_coins = parse_pokemeow_response(m_coins, context_module="shop")
    assert res_coins["category"] == "coin_starvation", f"Expected coin_starvation, got {res_coins}"
    assert res_coins["is_complication"] is True

    # 4. Quest ready test
    m_quest = DummyMessage(content="Your next Quest is now ready!")
    res_quest = parse_pokemeow_response(m_quest)
    assert res_quest["category"] == "quest_ready"

    # 5. Egg test
    m_egg = DummyMessage(content="Oh? The egg hatched into a Pichu!")
    res_egg = parse_pokemeow_response(m_egg)
    assert res_egg["category"] == "egg_event"

    # 6. Cooldown test
    m_cd = DummyMessage(content="Please wait 3.5 seconds before using this command again!")
    res_cd = parse_pokemeow_response(m_cd)
    assert res_cd["category"] == "cooldown_block"
    assert res_cd["details"]["wait_seconds"] == 3.5

    # 7. Fish flee test
    m_fish_flee = DummyMessage(description="The wild **Gyarados** got away!")
    res_fish_flee = parse_pokemeow_response(m_fish_flee, context_module="fishing", ball_used="ub")
    assert res_fish_flee["category"] == "fish_flee"
    assert res_fish_flee["details"]["ball_used"] == "ub"

    # 8. Active encounter pending test
    m_pending = DummyMessage(content="Please catch the Pokemon you spawned first!")
    res_pending = parse_pokemeow_response(m_pending, context_module="fishing")
    assert res_pending["category"] == "active_encounter_pending"
    assert res_pending["is_complication"] is True

    # 9. Casket minigame timeout test
    m_casket = DummyMessage(content="The casket sank away schrazen did not choose what to do with Sunken Casket in time.")
    res_casket = parse_pokemeow_response(m_casket, context_module="fishing")
    assert res_casket["category"] == "casket_timeout"
    assert res_casket["is_complication"] is True

    # 10. Shop invalid item test
    m_shop_err = DummyMessage(content="That item is not in the shop!")
    res_shop_err = parse_pokemeow_response(m_shop_err, context_module="shop")
    assert res_shop_err["category"] == "shop_invalid_item"
    assert res_shop_err["is_complication"] is True

    # 11. Empty message discard test
    m_empty = DummyMessage(content="")
    res_empty = parse_pokemeow_response(m_empty)
    assert res_empty is None

    # 12. CatchBot status test
    m_cb = DummyMessage(content="🤖 schrazen has spent 9,208,500 PokeCoins on total upgrades To run your CatchBot for its maximum yield: ;catchbot run Lifetime caught by CB: 9,320")
    res_cb = parse_pokemeow_response(m_cb, context_module="hunting")
    assert res_cb["category"] == "catchbot_status"
    assert res_cb["is_complication"] is False

    # 13. Event ticket status test
    m_event = DummyMessage(content="Flower-Crown Eeveelutions, Minior Forms, Gouging-Fire! Your Event Ticket is ACTIVE! Good luck on the event!")
    res_event = parse_pokemeow_response(m_event, context_module="hunting")
    assert res_event["category"] == "event_status"
    assert res_event["is_complication"] is False

    # 14. Wild spawn name extraction test (unbolded)
    m_spawn = DummyMessage(content="schrazen found a wild Marill! A wild Pokémon appeared! Uncommon (30% encounter rate)")
    res_spawn = parse_pokemeow_response(m_spawn, context_module="hunting")
    assert res_spawn["category"] == "hunt_encounter"
    assert res_spawn["details"]["pokemon_name"] == "Marill"
    assert res_spawn["details"]["rarity"] == "Uncommon"

    # 15. Safe rod test (normal fish catch containing fish with rod-like chars must not trigger missing rod)
    m_fish_catch = DummyMessage(content="Yashi found a wild Wooper! Yashi fished a wild Wooper! Pokeballs: 142")
    res_fish = parse_pokemeow_response(m_fish_catch, context_module="fishing")
    assert res_fish["category"] != "missing_rod"

    print("All 15 PokéMeow reader verification tests passed successfully!")


if __name__ == "__main__":
    test_reader()

