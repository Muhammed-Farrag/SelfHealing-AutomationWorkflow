import json
from pathlib import Path
from playbook.retriever import PlaybookRetriever

def enrich():
    input_path = "data/parsed_logs.jsonl"
    output_path = "data/episodes_enriched.jsonl"
    
    retriever = PlaybookRetriever()
    
    if not Path(input_path).exists():
        print(f"Input file {input_path} not found.")
        return

    enriched_records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            record = json.loads(line)
            # Retrieve top 2 entries
            entries = retriever.retrieve_for_episode(record, top_k=2)
            record["retrieved_playbook_entries"] = entries
            enriched_records.append(record)
            
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in enriched_records:
            f.write(json.dumps(rec) + "\n")
            
    print(f"✓ Enriched {len(enriched_records)} episodes -> {output_path}")

if __name__ == "__main__":
    enrich()
