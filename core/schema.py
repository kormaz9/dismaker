"""
DisMaker - JSON Şema ve Doğrulama Modelleri (Pydantic v2)
Otomatik Rol Menüsü, Kurallar ve Zengin Mimari Modelleri
"""

import json
import re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class ModerationPolicy(BaseModel):
    enabled: bool = Field(default=False, description="7/24 dinamik moderasyon motoru açık mı?")
    filter_profanity: bool = Field(default=True, description="Küfür ve hakaret filtresi")
    filter_invites: bool = Field(default=True, description="Discord davet linkleri engellemesi")
    mute_duration_seconds: int = Field(default=600, description="İhlal durumunda verilecek timeout süresi (saniye)")
    log_channel_name: str = Field(default="› mod-log", description="Moderasyon kayıtlarının düşeceği kanal")


class RoleDefinition(BaseModel):
    name: str = Field(..., description="Rolün tam adı")
    color: str = Field(default="#94A3B8", description="Rolün HEX renk kodu (#RRGGBB)")
    hoist: bool = Field(default=True, description="Üye listesinde ayrı gösterilsin mi?")
    mentionable: bool = Field(default=False, description="Herkesten bahsedilebilir mi?")
    permissions: List[str] = Field(default_factory=list, description="Discord izinleri listesi")

    @field_validator("color", mode="before")
    @classmethod
    def sanitize_color(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "#94A3B8"
        v = v.strip()
        if not v.startswith("#"):
            v = f"#{v}"
        if re.match(r"^#[0-9a-fA-F]{6}$", v):
            return v.upper()
        return "#94A3B8"


class ChannelPermissions(BaseModel):
    view: Optional[bool] = Field(default=True, description="Kanalı görme izni")
    send: Optional[bool] = Field(default=True, description="Mesaj gönderme izni")
    attach_files: Optional[bool] = Field(default=False, description="Dosya yükleme izni")
    add_reactions: Optional[bool] = Field(default=True, description="Tepki ekleme izni")
    connect: Optional[bool] = Field(default=True, description="Sese bağlanma izni")
    speak: Optional[bool] = Field(default=True, description="Seste konuşma izni")


class ChannelDefinition(BaseModel):
    name: str = Field(..., description="Kanal adı (kebab-case)")
    type: str = Field(default="text", description="Kanal tipi: 'text' veya 'voice'")
    topic: Optional[str] = Field(default="", description="Kanal konusu veya açıklaması")
    slowmode: int = Field(default=0, description="Yavaş mod süresi (saniye)")
    user_limit: int = Field(default=0, description="Ses kanalı kişi sınırı (0 = sınırsız)")
    permissions: Dict[str, ChannelPermissions] = Field(
        default_factory=dict,
        description="Rol veya @everyone izinleri"
    )

    @field_validator("type", mode="before")
    @classmethod
    def sanitize_type(cls, v: Any) -> str:
        s = str(v).lower().strip()
        return "voice" if "voice" in s or "ses" in s else "text"


class CategoryDefinition(BaseModel):
    name: str = Field(..., description="Kategori adı (UTF-8 sembollü ve BÜYÜK HARF)")
    channels: List[ChannelDefinition] = Field(default_factory=list, description="Kategori altındaki kanallar")


class RuleField(BaseModel):
    name: str = Field(..., description="Madde başlığı")
    value: str = Field(..., description="Madde açıklaması")


class RulesEmbed(BaseModel):
    title: str = Field(default="📜 SUNUCU KURALLARI", description="Kurallar embed başlığı")
    color: str = Field(default="#1E293B", description="Embed HEX rengi")
    description: str = Field(default="", description="Kurallar ön yazı/açıklama")
    fields: List[RuleField] = Field(default_factory=list, description="Kural maddeleri")
    footer: str = Field(default="Tüm üyeler bu kuralları kabul etmiş sayılır.", description="Embed alt bilgi")

    @field_validator("color", mode="before")
    @classmethod
    def sanitize_color(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "#1E293B"
        v = v.strip()
        if not v.startswith("#"):
            v = f"#{v}"
        if re.match(r"^#[0-9a-fA-F]{6}$", v):
            return v.upper()
        return "#1E293B"


class RoleMenuItem(BaseModel):
    role_name: str = Field(..., description="Verilecek rolün tam adı")
    button_label: str = Field(..., description="Buton üzerinde yazacak metin (Örn: 🎮 Oyuncu)")
    description: Optional[str] = Field(default="", description="Rolün kısa tanımı")


class RoleMenuEmbed(BaseModel):
    title: str = Field(default="🎭 ROL SEÇİM PANELİ", description="Rol menüsü embed başlığı")
    color: str = Field(default="#3B82F6", description="Panel HEX rengi")
    description: str = Field(default="Aşağıdaki butonlara tıklayarak dilediğiniz rolleri alabilir veya çıkartabilirsiniz.", description="Açıklama")
    items: List[RoleMenuItem] = Field(default_factory=list, description="Seçilebilir buton rolleri")

    @field_validator("color", mode="before")
    @classmethod
    def sanitize_color(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "#3B82F6"
        v = v.strip()
        if not v.startswith("#"):
            v = f"#{v}"
        if re.match(r"^#[0-9a-fA-F]{6}$", v):
            return v.upper()
        return "#3B82F6"


class ServerArchitecture(BaseModel):
    server_name: str = Field(..., description="Sunucunun adı")
    server_theme: str = Field(default="Genel Topluluk", description="Sunucu teması")
    moderation_policy: ModerationPolicy = Field(default_factory=ModerationPolicy)
    autorole: str = Field(default="Üye", description="Yeni gelenlere atanacak temel rol")
    roles: List[RoleDefinition] = Field(default_factory=list, description="Sunucu rolleri")
    categories: List[CategoryDefinition] = Field(default_factory=list, description="Kategoriler ve kanallar")
    rules_embed: Optional[RulesEmbed] = Field(default=None, description="Kurallar kanalı embed paneli")
    role_menu: Optional[RoleMenuEmbed] = Field(default=None, description="Etkileşimli butonlu rol alma paneli")

    def total_channels_count(self) -> int:
        return sum(len(cat.channels) for cat in self.categories)

    def text_channels_count(self) -> int:
        return sum(sum(1 for ch in cat.channels if ch.type == "text") for cat in self.categories)

    def voice_channels_count(self) -> int:
        return sum(sum(1 for ch in cat.channels if ch.type == "voice") for cat in self.categories)


def clean_json_text(raw_text: str) -> str:
    """
    LLM çıktısından Markdown kod bloklarını (```json ... ```) ve gereksiz metinleri temizler.
    """
    text = raw_text.strip()
    
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()
    else:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx : end_idx + 1].strip()

    return text


def parse_and_validate_architecture(raw_json: str) -> ServerArchitecture:
    """
    Ham LLM çıktısını temizler, JSON olarak çözümler ve Pydantic modeliyle doğrular.
    """
    cleaned = clean_json_text(raw_json)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Geçersiz JSON formatı: {e}\nTemizlenmiş içerik:\n{cleaned[:500]}")

    return ServerArchitecture.model_validate(data)
