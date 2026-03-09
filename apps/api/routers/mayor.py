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

from apps.api.config import settings
from apps.api.dependencies import (
    OptionalUser, OptionalBeadStore, OptionalMayor, TokenData,
    CurrentUser, ScopedBeadStore, ScopedMayor,
)
from apps.api.core.convoy_store import (
    Convoy, ConvoyStatus, ConvoyStep, StepStatus, get_convoy_store
)
from apps.api.core.convoy_executor import get_convoy_executor

router = APIRouter()


class ChatMessage(BaseModel):
    """A message in the chat conversation."""
    role: str  # 'user' or 'mayor'
    content: str


class ChatRequest(BaseModel):
    """Request to chat with the Mayor."""
    message: str
    campaign_id: str | None = None
    convoy_id: str | None = None
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
    store: OptionalBeadStore,
    user: OptionalUser,
    mayor: OptionalMayor,
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
    # In development mode, allow unauthenticated access with a dev user
    if user is None:
        if settings.revtown_env != "development":
            raise HTTPException(status_code=401, detail="Authentication required")
        # Create a dev user for development mode
        user = TokenData(
            user_id="dev-user-id",
            email="dev@localhost",
            organization_id="dev-org-id",
            role="owner",
        )

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
    import re

    # Build conversation context
    context = "\n".join([f"{m.role}: {m.content}" for m in history[-5:]])

    prompt = f"""You are the GTM Mayor analyzing a user message to determine their intent.

Conversation context:
{context}

User message: {message}

Determine the intent. Respond with ONLY valid JSON (no markdown, no explanation):
{{
    "type": "create_campaign" | "campaign_status" | "start_convoy" | "clarification_needed" | "general_question" | "conversation",
    "confidence": 0.0-1.0,
    "extracted_data": {{"goal": "...", "target_audience": "...", "budget": null}},
    "question": null
}}

Intent types:
- create_campaign: User wants to create a NEW campaign. Extract the goal from their message. If they mention leads, signups, awareness, product launch, etc., this IS a create_campaign intent.
- campaign_status: User asking about existing campaign status
- start_convoy: User wants to START EXECUTING an existing campaign. Keywords: "start the campaign", "begin execution", "execute", "run it", "let's go", "start execution"
- clarification_needed: Need more info to proceed
- general_question: Question about GTM, marketing, etc.
- conversation: General chat/greeting

IMPORTANT RULES:
1. If user says "start the campaign", "begin execution", "execute", "run it", "go ahead", "let's start" -> return type "start_convoy"
2. If user mentions creating/planning a NEW campaign with goals -> return type "create_campaign"
3. Don't confuse "start the campaign" (execute existing) with "create a campaign" (make new one)

Respond with ONLY the JSON object, nothing else."""

    try:
        response = await mayor.neurometric.complete(
            task_class="mayor_intent_analysis",
            prompt=prompt,
        )

        # Try to extract JSON from the response (handle markdown code blocks)
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        return json.loads(content)
    except json.JSONDecodeError as e:
        # Log the parsing error for debugging
        print(f"JSON parse error: {e}, content: {response.content[:200] if response else 'None'}")
        # Default to conversation
        return {"type": "conversation", "confidence": 0.5}
    except Exception as e:
        print(f"Intent analysis error: {e}")
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

    # Try to get goal from extracted data, or infer from message
    goal = extracted.get("goal")
    if not goal:
        # Try to infer goal from the user's message
        message_lower = request.message.lower()
        if "lead" in message_lower:
            goal = "Generate qualified leads"
        elif "signup" in message_lower or "sign up" in message_lower:
            goal = "Drive signups"
        elif "awareness" in message_lower or "brand" in message_lower:
            goal = "Increase brand awareness"
        elif "launch" in message_lower or "product" in message_lower:
            goal = "Launch new product"
        elif "saas" in message_lower:
            goal = "Generate leads for SaaS product"

    # If still no goal, ask for clarification
    if not goal:
        return wrap_response(ChatResponse(
            response="I'd love to help you create a campaign! What's the main goal you want to achieve? For example:\n\n• Generate qualified leads\n• Launch a new product\n• Increase brand awareness\n• Drive signups for an event",
            is_question=True,
        ).model_dump())

    # Create the campaign
    campaign_name = extracted.get("name", f"Lead Gen Campaign - {datetime.now().strftime('%Y-%m-%d')}")
    budget = extracted.get("budget")

    try:
        # Create campaign and convoy IDs
        campaign_id = uuid4()
        convoy_id = str(uuid4())

        # Create convoy plan using the Mayor
        mayor_convoy = await mayor.create_convoy(
            campaign_id=campaign_id,
            goal=goal,
            budget_cents=int(budget * 100) if budget else None,
        )

        # Convert Mayor convoy steps to ConvoyStep objects
        convoy_steps_data = []
        for step in mayor_convoy.steps:
            convoy_step = ConvoyStep(
                id=step.id,
                rig=step.rig.value,
                polecat_type=step.polecat_type,
                description=f"Execute {step.polecat_type} via {step.rig.value}",
                depends_on=step.depends_on,
                priority=step.priority,
            )
            convoy_steps_data.append(convoy_step)

        # Create and store the convoy
        convoy_store = get_convoy_store()
        convoy = Convoy(
            id=convoy_id,
            campaign_id=str(campaign_id),
            campaign_name=campaign_name,
            goal=goal,
            organization_id=str(user.organization_id) if user.organization_id else "",
            status=ConvoyStatus.DRAFT,
            steps=convoy_steps_data,
        )
        convoy_store.create(convoy)

        # Format steps for response
        convoy_steps = [step.to_dict() for step in convoy.steps]

        return wrap_response(ChatResponse(
            response=f"I've created your campaign: **{campaign_name}**\n\nGoal: {goal}\n\nI've planned {len(convoy.steps)} steps across multiple Rigs to achieve this goal. Review the plan on the right, and say **\"start the campaign\"** when you're ready to begin execution!",
            campaign={
                "id": str(campaign_id),
                "convoy_id": convoy_id,
                "name": campaign_name,
                "goal": goal,
                "status": "draft",
            },
            convoy_steps=convoy_steps,
            action_taken="campaign_created",
        ).model_dump())

    except Exception as e:
        import traceback
        print(f"Campaign creation error: {e}")
        traceback.print_exc()
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

    # Get the convoy from the store
    convoy_store = get_convoy_store()
    convoys = convoy_store.get_by_campaign(campaign_id)

    if not convoys:
        return wrap_response(ChatResponse(
            response="I couldn't find a convoy for this campaign. Would you like me to create an execution plan first?",
            is_question=True,
        ).model_dump())

    convoy = convoys[-1]  # Get the most recent convoy

    if convoy.status == ConvoyStatus.EXECUTING:
        return wrap_response(ChatResponse(
            response="This campaign is already running! Check the progress on the right panel.",
            campaign={
                "id": campaign_id,
                "convoy_id": convoy.id,
                "name": convoy.campaign_name,
                "goal": convoy.goal,
                "status": "executing",
            },
            convoy_steps=[step.to_dict() for step in convoy.steps],
        ).model_dump())

    try:
        # Start the convoy execution
        executor = get_convoy_executor()
        convoy = await executor.start_convoy(convoy.id)

        # Get running steps for the response message
        running_steps = convoy.running_steps
        running_names = [f"**{s.polecat_type.replace('_', ' ').title()}** - {s.description}" for s in running_steps[:3]]
        running_list = "\n• ".join(running_names) if running_names else "Tasks are being prepared..."

        return wrap_response(ChatResponse(
            response=f"**Campaign execution started!** 🚀\n\nI'm now orchestrating Polecats across your Rigs. The first tasks are running:\n\n• {running_list}\n\nWatch the progress on the right panel. I'll notify you when tasks need approval or if I have questions.",
            campaign={
                "id": campaign_id,
                "convoy_id": convoy.id,
                "name": convoy.campaign_name,
                "goal": convoy.goal,
                "status": "executing",
            },
            convoy_steps=[step.to_dict() for step in convoy.steps],
            action_taken="convoy_started",
        ).model_dump())

    except Exception as e:
        import traceback
        print(f"Start convoy error: {e}")
        traceback.print_exc()
        return wrap_response(ChatResponse(
            response=f"I encountered an issue starting the campaign: {str(e)}. Would you like me to try again?",
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


@router.get("/convoy/{convoy_id}/status", response_model=dict)
async def get_convoy_status(convoy_id: str):
    """
    Get the current status of a convoy.

    Used by the frontend to poll for real-time updates.
    """
    convoy_store = get_convoy_store()
    convoy = convoy_store.get(convoy_id)

    if not convoy:
        raise HTTPException(status_code=404, detail="Convoy not found")

    return wrap_response({
        "convoy": convoy.to_dict(),
        "campaign": {
            "id": convoy.campaign_id,
            "name": convoy.campaign_name,
            "goal": convoy.goal,
            "status": convoy.status.value,
        },
    })


@router.get("/campaign/{campaign_id}/convoy", response_model=dict)
async def get_campaign_convoy(campaign_id: str):
    """
    Get the active convoy for a campaign.
    """
    convoy_store = get_convoy_store()
    convoys = convoy_store.get_by_campaign(campaign_id)

    if not convoys:
        raise HTTPException(status_code=404, detail="No convoy found for campaign")

    convoy = convoys[-1]  # Most recent

    return wrap_response({
        "convoy": convoy.to_dict(),
        "campaign": {
            "id": convoy.campaign_id,
            "name": convoy.campaign_name,
            "goal": convoy.goal,
            "status": convoy.status.value,
        },
    })
