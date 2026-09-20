#!/usr/bin/env python3
"""
Discord Rich Presence (RPC) Client
Ported from C Discord RPC SDK:
    DiscordRichPresence discordPresence;
    memset(&discordPresence, 0, sizeof(discordPresence));
    discordPresence.state = "Playing Solo";
    discordPresence.details = "Competitive";
    discordPresence.startTimestamp = 1507665886;
    discordPresence.endTimestamp = 1507665886;
    discordPresence.largeImageText = "Numbani";
    discordPresence.smallImageText = "Rogue - Level 100";
    discordPresence.partyId = "ae488379-351d-4a4f-ad32-2b9b01c91657";
    discordPresence.partySize = 1;
    discordPresence.partyMax = 5;
    discordPresence.joinSecret = "MTI4NzM0OjFpMmhuZToxMjMxMjM= ";
    Discord_UpdatePresence(&discordPresence);
"""

import os
import sys
import time
import json
import struct
import base64
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()


def get_default_client_id() -> Optional[str]:
    """Retrieve Client ID from DISCORD_CLIENT_ID or infer from DISCORD_TOKEN."""
    client_id = os.getenv("DISCORD_CLIENT_ID")
    if client_id:
        return client_id.strip()

    token = os.getenv("DISCORD_TOKEN")
    if token and "." in token:
        first_part = token.split(".")[0]
        # Pad base64 if necessary
        padded = first_part + "=" * ((4 - len(first_part) % 4) % 4)
        try:
            decoded = base64.b64decode(padded).decode("utf-8")
            if decoded.isdigit():
                return decoded
        except Exception:
            pass
    return None


class NativeDiscordIPC:
    """
    Lightweight zero-dependency Discord IPC implementation for Windows and Unix.
    Communicates directly with Discord desktop client over named pipe or domain socket.
    """

    OP_HANDSHAKE = 0
    OP_FRAME = 1
    OP_CLOSE = 2
    OP_PING = 3
    OP_PONG = 4

    def __init__(self, client_id: str):
        self.client_id = str(client_id)
        self.pipe = None
        self._connected = False

    def connect(self) -> bool:
        if sys.platform == "win32":
            for i in range(10):
                pipe_path = rf"\\.\pipe\discord-ipc-{i}"
                try:
                    self.pipe = open(pipe_path, "w+b", buffering=0)
                    self._connected = True
                    break
                except (OSError, FileNotFoundError):
                    continue
        else:
            import socket
            temp_dirs = [
                os.environ.get("XDG_RUNTIME_DIR", ""),
                os.environ.get("TMPDIR", ""),
                os.environ.get("TMP", ""),
                os.environ.get("TEMP", ""),
                "/tmp",
            ]
            for temp_dir in temp_dirs:
                if not temp_dir:
                    continue
                for i in range(10):
                    sock_path = os.path.join(temp_dir, f"discord-ipc-{i}")
                    if os.path.exists(sock_path):
                        try:
                            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                            s.connect(sock_path)
                            self.pipe = s
                            self._connected = True
                            break
                        except OSError:
                            continue
                if self._connected:
                    break

        if not self._connected:
            return False

        # Send Handshake
        handshake = {"v": 1, "client_id": self.client_id}
        self._send(self.OP_HANDSHAKE, handshake)
        opcode, response = self._recv()
        return opcode == self.OP_FRAME

    def _send(self, opcode: int, data: Dict[str, Any]):
        payload = json.dumps(data).encode("utf-8")
        header = struct.pack("<II", opcode, len(payload))
        if hasattr(self.pipe, "write"):
            self.pipe.write(header + payload)
            self.pipe.flush()
        else:
            self.pipe.sendall(header + payload)

    def _recv(self):
        if hasattr(self.pipe, "read"):
            header = self.pipe.read(8)
            if not header or len(header) < 8:
                return None, None
            opcode, length = struct.unpack("<II", header)
            payload = self.pipe.read(length)
        else:
            header = self.pipe.recv(8)
            if not header or len(header) < 8:
                return None, None
            opcode, length = struct.unpack("<II", header)
            payload = bytearray()
            while len(payload) < length:
                chunk = self.pipe.recv(min(length - len(payload), 4096))
                if not chunk:
                    break
                payload.extend(chunk)
        return opcode, json.loads(payload.decode("utf-8"))

    def set_activity(self, activity: Dict[str, Any]):
        data = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": activity,
            },
            "nonce": str(time.time()),
        }
        self._send(self.OP_FRAME, data)
        return self._recv()

    def close(self):
        if self.pipe:
            try:
                self.pipe.close()
            except Exception:
                pass
            self.pipe = None
            self._connected = False


def update_presence(
    client_id: Optional[str] = None,
    state: str = "Playing Solo",
    details: str = "Competitive",
    start_timestamp: Optional[int] = 1507665886,
    end_timestamp: Optional[int] = 1507665886,
    large_image_key: Optional[str] = None,
    large_image_text: str = "Numbani",
    small_image_key: Optional[str] = None,
    small_image_text: str = "Rogue - Level 100",
    party_id: str = "ae488379-351d-4a4f-ad32-2b9b01c91657",
    party_size: int = 1,
    party_max: int = 5,
    join_secret: str = "MTI4NzM0OjFpMmhuZToxMjMxMjM= ",
    keep_alive: bool = False,
):
    """
    Python equivalent of C Discord_UpdatePresence:
        DiscordRichPresence discordPresence;
        memset(&discordPresence, 0, sizeof(discordPresence));
        discordPresence.state = "Playing Solo";
        discordPresence.details = "Competitive";
        discordPresence.startTimestamp = 1507665886;
        discordPresence.endTimestamp = 1507665886;
        discordPresence.largeImageText = "Numbani";
        discordPresence.smallImageText = "Rogue - Level 100";
        discordPresence.partyId = "ae488379-351d-4a4f-ad32-2b9b01c91657";
        discordPresence.partySize = 1;
        discordPresence.partyMax = 5;
        discordPresence.joinSecret = "MTI4NzM0OjFpMmhuZToxMjMxMjM= ";
        Discord_UpdatePresence(&discordPresence);
    """
    resolved_client_id = client_id or get_default_client_id()
    if not resolved_client_id:
        print("❌ Error: No Discord Client ID found.")
        print("   Set DISCORD_CLIENT_ID in your .env file or pass client_id parameter.")
        return False

    # Try pypresence if available
    try:
        from pypresence import Presence

        rpc = Presence(resolved_client_id)
        rpc.connect()
        print(f"✅ Connected to Discord RPC via pypresence (Client ID: {resolved_client_id})")

        payload = {
            "state": state,
            "details": details,
            "party_id": party_id,
            "party_size": [party_size, party_max],
        }
        if start_timestamp:
            payload["start"] = start_timestamp
        if end_timestamp:
            payload["end"] = end_timestamp
        if large_image_key:
            payload["large_image"] = large_image_key
        if large_image_text:
            payload["large_text"] = large_image_text
        if small_image_key:
            payload["small_image"] = small_image_key
        if small_image_text:
            payload["small_text"] = small_image_text
        if join_secret:
            payload["join"] = join_secret.strip()

        rpc.update(**payload)
        print("🎮 Presence updated successfully!")

        if keep_alive:
            print("⏳ Running presence loop. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(15)
            except KeyboardInterrupt:
                print("\n🛑 Stopping presence...")
                rpc.clear()
                rpc.close()
        return True

    except ImportError:
        # Fallback to zero-dependency native IPC
        print("ℹ️ pypresence not installed, using native Discord IPC...")
        ipc = NativeDiscordIPC(resolved_client_id)
        if not ipc.connect():
            print("❌ Failed to connect to Discord desktop client.")
            print("   Make sure the Discord desktop app is running on your machine.")
            return False

        print(f"✅ Connected to Discord RPC via native IPC (Client ID: {resolved_client_id})")

        activity = {
            "state": state,
            "details": details,
            "party": {
                "id": party_id,
                "size": [party_size, party_max],
            },
            "secrets": {
                "join": join_secret.strip(),
            },
        }

        timestamps = {}
        if start_timestamp:
            timestamps["start"] = start_timestamp
        if end_timestamp:
            timestamps["end"] = end_timestamp
        if timestamps:
            activity["timestamps"] = timestamps

        assets = {}
        if large_image_key:
            assets["large_image"] = large_image_key
        if large_image_text:
            assets["large_text"] = large_image_text
        if small_image_key:
            assets["small_image"] = small_image_key
        if small_image_text:
            assets["small_text"] = small_image_text
        if assets:
            activity["assets"] = assets

        ipc.set_activity(activity)
        print("🎮 Presence updated successfully via native IPC!")

        if keep_alive:
            print("⏳ Running presence loop. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(15)
            except KeyboardInterrupt:
                print("\n🛑 Stopping presence...")
                ipc.close()
        return True
    except Exception as e:
        print(f"❌ Error updating presence: {e}")
        return False


if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else None
    update_presence(client_id=cid, keep_alive=True)
