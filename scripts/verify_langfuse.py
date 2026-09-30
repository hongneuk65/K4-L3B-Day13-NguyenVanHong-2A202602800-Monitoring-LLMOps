"""Print safe Langfuse CP2 evidence without raw input/output or credentials."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from langfuse import get_client


SAFE_METADATA_KEYS = {
    "correlation_id",
    "prompt_name",
    "prompt_label",
    "prompt_version",
    "prompt_source",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Langfuse CP2 observation trees safely")
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    load_dotenv()

    client = get_client()
    observations = client.api.observations.get_many(
        limit=args.limit,
        fields="core,basic,metadata,model,usage,prompt,metrics,trace_context",
        from_start_time=datetime.now(timezone.utc) - timedelta(hours=args.hours),
    ).data
    by_trace: dict[str, list] = defaultdict(list)
    for observation in observations:
        by_trace[observation.trace_id].append(observation)

    roots = [
        items[0]
        for items in by_trace.values()
        if any(item.name == "lab-agent-run" and item.parent_observation_id is None for item in items)
    ]
    complete = 0
    print(f"observations={len(observations)} traces={len(by_trace)} root_traces={len(roots)}")
    for items in sorted(by_trace.values(), key=lambda group: group[0].start_time, reverse=True):
        root = next((item for item in items if item.name == "lab-agent-run" and item.parent_observation_id is None), None)
        if root is None:
            continue
        children = [item for item in items if item.parent_observation_id == root.id]
        names = {item.name for item in children}
        is_complete = {"retrieval", "generation"}.issubset(names)
        complete += is_complete
        metadata = root.metadata or {}
        safe_metadata = {key: metadata[key] for key in sorted(SAFE_METADATA_KEYS) if key in metadata}
        generation = next((item for item in children if item.name == "generation"), None)
        print(
            {
                "trace_id": root.trace_id,
                "root_id": root.id,
                "children": [(item.id, item.name, str(item.type), item.parent_observation_id) for item in children],
                "complete_tree": is_complete,
                "root_metadata": safe_metadata,
                "generation": {
                    "model": generation.model,
                    "usage": generation.usage_details,
                    "cost": generation.cost_details,
                    "prompt_name": generation.prompt_name,
                    "prompt_version": generation.prompt_version,
                } if generation else None,
            }
        )
    print(f"complete_trees={complete}")
    if complete < 10:
        raise SystemExit("Fewer than 10 complete observation trees were found")


if __name__ == "__main__":
    main()