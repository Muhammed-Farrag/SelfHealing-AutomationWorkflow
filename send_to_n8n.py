import json
import requests
import time
import os

N8N_WEBHOOK_URL = "https://roroo.app.n8n.cloud/webhook-test/self-healing-trigger"

DATA_FILE_PATH = "SelfHealing-AutomationWorkflow-main/data/episodes_unknown.jsonl"

def send_data_to_n8n():
    if not os.path.exists(DATA_FILE_PATH):
        print(f"File not found at: {DATA_FILE_PATH}")
        return

    print(f"Starting to send data from {DATA_FILE_PATH} to n8n...")
    
    with open(DATA_FILE_PATH, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            
            try:
                episode_data = json.loads(line)
                
                payload = {
                    "error_message": episode_data.get("log_excerpt", ""),
                    "dataset": {
                        "episode_id": episode_data.get("episode_id"),
                        "task_id": episode_data.get("task_id"),
                        "dag_id": episode_data.get("dag_id"),
                        "url": "https://httpbin.org/status/200" 
                    }
                }

                print(f"Sending Episode {episode_data.get('episode_id')} ({episode_data.get('failure_class')})...")
                response = requests.post(N8N_WEBHOOK_URL, json=payload)
                
                if response.status_code == 200:
                    print(f"Success! n8n received the data.")
                else:
                    print(f"Failed to send. Status Code: {response.status_code}")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"Error while sending: {e}")

if __name__ == "__main__":
    send_data_to_n8n()
