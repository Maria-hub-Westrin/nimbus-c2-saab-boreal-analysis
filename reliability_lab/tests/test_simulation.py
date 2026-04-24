from scenario_simulator import ScenarioSimulator

def test_simulation_runs():
    sim = ScenarioSimulator()
    results = sim.run(100)
    assert len(results) == 100