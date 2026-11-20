"""
DisMaker - Birim ve Entegrasyon Testleri
"""

import unittest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from core.schema import (
    ServerArchitecture,
    parse_and_validate_architecture,
    clean_json_text
)
from discord_bot.builder import (
    build_discord_permissions,
    hex_to_discord_color,
    format_tree_channel_name
)
from discord_bot.moderation import contains_profanity, DISCORD_INVITE_PATTERN
from core.database import Database
from core.gemini_client import GeminiArchitectClient
from pathlib import Path


class TestDisMakerSchema(unittest.TestCase):

    def test_clean_json_text(self):
        # Markdown kod bloğu temizleme
        raw = "```json\n{\"server_name\": \"Test Sunucu\"}\n```"
        self.assertEqual(clean_json_text(raw), '{"server_name": "Test Sunucu"}')

        # Başı ve sonu metinli JSON
        raw2 = "İşte mimari:\n{\"server_name\": \"Test 2\"}\nUmarım beğenirsiniz."
        self.assertEqual(clean_json_text(raw2), '{"server_name": "Test 2"}')

    def test_schema_validation(self):
        sample_json = {
            "server_name": "◈ KOD VE YAPAY ZEKA ◈",
            "server_theme": "Yazılım ve Teknoloji",
            "moderation_policy": {
                "enabled": True,
                "filter_profanity": True,
                "filter_invites": True,
                "mute_duration_seconds": 900,
                "log_channel_name": "› mod-log"
            },
            "autorole": "› Geliştirici",
            "roles": [
                {
                    "name": "◈ Kurucu",
                    "color": "#3B82F6",
                    "hoist": True,
                    "mentionable": False,
                    "permissions": ["ADMINISTRATOR"]
                },
                {
                    "name": "› Geliştirici",
                    "color": "#10B981",
                    "hoist": True,
                    "mentionable": False,
                    "permissions": ["VIEW_CHANNEL", "SEND_MESSAGES"]
                }
            ],
            "categories": [
                {
                    "name": "◈ BİLGİLENDİRME ◈",
                    "channels": [
                        {
                            "name": "› kurallar",
                            "type": "text",
                            "topic": "Sunucu kuralları",
                            "slowmode": 0,
                            "user_limit": 0,
                            "permissions": {
                                "everyone": {
                                    "view": True,
                                    "send": False,
                                    "attach_files": False,
                                    "add_reactions": True
                                }
                            }
                        }
                    ]
                }
            ],
            "rules_embed": {
                "title": "SUNUCU KURALLARI",
                "color": "#18181B",
                "description": "Topluluğumuza hoş geldiniz.",
                "fields": [
                    {"name": "Madde 1: Saygı", "value": "Tüm üyelere saygılı davranılmalıdır."}
                ],
                "footer": "Yürürlük: 2026"
            }
        }

        json_str = json.dumps(sample_json)
        arch = parse_and_validate_architecture(json_str)

        self.assertEqual(arch.server_name, "◈ KOD VE YAPAY ZEKA ◈")
        self.assertEqual(arch.total_channels_count(), 1)
        self.assertEqual(arch.roles[0].name, "◈ Kurucu")
        self.assertTrue(arch.roles[0].hoist)
        self.assertEqual(arch.moderation_policy.mute_duration_seconds, 900)
        self.assertEqual(arch.rules_embed.title, "SUNUCU KURALLARI")


class TestBuilderHelpers(unittest.TestCase):

    def test_permission_mapping(self):
        perms = build_discord_permissions(["ADMINISTRATOR", "MANAGE_MESSAGES"])
        self.assertTrue(perms.administrator)
        self.assertTrue(perms.manage_messages)
        self.assertFalse(perms.kick_members)

    def test_hex_to_color(self):
        col = hex_to_discord_color("#10B981")
        self.assertEqual(col.value, 0x10B981)

    def test_format_tree_channel_name(self):
        # Ara metin kanalı
        self.assertEqual(format_tree_channel_name("genel-sohbet", False, False), "├・genel-sohbet")
        # Son metin kanalı
        self.assertEqual(format_tree_channel_name("foto-paylasim", True, False), "╰・foto-paylasim")
        # Tematik ikonlu metin kanalı
        self.assertEqual(format_tree_channel_name("📸・foto-paylasim", False, False), "├・📸・foto-paylasim")
        # Ses kanalı
        self.assertEqual(format_tree_channel_name("Sohbet Odası 1", False, True), "├・🔊・Sohbet Odası 1")
        # AFK kanalı
        self.assertEqual(format_tree_channel_name("AFK Odası", False, True), "├・💤・AFK Odası")
        # Dinamik ses odası oluşturucu (Join-to-Create)
        self.assertEqual(format_tree_channel_name("Oda Oluştur", True, True), "╰・➕・Oda Oluştur")


class TestInteractiveViews(unittest.TestCase):

    def test_view_persistence_and_ids(self):
        from discord_bot.views import (
            PersistentRulesVerifyView,
            PersistentRoleSelectView,
            PersistentTicketCreateView,
            PersistentTicketCloseView,
            PersistentRoleDropdownView
        )
        import discord

        # 1. Doğrulama Kapısı Butonu
        rules_view = PersistentRulesVerifyView()
        self.assertIsNone(rules_view.timeout)
        self.assertEqual(rules_view.children[0].custom_id, "dis_rules_verify_btn")

        # 2. Canlı Destek Talebi Açma Butonu
        ticket_create_view = PersistentTicketCreateView()
        self.assertIsNone(ticket_create_view.timeout)
        self.assertEqual(ticket_create_view.children[0].custom_id, "dis_ticket_create_btn")

        # 3. Canlı Destek Talebi Kapatma Butonu
        ticket_close_view = PersistentTicketCloseView()
        self.assertIsNone(ticket_close_view.timeout)
        self.assertEqual(ticket_close_view.children[0].custom_id, "dis_ticket_close_btn")

        # 4. Açılır Menü ve Butonlu Rol Seçim Görünümü
        role_buttons = [(111, "Geliştirici", "💻 Geliştirici"), (222, "Tasarımcı", "🎨 Tasarımcı")]
        dropdown_opts = [discord.SelectOption(label="Geliştirici", value="111")]
        role_view = PersistentRoleSelectView(role_buttons=role_buttons, dropdown_options=dropdown_opts)
        self.assertIsNone(role_view.timeout)
        self.assertEqual(len(role_view.children), 3)  # 1 select menu + 2 buttons
        self.assertEqual(role_view.children[0].custom_id, "dis_role_dropdown_menu")
        self.assertEqual(role_view.children[1].custom_id, "dis_role_111")
        self.assertEqual(role_view.children[2].custom_id, "dis_role_222")


class TestModerationFilters(unittest.TestCase):

    def test_invite_regex(self):
        self.assertTrue(bool(DISCORD_INVITE_PATTERN.search("discord.gg/abc1234")))
        self.assertTrue(bool(DISCORD_INVITE_PATTERN.search("https://discord.com/invite/xyz-clan")))
        self.assertFalse(bool(DISCORD_INVITE_PATTERN.search("https://google.com")))

    def test_profanity_filter(self):
        self.assertTrue(contains_profanity("bu bir amk testi"))
        self.assertTrue(contains_profanity("orospu"))
        self.assertTrue(contains_profanity("siiiik"))
        self.assertFalse(contains_profanity("Merhaba nasılsınız arkadaşlar"))


class TestDatabase(unittest.TestCase):

    def test_db_operations(self):
        test_db_path = Path("test_dismaker.db")
        if test_db_path.exists():
            test_db_path.unlink()

        db_instance = Database(test_db_path)
        db_instance.save_guild_settings(
            guild_id=123456789,
            autorole_name="Geliştirici",
            autorole_id=987654321,
            moderation_enabled=True,
            filter_profanity=True,
            filter_invites=True,
            mute_duration_seconds=600,
            log_channel_id=111222333,
            log_channel_name="› mod-log"
        )

        settings = db_instance.get_guild_settings(123456789)
        self.assertIsNotNone(settings)
        self.assertEqual(settings["autorole_name"], "Geliştirici")
        self.assertEqual(settings["moderation_enabled"], 1)
        self.assertEqual(settings["mute_duration_seconds"], 600)

        # Temizlik
        if test_db_path.exists():
            test_db_path.unlink()


class TestGeminiModelFallback(unittest.TestCase):

    def test_cascading_fallback(self):
        """3.5 başarısız olduğunda (404) 2.5 modeline otomatik geçişi test eder"""
        async def run_test():
            valid_response_json = {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps({
                                        "server_name": "◈ FALLBACK SUCCESS ◈",
                                        "server_theme": "Test Teması",
                                        "moderation_policy": {"enabled": False},
                                        "autorole": "Üye",
                                        "roles": [],
                                        "categories": []
                                    })
                                }
                            ]
                        }
                    }
                ]
            }

            client = GeminiArchitectClient(
                api_key="TEST_API_KEY",
                models=["gemini-3.5-flash", "gemini-2.5-flash"]
            )

            # aiohttp ClientSession post metodunu mock'layalım
            # İlk çağrı (3.5) status: 404, ikinci çağrı (2.5) status: 200
            call_count = 0

            class MockResponse:
                def __init__(self, status, text_data):
                    self.status = status
                    self._text = text_data

                async def text(self):
                    return self._text

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            class MockSession:
                def __init__(self, *args, **kwargs):
                    pass

                def post(self, url, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if "gemini-3.5-flash" in url:
                        return MockResponse(404, '{"error": {"message": "Model not found"}}')
                    else:
                        return MockResponse(200, json.dumps(valid_response_json))

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            with patch("aiohttp.ClientSession", MockSession):
                arch, model_used = await client.generate_architecture("Test isteği")
                self.assertEqual(model_used, "gemini-2.5-flash")
                self.assertEqual(arch.server_name, "◈ FALLBACK SUCCESS ◈")
                self.assertEqual(call_count, 2)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
