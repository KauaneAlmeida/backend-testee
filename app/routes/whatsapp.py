import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

from app.services.orchestration_service import intelligent_orchestrator
from app.services.evolution_service import evolution_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    try:
        payload = await request.json()
        logger.info(f"📨 WhatsApp webhook recebido: {payload}")

        message_text = payload.get("message", "").strip()
        phone_number = payload.get("from") or payload.get("phone_number", "")
        message_id = payload.get("messageId") or payload.get("message_id", "")
        
        if not message_text or not phone_number:
            logger.error(f"❌ Payload inválido - Message: {message_text}, Phone: {phone_number}")
            raise HTTPException(
                status_code=400, 
                detail="Payload inválido: falta mensagem ou número de telefone"
            )

        # limpar número
        clean_phone = phone_number.replace('@s.whatsapp.net', '').replace('@g.us', '')
        session_id = clean_phone  

        logger.info(f"📱 Mensagem recebida de {clean_phone}: '{message_text[:50]}...'")

        # processar no orchestrator (ele cuida do fluxo + salvar no Firebase)
        orchestrator_result = await intelligent_orchestrator.process_message(
            message=message_text,
            session_id=session_id,
            phone_number=clean_phone,
            platform="whatsapp"
        )

        # resposta do bot
        bot_response = orchestrator_result.get("response", "")
        if not bot_response or not isinstance(bot_response, str):
            bot_response = "Desculpe, ocorreu um erro temporário. Por favor, tente novamente."

        # enviar resposta pro usuário via Evolution
        send_result = await evolution_service.send_text_message(clean_phone, bot_response)

        # log do progresso
        current_step = orchestrator_result.get("current_step", "unknown")
        flow_completed = orchestrator_result.get("flow_completed", False)
        lawyers_notified = orchestrator_result.get("lawyers_notified", False)

        logger.info(
            f"📊 Status - Session: {session_id} | Step: {current_step} | "
            f"Completed: {flow_completed} | Lawyers Notified: {lawyers_notified}"
        )

        return {
            "status": "ok",
            "session_id": session_id,
            "phone": clean_phone,
            "incoming_message": message_text,
            "bot_response": bot_response,
            "message_id": message_id,
            "evolution_send_status": {
                "success": send_result.get("success", False),
                "error": send_result.get("error") if not send_result.get("success") else None
            },
            "flow_info": {
                "current_step": current_step,
                "flow_completed": flow_completed,
                "lawyers_notified": lawyers_notified,
                "qualification_score": orchestrator_result.get("qualification_score", 0)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro crítico no WhatsApp webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no processamento: {str(e)}")


@router.post("/whatsapp/authorize")
async def handle_whatsapp_authorization(auth_data: Dict[str, Any]):
    try:
        session_id = auth_data.get("session_id", "")
        phone_number = auth_data.get("phone_number", "")
        source = auth_data.get("source", "unknown")
        
        logger.info(f"🎯 Autorização WhatsApp - Session: {session_id} | Phone: {phone_number} | Source: {source}")

        # delega pro orchestrator cuidar do salvamento e fluxo
        result = await intelligent_orchestrator.handle_whatsapp_authorization(auth_data)
        return result

    except Exception as e:
        logger.error(f"❌ Erro na autorização WhatsApp: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro na autorização: {str(e)}")


@router.get("/whatsapp/status")
async def check_whatsapp_status():
    try:
        status = await evolution_service.get_instance_status()
        is_active = status.get("success", False) and status.get("status") == "open"
        
        return {
            "status": "ok",
            "evolution_api": {
                "connected": is_active,
                "instance_name": evolution_service.instance_name,
                "state": status.get("status", "unknown"),
                "details": status
            },
            "integration_active": is_active,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "evolution_api": {
                "connected": False,
                "error": str(e)
            },
            "integration_active": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.post("/whatsapp/test")
async def test_whatsapp_message(test_data: Dict[str, Any]):
    try:
        phone = test_data.get("phone", "")
        message = test_data.get("message", "")
        
        if not phone or not message:
            raise HTTPException(status_code=400, detail="Phone e message são obrigatórios")
        
        result = await evolution_service.send_text_message(phone, message)
        
        return {
            "status": "ok",
            "sent": result.get("success", False),
            "phone": phone,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
