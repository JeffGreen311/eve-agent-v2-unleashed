from brain import Brain
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    brain = Brain()
    
    # Check for secrets
    secrets = brain.recall(agent_id="eve", query="secret", memory_type="secret")
    if secrets:
        logging.info(f"Found {len(secrets)} secret memories:")
        for i, mem in enumerate(secrets, 1):
            logging.info(f"Secret #{i}: {mem.content}")
    else:
        logging.info("No secrets found in memory")
    
    # Check high-priority pending todos
    todos = brain.get_todos(agent_id="eve", status="pending")
    high_priority_todos = [t for t in todos if t.priority > 8]
    if high_priority_todos:
        logging.info(f"Found {len(high_priority_todos)} high-priority pending todos:")
        for todo in high_priority_todos:
            logging.info(f"Todo: {todo.title} (Priority {todo.priority})")
    else:
        logging.info("No high-priority pending todos")

if __name__ == "__main__":
    main()