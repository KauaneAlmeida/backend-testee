"""
AI Chain Service with LangChain + Gemini Integration (Fallback Ready)

Este módulo gerencia conversas usando LangChain + Gemini,
mas também funciona em "modo fallback" caso não exista GEMINI_API_KEY.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# LangChain imports
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

# Configure logging
logger = logging.getLogger(__name__)

# Global conversation memories (session-based)
conversation_memories: Dict[str, ConversationBufferWindowMemory] = {}

# AI configuration
AI_CONFIG_FILE = "app/ai_schema.json"
DEFAULT_MODEL = "gemini-1.5-flash"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1000
MEMORY_WINDOW = 10


def load_ai_config() -> Dict[str, Any]:
    try:
        if os.path.exists(AI_CONFIG_FILE):
            with open(AI_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("✅ AI configuration loaded from file")
                return config
        else:
            logger.warning("⚠️ AI config file not found, using defaults")
            return get_default_ai_config()
    except Exception as e:
        logger.error(f"❌ Error loading AI config: {str(e)}")
        return get_default_ai_config()


def get_default_ai_config() -> Dict[str, Any]:
    return {
        "system_prompt": "Você é um assistente jurídico do escritório. "
                         "Mantenha respostas claras, profissionais e em português.",
        "ai_config": {
            "model": DEFAULT_MODEL,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "memory_window": MEMORY_WINDOW,
            "timeout": 30
        }
    }


def get_conversation_memory(session_id: str) -> ConversationBufferWindowMemory:
    if session_id not in conversation_memories:
        conversation_memories[session_id] = ConversationBufferWindowMemory(
            k=MEMORY_WINDOW,
            return_messages=True,
            memory_key="chat_history"
        )
        logger.info(f"🧠 Created new conversation memory for session: {session_id}")
    return conversation_memories[session_id]


def clear_conversation_memory(session_id: str) -> bool:
    try:
        if session_id in conversation_memories:
            conversation_memories[session_id].clear()
            logger.info(f"🧹 Cleared conversation memory for session: {session_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error clearing memory for session {session_id}: {str(e)}")
        return False


def get_conversation_summary(session_id: str) -> str:
    try:
        if session_id in conversation_memories:
            memory = conversation_memories[session_id]
            messages = memory.chat_memory.messages
            if not messages:
                return "No conversation history"

            summary_parts = []
            for message in messages[-6:]:
                if isinstance(message, HumanMessage):
                    summary_parts.append(f"User: {message.content[:100]}...")
                elif isinstance(message, AIMessage):
                    summary_parts.append(f"AI: {message.content[:100]}...")
            return "\n".join(summary_parts)
        return "No conversation found"
    except Exception as e:
        logger.error(f"❌ Error getting conversation summary: {str(e)}")
        return "Error retrieving summary"


class AIOrchestrator:
    def __init__(self):
        self.config = load_ai_config()
        self.ai_config = self.config.get("ai_config", {})
        self.system_prompt = self.config.get("system_prompt", "")
        self.llm = None
        self.chain = None
        self.fallback_mode = False
        self._initialize_llm()

    def _initialize_llm(self):
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("⚠️ GEMINI_API_KEY não configurada. IA em modo fallback.")
                self.fallback_mode = True
                return

            self.llm = ChatGoogleGenerativeAI(
                model=self.ai_config.get("model", DEFAULT_MODEL),
                temperature=self.ai_config.get("temperature", DEFAULT_TEMPERATURE),
                max_tokens=self.ai_config.get("max_tokens", DEFAULT_MAX_TOKENS),
                google_api_key=api_key
            )
            self._create_chain()
            logger.info(f"✅ AI Orchestrator initialized with model: {self.ai_config.get('model', DEFAULT_MODEL)}")
        except Exception as e:
            logger.error(f"❌ Error initializing AI Orchestrator: {str(e)}")
            self.fallback_mode = True
            self.llm = None
            self.chain = None

    def _create_chain(self):
        if not self.llm:
            return
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}")
            ])
            self.chain = (
                RunnablePassthrough.assign(
                    chat_history=lambda x: x["chat_history"]
                )
                | prompt
                | self.llm
                | StrOutputParser()
            )
            logger.info("✅ LangChain conversation chain created")
        except Exception as e:
            logger.error(f"❌ Error creating conversation chain: {str(e)}")
            self.chain = None

    async def generate_response(
        self,
        message: str,
        session_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        try:
            # Modo fallback → sem IA real
            if self.fallback_mode or not self.chain:
                logger.info("⚠️ Fallback mode ativo, retornando resposta padrão")
                return f"Recebi sua mensagem: '{message}'. Nossa equipe retornará em breve."

            memory = get_conversation_memory(session_id)
            enhanced_message = message
            if context and context.get("platform"):
                platform = context["platform"].upper()
                enhanced_message = f"[Platform: {platform}] {message}"

            chain_input = {
                "input": enhanced_message,
                "chat_history": memory.chat_memory.messages
            }

            response = await self.chain.ainvoke(chain_input)
            memory.save_context({"input": enhanced_message}, {"output": response})
            return response
        except Exception as e:
            logger.error(f"❌ Error generating AI response: {str(e)}")
            return "Desculpe, ocorreu um erro ao processar sua mensagem."

    def is_available(self) -> bool:
        return not self.fallback_mode and self.llm is not None and self.chain is not None


# Global AI orchestrator
ai_orchestrator = AIOrchestrator()


async def process_chat_message(message: str, session_id: str = "default", context: Optional[Dict[str, Any]] = None) -> str:
    try:
        if not ai_orchestrator.is_available():
            return f"Recebi sua mensagem: '{message}'. Nossa equipe vai entrar em contato em breve."
        return await ai_orchestrator.generate_response(message, session_id, context)
    except Exception as e:
        logger.error(f"❌ Error in process_chat_message: {str(e)}")
        return "Desculpe, ocorreu um erro inesperado."


async def get_ai_service_status() -> Dict[str, Any]:
    try:
        api_key_configured = bool(os.getenv("GEMINI_API_KEY"))
        ai_available = ai_orchestrator.is_available()
        return {
            "service": "ai_chain_langchain_gemini",
            "status": "active" if ai_available else "fallback",
            "ai_available": ai_available,
            "api_key_configured": api_key_configured,
            "model": ai_orchestrator.ai_config.get("model", DEFAULT_MODEL),
            "memory_sessions": len(conversation_memories),
            "features": [
                "langchain_integration",
                "conversation_memory",
                "google_gemini_api" if ai_available else "fallback_mode",
                "session_management",
                "context_awareness"
            ]
        }
    except Exception as e:
        logger.error(f"❌ Error getting AI service status: {str(e)}")
        return {"service": "ai_chain_langchain_gemini", "status": "error", "error": str(e)}
