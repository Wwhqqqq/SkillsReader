"""Ruliu callback signature verification and optional AES decrypt."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import struct
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)


def verify_signature(
    token: str,
    timestamp: str,
    rn: str,
    encrypt: str,
    signature: str,
) -> bool:
    if not token or not signature:
        return False
    parts = sorted([token, timestamp, rn, encrypt])
    digest = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
    return digest == signature


def _decrypt_aes_cbc(encoding_aes_key: str, ciphertext_b64: str) -> str:
    try:
        from Crypto.Cipher import AES  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pycryptodome required for encrypted callbacks") from exc

    aes_key = base64.b64decode(encoding_aes_key + "=")
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    plain = cipher.decrypt(base64.b64decode(ciphertext_b64))
    pad = plain[-1]
    if not isinstance(pad, int) or pad < 1 or pad > 32:
        pad = plain[-1] if isinstance(plain[-1], int) else 0
    content = plain[:-pad]
    msg_len = struct.unpack(">I", content[16:20])[0]
    return content[20 : 20 + msg_len].decode("utf-8")


def decrypt_message(encoding_aes_key: str, encrypt: str) -> str:
    if not encoding_aes_key:
        return encrypt
    return _decrypt_aes_cbc(encoding_aes_key, encrypt)


def _xml_to_dict(xml_text: str) -> dict[str, str]:
    root = ET.fromstring(xml_text)
    return {child.tag: (child.text or "") for child in root}


def parse_message_payload(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"Content": str(data)}
    if raw.startswith("<"):
        return _xml_to_dict(raw)
    return {"Content": raw}


def extract_incoming_fields(payload: dict[str, Any]) -> dict[str, Any]:
    content = (
        payload.get("Content")
        or payload.get("content")
        or payload.get("Text")
        or payload.get("text")
        or ""
    )
    if isinstance(content, dict):
        content = content.get("content") or content.get("Content") or ""

    group_id = (
        payload.get("GroupId")
        or payload.get("groupId")
        or payload.get("group_id")
        or payload.get("ChatId")
        or payload.get("chatId")
    )
    chat_type = payload.get("ChatType") or payload.get("chatType") or payload.get("chat_type")
    msg_type = payload.get("MsgType") or payload.get("msgtype") or payload.get("msgType")

    is_at_robot = payload.get("IsAtRobot")
    if is_at_robot is None:
        is_at_robot = payload.get("is_at_robot")
    if is_at_robot is None:
        is_at_robot = "@" in str(content)

    return {
        "content": str(content),
        "group_id": str(group_id) if group_id not in (None, "") else None,
        "chat_type": str(chat_type) if chat_type else None,
        "msg_type": str(msg_type).lower() if msg_type else "text",
        "is_at_robot": bool(is_at_robot),
        "from_user": payload.get("FromUserName") or payload.get("from_user"),
    }
