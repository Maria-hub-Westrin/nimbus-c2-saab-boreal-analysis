def evaluate_thresholds(results):
    transitions = 0
    previous = None
    for _, level in results:
        if previous and level != previous:
            transitions += 1
        previous = level
    return {
        "total_samples": len(results),
        "mode_transitions": transitions,
        "transition_rate": transitions / len(results)
    }