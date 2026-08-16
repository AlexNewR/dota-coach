from __future__ import annotations

import json
from pathlib import Path

text = Path(r"C:\Users\alwexn\Desktop\dota train\data\raw\io_data.json").read_text(encoding="utf-8")
data = json.loads(text)
node = data["nodes"][2]["data"]
print("node2 data type", type(node), "len", len(node) if isinstance(node, list) else None)
print("data[0] keys sample", list(node[0])[:30] if isinstance(node[0], dict) else node[0])
print("avg_gpm slot", node[97] if len(node)>97 else None)
print("value 98", node[98] if len(node)>98 else None)
print("value 99", node[99] if len(node)>99 else None)
print("value 105", node[105] if len(node)>105 else None)

# find item_stats key
for i, item in enumerate(node):
    if isinstance(item, dict) and "item_stats" in item:
        print("item_stats at", i, "ptr", item["item_stats"], "keys", list(item.keys())[:25])
        ptr = item["item_stats"]
        if isinstance(ptr, int) and ptr < len(node):
            stats = node[ptr]
            print("stats type", type(stats), "len", len(stats) if isinstance(stats, (list, dict)) else stats)
            if isinstance(stats, dict):
                print("stats keys", list(stats.keys())[:15])
            if isinstance(stats, list):
                print("stats[0]", stats[0] if stats else None)
        break
