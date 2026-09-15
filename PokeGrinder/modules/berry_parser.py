import re
from dataclasses import dataclass, field


@dataclass
class BerrySlot:
    slot_number: int
    berry_name: str
    stage_name: str  # "Planted", "Sprouted", "Taller", "Blooming", "Berry"
    stage_current: int  # 0-4 representing the stage number
    stage_max: int  # Usually 4
    needs_water: bool
    moisture: int = 100  # 0-100% moisture level
    hours_until_next_stage: int | None = None
    is_ripe: bool = False  # True if at "Berry" stage ready to harvest
    is_wilting: bool = False  # True if overgrown/wilting
    watering_history: dict[int, bool] = field(default_factory=dict)  # Track which stages watered


def parse_berry_garden(message_text: str) -> list[BerrySlot] | None:
    """
    Parse the ;berry garden overview message to extract slot info.
    Detects all 5 growth stages and moisture status.
    
    Looks for patterns like:
      Slot 1 — 🍓 Strawberry • Next stage in 4 hours
      Planted [STAGE 0/4] • 💧 Healthy
      Blooming [STAGE 3/4] • Needs watering
      Berry (Ready!) • Harvest ready
      
    Growth stages:
      0: Planted (🌱)
      1: Sprouted
      2: Taller (🌿)
      3: Blooming (🌸)
      4: Berry (🍇)
      
    Returns a list of BerrySlot objects or None if parsing fails.
    """
    if not message_text or "slot" not in message_text.lower():
        return None

    slots: list[BerrySlot] = []
    lines = message_text.split("\n")

    current_slot_num = 0
    current_berry = ""
    current_stage = 0
    current_stage_name = ""
    current_max_stage = 4
    current_needs_water = False
    current_moisture = 100
    current_is_ripe = False
    current_is_wilting = False
    hours_until_next = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Look for "Slot X" lines
        slot_match = re.search(r"[Ss]lot\s+(\d+)", line)
        if slot_match:
            # Save previous slot if exists
            if current_slot_num > 0:
                slot = BerrySlot(
                    slot_number=current_slot_num,
                    berry_name=current_berry,
                    stage_name=current_stage_name,
                    stage_current=current_stage,
                    stage_max=current_max_stage,
                    needs_water=current_needs_water,
                    moisture=current_moisture,
                    hours_until_next_stage=hours_until_next,
                    is_ripe=current_is_ripe,
                    is_wilting=current_is_wilting,
                )
                slots.append(slot)
            
            # Reset for new slot
            current_slot_num = int(slot_match.group(1))
            current_stage = 0
            current_stage_name = ""
            current_needs_water = False
            current_moisture = 100
            current_is_ripe = False
            current_is_wilting = False
            hours_until_next = None

            # Extract berry/slot descriptor text after dash.
            # Some locked slots have no bullet separator, so prefer the full suffix.
            dash_split = re.split(r"\s+[—-]\s+", line, maxsplit=1)
            descriptor = dash_split[1].strip() if len(dash_split) > 1 else ""
            if descriptor:
                current_berry = descriptor
            else:
                berry_match = re.search(r"—\s+(.+?)\s+(?:•|$)", line)
                if berry_match:
                    current_berry = berry_match.group(1).strip()
                else:
                    current_berry = "Unknown"

            # Explicitly mark locked slots so downstream logic can filter them out.
            lowered_line = line.lower()
            if "slot locked" in lowered_line or "requires" in lowered_line or ":lock:" in lowered_line:
                current_stage_name = "Locked"
                current_stage = 0
                current_needs_water = False
                current_moisture = 100
                current_is_ripe = False
                current_is_wilting = False

            # Extract hours until next stage
            hours_match = re.search(r"Next stage in (\d+)\s+hours?", line)
            if hours_match:
                hours_until_next = int(hours_match.group(1))
        
        # Look for growth stage lines
        elif any(keyword in line.lower() for keyword in ["planted", "sprouted", "taller", "blooming", "berry", "wilting"]):
            # Detect stage name and stage number
            line_lower = line.lower()
            
            if "planted" in line_lower:
                current_stage_name = "Planted"
                current_stage = 0
            elif "sprouted" in line_lower:
                current_stage_name = "Sprouted"
                current_stage = 1
            elif "taller" in line_lower:
                current_stage_name = "Taller"
                current_stage = 2
            elif "blooming" in line_lower:
                current_stage_name = "Blooming"
                current_stage = 3
            elif "berry" in line_lower or "ready" in line_lower:
                current_stage_name = "Berry"
                current_stage = 4
                current_is_ripe = True
            elif "wilting" in line_lower:
                current_stage_name = "Wilting"
                current_is_wilting = True

            # Parse stage number if present
            stage_match = re.search(r"\[?[Ss][Tt][Aa][Gg][Ee]?\s*(\d+)/(\d+)\]?", line)
            if not stage_match:
                stage_match = re.search(r"\((\d+)/(\d+)\)", line)
            
            if stage_match:
                current_stage = int(stage_match.group(1))
                current_max_stage = int(stage_match.group(2))

            # Check moisture status
            if "needs watering" in line_lower:
                current_needs_water = True
                current_moisture = 0  # Dry
            elif "healthy" in line_lower:
                current_needs_water = False
                current_moisture = 100  # Full
            elif "drying" in line_lower:
                current_needs_water = False
                current_moisture = 50  # Medium

    # Save final slot
    if current_slot_num > 0:
        slot = BerrySlot(
            slot_number=current_slot_num,
            berry_name=current_berry,
            stage_name=current_stage_name,
            stage_current=current_stage,
            stage_max=current_max_stage,
            needs_water=current_needs_water,
            moisture=current_moisture,
            hours_until_next_stage=hours_until_next,
            is_ripe=current_is_ripe,
            is_wilting=current_is_wilting,
        )
        slots.append(slot)

    return slots if slots else None
