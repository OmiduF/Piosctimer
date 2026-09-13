import { useEffect, useRef, useState } from "react";

// The backend serves this build, so the WebSocket lives on the SAME origin as
// the page. Deriving the URL from window.location makes the display work no
// matter which machine opens it (Pi kiosk on localhost, or a remote browser
// via the Pi's LAN IP) and behind the preview ingress (which routes /api).
function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/ws`;
}

// Connects to the backend WebSocket and keeps the latest state.
// Auto-reconnects with a short backoff so the Pi display self-heals.
export function useTimerSocket() {
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  useEffect(() => {
    let closed = false;

    const connect = () => {
      if (closed) return;
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data && data.type === "state") setState(data);
        } catch (e) {
          /* ignore malformed frame */
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closed) {
          reconnectRef.current = setTimeout(connect, 1500);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return { state, connected };
}
