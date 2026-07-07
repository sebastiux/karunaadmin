/**
 * Karuna Admin — realtime gateway.
 *
 * A deliberately small Node/TypeScript service. It relays "board changed"
 * messages between developers viewing the same Kanban board so their boards
 * refresh live. It holds no state and does no auth beyond room routing — the
 * FastAPI backend remains the source of truth. The frontend connects only when
 * VITE_REALTIME_URL is configured, so the platform works fine without it.
 *
 * Protocol:
 *   Connect:   ws://host/?room=project-<id>
 *   Message:   { "type": "board:changed", "room": "project-<id>" }
 *   Broadcast: the same message is forwarded to every *other* socket in the room.
 */
import { createServer } from "node:http";
import { WebSocketServer, WebSocket } from "ws";
import { URL } from "node:url";

const PORT = Number(process.env.PORT) || 8090;

interface RoomSocket extends WebSocket {
  room?: string;
  isAlive?: boolean;
}

const server = createServer((req, res) => {
  if (req.url?.startsWith("/health")) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", rooms: rooms.size }));
    return;
  }
  res.writeHead(200, { "Content-Type": "text/plain" });
  res.end("karuna-realtime gateway");
});

const wss = new WebSocketServer({ server });
const rooms = new Map<string, Set<RoomSocket>>();

function join(room: string, ws: RoomSocket) {
  if (!rooms.has(room)) rooms.set(room, new Set());
  rooms.get(room)!.add(ws);
  ws.room = room;
}

function leave(ws: RoomSocket) {
  if (!ws.room) return;
  const set = rooms.get(ws.room);
  if (set) {
    set.delete(ws);
    if (set.size === 0) rooms.delete(ws.room);
  }
}

wss.on("connection", (ws: RoomSocket, req) => {
  const url = new URL(req.url ?? "/", `http://${req.headers.host}`);
  const room = url.searchParams.get("room") ?? "default";
  join(room, ws);
  ws.isAlive = true;

  ws.on("pong", () => (ws.isAlive = true));

  ws.on("message", (data) => {
    let msg: { type?: string; room?: string };
    try {
      msg = JSON.parse(data.toString());
    } catch {
      return;
    }
    const target = msg.room ?? ws.room ?? room;
    const peers = rooms.get(target);
    if (!peers) return;
    const payload = JSON.stringify(msg);
    for (const peer of peers) {
      if (peer !== ws && peer.readyState === WebSocket.OPEN) {
        peer.send(payload);
      }
    }
  });

  ws.on("close", () => leave(ws));
  ws.on("error", () => leave(ws));
});

// Heartbeat: drop dead connections so rooms don't leak.
const heartbeat = setInterval(() => {
  for (const ws of wss.clients as Set<RoomSocket>) {
    if (ws.isAlive === false) {
      leave(ws);
      ws.terminate();
      continue;
    }
    ws.isAlive = false;
    ws.ping();
  }
}, 30000);

wss.on("close", () => clearInterval(heartbeat));

server.listen(PORT, () => {
  console.log(`karuna-realtime gateway listening on :${PORT}`);
});
