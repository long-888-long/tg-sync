#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：GitHub Actions 环境能否连接 Telegram"""
import os, sys, base64, socket, time, asyncio

print("[diag] 启动", flush=True)

# 1. 测试 TCP 连接 Telegram MTProto 服务器
def test_tcp(host, port, timeout=10):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception as e:
        return f"{type(e).__name__}: {e}"

print("[diag] TCP 测试 Telegram 服务器:", flush=True)
for host in ["149.154.167.51", "149.154.175.50", "91.108.56.130"]:
    r = test_tcp(host, 443)
    print(f"  {host}:443 -> {r}", flush=True)

# 2. 测试 DNS 解析
try:
    import socket as s2
    ip = s2.gethostbyname("telegram.org")
    print(f"[diag] DNS telegram.org -> {ip}", flush=True)
except Exception as e:
    print(f"[diag] DNS 失败: {e}", flush=True)

# 3. 测试 session 登录
session_b64 = os.environ.get("BOT_SESSION", "")
print(f"[diag] BOT_SESSION 长度: {len(session_b64)}", flush=True)
if session_b64:
    try:
        session_bytes = base64.b64decode(session_b64)
        session_path = "/tmp/diag_session.session"
        with open(session_path, "wb") as f:
            f.write(session_bytes)
        print(f"[diag] session 解码成功: {len(session_bytes)} bytes", flush=True)
        
        from telethon import TelegramClient
        API_ID = int(os.environ.get("API_ID", "2040"))
        API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
        client = TelegramClient(session_path, API_ID, API_HASH, connection_retries=1, timeout=15)
        
        async def test_login():
            print("[diag] 开始连接...", flush=True)
            await client.connect()
            print("[diag] connect() 完成", flush=True)
            auth = await client.is_user_authorized()
            print(f"[diag] is_user_authorized: {auth}", flush=True)
            if auth:
                me = await client.get_me()
                print(f"[diag] 登录成功: {me.first_name} (ID: {me.id})", flush=True)
            await client.disconnect()
        
        asyncio.run(asyncio.wait_for(test_login(), timeout=60))
    except asyncio.TimeoutError:
        print("[diag] 登录超时 (60s)", flush=True)
    except Exception as e:
        print(f"[diag] 登录异常: {type(e).__name__}: {e}", flush=True)
else:
    print("[diag] BOT_SESSION 为空!", flush=True)

print("[diag] 诊断完成", flush=True)