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
        # Create campaign ID
        campaign_id = uuid4()

        # Create convoy plan using the Mayor
        convoy = await mayor.create_convoy(
            campaign_id=campaign_id,
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
            response=f"I've created your campaign: **{campaign_name}**\n\nGoal: {goal}\n\nI've planned {len(convoy.steps)} steps across multiple Rigs to achieve this goal. Review the plan on the right, and say **\"start the campaign\"** when you're ready to begin execution!",
            campaign={
                "id": str(campaign_id),
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

    # For now, simulate starting the convoy by returning updated status
    # In production, this would trigger actual Temporal workflows

    # Create simulated running convoy steps
    # First few steps start running immediately
    convoy_steps = [
        {"id": "step_1", "rig": "intelligence_station", "polecat_type": "competitor_monitor", "status": "running", "description": "Analyzing competitor landscape"},
        {"id": "step_2", "rig": "content_factory", "polecat_type": "content_calendar", "status": "running", "description": "Planning content schedule"},
        {"id": "step_3", "rig": "content_factory", "polecat_type": "blog_draft", "status": "pending", "description": "Creating blog content"},
        {"id": "step_4", "rig": "content_factory", "polecat_type": "seo_optimize", "status": "pending", "description": "Optimizing for search"},
        {"id": "step_5", "rig": "landing_pad", "polecat_type": "landing_page_draft", "status": "pending", "description": "Building landing page"},
        {"id": "step_6", "rig": "sdr_hive", "polecat_type": "lead_enrich", "status": "pending", "description": "Enriching lead data"},
        {"id": "step_7", "rig": "sdr_hive", "polecat_type": "email_personalize", "status": "pending", "description": "Personalizing outreach"},
        {"id": "step_8", "rig": "social_command", "polecat_type": "social_post", "status": "pending", "description": "Scheduling social posts"},
    ]

    return wrap_response(ChatResponse(
        response="**Campaign execution started!** 🚀\n\nI'm now orchestrating Polecats across your Rigs. The first tasks are already running:\n\n• **Competitor Monitor** - Analyzing your competitive landscape\n• **Content Calendar** - Planning your content schedule\n\nWatch the progress on the right panel. I'll notify you when tasks need approval or if I have questions.",
        campaign={
            "id": campaign_id,
            "name": "Active Campaign",
            "goal": "Campaign execution",
            "status": "executing",
        },
        convoy_steps=convoy_steps,
        action_taken="convoy_started",
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
