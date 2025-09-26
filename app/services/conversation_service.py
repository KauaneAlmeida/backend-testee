"""
Conversation Flow Service - DEPRECIADO

ATENÇÃO: Este módulo foi DEPRECIADO para resolver conflitos de fluxo.

PROBLEMA IDENTIFICADO:
- Este ConversationManager competia com intelligent_hybrid_orchestrator
- Causava processamento duplicado e fluxos conflitantes  
- Diferentes estruturas de dados e validações

SOLUÇÃO:
- TODO o processamento agora é feito APENAS pelo intelligent_hybrid_orchestrator
- Este arquivo deve ser removido ou mantido apenas para compatibilidade legada
- Use app.services.orchestration_service.intelligent_orchestrator

MIGRAÇÃO:
- conversation_manager.start_conversation() → intelligent_orchestrator.process_message()
- conversation_manager.process_response() → intelligent_orchestrator.process_message()
- conversation_manager.get_conversation_status() → intelligent_orchestrator.get_session_context()
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

class ConversationManager:
    """
    DEPRECIADO: Este manager foi substituído pelo intelligent_hybrid_orchestrator
    
    Mantenho apenas para compatibilidade legada, mas todo processamento
    deve ser feito através do orchestrator unificado.
    """

    def __init__(self):
        logger.warning("⚠️ ConversationManager está DEPRECIADO. Use intelligent_hybrid_orchestrator")
        self.deprecated = True

    async def start_conversation(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """DEPRECIADO: Use intelligent_orchestrator.process_message()"""
        logger.error("❌ MÉTODO DEPRECIADO: start_conversation()")
        logger.error("❌ Use: intelligent_orchestrator.process_message() com saudação")
        
        return {
            "error": "MÉTODO DEPRECIADO",
            "message": "Este ConversationManager foi depreciado",
            "use_instead": "intelligent_orchestrator.process_message()",
            "reason": "Conflitos de fluxo resolvidos com unificação",
            "timestamp": datetime.now().isoformat()
        }

    async def process_response(self, session_id: str, user_response: str) -> Dict[str, Any]:
        """DEPRECIADO: Use intelligent_orchestrator.process_message()"""
        logger.error("❌ MÉTODO DEPRECIADO: process_response()")
        logger.error("❌ Use: intelligent_orchestrator.process_message()")
        
        return {
            "error": "MÉTODO DEPRECIADO", 
            "message": "Este ConversationManager foi depreciado",
            "use_instead": "intelligent_orchestrator.process_message()",
            "reason": "Conflitos de fluxo resolvidos com unificação",
            "timestamp": datetime.now().isoformat()
        }

    async def get_conversation_status(self, session_id: str) -> Dict[str, Any]:
        """DEPRECIADO: Use intelligent_orchestrator.get_session_context()"""
        logger.error("❌ MÉTODO DEPRECIADO: get_conversation_status()")
        logger.error("❌ Use: intelligent_orchestrator.get_session_context()")
        
        return {
            "error": "MÉTODO DEPRECIADO",
            "message": "Este ConversationManager foi depreciado", 
            "use_instead": "intelligent_orchestrator.get_session_context()",
            "reason": "Conflitos de fluxo resolvidos com unificação",
            "timestamp": datetime.now().isoformat()
        }

    def _format_brazilian_phone(self, phone_clean: str) -> str:
        """DEPRECIADO: Funcionalidade movida para orchestrator"""
        logger.error("❌ MÉTODO DEPRECIADO: _format_brazilian_phone()")
        return phone_clean

    async def get_flow(self) -> Dict[str, Any]:
        """DEPRECIADO: Use firebase_service.get_conversation_flow()"""
        logger.error("❌ MÉTODO DEPRECIADO: get_flow()")
        return {"error": "DEPRECIADO"}

    async def _complete_flow(self, session_id: str, session_data: Dict[str, Any], flow: Dict[str, Any]) -> Dict[str, Any]:
        """DEPRECIADO"""
        logger.error("❌ MÉTODO DEPRECIADO: _complete_flow()")
        return {"error": "DEPRECIADO"}

    async def _handle_phone_collection(self, session_id: str, session_data: Dict[str, Any], user_response: str) -> Dict[str, Any]:
        """DEPRECIADO"""
        logger.error("❌ MÉTODO DEPRECIADO: _handle_phone_collection()")
        return {"error": "DEPRECIADO"}

    async def _switch_to_ai_mode(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """DEPRECIADO"""
        logger.error("❌ MÉTODO DEPRECIADO: _switch_to_ai_mode()")
        return {"error": "DEPRECIADO"}


# Instância depreciada com aviso
class DeprecatedConversationManager(ConversationManager):
    """Wrapper para mostrar avisos de depreciação"""
    
    def __getattribute__(self, name):
        if name.startswith('_') or name in ['deprecated']:
            return super().__getattribute__(name)
            
        logger.warning(f"⚠️ ACESSO A MÉTODO DEPRECIADO: ConversationManager.{name}")
        logger.warning("⚠️ MIGRE PARA: intelligent_hybrid_orchestrator")
        
        return super().__getattribute__(name)


# IMPORTANTE: Manter compatibilidade mas com avisos
conversation_manager = DeprecatedConversationManager()

# Função helper para migração
def get_recommended_replacement():
    """
    Retorna informações sobre o substituto recomendado
    """
    return {
        "deprecated_service": "conversation_flow_service.ConversationManager",
        "recommended_replacement": "orchestration_service.intelligent_hybrid_orchestrator", 
        "migration_guide": {
            "old_start": "conversation_manager.start_conversation(session_id)",
            "new_start": "intelligent_orchestrator.process_message('oi', session_id, platform='web')",
            "old_process": "conversation_manager.process_response(session_id, message)",
            "new_process": "intelligent_orchestrator.process_message(message, session_id, platform='web')",
            "old_status": "conversation_manager.get_conversation_status(session_id)",
            "new_status": "intelligent_orchestrator.get_session_context(session_id)"
        },
        "benefits_of_migration": [
            "Elimina conflitos de fluxo",
            "Sistema unificado para web e WhatsApp", 
            "Validação consistente",
            "Melhor logging e debug",
            "Performance otimizada"
        ],
        "conflicts_resolved": [
            "Processamento duplicado de mensagens",
            "Estruturas de dados diferentes",
            "Competição entre managers",
            "Validações inconsistentes",
            "Auto-start com 'Olá'"
        ]
    }


# Log de inicialização com aviso
logger.warning("🚨 conversation_flow_service.py foi DEPRECIADO")
logger.warning("🚨 Conflitos de fluxo resolvidos com intelligent_hybrid_orchestrator")
logger.warning("🚨 Migre seu código para usar orchestration_service")

if __name__ == "__main__":
    import json
    print("=== MIGRAÇÃO NECESSÁRIA ===")
    print(json.dumps(get_recommended_replacement(), indent=2, ensure_ascii=False))