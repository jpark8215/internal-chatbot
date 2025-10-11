import threading
import time
import webbrowser

import uvicorn


def open_browser_when_ready(url: str, delay: float = 1.0) -> None:
    # Simple delay to allow the server to start before opening the browser.
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        # Non-fatal if browser cannot be opened automatically.
        pass


def run() -> None:
    url = "http://127.0.0.1:8000/"
    t = threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True)
    t.start()

    # Run the uvicorn server for the FastAPI app in app.py
    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload=False, workers=1)


if __name__ == "__main__":
    run()
