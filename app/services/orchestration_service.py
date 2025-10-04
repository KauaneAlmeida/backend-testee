import logging
import json
import os
import re
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.services.firebase_service import (
    get_user_session,
    save_user_session,
    save_lead_data,
    get_conversation_flow,
    get_firebase_service_status
)
from app.services.ai_chain import ai_orchestrator
from app.services.evolution_service import evolution_service
from app.services.lawyer_notification_service import lawyer_notification_service

logger = logging.getLogger(__name__)


def ensure_utc(dt: datetime) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class IntelligentHybridOrchestrator:
    def __init__(self):
        self.gemini_available = True
        self.gemini_timeout = 15.0
        self.law_firm_number = "+5511918368812"
        self.sessions = {}

    def _format_brazilian_phone(self, phone_clean: str) -> str:
        """Format Brazilian phone number correctly for WhatsApp."""
        try:
            if not phone_clean:
                return ""
            phone_clean = ''.join(filter(str.isdigit, str(phone_clean)))

            if phone_clean.startswith("55"):
                phone_clean = phone_clean[2:]

            if len(phone_clean) == 8:
                return f"55{phone_clean}"
            if len(phone_clean) == 9:
                return f"55{phone_clean}"
            if len(phone_clean) == 10:
                ddd = phone_clean[:2]
                number = phone_clean[2:]
                if len(number) == 8 and number[0] in ['6', '7', '8', '9']:
                    number = f"9{number}"
                return f"55{ddd}{number}"
            if len(phone_clean) == 11:
                ddd = phone_clean[:2]
                number = phone_clean[2:]
                return f"55{ddd}{number}"
            return f"55{phone_clean}"
        except Exception as e:
            logger.error(f"Error formatting phone number {phone_clean}: {str(e)}")
            return f"55{phone_clean if phone_clean else ''}"

    def _get_personalized_greeting(self, phone_number: Optional[str] = None, session_id: str = "", user_name: str = "") -> str:
        """
        🎯 MENSAGEM INICIAL ESTRATÉGICA OTIMIZADA
        
        Elementos psicológicos para conversão:
        ✅ Autoridade (escritório especializado, resultados)
        ✅ Urgência suave (situações que não podem esperar)
        ✅ Personalização (horário do dia)
        ✅ Prova social (milhares de casos)
        ✅ Benefício claro (solução rápida e eficaz)
        ✅ Call-to-action natural
        """
        brazil_tz = ZoneInfo('America/Sao_Paulo')
        now = datetime.now(brazil_tz)
        hour = now.hour
        
        if 5 <= hour < 12:
            greeting = "Bom dia"
        elif 12 <= hour < 18:
            greeting = "Boa tarde"
        else:
            greeting = "Boa noite"
        
        strategic_greeting = f"""{greeting}! 👋

Bem-vindo ao m.lima Advogados Associados. 💼

Para que eu possa direcionar você ao advogado especialista ideal e acelerar a solução do seu caso, preciso conhecer um pouco mais sobre sua situação.

Tudo bem? 😊"""
        
        return strategic_greeting

    def _get_whatsapp_unauthorized_message(self) -> str:
        """
        🚫 MENSAGEM PARA USUÁRIOS NÃO AUTORIZADOS NO WHATSAPP
        
        Retorna mensagem padrão quando alguém tenta iniciar conversa no WhatsApp
        sem ter passado pela landing page e clicado no botão de autorização.
        """
        return """Olá! 👋

Para iniciarmos seu atendimento personalizado e direcioná-lo ao advogado especialista ideal, precisamos que você acesse nossa página oficial:

🌐 https://mlima.adv.br

Lá você encontrará:
✅ Informações sobre nossas áreas de atuação
✅ Formulário de atendimento
✅ Botão direto para conversar conosco pelo WhatsApp

Aguardamos seu contato através da nossa página oficial! 😊

---
m.lima Advogados Associados
Atendimento autorizado apenas via site oficial"""

    def _get_strategic_whatsapp_message(self, user_name: str, area: str, phone_formatted: str) -> str:
        """
        🎯 MENSAGEM ESTRATÉGICA OTIMIZADA PARA CONVERSÃO
        
        Elementos psicológicos incluídos:
        ✅ Urgência (minutos, tempo limitado)
        ✅ Autoridade (equipe especializada, experiente) 
        ✅ Prova social (dezenas de casos resolvidos)
        ✅ Exclusividade (atenção personalizada)
        ✅ Benefício claro (resultados, agilidade)
        """
        first_name = user_name.split()[0] if user_name else "Cliente"
        
        area_messages = {
            "penal": {
                "expertise": "Nossa equipe especializada em Direito Penal já resolveu centenas de casos similares",
                "urgency": "Sabemos que situações criminais precisam de atenção IMEDIATA",
                "benefit": "proteger seus direitos e buscar o melhor resultado possível"
            },
            "saude": {
                "expertise": "Nossos advogados especialistas em Direito da Saúde têm expertise em ações contra planos",
                "urgency": "Questões de saúde não podem esperar",
                "benefit": "garantir seu tratamento e obter as coberturas devidas"
            },
            "default": {
                "expertise": "Nossa equipe jurídica experiente",
                "urgency": "Sua situação precisa de atenção especializada",
                "benefit": "alcançar a solução mais eficaz para seu caso"
            }
        }
        
        area_key = "default"
        if any(word in area.lower() for word in ["penal", "criminal", "crime"]):
            area_key = "penal"
        elif any(word in area.lower() for word in ["saude", "saúde", "plano", "medic"]):
            area_key = "saude"
            
        msgs = area_messages[area_key]
        
        strategic_message = f"""🚀 {first_name}, uma EXCELENTE notícia!

✅ Seu atendimento foi PRIORIZADO no sistema m.lima

{msgs['expertise']} com resultados comprovados e já foi IMEDIATAMENTE notificada sobre seu caso.

🎯 {msgs['urgency']} - por isso um advogado experiente entrará em contato com você nos PRÓXIMOS MINUTOS.

🏆 DIFERENCIAL m.lima:
- ⚡ Atendimento ágil e personalizado
- 🎯 Estratégia focada em RESULTADOS
- 📋 Acompanhamento completo do processo
- 💪 Equipe com vasta experiência

Você fez a escolha certa ao confiar no m.lima para {msgs['benefit']}.

⏰ Aguarde nossa ligação - sua situação está em excelentes mãos!

---
✉️ m.lima Advogados Associados
📱 Contato prioritário ativado"""

        return strategic_message

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        🔚 ENCERRA SESSÃO COMPLETAMENTE
        
        Chamado quando o fluxo está completo para limpar a sessão
        e impedir que continue recebendo mensagens.
        
        Args:
            session_id: ID da sessão a ser encerrada
            
        Returns:
            Dict com status do encerramento
        """
        try:
            logger.info(f"🔚 Encerrando sessão: {session_id}")
            
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"✅ Sessão removida do cache local: {session_id}")
            
            session_data = await get_user_session(session_id)
            
            if session_data:
                session_data["session_ended"] = True
                session_data["ended_at"] = ensure_utc(datetime.now(timezone.utc))
                session_data["current_step"] = "ended"
                
                await save_user_session(session_id, session_data)
                logger.info(f"✅ Sessão marcada como encerrada no Firebase: {session_id}")
                
                return {
                    "status": "ended",
                    "session_id": session_id,
                    "ended_at": session_data["ended_at"].isoformat(),
                    "message": "Sessão encerrada com sucesso"
                }
            else:
                logger.warning(f"⚠️ Sessão não encontrada no Firebase: {session_id}")
                return {
                    "status": "not_found",
                    "session_id": session_id,
                    "message": "Sessão não encontrada"
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao encerrar sessão {session_id}: {str(e)}")
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "message": "Erro ao encerrar sessão"
            }

    async def should_notify_lawyers(self, session_data: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """
        🧠 LÓGICA INTELIGENTE DE NOTIFICAÇÃO
        
        Decide quando notificar advogados baseado na plataforma e qualificação do lead
        Evita notificações prematuras e spam para a equipe jurídica
        """
        try:
            if session_data.get("lawyers_notified", False):
                return {
                    "should_notify": False,
                    "reason": "already_notified",
                    "message": "Advogados já foram notificados anteriormente"
                }
            
            lead_data = session_data.get("lead_data", {})
            message_count = session_data.get("message_count", 0)
            current_step = session_data.get("current_step", "")
            flow_completed = session_data.get("flow_completed", False)
            
            if platform == "web":
                required_fields = ["identification", "area_qualification", "case_details", "phone", "confirmation"]
                has_required_fields = all(lead_data.get(field) for field in required_fields)
                
                criteria_met = (
                    flow_completed and 
                    has_required_fields and
                    len(lead_data.get("identification", "").strip()) >= 3 and
                    len(lead_data.get("case_details", "").strip()) >= 15 and
                    len(lead_data.get("phone", "").strip()) >= 10
                )
                
                qualification_score = self._calculate_qualification_score(lead_data, platform)
                
                if criteria_met and qualification_score >= 0.8:
                    return {
                        "should_notify": True,
                        "reason": "web_flow_completed",
                        "qualification_score": qualification_score,
                        "message": f"Lead web qualificado - Score: {qualification_score:.2f}"
                    }
                
            elif platform == "whatsapp":
                required_fields = ["identification", "area_qualification", "phone"]
                has_required_fields = all(lead_data.get(field) for field in required_fields)
                
                engagement_criteria = (
                    message_count >= 3 and
                    has_required_fields and
                    len(lead_data.get("identification", "").strip()) >= 3 and
                    len(lead_data.get("area_qualification", "").strip()) >= 3 and
                    len(lead_data.get("phone", "").strip()) >= 10
                )
                
                advanced_step = current_step in ["step5_confirmation", "completed"]
                
                qualification_score = self._calculate_qualification_score(lead_data, platform)
                
                if engagement_criteria and advanced_step and qualification_score >= 0.7:
                    return {
                        "should_notify": True,
                        "reason": "whatsapp_qualified",
                        "qualification_score": qualification_score,
                        "engagement_level": message_count,
                        "current_step": current_step,
                        "message": f"Lead WhatsApp qualificado - Score: {qualification_score:.2f}, Step: {current_step}"
                    }
            
            return {
                "should_notify": False,
                "reason": "not_qualified_yet",
                "qualification_score": self._calculate_qualification_score(lead_data, platform),
                "missing_criteria": self._get_missing_criteria(session_data, platform),
                "message": "Lead ainda não atingiu critérios de qualificação"
            }
            
        except Exception as e:
            logger.error(f"Erro ao avaliar notificação: {str(e)}")
            return {
                "should_notify": False,
                "reason": "evaluation_error",
                "error": str(e),
                "message": "Erro na avaliação - não notificando por segurança"
            }

    def _calculate_qualification_score(self, lead_data: Dict[str, Any], platform: str) -> float:
        """Calcula score de qualificação do lead (0.0 a 1.0)"""
        try:
            score = 0.0
            
            name = lead_data.get("identification", "").strip()
            if len(name) >= 3:
                score += 0.15
            if len(name.split()) >= 2:
                score += 0.10
                
            phone = lead_data.get("phone", "").strip()
            if phone and len(phone) >= 10:
                score += 0.25
            
            area = lead_data.get("area_qualification", "").strip()
            if area:
                score += 0.15
                if any(keyword in area.lower() for keyword in ["penal", "saude", "saúde", "criminal", "plano"]):
                    score += 0.10
            
            details = lead_data.get("case_details", "").strip()
            if details:
                score += 0.08
                if len(details) >= 20:
                    score += 0.04
                if len(details) >= 50:
                    score += 0.03
            
            confirmation = lead_data.get("confirmation", "").strip()
            if confirmation:
                score += 0.10
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Erro ao calcular score: {str(e)}")
            return 0.0

    def _get_missing_criteria(self, session_data: Dict[str, Any], platform: str) -> list:
        """Identifica critérios faltantes para qualificação"""
        missing = []
        lead_data = session_data.get("lead_data", {})
        
        if not lead_data.get("identification"):
            missing.append("nome_completo")
        if not lead_data.get("phone"):
            missing.append("telefone")
        if not lead_data.get("area_qualification"):
            missing.append("area_juridica")
            
        if platform == "web":
            if not lead_data.get("case_details"):
                missing.append("detalhes_caso")
            if not lead_data.get("confirmation"):
                missing.append("confirmacao")
            if not session_data.get("flow_completed"):
                missing.append("fluxo_incompleto")
        elif platform == "whatsapp":
            if session_data.get("message_count", 0) < 3:
                missing.append("engajamento_insuficiente")
                
        return missing

    async def notify_lawyers_if_qualified(self, session_id: str, session_data: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """
        🎯 MÉTODO PRINCIPAL DE NOTIFICAÇÃO INTELIGENTE
        
        Avalia se deve notificar e executa a notificação se qualificado
        """
        try:
            notification_check = await self.should_notify_lawyers(session_data, platform)
            
            if not notification_check["should_notify"]:
                logger.info(f"📊 Não notificando advogados - Session: {session_id} | Razão: {notification_check['reason']}")
                return {
                    "notified": False,
                    "reason": notification_check["reason"],
                    "details": notification_check
                }
            
            lead_data = session_data.get("lead_data", {})
            user_name = lead_data.get("identification", "Lead Qualificado")
            area = lead_data.get("area_qualification", "não especificada")
            case_details = lead_data.get("case_details", "aguardando mais detalhes")
            phone_clean = lead_data.get("phone", "")
            
            logger.info(f"🚀 NOTIFICANDO ADVOGADOS - Session: {session_id} | Lead: {user_name} | Área: {area} | Platform: {platform}")
            
            try:
                notification_result = await lawyer_notification_service.notify_lawyers_of_new_lead(
                    lead_name=user_name,
                    lead_phone=phone_clean,
                    category=area,
                    additional_info={
                        "case_details": case_details,
                        "urgency": "high" if platform == "whatsapp" else "normal",
                        "platform": platform,
                        "qualification_score": notification_check.get("qualification_score", 0),
                        "session_id": session_id,
                        "engagement_level": session_data.get("message_count", 0),
                        "current_step": session_data.get("current_step", ""),
                        "lead_source": f"{platform}_qualified_lead",
                        "preferred_contact_time": lead_data.get("preferred_contact_time", "não informado")
                    }
                )
                
                if notification_result.get("success"):
                    session_data["lawyers_notified"] = True
                    session_data["lawyers_notified_at"] = ensure_utc(datetime.now(timezone.utc))
                    await save_user_session(session_id, session_data)
                    
                    logger.info(f"✅ Advogados notificados com sucesso - Session: {session_id}")
                    
                    return {
                        "notified": True,
                        "success": True,
                        "platform": platform,
                        "qualification_score": notification_check.get("qualification_score"),
                        "notification_result": notification_result
                    }
                else:
                    logger.error(f"❌ Falha na notificação dos advogados - Session: {session_id}")
                    return {
                        "notified": True,
                        "success": False,
                        "error": "notification_failed",
                        "details": notification_result
                    }
                    
            except Exception as notification_error:
                logger.error(f"❌ Erro ao notificar advogados - Session: {session_id}: {str(notification_error)}")
                return {
                    "notified": True,
                    "success": False,
                    "error": "notification_exception",
                    "exception": str(notification_error)
                }
                
        except Exception as e:
            logger.error(f"❌ Erro na lógica de notificação - Session: {session_id}: {str(e)}")
            return {
                "notified": False,
                "error": "notification_logic_error",
                "exception": str(e)
            }

    async def get_gemini_health_status(self) -> Dict[str, Any]:
        try:
            test_response = await asyncio.wait_for(
                ai_orchestrator.generate_response("test", session_id="__health_check__"),
                timeout=5.0
            )
            ai_orchestrator.clear_session_memory("__health_check__")
            if test_response and isinstance(test_response, str) and test_response.strip():
                self.gemini_available = True
                return {"service": "gemini_ai", "status": "active", "available": True}
            else:
                self.gemini_available = False
                return {"service": "gemini_ai", "status": "inactive", "available": False}
        except Exception as e:
            self.gemini_available = False
            return {"service": "gemini_ai", "status": "error", "available": False, "error": str(e)}

    async def get_overall_service_status(self) -> Dict[str, Any]:
        try:
            firebase_status = await get_firebase_service_status()
            ai_status = await self.get_gemini_health_status()
            firebase_healthy = firebase_status.get("status") == "active"
            ai_healthy = ai_status.get("status") == "active"
            
            if firebase_healthy and ai_healthy:
                overall_status = "active"
            elif firebase_healthy:
                overall_status = "degraded"
            else:
                overall_status = "error"
                
            return {
                "overall_status": overall_status,
                "firebase_status": firebase_status,
                "ai_status": ai_status,
                "features": {
                    "conversation_flow": firebase_healthy,
                    "ai_responses": ai_healthy,
                    "fallback_mode": firebase_healthy and not ai_healthy,
                    "whatsapp_integration": True,
                    "lead_collection": firebase_healthy,
                    "intelligent_notifications": True
                },
                "gemini_available": self.gemini_available,
                "fallback_mode": not self.gemini_available
            }
        except Exception as e:
            logger.error(f"Error getting overall service status: {str(e)}")
            return {
                "overall_status": "error",
                "error": str(e)
            }

    async def _get_or_create_session(self, session_id: str, platform: str, phone_number: Optional[str] = None) -> Dict[str, Any]:
        """Criar ou obter sessão - inicia direto no fluxo"""
        logger.info(f"Getting/creating session {session_id} for platform {platform}")
        
        session_data = await get_user_session(session_id)
        
        if session_data:
            logger.info(f"🔍 SESSÃO EXISTENTE ENCONTRADA:")
            logger.info(f"   - Session ID: {session_id}")
            logger.info(f"   - Current Step: {session_data.get('current_step')}")
            logger.info(f"   - Flow Completed: {session_data.get('flow_completed')}")
            logger.info(f"   - Session Ended: {session_data.get('session_ended')}")
            logger.info(f"   - WhatsApp Authorized: {session_data.get('whatsapp_authorized')}")
            logger.info(f"   - Has Lead Data: {bool(session_data.get('lead_data'))}")
            logger.info(f"   - Message Count: {session_data.get('message_count', 0)}")
            
            is_ended = session_data.get("session_ended", False)
            is_completed = session_data.get("flow_completed", False)
            
            if is_ended or is_completed:
                logger.warning(f"⚠️ Sessão {session_id} estava encerrada/completada - RESETANDO para novo fluxo")
                
                whatsapp_auth = session_data.get("whatsapp_authorized", False)
                auth_source = session_data.get("authorization_source", "")
                old_phone = session_data.get("phone_number", phone_number)
                
                session_data = {
                    "session_id": session_id,
                    "platform": platform,
                    "created_at": ensure_utc(datetime.now(timezone.utc)),
                    "current_step": "greeting",
                    "lead_data": {},
                    "message_count": 0,
                    "flow_completed": False,
                    "phone_submitted": False,
                    "lawyers_notified": False,
                    "last_updated": ensure_utc(datetime.now(timezone.utc)),
                    "first_interaction": True,
                    "whatsapp_authorized": whatsapp_auth if platform == "whatsapp" else False,
                    "authorization_source": auth_source,
                    "session_ended": False,
                    "phone_number": old_phone if platform == "whatsapp" else phone_number,
                    "reset_count": session_data.get("reset_count", 0) + 1,
                    "previous_session_ended_at": session_data.get("ended_at")
                }
                
                await save_user_session(session_id, session_data)
                logger.info(f"✨ Sessão RESETADA com sucesso - Session: {session_id}")
                return session_data
        
        if not session_data:
            session_data = {
                "session_id": session_id,
                "platform": platform,
                "created_at": ensure_utc(datetime.now(timezone.utc)),
                "current_step": "greeting",
                "lead_data": {},
                "message_count": 0,
                "flow_completed": False,
                "phone_submitted": False,
                "lawyers_notified": False,
                "last_updated": ensure_utc(datetime.now(timezone.utc)),
                "first_interaction": True,
                "whatsapp_authorized": False,
                "session_ended": False
            }
            logger.info(f"✨ NOVA SESSÃO CRIADA - Session: {session_id}")
            await save_user_session(session_id, session_data)
            
        if phone_number:
            session_data["phone_number"] = phone_number
            
        return session_data

    def _is_phone_number(self, message: str) -> bool:
        clean_message = ''.join(filter(str.isdigit, (message or "")))
        return 10 <= len(clean_message) <= 13

    def _get_flow_steps(self, platform: str = "web") -> Dict[str, Dict]:
        """
        🎯 FLUXO FINAL OTIMIZADO
        
        WhatsApp: Greeting → Nome → Área → Detalhes → Horário → Confirmação → Completed
        Web: Greeting → Nome → Área → Detalhes → Telefone → Confirmação → Completed
        
        ✅ WhatsApp pergunta horário preferencial (já tem o número)
        ✅ Web pergunta telefone normalmente
        ✅ Notificação dos advogados após confirmação final
        """
        
        if platform == "whatsapp":
            phone_step_question = "Obrigado pelos detalhes, {user_name}! 📝\n\nPara organizarmos o melhor atendimento, qual o melhor horário para nossos advogados entrarem em contato com você?\n\n🕐 Manhã (8h-12h)\n🕐 Tarde (12h-18h)\n🕐 Noite (18h-20h)\n\nOu fique à vontade para sugerir um horário específico!"
            phone_step_field = "preferred_contact_time"
        else:
            phone_step_question = "Obrigado pelos detalhes, {user_name}! 📝\n\nEstamos quase finalizando, preciso do seu WhatsApp com DDD (ex: 11999999999):"
            phone_step_field = "phone"
        
        return {
            "greeting": {
                "question": self._get_personalized_greeting(),
                "field": None,
                "next_step": "step1_name"
            },
            "step1_name": {
                "question": "Qual é o seu nome completo? 😊",
                "field": "identification",
                "next_step": "step3_area"
            },
            "step3_area": {
                "question": "Prazer em conhecê-lo, {user_name}! 🤝\n\nEm qual área do direito você precisa de nossa ajuda?\n\n⚖️ Direito Penal (crimes, investigações, defesas)\n🏥 Direito da Saúde (planos de saúde, ações médicas, liminares)\n\nQual dessas áreas tem a ver com sua situação?",
                "field": "area_qualification",
                "next_step": "step4_details"
            },
            "step4_details": {
                "question": "Entendi, {user_name}. 💼\n\nPara nossos advogados já terem uma visão completa, me conte:\n\n• Sua situação já está na justiça ou é algo que acabou de acontecer?\n• Tem algum prazo urgente ou audiência marcada?\n• Em que cidade isso está ocorrendo?\n\nFique à vontade para me contar os detalhes! 🤝",
                "field": "case_details",
                "next_step": "phone_collection"
            },
            "phone_collection": {
                "question": phone_step_question,
                "field": phone_step_field,
                "next_step": "step5_confirmation"
            },
            "step5_confirmation": {
                "question": "Perfeito, {user_name}! 🙏\n\nVou registrar todas essas informações para que o advogado responsável já entenda completamente seu caso e possa te ajudar com agilidade.\n\nEm alguns minutos você estará falando diretamente com um especialista. Podemos prosseguir? 🚀",
                "field": "confirmation",
                "next_step": "completed"
            }
        }

    def _validate_answer(self, answer: str, step: str, platform: str = "web") -> tuple[bool, str]:
        """
        ✅ VALIDAÇÃO OTIMIZADA
        """
        error_message = ""
        
        if not answer or len(answer.strip()) < 2:
            return False, "Por favor, forneça uma resposta válida."
            
        if step == "step1_name":
            if len(answer.split()) < 2:
                return False, "Por favor, informe seu nome completo (nome e sobrenome)."
            return True, ""
            
        elif step == "step3_area":
            keywords = ['penal', 'saude', 'saúde', 'criminal', 'liminar', 'medic', 'plano']
            if not any(keyword in answer.lower() for keyword in keywords):
                return False, "Por favor, escolha entre Direito Penal ou Direito da Saúde."
            return True, ""
            
        elif step == "step4_details":
            if len(answer.strip()) < 15:
                return False, "Por favor, me conte mais detalhes sobre sua situação para que possamos ajudá-lo melhor."
            return True, ""
            
        elif step == "phone_collection":
            if platform == "whatsapp":
                horario_keywords = ['manhã', 'manha', 'tarde', 'noite', 'horário', 'horario', 'h', ':', 'qualquer', 'tanto faz', 'não me importo']
                if not any(keyword in answer.lower() for keyword in horario_keywords) and not any(char.isdigit() for char in answer):
                    return False, "Por favor, me diga qual o melhor horário para contato (manhã, tarde ou noite)."
                return True, ""
            else:
                phone_clean = ''.join(filter(str.isdigit, answer))
                if len(phone_clean) < 10 or len(phone_clean) > 13:
                    return False, "Por favor, digite um número de WhatsApp válido com DDD (ex: 11999999999)."
                return True, ""
            
        elif step == "step5_confirmation":
            confirmation_words = ['sim', 'ok', 'pode', 'vamos', 'claro', 'aceito', 'concordo']
            if not any(word in answer.lower() for word in confirmation_words):
                return False, "Por favor, confirme se podemos prosseguir (responda 'sim' ou 'ok')."
            return True, ""
            
        return True, ""

    def _extract_phone_from_text(self, text: str) -> str:
        """Extrai telefone de qualquer texto"""
        phone_match = re.search(r'(\d{10,11})', text or "")
        return phone_match.group(1) if phone_match else ""

    async def _process_conversation_flow(self, session_data: Dict[str, Any], message: str) -> str:
        """
        ✅ FLUXO CONVERSACIONAL OTIMIZADO
        
        WhatsApp: Coleta horário preferencial (já tem telefone da sessão)
        Web: Coleta telefone normalmente
        """
        try:
            session_id = session_data["session_id"]
            current_step = session_data.get("current_step", "greeting")
            lead_data = session_data.get("lead_data", {})
            is_first_interaction = session_data.get("first_interaction", False)
            platform = session_data.get("platform", "web")
            lead_type = session_data.get("lead_type", "landing_chat_lead")
            
            if session_data.get("session_ended", False):
                logger.info(f"🔚 Sessão encerrada - Session: {session_id}")
                user_name = lead_data.get("identification", "").split()[0] if lead_data.get("identification") else ""
                return f"Esta conversa já foi finalizada, {user_name}. Nossa equipe entrará em contato em breve!"
            
            logger.info(f"Processing conversation - Step: {current_step}, Message: '{message[:50]}...', Platform: {platform}")
            
            flow_steps = self._get_flow_steps(platform)

            if is_first_interaction:
                session_data["first_interaction"] = False
                session_data["current_step"] = "step1_name"
                await save_user_session(session_id, session_data)
                
                greeting_msg = flow_steps["greeting"]["question"]
                name_question = flow_steps["step1_name"]["question"]
                return f"{greeting_msg}\n\n{name_question}"
            
            if current_step == "greeting":
                session_data["current_step"] = "step1_name"
                await save_user_session(session_id, session_data)
                return flow_steps["step1_name"]["question"]

            if current_step == "completed":
                user_name = lead_data.get("identification", "").split()[0] if lead_data.get("identification") else ""
                return f"Obrigado, {user_name}! Nossa equipe já foi notificada e entrará em contato em breve. 😊"
            
            if current_step == "phone_collection":
                if platform == "whatsapp":
                    is_valid, error_msg = self._validate_answer(message, current_step, platform)
                    if not is_valid:
                        return error_msg
                    
                    lead_data["preferred_contact_time"] = message.strip()
                    
                    phone_from_session = session_data.get("phone_number", "")
                    if phone_from_session:
                        lead_data["phone"] = phone_from_session
                        logger.info(f"✅ Usando telefone da sessão WhatsApp: {phone_from_session}")
                    else:
                        logger.warning(f"⚠️ Telefone não encontrado na sessão WhatsApp: {session_id}")
                    
                    session_data["lead_data"] = lead_data
                    session_data["phone_submitted"] = True
                    session_data["current_step"] = "step5_confirmation"
                    await save_user_session(session_id, session_data)
                    
                    return self._interpolate_message(flow_steps["step5_confirmation"]["question"], lead_data)
                
                else:
                    is_valid, error_msg = self._validate_answer(message, current_step, platform)
                    if not is_valid:
                        return error_msg
                    
                    phone_clean = ''.join(filter(str.isdigit, message))
                    lead_data["phone"] = phone_clean
                    session_data["lead_data"] = lead_data
                    session_data["phone_submitted"] = True
                    session_data["current_step"] = "step5_confirmation"
                    await save_user_session(session_id, session_data)
                    
                    return self._interpolate_message(flow_steps["step5_confirmation"]["question"], lead_data)

            if current_step in flow_steps:
                step_config = flow_steps[current_step]
                
                is_valid, error_msg = self._validate_answer(message, current_step, platform)
                if not is_valid:
                    return error_msg
                
                field_name = step_config["field"]
                if field_name:
                    lead_data[field_name] = message.strip()
                session_data["lead_data"] = lead_data

                next_step = step_config["next_step"]
                
                if next_step == "completed":
                    session_data["current_step"] = "completed"
                    session_data["flow_completed"] = True
                    await save_user_session(session_id, session_data)
                    return await self._handle_lead_finalization(session_id, session_data)
                    
                else:
                    session_data["current_step"] = next_step
                    await save_user_session(session_id, session_data)
                    
                    next_step_config = flow_steps[next_step]
                    return self._interpolate_message(next_step_config["question"], lead_data)

            logger.warning(f"Invalid state: {current_step}, resetting")
            session_data["current_step"] = "greeting"
            session_data["first_interaction"] = True
            await save_user_session(session_id, session_data)
            return self._get_personalized_greeting()

        except Exception as e:
            logger.error(f"Exception in conversation flow: {str(e)}")
            return self._get_personalized_greeting()

    def _interpolate_message(self, message: str, lead_data: Dict[str, Any]) -> str:
        """Interpolar dados do usuário na mensagem"""
        try:
            if not message:
                return "Como posso ajudá-lo?"
                
            user_name = lead_data.get("identification", "")
            if user_name and "{user_name}" in message:
                first_name = user_name.split()[0]
                message = message.replace("{user_name}", first_name)
                
            area = lead_data.get("area_qualification", "")
            if area and "{area}" in message:
                message = message.replace("{area}", area)
                
            return message
        except Exception as e:
            logger.error(f"Error interpolating message: {str(e)}")
            return message

    async def _handle_lead_finalization(self, session_id: str, session_data: Dict[str, Any]) -> str:
        """
        🎯 FINALIZAÇÃO INTELIGENTE COM NOTIFICAÇÃO GARANTIDA DOS ADVOGADOS
        
        Chamado APÓS a confirmação final do usuário
        ✅ AJUSTE 2: Notificação direta sem depender de critérios de qualificação
        """
        try:
            logger.info(f"Lead finalization for session: {session_id}")
            
            lead_data = session_data.get("lead_data", {})
            platform = session_data.get("platform", "web")
            user_name = lead_data.get("identification", "Cliente")
            first_name = user_name.split()[0] if user_name else "Cliente"
            area = lead_data.get("area_qualification", "não especificada")
            case_details = lead_data.get("case_details", "aguardando mais detalhes")
            
            phone_clean = lead_data.get("phone", "")
            if not phone_clean:
                phone_clean = session_data.get("phone_number", "")
                
            if not phone_clean or len(phone_clean) < 10:
                return f"Para finalizar, {first_name}, preciso do seu WhatsApp com DDD (ex: 11999999999):"

            phone_formatted = self._format_brazilian_phone(phone_clean)
            
            session_data.update({
                "phone_number": phone_clean,
                "phone_formatted": phone_formatted,
                "phone_submitted": True,
                "lead_qualified": True,
                "last_updated": ensure_utc(datetime.now(timezone.utc))
            })
            
            if "lead_data" not in session_data:
                session_data["lead_data"] = {}
            session_data["lead_data"]["phone"] = phone_clean
            
            await save_user_session(session_id, session_data)

            notification_success = False
            try:
                if not session_data.get("lawyers_notified", False):
                    logger.info(f"🚀 NOTIFICANDO ADVOGADOS (fluxo completo) - Session: {session_id} | Lead: {user_name} | Área: {area}")
                    
                    notification_result = await lawyer_notification_service.notify_lawyers_of_new_lead(
                        lead_name=user_name,
                        lead_phone=phone_clean,
                        category=area,
                        additional_info={
                            "case_details": case_details,
                            "urgency": "high" if platform == "whatsapp" else "normal",
                            "platform": platform,
                            "session_id": session_id,
                            "engagement_level": session_data.get("message_count", 0),
                            "current_step": "completed",
                            "lead_source": f"{platform}_completed_flow",
                            "preferred_contact_time": lead_data.get("preferred_contact_time", "não informado"),
                            "flow_completed": True
                        }
                    )
                    
                    if notification_result.get("success"):
                        session_data["lawyers_notified"] = True
                        session_data["lawyers_notified_at"] = ensure_utc(datetime.now(timezone.utc))
                        await save_user_session(session_id, session_data)
                        notification_success = True
                        logger.info(f"✅ Advogados notificados com sucesso - Session: {session_id}")
                    else:
                        logger.error(f"❌ Falha na notificação dos advogados - Session: {session_id}: {notification_result}")
                else:
                    logger.info(f"ℹ️ Advogados já foram notificados anteriormente - Session: {session_id}")
                    notification_success = True
                    
            except Exception as notification_error:
                logger.error(f"❌ Erro ao notificar advogados - Session: {session_id}: {str(notification_error)}")

            try:
                answers = []
                field_mapping = {
                    "identification": {"id": 1, "field": "name", "answer": lead_data.get("identification", "")},
                    "area_qualification": {"id": 3, "field": "area", "answer": lead_data.get("area_qualification", "")},
                    "case_details": {"id": 4, "field": "details", "answer": lead_data.get("case_details", "")},
                    "phone": {"id": 99, "field": "phone", "answer": phone_clean},
                    "preferred_contact_time": {"id": 98, "field": "contact_time", "answer": lead_data.get("preferred_contact_time", "não informado")},
                    "confirmation": {"id": 5, "field": "confirmation", "answer": lead_data.get("confirmation", "")}
                }
                
                for field, data in field_mapping.items():
                    if data["answer"]:
                        answers.append(data)

                lead_id = await save_lead_data({"answers": answers})
                logger.info(f"Lead saved with ID: {lead_id}")
                    
            except Exception as save_error:
                logger.error(f"Error saving lead: {str(save_error)}")

            whatsapp_success = False
            if platform == "web":
                strategic_message = self._get_strategic_whatsapp_message(user_name, area, phone_formatted)

                try:
                    send_result = await evolution_service.send_text_message(phone_formatted, strategic_message)
                    if send_result.get("success"):
                        logger.info(f"📱 WhatsApp estratégico enviado com sucesso para {phone_formatted}")
                        whatsapp_success = True
                    else:
                        logger.error(f"❌ Erro ao enviar WhatsApp estratégico: {send_result.get('error')}")
                except Exception as whatsapp_error:
                    logger.error(f"❌ Erro ao enviar WhatsApp estratégico: {str(whatsapp_error)}")

            notification_status = ""
            if notification_success:
                notification_status = " ⚡ Nossa equipe foi imediatamente notificada!"
            
            final_message = f"""Perfeito, {first_name}! ✅

Todas suas informações foram registradas com sucesso{notification_status}

Um advogado experiente do m.lima entrará em contato com você em breve para dar prosseguimento ao seu caso com toda atenção necessária.

{'📱 Mensagem de confirmação enviada no seu WhatsApp!' if whatsapp_success else '📝 Suas informações foram salvas com segurança.'}

Você fez a escolha certa ao confiar no escritório m.lima para cuidar do seu caso!

Em alguns minutos, um especialista entrará em contato."""

            return final_message
            
        except Exception as e:
            logger.error(f"Error in lead finalization: {str(e)}")
            user_name = session_data.get("lead_data", {}).get("identification", "")
            first_name = user_name.split()[0] if user_name else ""
            return f"Obrigado pelas informações, {first_name}! Nossa equipe entrará em contato em breve."

    async def _handle_phone_collection(self, phone_message: str, session_id: str, session_data: Dict[str, Any]) -> str:
        """
        ✅ COLETA DE TELEFONE SIMPLIFICADA (apenas para Web)
        """
        platform = session_data.get("platform", "web")

        if platform == "whatsapp":
            logger.info("⚡ WhatsApp usando telefone da sessão - redirecionando para finalização")
            return await self._handle_lead_finalization(session_id, session_data)

        try:
            phone_clean = ''.join(filter(str.isdigit, phone_message))
            user_name = session_data.get("lead_data", {}).get("identification", "")
            first_name = user_name.split()[0] if user_name else ""
            
            if len(phone_clean) < 10 or len(phone_clean) > 13:
                return f"Ops, {first_name}! Número inválido. Digite seu WhatsApp com DDD (ex: 11999999999):"

            if "lead_data" not in session_data:
                session_data["lead_data"] = {}

            session_data["lead_data"]["phone"] = phone_clean
            return await self._handle_lead_finalization(session_id, session_data)
            
        except Exception as e:
            logger.error(f"Error in phone collection: {str(e)}")
            user_name = session_data.get("lead_data", {}).get("identification", "")
            first_name = user_name.split()[0] if user_name else ""
            return f"Obrigado, {first_name}! Nossa equipe entrará em contato em breve."

    async def process_message(self, message: str, session_id: str, phone_number: Optional[str] = None, platform: str = "web") -> Dict[str, Any]:
        """
        🎯 PROCESSAMENTO PRINCIPAL OTIMIZADO
        
        WhatsApp: Greeting + Nome → Área → Detalhes → Horário → Confirmação → Notificação
        Web: Greeting + Nome → Área → Detalhes → Telefone → Confirmação → Notificação
        
        ✅ AJUSTE 3: WhatsApp só inicia fluxo se vier com ficha autorizada da landing page
        """
        try:
            logger.info(f"Processing message - Session: {session_id}, Platform: {platform}")
            logger.info(f"Message: '{message}'")

            if not session_id or session_id.strip() == "":
                return {
                    "response_type": "no_session",
                    "platform": platform,
                    "response": "⚠️ Para continuar, você precisa gerar sua ficha na nossa landing page.",
                    "flow_completed": False,
                    "lawyers_notified": False
                }    

            session_data = await self._get_or_create_session(session_id, platform, phone_number)
            
            if platform == "whatsapp":
                whatsapp_authorized = session_data.get("whatsapp_authorized", False)
                authorization_source = session_data.get("authorization_source", "")
                lead_data = session_data.get("lead_data", {})
                
                if not whatsapp_authorized and not lead_data:
                    logger.warning(f"🚫 WhatsApp não autorizado - Session: {session_id} | Bloqueando acesso")
                    return {
                        "response_type": "whatsapp_unauthorized",
                        "platform": platform,
                        "session_id": session_id,
                        "response": self._get_whatsapp_unauthorized_message(),
                        "flow_completed": False,
                        "lawyers_notified": False,
                        "whatsapp_authorized": False
                    }
                
                if lead_data and not whatsapp_authorized:
                    session_data["whatsapp_authorized"] = True
                    await save_user_session(session_id, session_data)
                    logger.info(f"✅ WhatsApp autorizado via lead_data - Session: {session_id}")
            
            lead_type = session_data.get("lead_type", "landing_chat_lead")

            if platform == "whatsapp" and phone_number:
                session_data["phone_number"] = phone_number
                if "lead_data" not in session_data:
                    session_data["lead_data"] = {}
                session_data["lead_data"]["phone"] = phone_number
                logger.info(f"📱 Número salvo na sessão WhatsApp: {phone_number}")

            response = await self._process_conversation_flow(session_data, message)
            
            session_data["message_count"] = session_data.get("message_count", 0) + 1
            session_data["last_updated"] = ensure_utc(datetime.now(timezone.utc))
            await save_user_session(session_id, session_data)
            
            result = {
                "response_type": f"{platform}_flow",
                "platform": platform,
                "session_id": session_id,
                "response": response,
                "ai_mode": False,
                "current_step": session_data.get("current_step"),
                "flow_completed": session_data.get("flow_completed", False),
                "lawyers_notified": session_data.get("lawyers_notified", False),
                "phone_submitted": session_data.get("phone_submitted", False),
                "lead_data": session_data.get("lead_data", {}),
                "message_count": session_data.get("message_count", 1),
                "whatsapp_authorized": session_data.get("whatsapp_authorized", platform != "whatsapp"),
                "session_ended": session_data.get("session_ended", False),
                "qualification_score": self._calculate_qualification_score(
                    session_data.get("lead_data", {}), platform
                )
            }
            
            if not result.get("response") or not isinstance(result["response"], str):
                result["response"] = "Como posso ajudá-lo hoje?"
                logger.warning(f"⚠️ Response vazio corrigido para session {session_id}")
            
            return result

        except Exception as e:
            logger.error(f"Exception in process_message: {str(e)}")
            return {
                "response_type": "orchestration_error",
                "platform": platform,
                "session_id": session_id,
                "response": self._get_personalized_greeting() or "Olá! Como posso ajudá-lo?",
                "error": str(e)
            }

    async def handle_whatsapp_authorization(self, auth_data: Dict[str, Any]):
        """
        🎯 HANDLER PARA AUTORIZAÇÃO WHATSAPP
        
        ✅ Marca a sessão como autorizada quando vem da landing page
        """
        try:
            session_id = auth_data.get("session_id", "")
            phone_number = auth_data.get("phone_number", "")
            source = auth_data.get("source", "unknown")
            user_data = auth_data.get("user_data", {})
            
            logger.info(f"🎯 Processando autorização WhatsApp - Session: {session_id}, Phone: {phone_number}, Source: {source}")
            
            if user_data and source == "landing_chat":
                session_data = {
                    "session_id": session_id,
                    "platform": "whatsapp",
                    "phone_number": phone_number,
                    "created_at": ensure_utc(datetime.now(timezone.utc)),
                    "current_step": "completed",
                    "lead_data": {
                        "identification": user_data.get("name", ""),
                        "area_qualification": user_data.get("area", "não especificada"),
                        "case_details": user_data.get("problem", "Detalhes do chat da landing"),
                        "phone": phone_number,
                        "confirmation": "sim"
                    },
                    "message_count": 1,
                    "flow_completed": True,
                    "phone_submitted": True,
                    "lead_qualified": True,
                    "lawyers_notified": False,
                    "whatsapp_authorized": True,
                    "session_ended": False,
                    "last_updated": ensure_utc(datetime.now(timezone.utc)),
                    "first_interaction": False,
                    "authorization_source": source
                }
                
                await save_user_session(session_id, session_data)
                
                notification_result = await self.notify_lawyers_if_qualified(session_id, session_data, "whatsapp")
                
                logger.info(f"✅ Sessão pré-populada criada para lead da landing - Session: {session_id}")
                
            else:
                session_data = await get_user_session(session_id)
                if session_data:
                    session_data["whatsapp_authorized"] = True
                    session_data["authorization_source"] = source
                    await save_user_session(session_id, session_data)
                    logger.info(f"✅ Sessão autorizada via botão - Session: {session_id}")
                else:
                    session_data = {
                        "session_id": session_id,
                        "platform": "whatsapp",
                        "phone_number": phone_number,
                        "created_at": ensure_utc(datetime.now(timezone.utc)),
                        "current_step": "greeting",
                        "lead_data": {},
                        "message_count": 0,
                        "flow_completed": False,
                        "phone_submitted": False,
                        "lawyers_notified": False,
                        "whatsapp_authorized": True,
                        "session_ended": False,
                        "last_updated": ensure_utc(datetime.now(timezone.utc)),
                        "first_interaction": True,
                        "authorization_source": source
                    }
                    await save_user_session(session_id, session_data)
                    logger.info(f"✅ Nova sessão autorizada criada - Session: {session_id}")
            
            return {
                "status": "authorization_processed",
                "session_id": session_id,
                "phone_number": phone_number,
                "source": source,
                "whatsapp_authorized": True,
                "pre_populated": bool(user_data and source == "landing_chat")
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no processamento da autorização WhatsApp: {str(e)}")
            return {
                "status": "authorization_error",
                "error": str(e)
            }

    async def handle_phone_number_submission(self, phone_number: str, session_id: str) -> Dict[str, Any]:
        """Handle phone number submission from web interface."""
        try:
            logger.info(f"Phone number submission for session {session_id}: {phone_number}")
            session_data = await get_user_session(session_id) or {}
            response = await self._handle_phone_collection(phone_number, session_id, session_data)
            return {
                "status": "success",
                "message": response,
                "phone_submitted": True
            }
        except Exception as e:
            logger.error(f"Error in phone submission: {str(e)}")
            return {
                "status": "error",
                "message": "Erro ao processar número de WhatsApp",
                "error": str(e)
            }

    async def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get current session context and status."""
        try:
            session_data = await get_user_session(session_id)
            if not session_data:
                return {"exists": False}

            context = {
                "exists": True,
                "session_id": session_id,
                "platform": session_data.get("platform", "unknown"),
                "current_step": session_data.get("current_step"),
                "flow_completed": session_data.get("flow_completed", False),
                "phone_submitted": session_data.get("phone_submitted", False),
                "lawyers_notified": session_data.get("lawyers_notified", False),
                "whatsapp_authorized": session_data.get("whatsapp_authorized", False),
                "session_ended": session_data.get("session_ended", False),
                "lead_data": session_data.get("lead_data", {}),
                "message_count": session_data.get("message_count", 0),
                "qualification_score": self._calculate_qualification_score(
                    session_data.get("lead_data", {}), 
                    session_data.get("platform", "web")
                )
            }
            
            return context
        except Exception as e:
            logger.error(f"Error getting session context: {str(e)}")
            return {"exists": False, "error": str(e)}


intelligent_orchestrator = IntelligentHybridOrchestrator()
hybrid_orchestrator = intelligent_orchestrator