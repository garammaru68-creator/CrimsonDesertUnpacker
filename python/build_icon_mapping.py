"""Build icon mapping table: node/resource types -> sprite atlas coordinates."""

import re
import os
import csv

UI_DIR = "C:/Users/denni/AppData/Local/Temp/cd_ui2/ui"
OUT_PATH = "D:/Dev/crimson-desert-unpacker/icon_mapping.csv"


def parse_icon_xmls(ui_dir):
    icons = {}
    for f in sorted(os.listdir(ui_dir)):
        if not f.startswith("cd_icon_map_0") or not f.endswith(".xml"):
            continue
        with open(os.path.join(ui_dir, f), "rb") as fp:
            content = fp.read().decode("utf-8", errors="replace")
        for m in re.finditer(
            r'Name="([^"]+)".*?Filename="([^"]+)".*?GetRect="([^"]+)"', content
        ):
            name, filename, rect = m.groups()
            icons[name] = {"filename": filename, "rect": rect, "source": f}
    return icons


NODE_TYPE_TO_ICON = {
    "village": "cd_Icon_map_capital_symbol",
    "castle": "cd_Icon_map_dominion_symbol",
    "gate": "cd_Icon_map_GimmickFlag",
    "fort": "cd_Icon_map_GimmickFlag_fusion",
    "tower": "cd_Icon_map_GimmickFlag",
    "beacon": "cd_Icon_map_GimmickFlag",
    "outpost": "cd_Icon_map_GimmickFlag",
    "stronghold": "cd_Icon_map_GimmickFlag_fusion",
    "camp": "cd_Icon_map_campfire_00",
    "rest_area": "cd_Icon_map_campfire_00",
    "shrine": "cd_Icon_map_church",
    "trade": "cd_icon_item_trade",
    "market": "cd_icon_item_trade",
    "guild": "cd_icon_item_trade",
    "harbor": "cd_Icon_map_gimmick_ship_boat_00",
    "cave": "cd_icon_map_enemy",
    "ruins": "cd_icon_map_enemy_die",
    "monster_lair": "cd_icon_map_enemy_elite",
    "dungeon": "cd_icon_map_enemy_elite",
    "mine": "cd_Icon_map_minegold_00",
    "ore_vein": "cd_Icon_map_minegold_00",
    "farm": "cd_icon_map_npc",
    "ranch": "cd_icon_map_npc",
    "workshop": "cd_icon_map_npc",
    "manor": "cd_Icon_map_capital_symbol",
    "abyss_node": "cd_Icon_map_abyssgate",
    "abyss_poi": "cd_Icon_map_abyssgate",
    "landmark": "cd_icon_map_npc_target",
    "tomb": "cd_icon_map_enemy_die",
    "bridge": "cd_Icon_map_GimmickFlag",
    "station": "cd_Icon_map_GimmickFlag",
    "military": "cd_Icon_map_cannon",
    "forest": "cd_icon_map_npc",
    "water": "cd_icon_map_fish",
    "shipwreck": "cd_icon_map_enemy_die",
    "laboratory": "cd_icon_map_npc",
    "storage": "cd_icon_map_npc",
    "watch_post": "cd_Icon_map_GimmickFlag",
    "oasis": "cd_icon_map_npc",
    "totem": "cd_icon_map_npc_target",
    "hut": "cd_icon_map_npc",
    "inn": "cd_Icon_map_inn",
    "shop": "cd_Icon_map_generalshop",
    "sawmill": "cd_icon_map_npc",
    "arena": "cd_icon_map_boss",
    "research": "cd_icon_map_npc",
    "secret": "cd_icon_map_npc_target",
    "house": "cd_icon_map_npc",
    "poi": "cd_icon_map_npc_target",
}

RESOURCE_TYPE_TO_ICON = {
    "gold": "cd_Icon_map_gimmick_minegold_00",
    "iron": "cd_Icon_map_gimmick_IronStone_00",
    "silver": "cd_Icon_map_gimmick_minesilver_00",
    "copper": "cd_Icon_map_gimmick_CopperOre_00",
    "diamond": "cd_Icon_map_gimmick_diamond_00",
    "ruby": "cd_Icon_map_gimmick_Ruby_00",
    "bismuth": "cd_Icon_map_gimmick_BismuthOre_00",
    "bluestone": "cd_Icon_map_gimmick_BlueStone_00",
    "redstone": "cd_Icon_map_gimmick_redstone_00",
    "whitestone": "cd_Icon_map_gimmick_WhiteStone_00",
    "greenstone": "cd_Icon_map_gimmick_GreenStone_00",
    "stone": "cd_Icon_map_gimmick_stonegate_00",
    "sulfur": "cd_Icon_map_gimmick_SulfurStone_00",
    "mercury": "cd_Icon_map_gimmick_Mercury_00",
    "coal": "cd_Icon_map_gimmick_IronStone_00",
    "tin": "cd_Icon_map_gimmick_CopperOre_00",
    "salt": "cd_Icon_map_gimmick_WhiteStone_00",
    "shiitake": "cd_Icon_map_gimmick_chaya_00",
    "matsutake": "cd_Icon_map_gimmick_chaya_00",
    "hericium": "cd_Icon_map_gimmick_chaya_00",
    "apple": "cd_Icon_map_gimmick_opuntia_00",
    "peach": "cd_Icon_map_gimmick_opuntia_00",
    "orange": "cd_Icon_map_gimmick_opuntia_00",
    "opuntia": "cd_Icon_map_gimmick_opuntia_00",
    "grape": "cd_Icon_map_gimmick_opuntia_00",
    "spiderweb": "cd_Icon_map_gimmick_abyss_mark_part_00",
    "bank": "cd_icon_map_bank",
    "blacksmith": "cd_icon_map_blacksmith",
    "generalshop": "cd_Icon_map_generalshop",
    "groceryshop": "cd_icon_map_groceryshop",
    "inn": "cd_Icon_map_inn",
    "stable": "cd_icon_map_stable",
    "church": "cd_Icon_map_church",
    "fish_spot": "cd_icon_map_fish",
}


def main():
    icons = parse_icon_xmls(UI_DIR)
    print("Total icons in atlas: %d" % len(icons))

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["map_type", "icon_name", "dds_file", "rect_x", "rect_y", "rect_w", "rect_h", "exists"])

        valid = 0
        missing = []

        for ntype, icon in sorted(NODE_TYPE_TO_ICON.items()):
            if icon in icons:
                ic = icons[icon]
                rx, ry, rw, rh = ic["rect"].split(",")
                writer.writerow(["node:%s" % ntype, icon, ic["filename"], rx, ry, rw, rh, "yes"])
                valid += 1
            else:
                writer.writerow(["node:%s" % ntype, icon, "", "", "", "", "", "no"])
                missing.append(("node:%s" % ntype, icon))

        for rtype, icon in sorted(RESOURCE_TYPE_TO_ICON.items()):
            if icon in icons:
                ic = icons[icon]
                rx, ry, rw, rh = ic["rect"].split(",")
                writer.writerow(["resource:%s" % rtype, icon, ic["filename"], rx, ry, rw, rh, "yes"])
                valid += 1
            else:
                writer.writerow(["resource:%s" % rtype, icon, "", "", "", "", "", "no"])
                missing.append(("resource:%s" % rtype, icon))

    total = len(NODE_TYPE_TO_ICON) + len(RESOURCE_TYPE_TO_ICON)
    print("Valid: %d / %d" % (valid, total))

    if missing:
        print("\nMissing icons:")
        for key, icon in missing:
            print("  %s -> %s" % (key, icon))

    print("\nSaved to: %s" % OUT_PATH)


if __name__ == "__main__":
    main()
