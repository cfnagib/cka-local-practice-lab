# Local CKA Dashboard

This is a local-only dashboard prototype. It displays a question, a live SSH PTY, and a timer. The VM reset and validation CLI scripts remain the source of truth while the UI is being expanded.

Start it from the project root:

```bash
python3 dashboard/server.py
```

Open http://127.0.0.1:8790. The dashboard uses WebSocket port 8791 for the terminal. Keep the terminal used to start the server open.

For daily use, install the desktop launcher and open **CKA Local Practice** from the application menu. It starts the local server in the background and opens the dashboard automatically.
