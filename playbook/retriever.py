"""
FAISS Retrieval Engine for YAML Repair Playbook
"""
import json
import os
from pathlib import Path

import faiss
import yaml
from rich.console import Console
from rich.pretty import pprint
from sentence_transformers import SentenceTransformer

console = Console()

class PlaybookRetriever:
    """
    Retrieves repair actions from a static YAML playbook using a FAISS vector index.
    """

    def __init__(
        self,
        playbook_path: str = "playbook/repair_playbook.yaml",
        index_path: str = "models/playbook.faiss",
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        """
        Load playbook YAML and either load an existing FAISS index from
        index_path or build and save a new one.
        """
        self.playbook_path = playbook_path
        self.index_path = index_path
        self.map_path = str(Path(index_path).parent / "playbook_entry_map.json")
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        
        # Load playbook
        if os.path.exists(self.playbook_path):
            with open(self.playbook_path, "r", encoding="utf-8") as f:
                self.playbook_entries = yaml.safe_load(f) or []
        else:
            self.playbook_entries = []
            
        # Entry ID mapping for lookup
        self.entry_by_id = {item["entry_id"]: item for item in self.playbook_entries}
        
        self.index = None
        self.entry_id_map = []
        
        if os.path.exists(self.index_path) and os.path.exists(self.map_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.map_path, "r", encoding="utf-8") as f:
                self.entry_id_map = json.load(f)

    def build_index(self) -> None:
        """
        Embed all playbook entries using sentence-transformers and build a
        FAISS FlatIP (inner product / cosine after normalisation) index.
        Save the index to index_path and save entry_id mapping to
        models/playbook_entry_map.json.
        """
        
        texts_to_embed = []
        self.entry_id_map = []
        
        for entry in self.playbook_entries:
            # Construct a rich text representation of the rule for embedding
            text_repr = (
                f"Title: {entry['title']}. "
                f"Class: {entry['failure_class']}. "
                f"Description: {entry['description']}. "
                f"Tags: {' '.join(entry.get('tags', []))}"
            )
            texts_to_embed.append(text_repr)
            self.entry_id_map.append(entry["entry_id"])
            
        if not texts_to_embed:
            return

        # Embed using sentence-transformers
        embeddings = self.model.encode(texts_to_embed, convert_to_numpy=True)
        # Normalize to use Inner Product for Cosine Similarity
        faiss.normalize_L2(embeddings)
        
        # Build index
        d = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(d)
        self.index.add(embeddings)
        
        # Save things
        os.makedirs(Path(self.index_path).parent, exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.map_path, "w", encoding="utf-8") as f:
            json.dump(self.entry_id_map, f, indent=2)
            
        # Calculate statistics
        class_counts = {}
        for entry in self.playbook_entries:
            f_class = entry.get("failure_class", "unknown")
            class_counts[f_class] = class_counts.get(f_class, 0) + 1
            
        console.print("[bold green]Index Build Statistics:[/bold green]")
        console.print(f"  Total Entries Indexed: [bold]{len(self.playbook_entries)}[/bold]")
        console.print("  [dim]Breakdown by Failure Class:[/dim]")
        for f_class, count in class_counts.items():
            console.print(f"    - {f_class}: {count}")

    def retrieve(
        self,
        query: str,
        failure_class: str | None = None,
        min_confidence: float = 0.0,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Embed query and retrieve top_k most similar playbook entries.
        If failure_class is provided, filter results to that class only
        before ranking. Also filters by min_confidence against the entry's confidence_floor.
        """
        if self.index is None:
            raise ValueError("Index is not loaded. Call build_index() first or initialize with an existing index.")
            
        # We search for and rank practically all elements so we can dynamically filter by failure_class
        search_k = self.index.ntotal
        if search_k == 0:
            return []
            
        query_emb = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_emb)
        
        scores, indices = self.index.search(query_emb, search_k)
        
        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx == -1:
                continue
                
            entry_id = self.entry_id_map[idx]
            entry = self.entry_by_id[entry_id]
            
            if failure_class and entry.get("failure_class") != failure_class:
                continue
                
            if float(entry.get("confidence_floor", 0.0)) < min_confidence:
                continue
                
            # Copy entry and add score
            result_item = entry.copy()
            result_item["score"] = float(score)
            results.append(result_item)
            
            if len(results) >= top_k:
                break
                
        return results

    def retrieve_for_episode(self, episode: dict, top_k: int = 3, min_confidence: float = 0.0) -> list[dict]:
        """
        Convenience wrapper: builds a query from an episode record's
        log_excerpt + template + failure_class, then calls retrieve().
        """
        log_excerpt = episode.get("log_excerpt", "")
        template = episode.get("template", "")
        failure_class = episode.get("failure_class", "")
        
        query_text = f"Failure: {failure_class}. Template: {template}. Logs: {log_excerpt}"
        
        return self.retrieve(
            query=query_text, 
            failure_class=failure_class if failure_class else None, 
            min_confidence=min_confidence,
            top_k=top_k
        )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Repair Playbook FAISS Retriever")
    parser.add_argument("--build", action="store_true", help="Build and save the FAISS index")
    parser.add_argument("--query", type=str, help="Query string to search for")
    parser.add_argument("--class", dest="failure_class", type=str, help="Filter by failure class", default=None)
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Minimum confidence floor")
    parser.add_argument("--top-k", type=int, default=3, help="Number of results to retrieve")
    args = parser.parse_args()

    retriever = PlaybookRetriever()

    if args.build:
        retriever.build_index()
        console.print("[bold green]FAISS index successfully built and embedded.[/bold green]")
    elif args.query:
        if not os.path.exists(retriever.index_path):
            console.print("[bold red]Index doesn't exist, building first...[/bold red]")
            retriever.build_index()
            
        console.print(f"[bold blue]Searching for:[/bold blue] '{args.query}' (Class: {args.failure_class})")
        try:
            results = retriever.retrieve(
                query=args.query, 
                failure_class=args.failure_class, 
                min_confidence=args.min_confidence,
                top_k=args.top_k
            )
            console.print("[bold green]Top Matches:[/bold green]")
            pprint(results)
        except Exception as e:
            console.print(f"[bold red]Error during retrieval:[/bold red] {e}")
    else:
        parser.print_help()
