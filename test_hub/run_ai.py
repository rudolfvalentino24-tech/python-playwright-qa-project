import os

import app as hub
from ai_designer import register_ai_designer
from bdd_sync import register_bdd_sync


register_ai_designer(hub)
register_bdd_sync(hub)


if __name__ == "__main__":
    hub.app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "3000")),
        debug=True,
    )
