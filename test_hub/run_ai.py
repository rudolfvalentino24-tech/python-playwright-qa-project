import os
from functools import lru_cache

import app as hub
import bdd_sync
from ai_designer import register_ai_designer


bdd_sync._scan_step_definitions = lru_cache(maxsize=1)(bdd_sync._scan_step_definitions)

register_ai_designer(hub)
bdd_sync.register_bdd_sync(hub)


if __name__ == "__main__":
    hub.app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "3000")),
        debug=True,
    )
