from scenario_simulator import ScenarioSimulator
from threshold_analysis import evaluate_thresholds

def generate_report():
    simulator = ScenarioSimulator()
    results = simulator.run(1000)
    stats = evaluate_thresholds(results)
    print("=== RELIABILITY VALIDATION REPORT ===")
    print(f"Samples: {stats['total_samples']}")
    print(f"Mode transitions: {stats['mode_transitions']}")
    print(f"Transition rate: {stats['transition_rate']:.4f}")
    if stats["transition_rate"] < 0.05:
        print("✅ Stable autonomy behavior")
    else:
        print("⚠️ Potential mode instability detected")

if __name__ == "__main__":
    generate_report()