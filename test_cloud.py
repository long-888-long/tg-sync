#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TG Forwarder Bot v2.2 自检脚本（22 项测试，纯标准库 + 可选 Pillow）"""
import json
import os
import sys
import unittest
from io import BytesIO
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot

CFG = {
    "BOT_TOKEN": "123456789:TESTTOKEN",
    "SOURCE": "@srcA,@srcB",
    "DEST": "@dest1",
    "MODE": "repost",
    "WM_MODE": "off",
    "AD_FILTER": "true",
    "EDIT_SYNC": "true",
    "STATE_FILE": "state_test.json",
}


def make_cfg(**over):
    d = dict(CFG)
    d.update(over)
    with mock.patch.dict(os.environ, d, clear=False):
        return bot.Config()


class FakeResponse:
    def __init__(self, data, code=200):
        if isinstance(data, bytes):
            self._data = data
        else:
            self._data = json.dumps(data).encode("utf-8")
        self.code = code

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestConfig(unittest.TestCase):
    def test_multi_source_parse(self):
        c = make_cfg(SOURCE="@a,@b,@c")
        self.assertEqual(c.source, ["@a", "@b", "@c"])

    def test_validate_missing_token(self):
        c = make_cfg(BOT_TOKEN="")
        self.assertTrue(any("BOT_TOKEN" in e for e in c.validate()))

    def test_validate_missing_source(self):
        c = make_cfg(SOURCE="")
        self.assertTrue(any("SOURCE" in e for e in c.validate()))

    def test_defaults(self):
        c = make_cfg()
        self.assertEqual(c.mode, "repost")
        self.assertTrue(c.ad_filter)
        self.assertTrue(c.edit_sync)


class TestText(unittest.TestCase):
    def test_strip_mentions(self):
        out = bot.strip_trace("你好 @srcA 看这个 t.me/srcA/x 还有 https://t.me/srcB/y", make_cfg())
        self.assertNotIn("@srcA", out)
        self.assertNotIn("t.me", out)
        self.assertNotIn("@srcB", out)

    def test_strip_replace_mentions(self):
        out = bot.strip_trace("来自 @srcA 的消息", make_cfg(REPLACE_MENTIONS="@我的频道"))
        self.assertIn("@我的频道", out)
        self.assertNotIn("@srcA", out)

    def test_ad_keyword_default(self):
        self.assertTrue(bot.contains_ad("加微信 xxx 扫码", []))
        self.assertFalse(bot.contains_ad("今天天气不错", []))

    def test_ad_keyword_custom(self):
        self.assertTrue(bot.contains_ad("招代理 秒到账", ["招代理"]))
        self.assertFalse(bot.contains_ad("今天天气不错", ["招代理"]))


class TestLLM(unittest.TestCase):
    @mock.patch.object(bot.urllib.request, "urlopen")
    def test_judge_ad_true(self, m):
        m.return_value = FakeResponse({"choices": [{"message": {"content": "广告"}}]})
        c = make_cfg(LLM_API_KEY="sk-test", AD_LLM="true")
        self.assertTrue(bot.llm_judge_ad("这条内容比较隐晦", c))

    @mock.patch.object(bot.urllib.request, "urlopen")
    def test_judge_ad_false(self, m):
        m.return_value = FakeResponse({"choices": [{"message": {"content": "非广告"}}]})
        c = make_cfg(LLM_API_KEY="sk-test", AD_LLM="true")
        self.assertFalse(bot.llm_judge_ad("普通新闻", c))

    @mock.patch.object(bot.urllib.request, "urlopen", side_effect=Exception("net"))
    def test_judge_ad_error_fallback(self, m):
        c = make_cfg(LLM_API_KEY="sk-test", AD_LLM="true")
        self.assertIsNone(bot.llm_judge_ad("x", c))

    @mock.patch.object(bot.urllib.request, "urlopen")
    def test_rewrite_called(self, m):
        m.return_value = FakeResponse({"choices": [{"message": {"content": "改写后文本"}}]})
        c = make_cfg(LLM_API_KEY="sk-test", REWRITE="true")
        self.assertEqual(bot.llm_rewrite("原始文本", c), "改写后文本")

    def test_rewrite_no_key_fallback(self):
        c = make_cfg(LLM_API_KEY="", REWRITE="true")
        out = bot.llm_rewrite("你好 @srcA", c)
        self.assertNotIn("@srcA", out)


class TestMedia(unittest.TestCase):
    def test_media_kind_selection(self):
        self.assertEqual(bot.MEDIA_HANDLERS[2][0], "photo")

    def test_multipart_builder(self):
        calls = {}

        def fake_urlopen(req, timeout=60):
            calls["url"] = req.full_url
            calls["method"] = req.get_method()
            calls["headers"] = str(req.headers)
            calls["body"] = req.data
            return FakeResponse({"ok": True, "result": {"message_id": 100}})

        with mock.patch.object(bot.urllib.request, "urlopen", side_effect=fake_urlopen):
            r = bot.send_photo(make_cfg(), "@dest1", b"\xff\xd8fake", "caption")
        self.assertTrue(r["ok"])
        self.assertIn("multipart/form-data", str(calls["headers"]))
        self.assertIn(b"filename=\"p.jpg\"", calls["body"])


class TestForward(unittest.TestCase):
    def setUp(self):
        self.state = {"offset": 0, "links": []}
        if os.path.exists("state_test.json"):
            os.unlink("state_test.json")

    def test_text_forward_no_ad(self):
        c = make_cfg()
        msg = {"message_id": 1, "chat": {"id": -1001, "username": "srcA"},
               "text": "今日新闻：油价上涨"}
        with mock.patch.object(bot, "send_text", return_value={"ok": True, "result": {"message_id": 10}}):
            res = bot.forward_message(c, msg, self.state)
        self.assertEqual(res, [("@dest1", 10)])

    def test_ad_message_not_forwarded(self):
        c = make_cfg()
        msg = {"message_id": 2, "chat": {"id": -1001, "username": "srcA"},
               "text": "加微信 xxx 扫码领红包"}
        res = bot.forward_message(c, msg, self.state)
        self.assertEqual(res, [])

    @mock.patch.object(bot.urllib.request, "urlopen")
    def test_photo_repost_flow(self, m):
        c = make_cfg()
        msg = {"message_id": 3, "chat": {"id": -1001, "username": "srcA"},
               "photo": [{"file_id": "f1"}], "caption": "看图"}
        calls = []

        def fake_urlopen(req, timeout=60):
            url = getattr(req, "full_url", req)
            calls.append(url)
            if "getFile" in url:
                return FakeResponse({"ok": True, "result": {"file_path": "photos/f1.jpg"}})
            if "/file/bot" in url:
                return FakeResponse(b"\xff\xd8\xff\xe0" * 10)
            if "sendPhoto" in url:
                return FakeResponse({"ok": True, "result": {"message_id": 20}})
            return FakeResponse({"ok": False})

        m.side_effect = fake_urlopen
        res = bot.forward_message(c, msg, self.state)
        self.assertEqual(res, [("@dest1", 20)])
        self.assertTrue(any("getFile" in x for x in calls))

    @mock.patch.object(bot, "download_file", return_value=None)
    @mock.patch.object(bot, "api_call", return_value={"ok": True, "result": {"message_id": 30}})
    def test_download_fail_fallback_forward(self, m_api, m_dl):
        c = make_cfg()
        msg = {"message_id": 4, "chat": {"id": -1001, "username": "srcA"},
               "photo": [{"file_id": "f2"}], "caption": ""}
        res = bot.forward_message(c, msg, self.state)
        self.assertEqual(res, [("@dest1", 30)])
        fwd = [x for x in m_api.call_args_list if len(x.args) > 1 and x.args[1] == "forwardMessage"]
        self.assertTrue(fwd)

    def test_edit_sync_updates_all_dests(self):
        c = make_cfg()
        self.state["links"] = [["@dest1", 101, 5, -1001], ["@dest2", 102, 5, -1001]]
        edit = {"message": {"message_id": 5, "chat": {"id": -1001}, "text": "修改后"}}
        with mock.patch.object(bot, "api_call", return_value={"ok": True, "result": True}) as m:
            n = bot.edit_sync(c, edit, self.state)
        self.assertEqual(n, 2)
        self.assertEqual(m.call_count, 2)

    def test_is_from_source(self):
        c = make_cfg()
        self.assertTrue(bot.is_from_source({"chat": {"id": -1001, "username": "srcA"}}, c))
        self.assertFalse(bot.is_from_source({"chat": {"id": -9999, "username": "other"}}, c))


class TestState(unittest.TestCase):
    def test_state_save_load(self):
        c = make_cfg(STATE_FILE="state_test.json")
        bot.save_state(c, {"offset": 5, "links": [["@d", 1, 2, -3]]})
        s = bot.load_state(c)
        self.assertEqual(s["offset"], 5)
        self.assertEqual(s["links"][0][0], "@d")
        os.unlink("state_test.json")

    def test_state_load_missing(self):
        c = make_cfg(STATE_FILE="no_such_file.json")
        s = bot.load_state(c)
        self.assertEqual(s, {"offset": 0, "links": []})


if __name__ == "__main__":
    unittest.main(verbosity=2)
