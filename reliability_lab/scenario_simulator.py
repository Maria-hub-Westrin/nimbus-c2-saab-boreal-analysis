import numpy as np
from rho_sa_model import ReliabilityModel

class ScenarioSimulator:
    def __init__(self):
        self.model = ReliabilityModel()

    def simulate_sensor_failure(self):
        return {
            "sensor_integrity": np.random.uniform(0.1, 0.5),
            "classification_confidence": np.random.uniform(0.5, 0.9),
            "fusion_quality": np.random.uniform(0.3, 0.7),
            "datalink": np.random.uniform(0.4, 0.8),
        }

    def run(self, n=1000):
        results = []
        for _ in range(n):
            inputs = self.simulate_sensor_failure()
            rho = self.model.compute_rho(inputs)
            level = self.model.autonomy_level(rho)
            results.append((rho, level))
        return results