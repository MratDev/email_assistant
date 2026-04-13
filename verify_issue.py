import json
from pprint import pprint
from langgraph.types import Command
import uuid
import sys

from graph import graph, AgentState

def simulate():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "email_id": "test_123",
        "email_subject": "Test Email",
        "email_sender": "test@example.com",
        "email_body": "Let's schedule a meeting for tomorrow at 10am."
    }
    
    # 1. Initial invoke
    print("--- Initial Invoke ---")
    result = graph.invoke(initial_state, config)
    # Print the state after pause
    state_before = graph.get_state(config)
    pprint(state_before.values)
    
    # 2. Resume
    print("\n--- Resuming ---")
    resume_data = {"approved": True}
    result_after = graph.invoke(Command(resume=resume_data), config)
    
    print("\n--- Final State ---")
    state_after = graph.get_state(config)
    pprint(state_after.values)

if __name__ == '__main__':
    simulate()
