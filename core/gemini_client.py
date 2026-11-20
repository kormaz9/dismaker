"""
DisMaker - Gemini AI İstemcisi ve Dinamik Model Fallback Motoru
3.1-flash-lite -> 3.5-flash -> 3.5-flash-lite -> 3.8-flash -> 3.7-flash -> flash-latest
"""

import asyncio
import json
import logging
from typing import Optional, Tuple
import aiohttp

from config import GEMINI_API_KEY, GEMINI_MODELS
from core.prompt import get_system_prompt, build_user_prompt
from core.schema import ServerArchitecture, parse_and_validate_architecture

logger = logging.getLogger("DisMaker.Gemini")

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAPIError(Exception):
    """Gemini API çağrılarında oluşan temel hata sınıfı"""
    pass


class GeminiArchitectClient:
    """
    Google Gemini API ile haberleşen, model fallback zincirine ve
    otomatik 503/Timeout yeniden deneme (retry) mekanizmasına sahip motor.
    """

    def __init__(self, api_key: Optional[str] = None, models: Optional[list[str]] = None):
        self.api_key = (api_key or GEMINI_API_KEY).strip()
        self.models = models or GEMINI_MODELS
        # Model başına zaman aşımı (25 saniye)
        self._request_timeout = aiohttp.ClientTimeout(total=25)

    async def generate_architecture(self, user_instruction: str) -> Tuple[ServerArchitecture, str]:
        """
        Kullanıcı isteğini Gemini modellerine sırayla gönderir.
        Başarılı olan modelin çıktısını doğrular ve (ServerArchitecture, kullanılan_model_adı) döndürür.
        """
        if not self.api_key or "BURAYA" in self.api_key:
            raise GeminiAPIError(
                "Gemini API Key bulunamadı veya yapılandırılmadı! "
                "Lütfen .env dosyasındaki GEMINI_API_KEY alanını doldurun."
            )

        payload = {
            "system_instruction": {
                "parts": [{"text": get_system_prompt()}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_user_prompt(user_instruction)}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95,
                "topK": 40,
                "maxOutputTokens": 8192
            }
        }

        errors_log: list[str] = []

        async with aiohttp.ClientSession() as session:
            for model_name in self.models:
                url = f"{GEMINI_API_BASE_URL}/{model_name}:generateContent?key={self.api_key}"
                logger.info(f"◈ [Gemini AI] '{model_name}' modeli deneniyor...")

                # Geçici yoğunluk (503) ve ani takılmalara karşı model başına 2 deneme
                for attempt in range(1, 3):
                    try:
                        async with session.post(
                            url,
                            headers={"Content-Type": "application/json"},
                            json=payload,
                            timeout=self._request_timeout
                        ) as response:
                            status = response.status
                            response_text = await response.text()

                            if status == 200:
                                try:
                                    data = json.loads(response_text)
                                    candidates = data.get("candidates", [])
                                    if not candidates:
                                        raise ValueError("Gemini API boş aday listesi döndürdü.")

                                    raw_content = candidates[0]["content"]["parts"][0]["text"]
                                    architecture = parse_and_validate_architecture(raw_content)
                                    logger.info(f"✓ [Gemini AI] '{model_name}' modeli başarıyla geçerli mimari üretti.")
                                    return architecture, model_name

                                except Exception as parse_err:
                                    err_msg = f"'{model_name}' modelinin JSON çıktısı doğrulanamadı: {parse_err}"
                                    logger.warning(f"⚠ {err_msg}")
                                    errors_log.append(err_msg)
                                    break  # JSON bozuksa bu modeli tekrar deneme

                            # 503 (High Demand) durumu: 2 saniye bekle ve tekrar dene
                            if status == 503 and attempt < 2:
                                logger.info(f"⏳ '{model_name}' anlık yoğunlukta (503). 2 saniye sonra tekrar deneniyor...")
                                await asyncio.sleep(2.0)
                                continue

                            # Hata durumu detayı
                            error_detail = ""
                            try:
                                err_json = json.loads(response_text)
                                error_detail = err_json.get("error", {}).get("message", response_text)
                            except Exception:
                                error_detail = response_text[:150]

                            fail_msg = f"'{model_name}' başarısız oldu (HTTP {status}): {error_detail}"
                            logger.warning(f"⚠ {fail_msg}")
                            errors_log.append(fail_msg)
                            break

                    except asyncio.TimeoutError:
                        if attempt < 2:
                            logger.info(f"⏳ '{model_name}' zaman aşımına uğradı. Yeniden deneniyor (Deneme 2)...")
                            await asyncio.sleep(1.5)
                            continue
                        err_msg = f"'{model_name}' modeli 30 saniye içinde yanıt vermedi (Timeout)."
                        logger.warning(f"⚠ {err_msg}")
                        errors_log.append(err_msg)
                        break

                    except Exception as ex:
                        err_msg = f"'{model_name}' bağlantı hatası: {ex}"
                        logger.warning(f"⚠ {err_msg}")
                        errors_log.append(err_msg)
                        break

        # Tüm modeller başarısız olursa
        raise GeminiAPIError(
            "Tüm Gemini modelleri denendi ancak yanıt alınamadı.\n"
            + "\n".join(f"• {e}" for e in errors_log)
        )

    def generate_architecture_sync(self, user_instruction: str) -> Tuple[ServerArchitecture, str]:
        """Senkron ortamlarda (CLI test vb.) kullanım için wrapper"""
        return asyncio.run(self.generate_architecture(user_instruction))
