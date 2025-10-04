import logging
import os
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Configurações da Evolution API (adicionar no .env)
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolutionapi.cataliad.com")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "D8kNGAFZOhFk07yCmul5bJ3fgoLI6GtA")
EVOLUTION_INSTANCE_NAME = os.getenv("EVOLUTION_INSTANCE_NAME", "instanciakauane")

class EvolutionService:
    """
    Serviço para integração com Evolution API
    Responsável por enviar mensagens via WhatsApp usando Evolution
    """
    
    def __init__(self):
        self.api_url = EVOLUTION_API_URL
        self.api_key = EVOLUTION_API_KEY
        self.instance_name = EVOLUTION_INSTANCE_NAME
        self.timeout = 30.0
        
        if not self.api_key:
            logger.warning("⚠️ EVOLUTION_API_KEY não configurada no .env")
    
    def _format_phone_number(self, phone: str) -> str:
        """
        Formata número para padrão Evolution API
        Input: 5511999999999 ou 11999999999
        Output: 5511999999999@s.whatsapp.net
        """
        try:
            # Remove caracteres não numéricos
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            
            # Remove sufixo se já tiver
            clean_phone = clean_phone.replace('@s.whatsapp.net', '').replace('@g.us', '')
            
            # Garantir que começa com 55
            if not clean_phone.startswith('55'):
                if len(clean_phone) == 11:  # 11999999999
                    clean_phone = f"55{clean_phone}"
                elif len(clean_phone) == 10:  # 1199999999
                    clean_phone = f"55{clean_phone}"
            
            # Adicionar sufixo WhatsApp
            return f"{clean_phone}@s.whatsapp.net"
            
        except Exception as e:
            logger.error(f"❌ Erro ao formatar número {phone}: {str(e)}")
            return f"{phone}@s.whatsapp.net"
    
    async def send_text_message(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Envia mensagem de texto via Evolution API
        
        Args:
            phone_number: Número do destinatário (com ou sem @s.whatsapp.net)
            message: Texto da mensagem
            
        Returns:
            Dict com status do envio
        """
        try:
            # Formatar número
            formatted_phone = self._format_phone_number(phone_number)
            
            # URL da Evolution API
            url = f"{self.api_url}/message/sendText/{self.instance_name}"
            
            # Headers
            headers = {
                "apikey": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Payload
            payload = {
                "number": formatted_phone,
                "text": message
            }
            
            logger.info(f"📤 [EVOLUTION] Enviando mensagem para {formatted_phone}")
            logger.debug(f"📤 [EVOLUTION] URL: {url}")
            logger.debug(f"📤 [EVOLUTION] Payload: {payload}")
            
            # Fazer request
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                # Verificar resposta
                if response.status_code in [200, 201]:
                    logger.info(f"✅ [EVOLUTION] Mensagem enviada com sucesso para {formatted_phone}")
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "data": response.json(),
                        "phone": formatted_phone
                    }
                else:
                    logger.error(f"❌ [EVOLUTION] Erro ao enviar: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                        "phone": formatted_phone
                    }
                    
        except httpx.TimeoutException:
            logger.error(f"⏱️ [EVOLUTION] Timeout ao enviar para {phone_number}")
            return {
                "success": False,
                "error": "timeout",
                "message": "Evolution API não respondeu no tempo esperado"
            }
        except Exception as e:
            logger.error(f"❌ [EVOLUTION] Erro ao enviar mensagem: {str(e)}")
            return {
                "success": False,
                "error": "exception",
                "message": str(e)
            }
    
    async def send_media_message(self, phone_number: str, media_url: str, caption: str = "") -> Dict[str, Any]:
        """
        Envia mensagem com mídia (imagem, vídeo, documento)
        
        Args:
            phone_number: Número do destinatário
            media_url: URL da mídia
            caption: Legenda (opcional)
            
        Returns:
            Dict com status do envio
        """
        try:
            formatted_phone = self._format_phone_number(phone_number)
            
            url = f"{self.api_url}/message/sendMedia/{self.instance_name}"
            
            headers = {
                "apikey": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "number": formatted_phone,
                "mediaUrl": media_url,
                "caption": caption
            }
            
            logger.info(f"📤 [EVOLUTION] Enviando mídia para {formatted_phone}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"✅ [EVOLUTION] Mídia enviada com sucesso")
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "data": response.json()
                    }
                else:
                    logger.error(f"❌ [EVOLUTION] Erro ao enviar mídia: {response.text}")
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text
                    }
                    
        except Exception as e:
            logger.error(f"❌ [EVOLUTION] Erro ao enviar mídia: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_instance_status(self) -> Dict[str, Any]:
        """
        Verifica status da instância Evolution
        
        Returns:
            Dict com informações de status
        """
        try:
            url = f"{self.api_url}/instance/connectionState/{self.instance_name}"
            
            headers = {
                "apikey": self.api_key
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ [EVOLUTION] Status: {data.get('state', 'unknown')}")
                    return {
                        "success": True,
                        "status": data.get("state"),
                        "data": data
                    }
                else:
                    logger.error(f"❌ [EVOLUTION] Erro ao verificar status: {response.text}")
                    return {
                        "success": False,
                        "error": response.text
                    }
                    
        except Exception as e:
            logger.error(f"❌ [EVOLUTION] Erro ao verificar status: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }
    
    async def get_qrcode(self) -> Dict[str, Any]:
        """
        Obtém QR Code para conexão (se necessário)
        
        Returns:
            Dict com QR code base64
        """
        try:
            url = f"{self.api_url}/instance/connect/{self.instance_name}"
            
            headers = {
                "apikey": self.api_key
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "qrcode": data.get("qrcode", {}).get("base64"),
                        "data": data
                    }
                else:
                    return {
                        "success": False,
                        "error": response.text
                    }
                    
        except Exception as e:
            logger.error(f"❌ [EVOLUTION] Erro ao obter QR code: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# Instância global
evolution_service = EvolutionService()

# Funções auxiliares para compatibilidade
async def send_evolution_message(phone_number: str, message: str) -> Dict[str, Any]:
    """Wrapper para envio de mensagem"""
    return await evolution_service.send_text_message(phone_number, message)

async def get_evolution_status() -> Dict[str, Any]:
    """Wrapper para verificar status"""
    return await evolution_service.get_instance_status()