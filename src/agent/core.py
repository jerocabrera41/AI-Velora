"""Core agent using LangGraph for conversation orchestration."""

import json
import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agent.intents import Intent, classify_intent_fallback, parse_llm_intent
from src.agent.prompts import INTENT_CLASSIFICATION_PROMPT, SYSTEM_PROMPT
from src.agent.tools import TOOL_DEFINITIONS, AgentTools
from src.config import settings
from src.database.models import MessageRole
from src.services.conversation_service import ConversationService
from src.services.pms_service import PMSService


# --- State definition ---


class AgentState(TypedDict):
    """State that flows through the LangGraph nodes."""

    # Input
    user_message: str
    guest_phone: str
    conversation_id: str
    hotel_id: str

    # Context gathered during processing
    intent: str
    booking: dict | None
    hotel_info: dict | None

    # Conversation history for the LLM
    messages: list[dict[str, str]]

    # Output
    response: str
    metadata: dict[str, Any]


# --- Agent class ---


class HotelAgent:
    """LangGraph-powered hotel concierge agent."""

    def __init__(
        self,
        pms: PMSService,
        conversation_service: ConversationService,
        hotel_id: uuid.UUID,
    ) -> None:
        self.pms = pms
        self.conversation_service = conversation_service
        self.hotel_id = hotel_id
        self.tools = AgentTools(pms, conversation_service, hotel_id)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("load_context", self._load_context)
        graph.add_node("classify_intent", self._classify_intent)
        graph.add_node("handle_greeting", self._handle_greeting)
        graph.add_node("handle_booking", self._handle_booking)
        graph.add_node("handle_amenities", self._handle_amenities)
        graph.add_node("handle_service_request", self._handle_service_request)
        graph.add_node("handle_faq", self._handle_faq)
        graph.add_node("handle_out_of_scope", self._handle_out_of_scope)
        graph.add_node("generate_response", self._generate_response)

        # Set entry point
        graph.set_entry_point("load_context")

        # Edges
        graph.add_edge("load_context", "classify_intent")

        # Conditional routing based on intent
        graph.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "greeting": "handle_greeting",
                "booking_info": "handle_booking",
                "amenities_query": "handle_amenities",
                "service_request": "handle_service_request",
                "faq_general": "handle_faq",
                "out_of_scope": "handle_out_of_scope",
            },
        )

        # All handlers lead to generate_response
        graph.add_edge("handle_greeting", "generate_response")
        graph.add_edge("handle_booking", "generate_response")
        graph.add_edge("handle_amenities", "generate_response")
        graph.add_edge("handle_service_request", "generate_response")
        graph.add_edge("handle_faq", "generate_response")
        graph.add_edge("handle_out_of_scope", "generate_response")

        # End
        graph.add_edge("generate_response", END)

        return graph.compile()

    # --- Node implementations ---

    async def _load_context(self, state: AgentState) -> dict:
        """Load hotel info and conversation history."""
        logger.info(f"Loading context for conversation {state['conversation_id']}")

        hotel_info = await self.pms.get_hotel(self.hotel_id)

        # Load conversation history
        history = await self.conversation_service.get_conversation_history(
            uuid.UUID(state["conversation_id"]),
            limit=settings.max_conversation_history,
        )

        # Try to find a booking for this guest
        booking = await self.pms.get_booking_by_phone(state["guest_phone"])

        return {
            "hotel_info": hotel_info,
            "messages": history,
            "booking": booking,
        }

    async def _classify_intent(self, state: AgentState) -> dict:
        """Classify the user's intent using the LLM with keyword fallback."""
        message = state["user_message"]
        logger.info(f"Classifying intent for: '{message[:80]}...'")

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

            prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message)
            response = await client.messages.create(
                model=settings.llm_model,
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_intent = response.content[0].text.strip()
            intent = parse_llm_intent(raw_intent)
            logger.info(f"LLM classified intent: {intent.value} (raw: {raw_intent})")

        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}, using fallback")
            intent = classify_intent_fallback(message)

        return {"intent": intent.value}

    def _route_by_intent(self, state: AgentState) -> str:
        """Route to the appropriate handler based on intent."""
        return state["intent"]

    async def _handle_greeting(self, state: AgentState) -> dict:
        """Handle greeting messages."""
        logger.info("Handling greeting intent")
        guest_name = None
        if state.get("booking"):
            guest_name = state["booking"].get("guest_name")

        if guest_name:
            greeting = (
                f"Hola {guest_name}! Bienvenido/a a Hotel Palermo Soho. "
                "Soy Sofia, tu asistente virtual. En que puedo ayudarte?"
            )
        else:
            greeting = (
                "Hola! Bienvenido/a a Hotel Palermo Soho. "
                "Soy Sofia, tu asistente virtual. "
                "Si tenes una reserva, compartime tu numero de confirmacion "
                "y te doy toda la info que necesites."
            )
        return {"response": greeting, "metadata": {"handler": "greeting"}}

    async def _handle_booking(self, state: AgentState) -> dict:
        """Handle booking-related queries using the LLM with tools."""
        logger.info("Handling booking_info intent")
        return await self._llm_with_tools(state, "booking_info")

    async def _handle_amenities(self, state: AgentState) -> dict:
        """Handle amenity queries using the LLM with tools."""
        logger.info("Handling amenities_query intent")
        return await self._llm_with_tools(state, "amenities_query")

    async def _handle_service_request(self, state: AgentState) -> dict:
        """Handle service requests using the LLM with tools."""
        logger.info("Handling service_request intent")
        return await self._llm_with_tools(state, "service_request")

    async def _handle_faq(self, state: AgentState) -> dict:
        """Handle FAQ queries using the LLM with tools."""
        logger.info("Handling faq_general intent")
        return await self._llm_with_tools(state, "faq_general")

    async def _handle_out_of_scope(self, state: AgentState) -> dict:
        """Handle out-of-scope queries with escalation."""
        logger.info("Handling out_of_scope intent")
        return await self._llm_with_tools(state, "out_of_scope")

    async def _generate_response(self, state: AgentState) -> dict:
        """Final response formatting (passthrough, response already set)."""
        logger.info(
            f"Final response generated for conversation {state['conversation_id']} "
            f"(intent={state['intent']})"
        )
        return {}

    # --- LLM interaction ---

    async def _llm_with_tools(self, state: AgentState, intent: str) -> dict:
        """Call Claude with tools to handle a guest query."""
        start_time = time.time()

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

            # Build system prompt with hotel info
            hotel_info = state.get("hotel_info") or {}
            system = SYSTEM_PROMPT.format(
                hotel_name=hotel_info.get("name", "Hotel Palermo Soho"),
                hotel_info=json.dumps(hotel_info, ensure_ascii=False, indent=2),
            )

            # Build messages (history + current message)
            messages = []
            for msg in state.get("messages", []):
                if msg["role"] in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Add booking context if available
            booking = state.get("booking")
            if booking:
                booking_context = (
                    f"[Contexto interno - reserva encontrada para este huesped: "
                    f"{json.dumps(booking, ensure_ascii=False)}]"
                )
                messages.append({"role": "user", "content": booking_context})
                messages.append(
                    {
                        "role": "assistant",
                        "content": "Entendido, tengo los datos de la reserva.",
                    }
                )

            messages.append({"role": "user", "content": state["user_message"]})

            # Call Claude with tools
            response = await client.messages.create(
                model=settings.llm_model,
                max_tokens=1024,
                system=system,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # Process tool calls in a loop
            max_tool_rounds = 3
            for _round in range(max_tool_rounds):
                if response.stop_reason != "tool_use":
                    break

                # Execute tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = await self._execute_tool(
                            block.name,
                            block.input,
                            state,
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(
                                    tool_result, ensure_ascii=False
                                ),
                            }
                        )

                # Continue conversation with tool results
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                response = await client.messages.create(
                    model=settings.llm_model,
                    max_tokens=1024,
                    system=system,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                )

            # Extract final text response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"LLM response generated in {latency_ms}ms")

            return {
                "response": final_text,
                "metadata": {
                    "handler": intent,
                    "latency_ms": latency_ms,
                    "model": settings.llm_model,
                },
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"LLM call failed after {latency_ms}ms: {e}")

            # Fallback response
            fallback_responses = {
                "booking_info": "Disculpa, no pude acceder a la informacion de tu reserva en este momento. Te recomiendo contactar a recepcion al +54 11 4833-1234.",
                "amenities_query": "Disculpa, no pude obtener la informacion en este momento. Podes consultar en recepcion o llamar al +54 11 4833-1234.",
                "service_request": "Disculpa, no pude procesar tu pedido automaticamente. Por favor comunicate con recepcion al +54 11 4833-1234.",
                "faq_general": "Disculpa, no puedo responder tu consulta en este momento. Te recomiendo contactar a recepcion al +54 11 4833-1234.",
                "out_of_scope": "Esa consulta excede lo que puedo resolver. Te comunico con nuestro equipo de recepcion para que puedan ayudarte.",
            }
            return {
                "response": fallback_responses.get(
                    intent,
                    "Disculpa, tuve un problema tecnico. Por favor contacta a recepcion.",
                ),
                "metadata": {
                    "handler": intent,
                    "latency_ms": latency_ms,
                    "error": str(e),
                },
            }

    async def _execute_tool(
        self, tool_name: str, tool_input: dict, state: AgentState
    ) -> Any:
        """Execute a tool call from the LLM."""
        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

        tool_map = {
            "get_booking_details": lambda: self.tools.get_booking_details(
                tool_input["confirmation_number"]
            ),
            "get_booking_by_phone": lambda: self.tools.get_booking_by_phone(
                tool_input["phone"]
            ),
            "get_hotel_amenities": lambda: self.tools.get_hotel_amenities(),
            "get_hotel_policies": lambda: self.tools.get_hotel_policies(),
            "search_faq": lambda: self.tools.search_faq(tool_input["query"]),
            "create_service_request": lambda: self.tools.create_service_request(
                tool_input["booking_id"],
                tool_input["request_type"],
                tool_input["details"],
            ),
            "escalate_to_human": lambda: self.tools.escalate_to_human(
                tool_input.get("conversation_id", state["conversation_id"]),
                tool_input["reason"],
            ),
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            logger.error(f"Unknown tool: {tool_name}")
            return {"error": f"Tool '{tool_name}' not found"}

        try:
            result = await handler()
            logger.debug(f"Tool {tool_name} result: {result}")
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"error": str(e)}

    # --- Public API ---

    async def process_message(
        self,
        user_message: str,
        guest_phone: str,
        conversation_id: uuid.UUID,
    ) -> dict:
        """Process a guest message and return a response.

        This is the main entry point for the agent.
        """
        logger.info(
            f"Processing message from {guest_phone} in conversation {conversation_id}"
        )

        initial_state: AgentState = {
            "user_message": user_message,
            "guest_phone": guest_phone,
            "conversation_id": str(conversation_id),
            "hotel_id": str(self.hotel_id),
            "intent": "",
            "booking": None,
            "hotel_info": None,
            "messages": [],
            "response": "",
            "metadata": {},
        }

        # Run the graph
        result = await self.graph.ainvoke(initial_state)

        return {
            "response": result.get("response", ""),
            "intent": result.get("intent", ""),
            "metadata": result.get("metadata", {}),
        }
