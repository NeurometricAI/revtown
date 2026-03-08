"""
Mayor Router - Conversational interface with the GTM Mayor.

Base path: /api/v1/mayor
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import CurrentUser, ScopedBeadStore, ScopedMayor

router = APIRouter()


class ChatMessage(BaseModel):
    """A message in the chat conversation."""
    role: str  # 'user' or 'mayor'
    content: str


class ChatRequest(BaseModel):
    """Request to chat with the Mayor."""
    message: str
    campaign_id: str | None = None
    conversation_history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    """Response from the Mayor."""
    response: str
    is_question: bool = False
    campaign: dict | None = None
    convoy_steps: list[dict] | None = None
    action_taken: str | None = None


def wrap_response(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap response data in standard format."""
    return {
        "data": data,
        "meta": {
            "version": "v1",
            "timestamp": datetime.utcnow().isoformat(),
            **(meta or {}),
        },
    }


# Store for active conversations (in production, use Redis or DB)
_conversations: dict[str, list[ChatMessage]] = {}


@router.post("/chat", response_model=dict)
async def chat_with_mayor(
    request: ChatRequest,
    store: ScopedBeadStore,
    user: CurrentUser,
    mayor: ScopedMayor,
):
    """
    Chat with the GTM Mayor.

    The Mayor can:
    - Answer questions about campaigns
    - Help plan new campaigns
    - Create and manage convoys
    - Provide status updates
    - Ask clarifying questions
    """
    # Build context from conversation history
    history = request.conversation_history

    # Analyze the user's message to determine intent
    intent = await _analyze_intent(request.message, history, mayor)

    # Handle different intents
    if intent["type"] == "create_campaign":
        return await _handle_create_campaign(request, store, mayor, user, intent)

    elif intent["type"] == "campaign_status":
        return await _handle_campaign_status(request, store, mayor, intent)

    elif intent["type"] == "start_convoy":
        return await _handle_start_convoy(request, store, mayor, intent)

    elif intent["type"] == "clarification_needed":
        return wrap_response(ChatResponse(
            response=intent["question"],
            is_question=True,
        ).model_dump())

    elif intent["type"] == "general_question":
        return await _handle_general_question(request, mayor, intent)

    else:
        # Default conversational response
        return await _handle_conversation(request, mayor, history)


async def _analyze_intent(
    message: str,
    history: list[ChatMessage],
    mayor: ScopedMayor,
) -> dict[str, Any]:
    """Analyze the user's message to determine intent."""
    # Build conversation context
    context = "\n".join([f"{m.role}: {m.content}" for m in history[-5:]])

    prompt = f"""You are the GTM Mayor analyzing a user message to determine their intent.

Conversation context:
{context}

User message: {message}

Determine the intent. Respond with JSON:
{{
    "type": "create_campaign" | "campaign_status" | "start_convoy" | "clarification_needed" | "general_question" | "conversation",
    "confidence": 0.0-1.0,
    "extracted_data": {{...}},  // Any relevant data extracted from the message
    "question": "..."  // If clarification_needed, what to ask
}}

Intent types:
- create_campaign: User wants to create a new campaign (look for goals, targets, etc.)
- campaign_status: User asking about existing campaign status
- start_convoy: User wants to start/execute a campaign
- clarification_needed: Need more info to proceed
- general_question: Question about GTM, marketing, etc.
- conversation: General chat/greeting
"""

    try:
        response = await mayor.neurometric.complete(
            task_class="mayor_intent_analysis",
            prompt=prompt,
        )
        return json.loads(response.content)
    except Exception:
        # Default to conversation
        return {"type": "conversation", "confidence": 0.5}


async def _handle_create_campaign(
    request: ChatRequest,
    store: ScopedBeadStore,
    mayor: ScopedMayor,
    user: CurrentUser,
    intent: dict,
) -> dict:
    """Handle campaign creation intent."""
    extracted = intent.get("extracted_data", {})

    # Check if we have enough info
    if not extracted.get("goal"):
        return wrap_response(ChatResponse(
            response="I'd love to help you create a campaign! What's the main goal you want to achieve? For example:\n\n• Generate qualified leads\n• Launch a new product\n• Increase brand awareness\n• Drive signups for an event",
            is_question=True,
        ).model_dump())

    # Create the campaign
    campaign_name = extracted.get("name", f"Campaign {datetime.now().strftime('%Y-%m-%d')}")
    goal = extracted.get("goal")
    budget = extracted.get("budget")
    rigs = extracted.get("rigs", ["content_factory", "sdr_hive"])

    try:
        # Create campaign bead
        campaign = await store.create_campaign({
            "name": campaign_name,
            "goal": goal,
            "budget": budget,
            "rigs_enabled": rigs,
            "status": "draft",
        })

        # Create convoy plan
        convoy = await mayor.create_convoy(
            campaign_id=campaign.id,
            goal=goal,
            budget_cents=int(budget * 100) if budget else None,
        )

        convoy_steps = [
            {
                "id": step.id,
                "rig": step.rig.value,
                "polecat_type": step.polecat_type,
                "status": step.status,
                "description": f"Execute {step.polecat_type} via {step.rig.value}",
            }
            for step in convoy.steps
        ]

        return wrap_response(ChatResponse(
            response=f"I've created your campaign: **{campaign_name}**\n\nGoal: {goal}\n\nI've planned {len(convoy.steps)} steps across the following Rigs to achieve this goal. Review the plan on the right, and let me know when you're ready to start execution!",
            campaign={
                "id": str(campaign.id),
                "name": campaign_name,
                "goal": goal,
                "status": "draft",
            },
            convoy_steps=convoy_steps,
            action_taken="campaign_created",
        ).model_dump())

    except Exception as e:
        return wrap_response(ChatResponse(
            response=f"I encountered an issue creating the campaign: {str(e)}. Can you try rephrasing your request?",
            is_question=True,
        ).model_dump())


async def _handle_campaign_status(
    request: ChatRequest,
    store: ScopedBeadStore,
    mayor: ScopedMayor,
    intent: dict,
) -> dict:
    """Handle campaign status inquiry."""
    campaign_id = request.campaign_id or intent.get("extracted_data", {}).get("campaign_id")

    if not campaign_id:
        # List recent campaigns
        campaigns = await store.list_campaigns(limit=5)
        if not campaigns:
            return wrap_response(ChatResponse(
                response="You don't have any campaigns yet. Would you like to create one? Just tell me what you want to achieve!",
                is_question=True,
            ).model_dump())

        campaign_list = "\n".join([f"• **{c.name}**: {c.status}" for c in campaigns])
        return wrap_response(ChatResponse(
            response=f"Here are your recent campaigns:\n\n{campaign_list}\n\nWhich one would you like to know more about?",
            is_question=True,
        ).model_dump())

    # Get specific campaign status
    try:
        campaign = await store.get_campaign(UUID(campaign_id))
        convoys = mayor.get_active_convoys(UUID(campaign_id))

        if convoys:
            convoy = convoys[-1]
            completed = len([s for s in convoy.steps if s.status == "completed"])
            total = len(convoy.steps)
            progress = f"{completed}/{total} steps completed"

            convoy_steps = [
                {
                    "id": step.id,
                    "rig": step.rig.value,
                    "polecat_type": step.polecat_type,
                    "status": step.status,
                }
                for step in convoy.steps
            ]

            return wrap_response(ChatResponse(
                response=f"**{campaign.name}**\n\nStatus: {convoy.status.value}\nProgress: {progress}\n\nThe convoy is currently {convoy.status.value}. Check the task list on the right for details.",
                campaign={
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "goal": campaign.goal,
                    "status": campaign.status,
                },
                convoy_steps=convoy_steps,
            ).model_dump())
        else:
            return wrap_response(ChatResponse(
                response=f"**{campaign.name}** is in {campaign.status} status but doesn't have an active convoy yet. Would you like me to create an execution plan?",
                campaign={
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "goal": campaign.goal,
                    "status": campaign.status,
                },
                is_question=True,
            ).model_dump())

    except Exception as e:
        return wrap_response(ChatResponse(
            response=f"I couldn't find that campaign. Could you tell me more about which campaign you're asking about?",
            is_question=True,
        ).model_dump())


async def _handle_start_convoy(
    request: ChatRequest,
    store: ScopedBeadStore,
    mayor: ScopedMayor,
    intent: dict,
) -> dict:
    """Handle request to start convoy execution."""
    campaign_id = request.campaign_id

    if not campaign_id:
        return wrap_response(ChatResponse(
            response="Which campaign would you like to start? You can create a new one by telling me your goal.",
            is_question=True,
        ).model_dump())

    try:
        convoys = mayor.get_active_convoys(UUID(campaign_id))
        if not convoys:
            return wrap_response(ChatResponse(
                response="This campaign doesn't have a convoy plan yet. Let me create one first. What's the main goal?",
                is_question=True,
            ).model_dump())

        convoy = convoys[-1]
        started = await mayor.start_convoy(convoy.id)

        convoy_steps = [
            {
                "id": step.id,
                "rig": step.rig.value,
                "polecat_type": step.polecat_type,
                "status": step.status,
            }
            for step in started.steps
        ]

        return wrap_response(ChatResponse(
            response=f"Convoy execution started! 🚀\n\nI'm now orchestrating {len(started.ready_steps)} Polecats across your Rigs. You can watch the progress on the right panel.\n\nI'll let you know if any tasks need your approval or if I have questions.",
            convoy_steps=convoy_steps,
            action_taken="convoy_started",
        ).model_dump())

    except Exception as e:
        return wrap_response(ChatResponse(
            response=f"I couldn't start the convoy: {str(e)}. Would you like me to try again?",
            is_question=True,
        ).model_dump())


async def _handle_general_question(
    request: ChatRequest,
    mayor: ScopedMayor,
    intent: dict,
) -> dict:
    """Handle general GTM/marketing questions."""
    prompt = f"""You are the GTM Mayor, an expert in go-to-market strategy.

Answer this question helpfully and concisely:
{request.message}

If the question relates to something you can help execute (creating campaigns, generating content, etc.),
offer to help with that specifically.
"""

    try:
        response = await mayor.neurometric.complete(
            task_class="mayor_general_qa",
            prompt=prompt,
        )

        return wrap_response(ChatResponse(
            response=response.content,
        ).model_dump())

    except Exception:
        return wrap_response(ChatResponse(
            response="I'd be happy to help with GTM strategy! Could you rephrase your question?",
        ).model_dump())


async def _handle_conversation(
    request: ChatRequest,
    mayor: ScopedMayor,
    history: list[ChatMessage],
) -> dict:
    """Handle general conversation."""
    context = "\n".join([f"{m.role}: {m.content}" for m in history[-5:]])

    prompt = f"""You are the GTM Mayor, a friendly and knowledgeable campaign orchestrator.

Conversation so far:
{context}

User: {request.message}

Respond naturally. If they seem to want to do something specific (create a campaign, check status, etc.),
guide them towards that. Keep responses concise but helpful.
"""

    try:
        response = await mayor.neurometric.complete(
            task_class="mayor_conversation",
            prompt=prompt,
        )

        return wrap_response(ChatResponse(
            response=response.content,
        ).model_dump())

    except Exception:
        return wrap_response(ChatResponse(
            response="Hello! I'm the GTM Mayor. I help plan and execute go-to-market campaigns. What would you like to accomplish today?",
        ).model_dump())
