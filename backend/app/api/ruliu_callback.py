"""Ruliu robot callback — group @mention handling."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.push.ruliu_commands import should_reply_to_group_message
from app.services.push.ruliu_crypto import (
    decrypt_message,
    extract_incoming_fields,
    parse_message_payload,
    verify_signature,
)
from app.services.push.ruliu_notifier import send_group_md
from app.services.enrichment.vendor_summary import collect_vendor_stats, format_vendor_coverage_md

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ruliu", tags=["ruliu"])


def _parse_form_fields(raw: bytes) -> dict[str, str]:
    text = raw.decode("utf-8", errors="ignore")
    if not text:
        return {}
    if text.strip().startswith("{"):
        data = json.loads(text)
        return {k: str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    parsed = parse_qs(text, keep_blank_values=True)
    return {k: v[0] if v else "" for k, v in parsed.items()}


async def _build_reply(session: AsyncSession) -> str:
    stats = await collect_vendor_stats(session)
    return format_vendor_coverage_md(stats)


async def _handle_incoming(
    session: AsyncSession,
    fields: dict[str, Any],
) -> dict[str, Any]:
    content = fields.get("content", "")
    group_id = fields.get("group_id")
    chat_type = fields.get("chat_type")
    is_at_robot = fields.get("is_at_robot", False)
    msg_type = fields.get("msg_type", "text")

    if msg_type and msg_type not in ("text", "TEXT", ""):
        return {"handled": False, "reason": "unsupported_msg_type"}

    if not should_reply_to_group_message(
        content=content,
        chat_type=chat_type,
        is_at_robot=is_at_robot,
    ):
        return {"handled": False, "reason": "not_matched"}

    reply_md = await _build_reply(session)
    settings = get_settings()
    target_group = group_id or settings.ruliu_group_id
    if not target_group:
        return {"handled": False, "reason": "missing_group_id", "reply_md": reply_md}

    send_result = await send_group_md(reply_md, group_id=str(target_group), force=True)
    return {
        "handled": True,
        "group_id": target_group,
        "reply_md": reply_md,
        "send_result": send_result,
    }


@router.post("/callback")
async def ruliu_callback(
    request: Request,
    signature: str = Query(default=""),
    timestamp: str = Query(default=""),
    rn: str = Query(default=""),
    session: AsyncSession = Depends(get_db),
):
    """如流机器人回调：URL 校验 + 群聊 @机器人消息。"""
    settings = get_settings()
    token = settings.ruliu_callback_token
    raw = await request.body()
    form = _parse_form_fields(raw)

    sig = signature or form.get("signature", "")
    ts = timestamp or form.get("timestamp", "")
    nonce = rn or form.get("rn", "")

    echostr = form.get("echostr", "")
    if echostr:
        encrypt = echostr
        if token and not verify_signature(token, ts, nonce, encrypt, sig):
            raise HTTPException(status_code=403, detail="invalid signature")
        if settings.ruliu_callback_aes_key:
            try:
                echostr = decrypt_message(settings.ruliu_callback_aes_key, echostr)
            except Exception as exc:
                logger.warning("echostr decrypt failed: %s", exc)
        return PlainTextResponse(content=echostr)

    encrypt = form.get("Encrypt") or form.get("encrypt", "")
    message_json = form.get("messageJson") or form.get("message_json", "")
    message_xml = form.get("message") or form.get("Message", "")

    payload_raw = message_json or message_xml
    if encrypt:
        if token and not verify_signature(token, ts, nonce, encrypt, sig):
            raise HTTPException(status_code=403, detail="invalid signature")
        if settings.ruliu_callback_aes_key:
            try:
                payload_raw = decrypt_message(settings.ruliu_callback_aes_key, encrypt)
            except Exception as exc:
                logger.exception("message decrypt failed")
                raise HTTPException(status_code=400, detail=f"decrypt failed: {exc}") from exc
        else:
            payload_raw = encrypt

    if not payload_raw and raw:
        try:
            payload_raw = raw.decode("utf-8")
        except Exception:
            payload_raw = ""

    if not payload_raw:
        return PlainTextResponse(content="success")

    try:
        payload = parse_message_payload(payload_raw)
    except Exception as exc:
        logger.warning("payload parse failed: %s", exc)
        return PlainTextResponse(content="success")

    fields = extract_incoming_fields(payload)
    result = await _handle_incoming(session, fields)
    logger.info("ruliu callback handled=%s reason=%s", result.get("handled"), result.get("reason"))
    return PlainTextResponse(content="success")


@router.post("/simulate-group-at")
async def simulate_group_at(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """本地模拟群聊 @机器人 提问（无需如流回调）。"""
    body = await request.json()
    content = body.get("content", "你都收录了哪些公司的skill")
    group_id = body.get("group_id") or get_settings().ruliu_group_id
    fields = {
        "content": content,
        "group_id": str(group_id) if group_id else None,
        "chat_type": "group",
        "is_at_robot": True,
        "msg_type": "text",
    }
    result = await _handle_incoming(session, fields)
    return result
