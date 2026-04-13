from typing import TypedDict, Optional, Literal, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from tools.google_tools import create_gmail_draft, schedule_calendar_meeting, mark_email_as_read
from datetime import datetime

class AgentState(TypedDict):
    email_id: str
    email_subject: str
    email_sender: str
    email_body: str
    
    intent: Optional[str]  # 'draft', 'meeting', 'ignore'
    
    draft_body: Optional[str]
    meeting_details: Optional[Dict[str, Any]]
    
    human_approved: Optional[bool]
    human_edited_draft: Optional[str]

llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0)

def categorize_intent(state: AgentState):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an email assistant. Read the email and decide the intent. "
                   "The current date and time is {current_time}. "
                   "If it asks for a meeting, output 'meeting'. If it requires a simple reply, output 'draft'. "
                   "If it is spam, newsletter, or doesn't need an action, output 'ignore'. "
                   "Respond ONLY with one of: meeting, draft, ignore."),
        ("user", "Subject: {subject}\nSender: {sender}\nBody: {body}")
    ])
    chain = prompt | llm
    response = chain.invoke({
        "current_time": datetime.now().astimezone().isoformat(),
        "subject": state["email_subject"],
        "sender": state["email_sender"],
        "body": state["email_body"]
    })
    
    intent = response.content.strip().lower()
    if intent not in ['meeting', 'draft', 'ignore']:
        intent = 'ignore'
        
    return {"intent": intent}

def prepare_action(state: AgentState):
    intent = state.get("intent")
    
    if intent == "draft":
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant. Draft a polite, concise reply to this email. The current date and time is {current_time}."),
            ("user", "Subject: {subject}\nSender: {sender}\nBody: {body}")
        ])
        chain = prompt | llm
        response = chain.invoke({
            "current_time": datetime.now().astimezone().isoformat(),
            "subject": state["email_subject"],
            "sender": state["email_sender"],
            "body": state["email_body"]
        })
        return {"draft_body": response.content}
        
    elif intent == "meeting":
        # Extract meeting details using LLM function calling or structured output
        schema = {
            "title": "MeetingDetails",
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Title of the meeting"},
                "description": {"type": "string", "description": "Agenda or description"},
                "start_time": {"type": "string", "description": "ISO 8601 start time in UTC, e.g., 2024-05-01T09:00:00Z"},
                "end_time": {"type": "string", "description": "ISO 8601 end time in UTC"},
            },
            "required": ["summary", "description", "start_time", "end_time"]
        }
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant setting up a meeting based on an email. "
                       "The current date and time is {current_time}. "
                       "Extract meeting details and guess the upcoming date logically based on the current time. "
                       "Respond using the provided JSON schema."),
            ("user", "Subject: {subject}\nBody: {body}")
        ])
        structured_llm = llm.with_structured_output(schema)
        chain = prompt | structured_llm
        details = chain.invoke({
            "current_time": datetime.now().astimezone().isoformat(),
            "subject": state["email_subject"],
            "body": state["email_body"]
        })
        return {"meeting_details": details}
        
    return {}

def human_review(state: AgentState) -> Command[Literal["execute_action", "__end__"]]:
    intent = state.get("intent")
    
    # We surface the data to the human via interrupt
    interrupt_payload = {
        "email_id": state["email_id"],
        "subject": state["email_subject"],
        "sender": state["email_sender"],
        "intent": intent,
        "draft_body": state.get("draft_body"),
        "meeting_details": state.get("meeting_details")
    }
    
    # Pause for human decision
    human_decision = interrupt(interrupt_payload)
    
    if human_decision.get("approved"):
        # Update state based on potential human edits
        update_data = {"human_approved": True}
        if human_decision.get("edited_draft"):
            update_data["human_edited_draft"] = human_decision.get("edited_draft")
        
        return Command(update=update_data, goto="execute_action")
    else:
         # Mark as read anyway if skipped or rejected
        mark_email_as_read(state["email_id"])
        return Command(update={"human_approved": False}, goto=END)

def execute_action(state: AgentState):
    intent = state.get("intent")
    
    if intent == "draft":
        body = state.get("human_edited_draft") or state.get("draft_body")
        create_gmail_draft(
            sender=state["email_sender"], 
            subject=state["email_subject"], 
            body=body
        )
    elif intent == "meeting":
        details = state.get("meeting_details", {})
        schedule_calendar_meeting(
            summary=details.get("summary", "Meeting"),
            description=details.get("description", ""),
            start_time=details.get("start_time"),
            end_time=details.get("end_time"),
            attendees=[state["email_sender"]]
        )
        
    # Mark as read since we processed it
    mark_email_as_read(state["email_id"])
    return {}

def route_after_categorize(state: AgentState) -> Literal["prepare_action", "__end__"]:
    if state["intent"] == "ignore":
        mark_email_as_read(state["email_id"])
        return END
    return "prepare_action"

def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("categorize", categorize_intent)
    builder.add_node("prepare_action", prepare_action)
    builder.add_node("human_review", human_review)
    builder.add_node("execute_action", execute_action)
    
    builder.add_edge(START, "categorize")
    builder.add_conditional_edges("categorize", route_after_categorize)
    builder.add_edge("prepare_action", "human_review")
    # human_review uses Command(goto=...) so no explicit edge is needed here.
    builder.add_edge("execute_action", END)
    
    from langgraph.checkpoint.memory import InMemorySaver
    memory = InMemorySaver()
    return builder.compile(checkpointer=memory)

graph = build_graph()
